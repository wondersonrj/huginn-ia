import http.client
import json
import threading
from unittest.mock import MagicMock
import sys

import pytest

from smart_connector import config
from smart_connector.api import make_server, oracle_operation


def test_tls_certificate_and_authenticated_health(tmp_path):
    import datetime
    import ipaddress
    import socket
    import ssl
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(x509.NameOID.COMMON_NAME, "localhost")])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(now - datetime.timedelta(minutes=1))
            .not_valid_after(now + datetime.timedelta(days=1))
            .add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]), False)
            .sign(key, hashes.SHA256()))
    cert_path, key_path = tmp_path / "cert.pem", tmp_path / "key.pem"
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                           serialization.NoEncryption()))
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    cfg = dict(config.defaults(), port=port, tls_cert=str(cert_path), tls_key=str(key_path))
    server = make_server(cfg)
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    try:
        context = ssl.create_default_context(cafile=str(cert_path))
        conn = http.client.HTTPSConnection("127.0.0.1", port, context=context, timeout=5)
        conn.request("GET", "/health", headers={"Authorization": "Bearer " + cfg["token"]})
        response = conn.getresponse()
        assert response.status == 200 and json.loads(response.read())["status"] == "ok"
        conn.close()
        untrusted = http.client.HTTPSConnection("127.0.0.1", port, timeout=5)
        try:
            with pytest.raises(ssl.SSLCertVerificationError):
                untrusted.request("GET", "/health")
        finally:
            untrusted.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_remote_requires_tls_and_authorization():
    cfg = config.defaults()
    cfg["host"] = "0.0.0.0"
    with pytest.raises(ValueError):
        config.validate(cfg)
    cfg.update(tls_cert="cert", tls_key="key")
    with pytest.raises(ValueError):
        config.validate(cfg)
    cfg["remote_authorized"] = True
    config.validate(cfg)
    # Invalid TLS cannot silently fall back to HTTP.
    cfg["port"] = 18367
    with pytest.raises(OSError):
        make_server(cfg)


def test_api_auth_allowlist_and_redaction(caplog):
    cfg = config.defaults()
    # Bind ephemeral test port after validation by reserving it first.
    import socket
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        cfg["port"] = sock.getsockname()[1]
    calls = []

    def operation(cfg, path):
        calls.append(path)
        raise RuntimeError("secret-password host=secret-host")

    server = make_server(cfg, operation)
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    try:
        def request(path, token=None, method="GET"):
            conn = http.client.HTTPConnection("127.0.0.1", cfg["port"], timeout=5)
            conn.request(method, path, headers={"Authorization": "Bearer " + token} if token else {})
            response = conn.getresponse()
            result = response.status, response.read().decode()
            conn.close()
            return result
        assert request("/health")[0] == 401
        assert request("/health", "wrong")[0] == 401
        assert request("/health", cfg["token"])[0] == 200
        for path in ("/sql", "/oracle/test?sql=DELETE", "/oracle/anything"):
            assert request(path, cfg["token"])[0] == 404
        assert request("/oracle/test", cfg["token"], "POST")[0] == 501
        status, body = request("/oracle/test", cfg["token"])
        assert status == 503
        assert "secret-password" not in body + caplog.text
        assert "secret-host" not in body + caplog.text
        assert calls == ["/oracle/test"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_oracle_thin_readonly_fixed_sql(monkeypatch):
    driver = MagicMock()
    monkeypatch.setitem(sys.modules, "oracledb", driver)
    cfg = dict(config.defaults(), oracle_host="db", oracle_service="service", oracle_user="reader", oracle_password="fake")
    driver.is_thin_mode.return_value = True
    conn = driver.connect.return_value.__enter__.return_value
    cursor = conn.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = (1,)
    assert oracle_operation(cfg, "/oracle/test")["ok"]
    assert [call.args[0] for call in cursor.execute.call_args_list] == ["SET TRANSACTION READ ONLY", "SELECT 1 FROM DUAL"]
    assert conn.call_timeout == 5000
    with pytest.raises(KeyError):
        oracle_operation(cfg, "DROP TABLE")
    driver.is_thin_mode.return_value = False
    with pytest.raises(RuntimeError):
        oracle_operation(cfg, "/oracle/test")


@pytest.mark.skipif(sys.platform != "win32", reason="Windows DPAPI and ACL test")
def test_dpapi_roundtrip_and_preserve(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "data_dir", lambda: tmp_path / "protected")
    cfg = dict(config.defaults(), oracle_password="FAKE-TEST-ONLY-password")
    config.save(cfg)
    blob = (config.data_dir() / "config.dpapi").read_bytes()
    assert cfg["oracle_password"].encode() not in blob
    assert cfg["token"].encode() not in blob
    assert config.load() == cfg
    config.initialize()
    assert (config.data_dir() / "config.dpapi").read_bytes() == blob
    import win32security
    descriptor = win32security.GetNamedSecurityInfo(str(config.data_dir()), win32security.SE_FILE_OBJECT,
                                                    win32security.DACL_SECURITY_INFORMATION)
    acl = descriptor.GetSecurityDescriptorDacl()
    trustees = {win32security.ConvertSidToStringSid(acl.GetAce(i)[2]) for i in range(acl.GetAceCount())}
    assert trustees == {"S-1-5-18", "S-1-5-32-544", "S-1-5-19"}
