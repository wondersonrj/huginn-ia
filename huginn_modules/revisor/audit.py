"""Motor inicial de auditoria cadastral HUGINN (somente leitura).
Entradas são registros exportados do WinThor, sem dependência do Oracle.
Alertas são sugestões; nenhum SQL de alteração é gerado.
"""
from __future__ import annotations
import re
from collections import defaultdict
from dataclasses import asdict, dataclass
from difflib import SequenceMatcher
from typing import Any

@dataclass(frozen=True)
class Finding:
    module: str
    record_id: str
    field: str
    rule: str
    severity: str
    current: str
    suggestion: str
    evidence: str

def normalized(value: Any) -> str:
    import unicodedata
    s = unicodedata.normalize("NFKD", str(value or ""))
    return re.sub(r"\s+", " ", "".join(c for c in s if not unicodedata.combining(c)).upper()).strip()

def digits(value: Any) -> str:
    return re.sub(r"\D", "", str(value or ""))

def valid_cnpj(value: Any) -> bool:
    s = digits(value)
    if len(s) != 14 or len(set(s)) == 1:
        return False
    def check(base: str, weights: list[int]) -> str:
        remainder = sum(int(n) * w for n, w in zip(base, weights)) % 11
        return str(0 if remainder < 2 else 11 - remainder)
    return s[12] == check(s[:12], [5,4,3,2,9,8,7,6,5,4,3,2]) and s[13] == check(s[:13], [6,5,4,3,2,9,8,7,6,5,4,3,2])

def audit_clients(rows: list[dict], required_rca: bool = True) -> list[Finding]:
    findings = []
    by_cnpj = defaultdict(list)
    for row in rows:
        key = str(row.get("codcli", ""))
        cnpj = digits(row.get("cgcent"))
        if cnpj:
            if len(cnpj) == 14 and not valid_cnpj(cnpj):
                findings.append(Finding("clientes",key,"cgcent","cnpj_invalido","alta",cnpj,"Conferir documento","Dígitos verificadores não conferem"))
            by_cnpj[cnpj].append(key)
        if required_rca and not str(row.get("codusur1") or "").strip():
            findings.append(Finding("clientes",key,"codusur1","rca_ausente","media","","Verificar vendedor responsável","Regra comercial configurada"))
        if row.get("cep") and len(digits(row["cep"])) != 8:
            findings.append(Finding("clientes",key,"cep","cep_formato","media",str(row["cep"]),"Conferir CEP","CEP deve conter oito dígitos"))
    for cnpj, ids in by_cnpj.items():
        if len(ids) > 1:
            for key in ids:
                findings.append(Finding("clientes",key,"cgcent","cnpj_duplicado","alta",cnpj,"Revisar cadastros repetidos",f"Códigos relacionados: {', '.join(ids)}"))
    # Alerta de carteira: mesmo endereço COMPLETO e RCAs distintos, nunca erro conclusivo.
    groups = defaultdict(list)
    for row in rows:
        address = tuple(normalized(row.get(f)) for f in ("enderent","numeroent","bairroent","municent","estent"))
        if all(address[:3]):
            groups[address].append(row)
    for address, group in groups.items():
        rcas = {str(r.get("codusur1") or "") for r in group if r.get("codusur1")}
        if len(rcas) > 1:
            for row in group:
                findings.append(Finding("clientes",str(row.get("codcli","")),"codusur1","carteira_mesmo_endereco","baixa",str(row.get("codusur1","")),"Conferir divisão comercial",f"Endereço coincidente; RCAs: {', '.join(sorted(rcas))}"))
    return findings

def audit_suppliers(rows: list[dict], clients: list[dict]) -> list[Finding]:
    findings = []
    client_cnpjs = {digits(r.get("cgcent")) for r in clients if digits(r.get("cgcent"))}
    for row in rows:
        key = str(row.get("codfornec",""))
        cnpj = digits(row.get("cgc"))
        if len(cnpj) == 14 and not valid_cnpj(cnpj):
            findings.append(Finding("fornecedores",key,"cgc","cnpj_invalido","alta",cnpj,"Conferir documento","Dígitos verificadores não conferem"))
        if cnpj and cnpj in client_cnpjs:
            findings.append(Finding("fornecedores",key,"cgc","tambem_cliente","informativa",cnpj,"Verificar consistência entre cadastros","Mesmo documento presente em PCCLIENT; pode ser legítimo"))
    return findings

def audit_products(rows: list[dict], prices: list[dict], stock: list[dict], packaging: list[dict]) -> list[Finding]:
    findings = []
    priced = {str(r.get("codprod")) for r in prices if (r.get("pvenda") or 0) > 0}
    costed = {str(r.get("codprod")) for r in stock if (r.get("custoreal") or 0) > 0}
    packed = {str(r.get("codprod")) for r in packaging}
    for row in rows:
        key = str(row.get("codprod",""))
        if key not in priced:
            findings.append(Finding("produtos",key,"pvenda","preco_nao_localizado","media","","Conferir tabela/filial aplicável","Nenhum preço positivo na exportação recebida"))
        if key not in costed:
            findings.append(Finding("produtos",key,"custoreal","custo_nao_localizado","media","","Conferir custos por filial","Nenhum custo positivo na exportação recebida"))
        if row.get("venda_por_embalagem") is True and key not in packed:
            findings.append(Finding("produtos",key,"pcembalagem","embalagem_ausente","alta","","Conferir cadastro de embalagem","Produto marcado para venda por embalagem"))
    return findings

def run_audit(payload: dict) -> list[dict]:
    clients = payload.get("clientes", [])
    result = audit_clients(clients, payload.get("config",{}).get("exigir_rca", True))
    result += audit_suppliers(payload.get("fornecedores", []), clients)
    result += audit_products(payload.get("produtos", []), payload.get("precos", []), payload.get("estoque", []), payload.get("embalagens", []))
    return [asdict(f) for f in result]
