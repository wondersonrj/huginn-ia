"""Machine DPAPI + explicit ACL: readable by administrators and LocalService only."""
import json
import os
from pathlib import Path
import secrets


def data_dir():
    return Path(os.environ.get("ProgramData", r"C:\ProgramData")) / "HUGINN" / "SmartConnector"


def validate(cfg):
    if not 1 <= int(cfg["port"]) <= 65535:
        raise ValueError("Porta da API inválida")
    if cfg["host"] != "127.0.0.1":
        if not (cfg.get("remote_authorized") and cfg.get("tls_cert") and cfg.get("tls_key")):
            raise ValueError("Acesso remoto exige autorização explícita e certificado/chave TLS")
    if bool(cfg.get("tls_cert")) != bool(cfg.get("tls_key")):
        raise ValueError("Informe certificado e chave TLS juntos")
    if len(cfg.get("token", "")) < 32:
        raise ValueError("Token inválido")
    if not 1 <= int(cfg["oracle_port"]) <= 65535:
        raise ValueError("Porta Oracle inválida")


def defaults():
    return dict(host="127.0.0.1", port=8765, token=secrets.token_urlsafe(32),
                oracle_host="", oracle_port=1521, oracle_service="", oracle_user="",
                oracle_password="", tls_cert="", tls_key="", remote_authorized=False)


def protect_directory(path):
    import win32security
    path.mkdir(parents=True, exist_ok=True)
    # Replace the whole DACL, including explicit entries inherited from old layouts.
    descriptor = win32security.ConvertStringSecurityDescriptorToSecurityDescriptor(
        "D:P(A;OICI;FA;;;SY)(A;OICI;FA;;;BA)(A;OICI;0x1301bf;;;LS)",
        win32security.SDDL_REVISION_1)
    win32security.SetNamedSecurityInfo(str(path), win32security.SE_FILE_OBJECT,
        win32security.DACL_SECURITY_INFORMATION | win32security.PROTECTED_DACL_SECURITY_INFORMATION,
        None, None, descriptor.GetSecurityDescriptorDacl(), None)


def save(cfg):
    import win32crypt
    validate(cfg)
    root = data_dir()
    protect_directory(root)
    blob = win32crypt.CryptProtectData(json.dumps(cfg).encode(), "HUGINN Smart Connector",
                                      None, None, None, 0x5)  # LOCAL_MACHINE + UI_FORBIDDEN; ACL is essential
    temporary = root / "config.tmp"
    temporary.write_bytes(blob)
    temporary.replace(root / "config.dpapi")


def load():
    import win32crypt
    blob = (data_dir() / "config.dpapi").read_bytes()
    cfg = json.loads(win32crypt.CryptUnprotectData(blob, None, None, None, 1)[1])
    validate(cfg)
    return cfg


def initialize():
    if not (data_dir() / "config.dpapi").exists():
        save(defaults())
