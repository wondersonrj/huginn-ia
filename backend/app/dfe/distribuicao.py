"""Mensagens do web service NFeDistribuicaoDFe (montagem e leitura).

NT 2014.002: distDFeInt versao 1.01, SOAP 1.2, consultas distNSU / consNSU / consChNFe.
Os documentos voltam em docZip (Base64 de GZip); os bytes descompactados sao
preservados exatamente como a SEFAZ entregou.
"""
from __future__ import annotations

import base64
import io
import gzip
import re
from dataclasses import dataclass, field
from xml.sax.saxutils import escape

from defusedxml import ElementTree as ET

NS_NFE = "http://www.portalfiscal.inf.br/nfe"
NS_WSDL = "http://www.portalfiscal.inf.br/nfe/wsdl/NFeDistribuicaoDFe"
SOAP_ACTION = NS_WSDL + "/nfeDistDFeInteresse"
URL_PRODUCAO = "https://www1.nfe.fazenda.gov.br/NFeDistribuicaoDFe/NFeDistribuicaoDFe.asmx"
URL_HOMOLOGACAO = "https://hom1.nfe.fazenda.gov.br/NFeDistribuicaoDFe/NFeDistribuicaoDFe.asmx"
NSU_ZERO = "0" * 15
MAX_DOC_BYTES = 5 * 1024 * 1024

# Codigos IBGE de UF aceitos em cUFAutor.
UF_IBGE = {
    "RO": 11, "AC": 12, "AM": 13, "RR": 14, "PA": 15, "AP": 16, "TO": 17, "MA": 21, "PI": 22,
    "CE": 23, "RN": 24, "PB": 25, "PE": 26, "AL": 27, "SE": 28, "BA": 29, "MG": 31, "ES": 32,
    "RJ": 33, "SP": 35, "PR": 41, "SC": 42, "RS": 43, "MS": 50, "MT": 51, "GO": 52, "DF": 53,
}

# CNPJ: 14 posicoes; a partir de julho/2026 as 12 primeiras podem ser alfanumericas (NT 2014.002 v1.40).
_CNPJ = re.compile(r"^[0-9A-Z]{12}[0-9]{2}$")
_NSU = re.compile(r"^[0-9]{1,15}$")
_CHAVE = re.compile(r"^[0-9]{44}$")


class ErroDistribuicao(Exception):
    """Erro de montagem ou leitura (mensagem segura para log/tela)."""


def normalizar_cnpj(cnpj: str) -> str:
    valor = re.sub(r"[.\-/\s]", "", cnpj or "").upper()
    if not _CNPJ.match(valor):
        raise ErroDistribuicao("CNPJ inválido para a distribuição DF-e.")
    return valor


def normalizar_nsu(nsu: str | int) -> str:
    texto = str(nsu).strip()
    if not _NSU.match(texto):
        raise ErroDistribuicao("NSU inválido.")
    return texto.zfill(15)


def _cabecalho(tp_amb: int, uf: str, cnpj: str) -> str:
    if tp_amb not in (1, 2):
        raise ErroDistribuicao("Ambiente deve ser 1 (produção) ou 2 (homologação).")
    if uf not in UF_IBGE:
        raise ErroDistribuicao("UF do interessado inválida.")
    return (f'<distDFeInt xmlns="{NS_NFE}" versao="1.01"><tpAmb>{tp_amb}</tpAmb>'
            f"<cUFAutor>{UF_IBGE[uf]}</cUFAutor><CNPJ>{escape(normalizar_cnpj(cnpj))}</CNPJ>")


def montar_dist_nsu(tp_amb: int, uf: str, cnpj: str, ult_nsu: str | int) -> str:
    return _cabecalho(tp_amb, uf, cnpj) + f"<distNSU><ultNSU>{normalizar_nsu(ult_nsu)}</ultNSU></distNSU></distDFeInt>"


def montar_cons_nsu(tp_amb: int, uf: str, cnpj: str, nsu: str | int) -> str:
    return _cabecalho(tp_amb, uf, cnpj) + f"<consNSU><NSU>{normalizar_nsu(nsu)}</NSU></consNSU></distDFeInt>"


def montar_cons_chave(tp_amb: int, uf: str, cnpj: str, chave: str) -> str:
    if not _CHAVE.match(chave or ""):
        raise ErroDistribuicao("Chave de acesso inválida.")
    return _cabecalho(tp_amb, uf, cnpj) + f"<consChNFe><chNFe>{chave}</chNFe></consChNFe></distDFeInt>"


def envelope_soap(dados: str) -> bytes:
    return ('<?xml version="1.0" encoding="utf-8"?>'
            '<soap12:Envelope xmlns:soap12="http://www.w3.org/2003/05/soap-envelope">'
            f'<soap12:Body><nfeDistDFeInteresse xmlns="{NS_WSDL}"><nfeDadosMsg>{dados}</nfeDadosMsg>'
            "</nfeDistDFeInteresse></soap12:Body></soap12:Envelope>").encode("utf-8")


