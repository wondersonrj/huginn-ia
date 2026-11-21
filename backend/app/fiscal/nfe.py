"""Leitura dos dados fiscais de uma NF-e (procNFe ou NFe) para o Consultor."""
from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation

from defusedxml import ElementTree as ET

from .modelos import ItemNota, NotaResumo

NS = {"n": "http://www.portalfiscal.inf.br/nfe"}
MAX_BYTES = 5 * 1024 * 1024


class ErroNFe(Exception):
    pass


def _t(el, caminho: str, padrao: str = "") -> str:
    if el is None:
        return padrao
    achado = el.find(caminho, NS)
    return achado.text.strip() if achado is not None and achado.text else padrao


def _dec(el, caminho: str) -> Decimal:
    v = _t(el, caminho, "0")
    try:
        return Decimal(v)
    except InvalidOperation as exc:
        raise ErroNFe(f"valor numerico invalido em {caminho}: {v!r}") from exc


def ler_nfe(dados: bytes) -> NotaResumo:
    if len(dados) > MAX_BYTES:
        raise ErroNFe("XML acima de 5 MB")
    try:
        raiz = ET.fromstring(dados, forbid_dtd=True)
    except Exception as exc:  # defusedxml/ParseError
        raise ErroNFe(f"XML invalido: {exc.__class__.__name__}") from exc
    inf = raiz.find(".//n:infNFe", NS)
    if inf is None:
        raise ErroNFe("nao e uma NF-e (infNFe ausente)")
    if _t(inf, "n:ide/n:mod") != "55":
        raise ErroNFe("somente NF-e modelo 55")
    chave = inf.get("Id", "")[3:]
    dh = _t(inf, "n:ide/n:dhEmi")[:10]
    try:
        emissao = date.fromisoformat(dh)
    except ValueError as exc:
        raise ErroNFe("data de emissao invalida") from exc

    emit, dest = inf.find("n:emit", NS), inf.find("n:dest", NS)
    itens = []
    for det in inf.findall("n:det", NS):
        prod, icms = det.find("n:prod", NS), det.find("n:imposto/n:ICMS", NS)
        grupo = next(iter(icms), None) if icms is not None else None
        itens.append(ItemNota(
            n_item=int(det.get("nItem", "0")),
            cprod=_t(prod, "n:cProd"), descricao=_t(prod, "n:xProd"),
            ncm=_t(prod, "n:NCM"), cfop=_t(prod, "n:CFOP"),
            orig=_t(grupo, "n:orig", "0"),
            v_prod=_dec(prod, "n:vProd"), v_desc=_dec(prod, "n:vDesc"),
            cst=_t(grupo, "n:CST"), csosn=_t(grupo, "n:CSOSN"),
            p_icms=_dec(grupo, "n:pICMS"), v_icms=_dec(grupo, "n:vICMS"),
            p_cred_sn=_dec(grupo, "n:pCredSN"), v_cred_sn=_dec(grupo, "n:vCredICMSSN"),
        ))
    if not itens:
        raise ErroNFe("NF-e sem itens")
    return NotaResumo(
        chave=chave, data_emissao=emissao,
        cnpj_emit=_t(emit, "n:CNPJ"), uf_emit=_t(emit, "n:enderEmit/n:UF"),
        crt_emit=_t(emit, "n:CRT"),
        cnpj_dest=_t(dest, "n:CNPJ"), uf_dest=_t(dest, "n:enderDest/n:UF"),
        itens=tuple(itens),
    )
