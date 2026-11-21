"""Manifestacao do destinatario - evento 210210 "Ciencia da Operacao" (Ambiente Nacional, cOrgao 91).

Sem a ciencia, a distribuicao DF-e so entrega o RESUMO (resNFe). A ciencia nao confirma
a operacao; depois, o destinatario deve concluir com confirmacao, desconhecimento ou
operacao nao realizada, nos prazos legais.

Assinatura XMLDSig enveloped: C14N 1.0 inclusiva, RSA-SHA1, Reference = #Id do infEvento.
OPCIONAL na aplicacao (desligado por padrao).
"""
from __future__ import annotations

import base64
import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from defusedxml import ElementTree as SafeET
from lxml import etree

from .distribuicao import NS_NFE, ErroDistribuicao, normalizar_cnpj

NS_DSIG = "http://www.w3.org/2000/09/xmldsig#"
NS_WSDL_EVENTO = "http://www.portalfiscal.inf.br/nfe/wsdl/NFeRecepcaoEvento4"
ACTION_EVENTO = NS_WSDL_EVENTO + "/nfeRecepcaoEvento"
URL_EVENTO_PRODUCAO = "https://www.nfe.fazenda.gov.br/NFeRecepcaoEvento4/NFeRecepcaoEvento4.asmx"
URL_EVENTO_HOMOLOGACAO = "https://hom1.nfe.fazenda.gov.br/NFeRecepcaoEvento4/NFeRecepcaoEvento4.asmx"
TP_CIENCIA = "210210"
DESC_CIENCIA = "Ciencia da Operacao"
_CHAVE = re.compile(r"^[0-9]{44}$")
# Situacoes do retorno: 135/136 = evento registrado; 573 = duplicidade (ja havia ciencia).
REGISTRADO = {"135", "136"}
JA_EXISTIA = {"573"}


def _dh(agora: datetime) -> str:
    # Horario de Brasilia com offset explicito (AAAA-MM-DDThh:mm:ss-03:00).
    br = agora.astimezone(timezone(timedelta(hours=-3))) if agora.tzinfo else agora
    return br.strftime("%Y-%m-%dT%H:%M:%S") + "-03:00"


def montar_evento_ciencia(tp_amb: int, cnpj: str, chave: str, agora: datetime, n_seq: int = 1) -> str:
    if not _CHAVE.match(chave or ""):
        raise ErroDistribuicao("Chave de acesso inválida.")
    if tp_amb not in (1, 2):
        raise ErroDistribuicao("Ambiente inválido.")
    ident = f"ID{TP_CIENCIA}{chave}{n_seq:02d}"
    return (f'<evento xmlns="{NS_NFE}" versao="1.00"><infEvento Id="{ident}"><cOrgao>91</cOrgao>'
            f"<tpAmb>{tp_amb}</tpAmb><CNPJ>{normalizar_cnpj(cnpj)}</CNPJ><chNFe>{chave}</chNFe>"
            f"<dhEvento>{_dh(agora)}</dhEvento><tpEvento>{TP_CIENCIA}</tpEvento><nSeqEvento>{n_seq}</nSeqEvento>"
            f'<verEvento>1.00</verEvento><detEvento versao="1.00"><descEvento>{DESC_CIENCIA}</descEvento>'
            "</detEvento></infEvento></evento>")


