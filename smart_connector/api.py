"""Authenticated fixed operations only. Never accepts SQL or logs request data."""
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import logging
import ssl

from smart_connector import VERSION
from smart_connector.config import validate
from smart_connector.capabilities import capabilities

LOG = logging.getLogger("smart_connector")
OPERATIONS = {"/oracle/test": "SELECT 1 FROM DUAL",
              "/oracle/server-time": "SELECT SYSTIMESTAMP FROM DUAL"}


def oracle_operation(cfg, operation):
    import oracledb
    sql = OPERATIONS[operation]  # No SQL input, bind interpolation, or caller-supplied identifiers
    if not oracledb.is_thin_mode():
        raise RuntimeError("Thin required")
    if not all(cfg.get(k) for k in ("oracle_host", "oracle_service", "oracle_user", "oracle_password")):
        raise ValueError("Oracle unconfigured")
    with oracledb.connect(user=cfg["oracle_user"], password=cfg["oracle_password"],
                          host=cfg["oracle_host"], port=int(cfg["oracle_port"]),
                          service_name=cfg["oracle_service"], tcp_connect_timeout=5,
                          retry_count=0) as conn:
        conn.call_timeout = 5000
        with conn.cursor() as cursor:
            cursor.execute("SET TRANSACTION READ ONLY")
            cursor.execute(sql)
            value = cursor.fetchone()[0]
    return {"ok": True, "driver": "python-oracledb Thin", "value": str(value)}


def make_server(cfg, operation=oracle_operation):
    validate(cfg)

    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(10)

        def log_message(self, *args):
            pass  # Base class logs arbitrary request paths, which may contain secrets

        def reply(self, status, body):
            payload = json.dumps(body).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(payload)

        def do_GET(self):
            expected = "Bearer " + cfg["token"]
            actual = self.headers.get("Authorization", "")
            if not hmac.compare_digest(actual.encode(), expected.encode()):
                return self.reply(401, {"error": "unauthorized"})
            if self.path == "/health":
                return self.reply(200, {"status": "ok", "version": VERSION,
                                        "oracle_configured": all(bool(cfg.get(key)) for key in
                                            ("oracle_host", "oracle_service", "oracle_user", "oracle_password"))})
            if self.path == "/api/v1/capabilities":
                return self.reply(200, capabilities())
            if self.path not in OPERATIONS:
                return self.reply(404, {"error": "unknown_operation"})
            try:
                return self.reply(200, operation(cfg, self.path))
            except Exception:
                # Driver exceptions can contain DSNs, credentials or query data.
                LOG.warning("Oracle operation failed; verify configuration, network and Thin compatibility")
                return self.reply(503, {"error": "oracle_unavailable",
                                        "hint": "Verifique configuração, rede, grants SELECT e compatibilidade Thin"})

    server = ThreadingHTTPServer((cfg["host"], int(cfg["port"])), Handler)
    server.daemon_threads = True
    if cfg.get("tls_cert"):
        try:
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.minimum_version = ssl.TLSVersion.TLSv1_2
            context.load_cert_chain(cfg["tls_cert"], cfg["tls_key"])
            server.socket = context.wrap_socket(server.socket, server_side=True)
        except Exception:
            server.server_close()
            raise
    return server
