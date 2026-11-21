"""Contrato JSON da devolutiva para o WinThor (<chave>.huginn.json), versao 1.1.

Regras: `aviso` obrigatorio e nao vazio; campos novos so aumentam a versao menor;
o leitor (HUGINN XML) ignora o que nao conhece.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from .modelos import AVISO_CONTADOR, Alerta, NotaResumo, PerfilCliente, ResultadoItem, StatusValidacao
from .regras import VERSAO_REGRAS

VERSAO_CONTRATO = "1.1"
STATUS_VALIDOS = {s.value for s in StatusValidacao}


def _num(v: Decimal | None) -> float | None:
    return None if v is None else float(v)


def montar(nota: NotaResumo, perfil: PerfilCliente, sha256: str, resultados: list[ResultadoItem],
           alertas: list[Alerta], agora: datetime | None = None) -> dict:
    agora = agora or datetime.now(timezone.utc)
    itens = []
    for r in resultados:
        s, v = r.sugestao, r.validacao
        itens.append({
            "nItem": r.item.n_item, "cProd": r.item.cprod, "descricao": r.item.descricao,
            "ncm": r.item.ncm, "cfop_xml": r.item.cfop, "orig": r.item.orig,
            "sugestao": {
                "regra": s.regra, "tipo": s.tipo, "icms_carga": _num(s.carga_icms_saida_interna),
                "beneficio": s.beneficio, "ato": s.ato, "url": s.url,
                "confianca": s.confianca.value,
                "credito_icms_entrada": s.credito_icms_entrada,
                "credito_icms_estimado": _num(s.credito_icms_estimado),
                "pis_cofins_cbs": s.pis_cofins_cbs, "observacoes": s.observacoes,
            },
            "validacao": {
                "status": v.status.value, "winthor": {"icms_carga": _num(v.carga_winthor)},
                "diferenca_estimada": _num(v.diferenca_estimada), "detalhe": v.detalhe,
            },
            "guia": r.guia,
            "dica_venda": [{"uf": d.uf, "aliquota": _num(d.aliquota), "base_legal": d.base_legal,
                            "obs": d.observacao} for d in r.dicas],
        })
    resumo = {st: sum(1 for i in itens if i["validacao"]["status"] == st) for st in STATUS_VALIDOS}
    resumo["diferenca_estimada_total"] = round(sum(
        (i["validacao"]["diferenca_estimada"] or 0) for i in itens), 2)
    return {
        "versao": VERSAO_CONTRATO,
        "aviso": AVISO_CONTADOR,
        "gerado_em": agora.isoformat(timespec="seconds"),
        "chave": nota.chave, "sha256": sha256, "data_emissao": nota.data_emissao.isoformat(),
        "emitente": {"cnpj": nota.cnpj_emit, "uf": nota.uf_emit, "crt": nota.crt_emit},
        "perfil": {
            "cnpj": perfil.cnpj, "uf": perfil.uf, "regime": perfil.regime.value,
            "atividade": perfil.atividade.value,
            "beneficios": [b.codigo.value for b in perfil.beneficios if b.vigente(nota.data_emissao)],
            "contador": perfil.contador.texto() if perfil.contador else None,
        },
        "regras_versao": VERSAO_REGRAS,
        "alertas": [{"nivel": a.nivel, "codigo": a.codigo, "mensagem": a.mensagem} for a in alertas],
        "resumo": resumo,
        "itens": itens,
    }


def validar_devolutiva(d: dict) -> None:
    """Confere o contrato antes de gravar. Levanta ValueError com o motivo."""
    if not str(d.get("aviso", "")).strip():
        raise ValueError("aviso ao contador ausente")
    if not str(d.get("versao", "")).startswith("1."):
        raise ValueError("versao de contrato nao suportada")
    if len(str(d.get("chave", ""))) != 44:
        raise ValueError("chave invalida")
    for i in d.get("itens", []):
        if i["validacao"]["status"] not in STATUS_VALIDOS:
            raise ValueError(f"status invalido no item {i.get('nItem')}")
        if i["sugestao"]["confianca"] not in {"alta", "media", "baixa"}:
            raise ValueError(f"confianca invalida no item {i.get('nItem')}")


def gravar(d: dict, pasta: Path) -> Path:
    validar_devolutiva(d)
    pasta.mkdir(parents=True, exist_ok=True)
    destino = pasta / f"{d['chave']}.huginn.json"
    tmp = destino.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(destino)
    return destino
