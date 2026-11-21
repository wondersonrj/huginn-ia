"""CNPJs a consultar: filiais do WinThor (PCFILIAL) com a mesma raiz do e-CNPJ.

A SEFAZ autentica pela raiz (8 primeiros caracteres) e aceita consulta para qualquer
CNPJ com essa raiz. Somente leitura; recebe um cursor DB-API ja conectado.
"""
from __future__ import annotations

import re

from .distribuicao import UF_IBGE, ErroDistribuicao, normalizar_cnpj

_OWNER = re.compile(r"^[A-Z][A-Z0-9_$#]{0,29}$")


def filiais_da_raiz(cursor, owner: str, cnpj_certificado: str) -> list[dict]:
    owner = (owner or "").upper()
    if not _OWNER.match(owner):
        raise ErroDistribuicao("Schema (owner) inválido.")
    raiz = normalizar_cnpj(cnpj_certificado)[:8]
    cursor.execute(
        f'SELECT CODIGO, RAZAOSOCIAL, CGC, UF FROM "{owner}"."PCFILIAL" '
        "WHERE CODIGO <> '99' AND SUBSTR(REGEXP_REPLACE(UPPER(CGC), '[^0-9A-Z]', ''), 1, 8) = :raiz "
        "ORDER BY CODIGO", dict(raiz=raiz))
    filiais, vistos = [], set()
    for codigo, nome, cgc, uf in cursor.fetchall():
        try:
            cnpj = normalizar_cnpj(cgc or "")
        except ErroDistribuicao:
            continue
        if cnpj in vistos:
            continue
        vistos.add(cnpj)
        uf = (uf or "").strip().upper()
        filiais.append({"codigo": str(codigo).strip(), "nome": nome, "cnpj": cnpj,
                        "uf": uf if uf in UF_IBGE else ""})
    return filiais
