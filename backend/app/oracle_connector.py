"""Conector Oracle direto: somente leitura, sem guardar credenciais em disco."""
from dataclasses import dataclass, field
import os
import re
from typing import Any

@dataclass(frozen=True)
class OracleConfig:
    host: str
    port: int
    service: str
    user: str
    password: str = field(repr=False)

    @classmethod
    def from_env(cls):
        return cls(
            os.environ.get("HUGINN_ORACLE_HOST", ""),
            int(os.environ.get("HUGINN_ORACLE_PORT", "1521")),
            os.environ.get("HUGINN_ORACLE_SERVICE", ""),
            os.environ.get("HUGINN_ORACLE_USER", ""),
            os.environ.get("HUGINN_ORACLE_PASSWORD", ""),
        )

    def validate(self):
        if not all([self.host, self.service, self.user, self.password]):
            raise ValueError("Configure host, serviço, usuário e senha Oracle no ambiente")
        if not 1 <= self.port <= 65535:
            raise ValueError("Porta Oracle inválida")
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", self.host):
            raise ValueError("Hostname Oracle inválido")

def connect_readonly(cfg: OracleConfig):
    """A conta Oracle DEVE ter somente SELECT; sessão read-only é proteção adicional."""
    cfg.validate()
    import oracledb
    dsn = oracledb.makedsn(cfg.host, cfg.port, service_name=cfg.service)
    connection = oracledb.connect(
        user=cfg.user, password=cfg.password, dsn=dsn,
        tcp_connect_timeout=5, retry_count=0,
    )
    try:
        connection.call_timeout = 5000
        with connection.cursor() as cur:
            cur.execute("SET TRANSACTION READ ONLY")
        return connection
    except Exception:
        connection.close()
        raise

def check_connection(cfg: OracleConfig | None = None) -> dict[str, Any]:
    cfg = cfg or OracleConfig.from_env()
    con = connect_readonly(cfg)
    try:
        with con.cursor() as cur:
            cur.execute("SELECT 1 FROM DUAL")
            row = cur.fetchone()
            ok = row is not None and row[0] == 1
        return {"conectado": ok, "modo": "somente leitura", "driver": "python-oracledb Thin"}
    finally:
        con.close()
