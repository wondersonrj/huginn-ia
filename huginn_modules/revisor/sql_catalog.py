"""SQL read-only baseado EXCLUSIVAMENTE em colunas confirmadas no dump enviado.
O catálogo recebido não contém PCPRODUT/PCEST/PCTABPR/PCEMBALAGEM.
Essas tabelas são bloqueadas até completar o mapeamento de metadados.
"""
from __future__ import annotations
import csv
from pathlib import Path

TABLE_FIELDS = {
    "PCCLIENT": ["CODCLI","CLIENTE","FANTASIA","CGCENT","IEENT","ENDERENT","BAIRROENT","MUNICENT","ESTENT","CEPENT","EMAIL","CODUSUR1","CODPRACA","CODATV1"],
    "PCFORNEC": ["CODFORNEC","FORNECEDOR","FANTASIA","CGC","IE","ENDER","BAIRRO","CIDADE","ESTADO","CEP","EMAIL","BLOQUEIO"],
    "PCUSUARI": ["CODUSUR","NOME","BLOQUEIO","CODSUPERVISOR"],
    "PCPRACA": ["CODPRACA","PRACA","CODMUNIC","CEPINICIAL","CEPFINAL"],
}

def read_catalog(path: str | Path) -> dict[str,set[str]]:
    out: dict[str,set[str]] = {}
    with open(path, encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream, delimiter=";"):
            table, col = row["TABELA"].upper(), row["COLUNA"].upper()
            out.setdefault(table,set()).add(col)
    return out

def build_selects(catalog: dict[str,set[str]]) -> dict[str,str]:
    queries = {}
    for table, fields in TABLE_FIELDS.items():
        missing = set(fields) - catalog.get(table,set())
        if missing:
            raise ValueError(f"Metadados ausentes em {table}: {', '.join(sorted(missing))}")
        queries[table] = f"SELECT {', '.join(fields)} FROM {table}"
    return queries

def build_product_query(catalog: dict[str,set[str]]) -> str:
    required = {"CODPROD","DESCRICAO"}
    if not required.issubset(catalog.get("PCPRODUT",set())):
        raise ValueError("PCPRODUT não consta com colunas mínimas no catálogo recebido")
    return "SELECT CODPROD, DESCRICAO FROM PCPRODUT"
