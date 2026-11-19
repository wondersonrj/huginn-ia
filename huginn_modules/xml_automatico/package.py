"""Contrato de pacote XML HUGINN para entrega local ao WinThor.
Nunca altera XML assinado, nem registra NF-e diretamente no Oracle.
"""
from __future__ import annotations
import hashlib
import io
import json
import zipfile
from xml.etree import ElementTree as ET

def build_package(xml_original: bytes, analysis: dict) -> bytes:
    if not xml_original or b"<!DOCTYPE" in xml_original.upper():
        raise ValueError("XML inválido ou com DTD não permitida")
    try:
        root = ET.fromstring(xml_original)
    except ET.ParseError as exc:
        raise ValueError("XML inválido") from exc
    if not root.tag.endswith(("nfeProc", "NFe")):
        raise ValueError("Documento não é NF-e")
    analysis_bytes = json.dumps(analysis, ensure_ascii=False, sort_keys=True).encode("utf-8")
    manifest = {
        "schema": "huginn-xml-1",
        "files": {
            "nota.xml": hashlib.sha256(xml_original).hexdigest(),
            "analise.json": hashlib.sha256(analysis_bytes).hexdigest(),
        },
        "policy": "advisory_only",
    }
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("nota.xml", xml_original)
        z.writestr("analise.json", analysis_bytes)
        z.writestr("manifesto.json", json.dumps(manifest, ensure_ascii=False, sort_keys=True))
    return buffer.getvalue()

def verify_package(data: bytes) -> dict:
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        expected = {"nota.xml", "analise.json", "manifesto.json"}
        if set(z.namelist()) != expected:
            raise ValueError("Conteúdo ZIP inesperado")
        manifest = json.loads(z.read("manifesto.json"))
        if manifest.get("schema") != "huginn-xml-1":
            raise ValueError("Versão incompatível")
        for name in ("nota.xml", "analise.json"):
            if hashlib.sha256(z.read(name)).hexdigest() != manifest["files"][name]:
                raise ValueError(f"Falha de integridade: {name}")
        return manifest
