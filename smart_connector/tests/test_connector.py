import http.client
import json
import threading
from unittest.mock import MagicMock
import sys

import pytest

from smart_connector import config
from smart_connector.api import make_server, oracle_operation


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
