"""Machine DPAPI + explicit ACL: readable by administrators and LocalService only."""
import json
import os
from pathlib import Path
import secrets
import subprocess


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
    path.mkdir(parents=True, exist_ok=True)
    # SIDs avoid localized account names. No inherited Users/Authenticated Users access.
    subprocess.run(["icacls.exe", str(path), "/inheritance:r", "/grant:r",
                    "*S-1-5-18:(OI)(CI)F", "*S-1-5-32-544:(OI)(CI)F",
                    "*S-1-5-19:(OI)(CI)M"], check=True, capture_output=True)


def save(cfg):
    import win32crypt
    validate(cfg)
    root = data_dir()
    protect_directory(root)
    blob = win32crypt.CryptProtectData(json.dumps(cfg).encode(), "HUGINN Smart Connector",
                                      None, None, None, 0x4)  # LOCAL_MACHINE, ACL is essential
    temporary = root / "config.tmp"
    temporary.write_bytes(blob)
    temporary.replace(root / "config.dpapi")


def load():
    import win32crypt
    blob = (data_dir() / "config.dpapi").read_bytes()
    cfg = json.loads(win32crypt.CryptUnprotectData(blob, None, None, None, 0)[1])
    validate(cfg)
    return cfg


def initialize():
    if not (data_dir() / "config.dpapi").exists():
        save(defaults())
