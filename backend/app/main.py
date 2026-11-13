from decimal import Decimal, InvalidOperation
from io import BytesIO
from typing import Any
from defusedxml import ElementTree as ET
from fastapi import FastAPI, File, HTTPException, UploadFile, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError
from starlette.concurrency import run_in_threadpool
from starlette.staticfiles import StaticFiles
from pathlib import Path
from app.oracle_connector import OracleConfig, check_connection, connection_diagnostic

app = FastAPI(title="HUGINN IA API", version="0.1.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"], allow_credentials=False, allow_methods=["GET", "POST"], allow_headers=["*"])
MAX_XML = 5 * 1024 * 1024


class OracleConnectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    host: str = Field(min_length=1, max_length=253)
    port: int = Field(default=1521, ge=1, le=65535)
    service: str = Field(min_length=1, max_length=255)
    user: str = Field(min_length=1, max_length=128)
    password: SecretStr = Field(min_length=1, max_length=1024)


@app.post("/api/oracle/testar")
async def testar_oracle(request: Request):
    # Local development only: no arbitrary SQL or persistent credentials.
    if not request.client or request.client.host not in {"127.0.0.1", "::1"}:
        raise HTTPException(403, "Teste Oracle disponível apenas no ambiente local")
    origin = request.headers.get("origin")
    if origin and origin not in {
        "http://localhost:5173", "http://127.0.0.1:5173",
        "http://localhost:8000", "http://127.0.0.1:8000",
    }:
        raise HTTPException(403, "Origem não permitida")
    try:
        payload = OracleConnectionRequest.model_validate(await request.json())
        cfg = OracleConfig(payload.host, payload.port, payload.service,
                           payload.user, payload.password.get_secret_value())
        cfg.validate()
    except (ValidationError, ValueError):
        # Do not echo submitted fields or driver errors containing credentials.
        raise HTTPException(422, "Informe host, porta, serviço, usuário e senha válidos") from None
    try:
        result = await run_in_threadpool(check_connection, cfg)
    except Exception as exc:
        raise HTTPException(502, connection_diagnostic(exc)) from None
    if not result["conectado"]:
        raise HTTPException(502, "Oracle não confirmou o teste de leitura")
    return result

def child(node, name):
    return next((c for c in node if c.tag.rsplit("}", 1)[-1] == name), None) if node is not None else None

def descendants(node, name):
    return [x for x in node.iter() if x.tag.rsplit("}", 1)[-1] == name]

def value(node, name):
    c = child(node, name)
    return (c.text or "").strip() if c is not None else ""

def decimal_value(s):
    try:
        number = Decimal(s or "0")
    except InvalidOperation as exc:
        raise ValueError("Valor numérico inválido no XML") from exc
    if not number.is_finite():
        raise ValueError("Valor numérico inválido no XML")
    return str(number)

def parse_nfe(data: bytes) -> dict[str, Any]:
    try:
        root = ET.parse(BytesIO(data)).getroot()
    except Exception as exc:
        raise ValueError("XML inválido ou não permitido") from exc
    nfes = descendants(root, "NFe")
    if root.tag.rsplit("}", 1)[-1] == "NFe":
        nfes = [root]
    if len(nfes) != 1:
        raise ValueError("O arquivo deve conter exatamente uma NFe")
    nfe = nfes[0]
    infs = descendants(nfe, "infNFe")
    if len(infs) != 1:
        raise ValueError("Estrutura infNFe não encontrada")
    inf = infs[0]
    ide, emit = child(inf, "ide"), child(inf, "emit")
    if ide is None or emit is None:
        raise ValueError("Identificação ou emitente ausente")
    itens = []
    for det in descendants(inf, "det"):
        prod = child(det, "prod")
        if prod is None:
            continue
        itens.append({
            "numero": det.attrib.get("nItem", ""),
            "codigo": value(prod, "cProd"),
            "descricao": value(prod, "xProd"),
            "ncm": value(prod, "NCM"),
            "cfop": value(prod, "CFOP"),
            "quantidade": decimal_value(value(prod, "qCom")),
            "valor_unitario": decimal_value(value(prod, "vUnCom")),
            "valor_total": decimal_value(value(prod, "vProd")),
            "status": "Pendente de comparação com WinThor",
        })
    return {
        "modo": "Análise de XML sem integração Oracle/SEFAZ",
        "chave": inf.attrib.get("Id", "").removeprefix("NFe"),
        "numero": value(ide, "nNF"),
        "serie": value(ide, "serie"),
        "data_emissao": value(ide, "dhEmi") or value(ide, "dEmi"),
        "emitente": {"cnpj": value(emit, "CNPJ"), "nome": value(emit, "xNome")},
        "itens": itens,
        "total_itens": len(itens),
    }

@app.get("/api/health")
def health():
    return {"status": "ok", "modo": "demo-sem-oracle"}

@app.post("/api/nfe/importar")
async def importar_nfe(file: UploadFile = File(...)):
    if not (file.filename or "").lower().endswith(".xml"):
        raise HTTPException(400, "Envie um arquivo .xml")
    content = await file.read(MAX_XML + 1)
    if len(content) > MAX_XML:
        raise HTTPException(413, "XML acima de 5 MB")
    try:
        return parse_nfe(content)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc


# A portable build serves React and the API from one loopback origin.
web_dir = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if web_dir.is_dir():
    app.mount("/", StaticFiles(directory=web_dir, html=True), name="frontend")
