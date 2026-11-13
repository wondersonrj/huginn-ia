"""Conector Oracle direto: somente leitura, sem guardar credenciais em disco."""
from dataclasses import dataclass, field
import os
import re
from typing import Any


def connection_diagnostic(exc: Exception) -> str:
    """Return only known, actionable messages, never raw driver error text."""
    error = exc.args[0] if exc.args else None
    code = getattr(error, "full_code", "")
    messages = {
        "ORA-01017": "Usuário ou senha inválidos. Confirme as credenciais com o DBA.",
        "ORA-28000": "Conta Oracle bloqueada. Solicite desbloqueio ao DBA.",
        "ORA-28001": "Senha Oracle expirada. Solicite a atualização ao DBA.",
        "ORA-12514": "Service Name não reconhecido pelo listener. Confirme o serviço com o DBA.",
        "DPY-6001": "Service Name não reconhecido pelo listener. Confirme o serviço com o DBA.",
        "ORA-12541": "Listener indisponível. Verifique host, porta e firewall.",
        "DPY-6005": "Não foi possível alcançar o listener. Verifique host, porta, rede e firewall.",
        "DPY-3010": "Versão do servidor incompatível com o driver Thin. Este pacote é destinado ao Oracle 19c.",
        "DPY-3015": "Verificador de senha incompatível com Thin. Consulte o DBA sobre autenticação compatível.",
        "DPY-4011": "Conexão encerrada. Verifique com o DBA a política de criptografia/autenticação do Oracle.",
        "DPY-4024": "Tempo de resposta excedido. Verifique a rede e a disponibilidade do Oracle.",
    }
    return messages.get(code, "Não foi possível conectar ao Oracle. Verifique rede, serviço e credenciais de leitura.")

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
