"""Envio SOAP 1.2 com o certificado A1 (ICP-Brasil) da empresa.

O .pfx e aberto em memoria; para o TLS, o par certificado/chave vai para uma pasta
temporaria privada, com a chave CIFRADA por uma senha aleatoria, e e apagado assim
que o contexto TLS carrega. Senha e chave nunca vao para log.
"""
from __future__ import annotations

import http.client
import os
import re
import secrets
import shutil
import ssl
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol
from urllib.parse import urlparse

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import pkcs12
from cryptography.x509.oid import NameOID

from .distribuicao import SOAP_ACTION, ErroDistribuicao

TIMEOUT_S = 60
MAX_RESPOSTA = 30 * 1024 * 1024


class Transporte(Protocol):
    def enviar(self, url: str, envelope: bytes, action: str = SOAP_ACTION) -> bytes: ...


@dataclass
class InfoCertificado:
    titular: str
    cnpj: str
    validade: datetime


def ler_certificado(pfx: bytes, senha: str):
    try:
        chave, cert, cadeia = pkcs12.load_key_and_certificates(pfx, senha.encode("utf-8") if senha else None)
    except ValueError as exc:
        raise ErroDistribuicao("Certificado A1 inválido ou senha incorreta.") from exc
    if chave is None or cert is None:
        raise ErroDistribuicao("O arquivo .pfx não contém chave privada e certificado.")
    return chave, cert, cadeia or []


def info_certificado(cert) -> InfoCertificado:
    cn = cert.subject.get_attributes_for_oid(NameOID.COMMON_NAME)
    titular = cn[0].value if cn else ""
    # e-CNPJ ICP-Brasil: CN = "RAZAO SOCIAL:CNPJ"
    achado = re.search(r":([0-9A-Z]{12}[0-9]{2})$", titular)
    validade = getattr(cert, "not_valid_after_utc", None) or cert.not_valid_after.replace(tzinfo=timezone.utc)
    return InfoCertificado(titular=titular, cnpj=achado.group(1) if achado else "", validade=validade)


def contexto_tls(pfx: bytes, senha: str) -> ssl.SSLContext:
    chave, cert, cadeia = ler_certificado(pfx, senha)
    info = info_certificado(cert)
    if info.validade < datetime.now(timezone.utc):
        raise ErroDistribuicao(f"Certificado vencido em {info.validade:%d/%m/%Y}.")
    ctx = ssl.create_default_context()
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    pasta = tempfile.mkdtemp(prefix="huginn-dfe-")
    try:
        os.chmod(pasta, 0o700)
        senha_tmp = secrets.token_urlsafe(32)
        arq_cert, arq_chave = Path(pasta, "c.pem"), Path(pasta, "k.pem")
        arq_cert.write_bytes(cert.public_bytes(serialization.Encoding.PEM) +
                             b"".join(c.public_bytes(serialization.Encoding.PEM) for c in cadeia))
        arq_chave.write_bytes(chave.private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
            serialization.BestAvailableEncryption(senha_tmp.encode())))
        ctx.load_cert_chain(str(arq_cert), str(arq_chave), password=senha_tmp)
    finally:
        shutil.rmtree(pasta, ignore_errors=True)
    return ctx


class TransporteSefaz:
    """Transporte real. A cadeia de confianca do servidor da SEFAZ (ICP-Brasil) precisa
    estar no repositorio de certificados do Windows/Python, ou em cafile."""

    def __init__(self, contexto: ssl.SSLContext, cafile: str | None = None):
        self.contexto = contexto
        if cafile:
            self.contexto.load_verify_locations(cafile=cafile)

    def enviar(self, url: str, envelope: bytes, action: str = SOAP_ACTION) -> bytes:
        alvo = urlparse(url)
        if alvo.scheme != "https" or not alvo.hostname or not alvo.hostname.endswith(".fazenda.gov.br"):
            raise ErroDistribuicao("Endereço da SEFAZ não permitido.")
        con = http.client.HTTPSConnection(alvo.hostname, alvo.port or 443, context=self.contexto, timeout=TIMEOUT_S)
        try:
            con.request("POST", alvo.path, body=envelope, headers={
                "Content-Type": f'application/soap+xml; charset=utf-8; action="{action}"'})
            resp = con.getresponse()
            dados = resp.read(MAX_RESPOSTA + 1)
        except (OSError, http.client.HTTPException) as exc:
            raise ErroDistribuicao(f"Falha de comunicação com a SEFAZ: {type(exc).__name__}") from exc
        finally:
            con.close()
        if len(dados) > MAX_RESPOSTA:
            raise ErroDistribuicao("Resposta da SEFAZ acima do limite.")
        if resp.status >= 500 and b"retDistDFeInt" not in dados:
            raise ErroDistribuicao(f"SEFAZ respondeu HTTP {resp.status}.")
        return dados