@dataclass
class Documento:
    nsu: str
    schema: str
    conteudo: bytes            # XML descompactado, byte a byte
    tipo: str = ""             # procNFe | resNFe | procEventoNFe | resEvento | outro
    chave: str = ""
    emitente_cnpj: str = ""
    emitente_nome: str = ""
    emissao: str = ""
    valor: str = ""
    situacao: str = ""         # cSitNFe do resumo (1 autorizada, 2 denegada, 3 cancelada)
    evento: str = ""           # tpEvento


@dataclass
class Retorno:
    c_stat: str
    x_motivo: str
    ult_nsu: str = NSU_ZERO
    max_nsu: str = NSU_ZERO
    dh_resp: str = ""
    documentos: list[Documento] = field(default_factory=list)


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _filho(elem, nome: str):
    for c in elem:
        if _local(c.tag) == nome:
            return c
    return None


def _texto(elem, nome: str) -> str:
    if elem is None:
        return ""
    for c in elem.iter():
        if _local(c.tag) == nome:
            return (c.text or "").strip()
    return ""


def _descompactar(texto_b64: str) -> bytes:
    try:
        comprimido = base64.b64decode(texto_b64, validate=False)
        with gzip.GzipFile(fileobj=io.BytesIO(comprimido)) as arq:
            dados = arq.read(MAX_DOC_BYTES + 1)
    except (OSError, ValueError) as exc:
        raise ErroDistribuicao("docZip inválido.") from exc
    if len(dados) > MAX_DOC_BYTES:
        raise ErroDistribuicao("Documento acima do limite permitido.")
    return dados


def classificar(doc: Documento) -> Documento:
    try:
        raiz = ET.fromstring(doc.conteudo, forbid_dtd=True)
    except Exception as exc:  # noqa: BLE001 - XML do documento invalido
        raise ErroDistribuicao(f"XML do NSU {doc.nsu} inválido.") from exc
    nome = _local(raiz.tag)
    doc.tipo = nome if nome in ("procNFe", "nfeProc", "resNFe", "procEventoNFe", "resEvento") else "outro"
    if nome in ("nfeProc", "procNFe"):
        doc.tipo = "procNFe"
        inf = next((e for e in raiz.iter() if _local(e.tag) == "infNFe"), None)
        if inf is not None:
            doc.chave = (inf.get("Id") or "")[3:]
            emit = _filho(inf, "emit")
            doc.emitente_cnpj = _texto(emit, "CNPJ") or _texto(emit, "CPF")
            doc.emitente_nome = _texto(emit, "xNome")
            doc.emissao = _texto(_filho(inf, "ide"), "dhEmi")
            doc.valor = _texto(_filho(inf, "total"), "vNF")
    elif nome == "resNFe":
        doc.chave = _texto(raiz, "chNFe")
        doc.emitente_cnpj = _texto(raiz, "CNPJ") or _texto(raiz, "CPF")
        doc.emitente_nome = _texto(raiz, "xNome")
        doc.emissao = _texto(raiz, "dhEmi")
        doc.valor = _texto(raiz, "vNF")
        doc.situacao = _texto(raiz, "cSitNFe")
    elif nome in ("procEventoNFe", "resEvento"):
        doc.chave = _texto(raiz, "chNFe")
        doc.evento = _texto(raiz, "tpEvento")
    return doc


def ler_retorno(resposta: bytes) -> Retorno:
    """Le a resposta SOAP (ou o retDistDFeInt puro) e descompacta os documentos."""
    try:
        raiz = ET.fromstring(resposta, forbid_dtd=True)
    except Exception as exc:  # noqa: BLE001
        raise ErroDistribuicao("Resposta da SEFAZ ilegível.") from exc
    ret = next((e for e in raiz.iter() if _local(e.tag) == "retDistDFeInt"), None)
    if ret is None:
        falha = next((e for e in raiz.iter() if _local(e.tag) in ("Text", "faultstring")), None)
        motivo = (falha.text or "").strip()[:200] if falha is not None else "sem retDistDFeInt"
        raise ErroDistribuicao("Resposta inesperada da SEFAZ: " + motivo)
    r = Retorno(c_stat=_texto(ret, "cStat"), x_motivo=_texto(ret, "xMotivo"),
                ult_nsu=_texto(ret, "ultNSU") or NSU_ZERO, max_nsu=_texto(ret, "maxNSU") or NSU_ZERO,
                dh_resp=_texto(ret, "dhResp"))
    lote = _filho(ret, "loteDistDFeInt")
    if lote is not None:
        for dz in lote:
            if _local(dz.tag) != "docZip":
                continue
            doc = Documento(nsu=normalizar_nsu(dz.get("NSU", "0")), schema=dz.get("schema", ""),
                            conteudo=_descompactar(dz.text or ""))
            r.documentos.append(classificar(doc))
    return r