def assinar_evento(evento_xml: str, chave_privada, certificado) -> str:
    """Assina o infEvento (XMLDSig enveloped) e devolve o <evento> assinado."""
    parser = etree.XMLParser(resolve_entities=False, no_network=True, remove_blank_text=True)
    evento = etree.fromstring(evento_xml.encode("utf-8"), parser)
    inf = evento.find(f"{{{NS_NFE}}}infEvento")
    ident = inf.get("Id")
    digest = base64.b64encode(hashlib.sha1(etree.tostring(inf, method="c14n")).digest()).decode()
    sig = etree.SubElement(evento, f"{{{NS_DSIG}}}Signature", nsmap={None: NS_DSIG})
    si = etree.SubElement(sig, f"{{{NS_DSIG}}}SignedInfo")
    etree.SubElement(si, f"{{{NS_DSIG}}}CanonicalizationMethod",
                     Algorithm="http://www.w3.org/TR/2001/REC-xml-c14n-20010315")
    etree.SubElement(si, f"{{{NS_DSIG}}}SignatureMethod", Algorithm=NS_DSIG + "rsa-sha1")
    ref = etree.SubElement(si, f"{{{NS_DSIG}}}Reference", URI="#" + ident)
    tr = etree.SubElement(ref, f"{{{NS_DSIG}}}Transforms")
    etree.SubElement(tr, f"{{{NS_DSIG}}}Transform", Algorithm=NS_DSIG + "enveloped-signature")
    etree.SubElement(tr, f"{{{NS_DSIG}}}Transform", Algorithm="http://www.w3.org/TR/2001/REC-xml-c14n-20010315")
    etree.SubElement(ref, f"{{{NS_DSIG}}}DigestMethod", Algorithm=NS_DSIG + "sha1")
    etree.SubElement(ref, f"{{{NS_DSIG}}}DigestValue").text = digest
    assinatura = chave_privada.sign(etree.tostring(si, method="c14n"), padding.PKCS1v15(), hashes.SHA1())
    etree.SubElement(sig, f"{{{NS_DSIG}}}SignatureValue").text = base64.b64encode(assinatura).decode()
    ki = etree.SubElement(sig, f"{{{NS_DSIG}}}KeyInfo")
    x509 = etree.SubElement(ki, f"{{{NS_DSIG}}}X509Data")
    der = certificado.public_bytes(serialization.Encoding.DER)
    etree.SubElement(x509, f"{{{NS_DSIG}}}X509Certificate").text = base64.b64encode(der).decode()
    return etree.tostring(evento, encoding="unicode")


def envelope_evento(eventos_assinados: list[str], id_lote: int) -> bytes:
    if not 1 <= len(eventos_assinados) <= 20:
        raise ErroDistribuicao("O lote de eventos deve ter de 1 a 20 eventos.")
    # O <evento> assinado ja declara o xmlns da NF-e; o envEvento declara o mesmo namespace.
    corpo = "".join(eventos_assinados)
    return ('<?xml version="1.0" encoding="utf-8"?>'
            '<soap12:Envelope xmlns:soap12="http://www.w3.org/2003/05/soap-envelope"><soap12:Body>'
            f'<nfeDadosMsg xmlns="{NS_WSDL_EVENTO}"><envEvento xmlns="{NS_NFE}" versao="1.00">'
            f"<idLote>{int(id_lote)}</idLote>{corpo}</envEvento></nfeDadosMsg>"
            "</soap12:Body></soap12:Envelope>").encode("utf-8")


@dataclass
class RetornoEvento:
    chave: str
    c_stat: str
    x_motivo: str
    protocolo: str = ""

    @property
    def ok(self) -> bool:
        return self.c_stat in REGISTRADO or self.c_stat in JA_EXISTIA


def ler_retorno_evento(resposta: bytes) -> tuple[str, str, list[RetornoEvento]]:
    try:
        raiz = SafeET.fromstring(resposta, forbid_dtd=True)
    except Exception as exc:  # noqa: BLE001
        raise ErroDistribuicao("Resposta do evento ilegível.") from exc
    local = lambda e: e.tag.rsplit("}", 1)[-1]  # noqa: E731
    ret = next((e for e in raiz.iter() if local(e) == "retEnvEvento"), None)
    if ret is None:
        raise ErroDistribuicao("Resposta inesperada no envio do evento.")
    texto = lambda el, n: next(((c.text or "").strip() for c in el if local(c) == n), "")  # noqa: E731
    itens = []
    for r in (e for e in ret if local(e) == "retEvento"):
        inf = next((c for c in r if local(c) == "infEvento"), None)
        if inf is not None:
            itens.append(RetornoEvento(chave=texto(inf, "chNFe"), c_stat=texto(inf, "cStat"),
                                       x_motivo=texto(inf, "xMotivo"), protocolo=texto(inf, "nProt")))
    return texto(ret, "cStat"), texto(ret, "xMotivo"), itens
