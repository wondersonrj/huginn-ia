"""Real WinHTTP + local TLS fixture; never probes a real customer/Cloud/Oracle."""
import datetime
import ipaddress
import os
from pathlib import Path
import socket
import subprocess
import sys
import threading

import pytest

ROOT = Path(__file__).resolve().parents[2]
pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows WinHTTP/PowerShell")


def run_script(path):
    # PowerShell 7's inherited module paths can select incompatible Core modules in Windows PS 5.1.
    env = dict(os.environ)
    env["PSModulePath"] = os.path.join(os.environ["SystemRoot"], "System32", "WindowsPowerShell", "v1.0", "Modules")
    result = subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-File", str(path)],
                            env=env, capture_output=True, text=True, timeout=90)
    assert result.returncode == 0, result.stdout + result.stderr


def test_diagnostic_policy_unit_script():
    run_script(ROOT / "smart_connector/diagnostics/tests.ps1")


def test_winhttp_tls_auth_and_reconnection(tmp_path):
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from smart_connector.api import make_server
    from smart_connector.config import defaults
    now = datetime.datetime.now(datetime.timezone.utc)
    root_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(x509.NameOID.COMMON_NAME, "HUGINN CI ephemeral root")])
    root = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(root_key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(now - datetime.timedelta(minutes=5))
            .not_valid_after(now + datetime.timedelta(days=1))
            .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
            .sign(root_key, hashes.SHA256()))
    leaf_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    leaf = (x509.CertificateBuilder().subject_name(x509.Name([x509.NameAttribute(x509.NameOID.COMMON_NAME, "localhost")]))
            .issuer_name(name).public_key(leaf_key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now - datetime.timedelta(minutes=5)).not_valid_after(now + datetime.timedelta(days=1))
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .add_extension(x509.SubjectAlternativeName([x509.IPAddress(ipaddress.ip_address("127.0.0.1"))]), False)
            .add_extension(x509.ExtendedKeyUsage([x509.oid.ExtendedKeyUsageOID.SERVER_AUTH]), False)
            .sign(root_key, hashes.SHA256()))
    cert_path, key_path, root_path = tmp_path / "leaf.pem", tmp_path / "leaf.key", tmp_path / "root.cer"
    cert_path.write_bytes(leaf.public_bytes(serialization.Encoding.PEM))
    key_path.write_bytes(leaf_key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                               serialization.NoEncryption()))
    root_path.write_bytes(root.public_bytes(serialization.Encoding.DER))
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    cfg = dict(defaults(), port=port, tls_cert=str(cert_path), tls_key=str(key_path))
    server = make_server(cfg, operation=lambda *_: {"ok": True})
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    # All interpolated values are trusted fixture data, never customer input or credentials.
    script = tmp_path / "integration.ps1"
    script.write_text(r"""
$ErrorActionPreference = 'Stop'
Import-Module '%s' -Force
$module = Get-Module Huginn.CloudDiagnostics
$token = ConvertTo-SecureString '%s' -AsPlainText -Force
$bad = ConvertTo-SecureString ('wrong-' + ('x' * 40)) -AsPlainText -Force
$cert = $null
try {
    $untrusted = Test-HuginnCloud -BaseUrl 'https://127.0.0.1:%d' -Token $token -TimeoutSeconds 3
    if ($untrusted.authenticated_https -or $untrusted.stages[-1].result -notmatch '^tls_') {
        throw ('Untrusted certificate accepted or misclassified: ' + ($untrusted | ConvertTo-Json -Depth 8))
    }
    $cert = Import-Certificate -FilePath '%s' -CertStoreLocation Cert:\CurrentUser\Root
    $rejected = Test-HuginnCloud -BaseUrl 'https://127.0.0.1:%d' -Token $bad -TimeoutSeconds 3
    if ($rejected.stages[-1].result -ne 'authentication_rejected') { throw 'Wrong token accepted' }
    $ok = Test-HuginnCloud -BaseUrl 'https://127.0.0.1:%d' -Token $token -TimeoutSeconds 3 -OracleReadTest
    if (-not $ok.authenticated_https -or $ok.oracle_read -ne 'ok') {
        throw ('Reconnect/TLS/health failed: ' + ($ok | ConvertTo-Json -Depth 8))
    }
    $module.Invoke({
        param($origin)
        $response = Invoke-HuginnRequest ($origin + '/api/v1/capabilities') ('%s') 3000
        if ($response.status -ne 200 -or $response.body.api_version -ne '1.0') { throw 'Capabilities contract' }
    }, @('https://127.0.0.1:%d'))
} finally {
    if ($cert) { Remove-Item ('Cert:\CurrentUser\Root\' + $cert.Thumbprint) -Force }
    $token.Dispose(); $bad.Dispose()
}
Write-Host 'Real WinHTTP untrusted/trusted TLS, authentication, contract and reconnect: PASS'
""" % (str(ROOT / "smart_connector/diagnostics/Huginn.CloudDiagnostics.psm1").replace("'", "''"), cfg["token"],
       port, str(root_path).replace("'", "''"), port, port, cfg["token"], port), encoding="utf-8")
    try:
        run_script(script)
    finally:
        server.shutdown()
        server.server_close()
        thread.join()
