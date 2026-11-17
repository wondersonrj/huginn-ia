from http.client import HTTPConnection
import socket
import threading

import pytest

from smart_connector.api import make_server
from smart_connector.capabilities import REPORT_MODULES, capabilities
from smart_connector.config import defaults
from smart_connector.contracts.reports_v1 import ContractError, Scope, validate_request


def test_versioned_capabilities_truthful_and_authenticated():
    cfg = dict(defaults(), oracle_host="host-only-is-not-configured")
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        cfg["port"] = sock.getsockname()[1]
    server = make_server(cfg)
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    try:
        for path in ("/api/v1/capabilities", "/health"):
            conn = HTTPConnection("127.0.0.1", cfg["port"], timeout=5)
            conn.request("GET", path)
            response = conn.getresponse()
            assert response.status == 401
            response.read()
            conn.close()
        import json
        conn = HTTPConnection("127.0.0.1", cfg["port"], timeout=5)
        conn.request("GET", "/api/v1/capabilities", headers={"Authorization": "Bearer " + cfg["token"]})
        response = conn.getresponse()
        assert response.status == 200
        body = json.loads(response.read())
        assert body == capabilities() and body["api_version"] == "1.0"
        assert set(body["reports"]) == set(REPORT_MODULES)
        assert not any(item["available"] for item in body["reports"].values())
        conn.close()
        conn = HTTPConnection("127.0.0.1", cfg["port"], timeout=5)
        conn.request("GET", "/health", headers={"Authorization": "Bearer " + cfg["token"]})
        assert not json.loads(conn.getresponse().read())["oracle_configured"]
        conn.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def pairs(**changes):
    values = dict(filial="1", inicio="2026-01-01", fim="2026-01-31", pagina="1", limite="100")
    values.update(changes)
    return list(values.items())


SCOPE = Scope(frozenset({"1"}), frozenset(REPORT_MODULES))


@pytest.mark.parametrize("module", REPORT_MODULES)
def test_proposed_contract_accepts_bounded_requests(module):
    request = validate_request(module, pairs(), SCOPE)
    assert request.branch == "1" and request.page_size == 100


@pytest.mark.parametrize("changes", [dict(sql="SELECT 1"), dict(filial="1 OR 1=1"),
    dict(inicio="2026-02-30"), dict(fim="2026-02-01"), dict(fim="2025-01-01"),
    dict(limite="201"), dict(limite="0"), dict(pagina="99999"), dict(pagina="102", limite="100"),
    dict(inicio="20260101"), dict(pagina="-1"), dict(filial="0")])
def test_proposed_contract_rejects_unbounded_or_arbitrary_input(changes):
    with pytest.raises(ContractError):
        validate_request("vendas", pairs(**changes), SCOPE)


def test_proposed_contract_rejects_duplicate_and_cross_branch():
    with pytest.raises(ContractError):
        validate_request("vendas", pairs() + [("filial", "2")], SCOPE)
    for scope in (Scope(frozenset({"2"}), frozenset(REPORT_MODULES)), Scope(frozenset({"1"}), frozenset())):
        with pytest.raises(ContractError) as error:
            validate_request("vendas", pairs(), scope)
        assert error.value.status == 403
