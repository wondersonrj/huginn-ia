import pytest
from fastapi.testclient import TestClient

from app.main import MAX_XML, app
from test_nfe import XML


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def upload(client, content=XML, filename="nota.xml"):
    return client.post(
        "/api/nfe/importar",
        files={"file": (filename, content, "application/xml")},
    )


def test_health(client):
    assert client.get("/api/health").json() == {
        "status": "ok", "modo": "demo-sem-oracle"
    }


@pytest.mark.parametrize("wrapped", [True, False])
def test_import_nfe(client, wrapped):
    content = XML
    if not wrapped:
        content = XML.replace(b'<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe">', b"").replace(b"</nfeProc>", b"")
    response = upload(client, content)
    assert response.status_code == 200
    data = response.json()
    assert data["numero"] == "12"
    assert data["total_itens"] == 1
    assert data["itens"][0]["valor_total"] == "21.00"
    assert data["itens"][0]["status"] == "Pendente de comparação com WinThor"


@pytest.mark.parametrize("field", [b"qCom", b"vUnCom", b"vProd"])
@pytest.mark.parametrize("invalid", [b"banana", b"NaN", b"Infinity", b"-Infinity"])
def test_reject_invalid_numbers(client, field, invalid):
    from xml.etree import ElementTree

    root = ElementTree.fromstring(XML)
    root.find(f".//{{*}}{field.decode()}").text = invalid.decode()
    response = upload(client, ElementTree.tostring(root))
    assert response.status_code == 422
    assert response.json()["detail"] == "Valor numérico inválido no XML"


@pytest.mark.parametrize("content", [
    b"<broken>",
    b"<root/>",
    b"<NFe><infNFe/></NFe>",
    b'<!DOCTYPE NFe [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><NFe>&xxe;</NFe>',
])
def test_reject_invalid_or_unsafe_xml(client, content):
    assert upload(client, content).status_code == 422


def test_reject_wrong_extension(client):
    assert upload(client, filename="nota.txt").status_code == 400


def test_reject_large_file(client):
    assert upload(client, b" " * (MAX_XML + 1)).status_code == 413


def test_require_file(client):
    assert client.post("/api/nfe/importar").status_code == 422
