"""Rotas HUGINN de demonstração local. Não montar em produção sem auth/tenant.
Entrada JSON sintética: nenhum upload persistido, nenhum acesso Oracle.
"""
from __future__ import annotations
import base64
import binascii
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from huginn_modules.revisor.audit import run_audit
from huginn_modules.xml_automatico.package import build_package, verify_package

router = APIRouter(prefix="/huginn-lab", tags=["huginn-lab"])

class AuditRequest(BaseModel):
    payload: dict = Field(default_factory=dict)

class XmlRequest(BaseModel):
    xml_base64: str = Field(max_length=5_000_000)
    analysis: dict = Field(default_factory=dict)

@router.post("/revisor/auditar")
def audit(req: AuditRequest):
    payload = req.payload
    allowed = {"clientes","fornecedores","produtos","precos","estoque","embalagens","config"}
    if set(payload) - allowed:
        raise HTTPException(422,"Seções não reconhecidas")
    if any(not isinstance(payload.get(k,[]),list) for k in allowed-{"config"}):
        raise HTTPException(422,"Seções de registros devem ser listas")
    if sum(len(payload.get(k,[])) for k in allowed-{"config"}) > 10000:
        raise HTTPException(413,"Limite de 10000 registros por requisição")
    try:
        findings = run_audit(payload)
    except (TypeError, ValueError, KeyError) as exc:
        raise HTTPException(422,"Dados de auditoria inválidos") from exc
    return {"count":len(findings),"findings":findings,"mode":"read_only","production_ready":False}

@router.post("/xml/empacotar")
def package_xml(req: XmlRequest):
    try:
        xml = base64.b64decode(req.xml_base64, validate=True)
        if len(xml)>3_000_000:
            raise HTTPException(413,"XML excede limite")
        result=build_package(xml,req.analysis)
        return {"package_base64":base64.b64encode(result).decode("ascii"),
                "manifest":verify_package(result),"production_ready":False}
    except (ValueError,binascii.Error) as exc:
        raise HTTPException(422,"XML inválido") from exc
