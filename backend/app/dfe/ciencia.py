"""Envio da ciencia da operacao para os resumos pendentes (OPCIONAL: desligado por padrao).

Depois da ciencia, o XML completo chega pela distribuicao no proximo ciclo permitido.
Registro em <pasta>/manifestacoes.jsonl (chave, cStat, protocolo, data). Nunca reenvia
uma chave ja registrada (135/136/573).
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Callable

from .armazenamento import Armazenamento
from .distribuicao import ErroDistribuicao, normalizar_cnpj
from .manifestacao import (ACTION_EVENTO, URL_EVENTO_HOMOLOGACAO, URL_EVENTO_PRODUCAO, assinar_evento,
                           envelope_evento, ler_retorno_evento, montar_evento_ciencia)
from .transporte import Transporte

MAX_POR_LOTE = 20


def _registro(pasta: Path) -> Path:
    return Path(pasta) / "manifestacoes.jsonl"


def ja_manifestadas(pasta: Path) -> set[str]:
    arq = _registro(pasta)
    if not arq.exists():
        return set()
    ok = set()
    for linha in arq.read_text(encoding="utf-8").splitlines():
        if linha.strip():
            item = json.loads(linha)
            if item.get("ok"):
                ok.add(item["chave"])
    return ok


def manifestar_pendentes(cnpj: str, tp_amb: int, transporte: Transporte, chave_privada, certificado,
                         armazenamento: Armazenamento, chaves: list[str] | None = None,
                         agora: Callable[[], datetime] = datetime.now) -> list[dict]:
    """Envia ciencia para os resumos pendentes do CNPJ (ou so para `chaves`, se informado)."""
    cnpj = normalizar_cnpj(cnpj)
    feitas = ja_manifestadas(armazenamento.pasta)
    alvo = [p["chave"] for p in armazenamento.resumos_pendentes()
            if p.get("cnpj_interessado") == cnpj and p.get("situacao_nfe") == "1" and p["chave"] not in feitas]
    if chaves is not None:
        alvo = [c for c in alvo if c in set(chaves)]
    alvo = alvo[:MAX_POR_LOTE]
    if not alvo:
        return []
    momento = agora()
    eventos = [assinar_evento(montar_evento_ciencia(tp_amb, cnpj, c, momento), chave_privada, certificado)
               for c in alvo]
    url = URL_EVENTO_PRODUCAO if tp_amb == 1 else URL_EVENTO_HOMOLOGACAO
    resultado = []
    try:
        c_stat, x_motivo, itens = ler_retorno_evento(
            transporte.enviar(url, envelope_evento(eventos, int(momento.strftime("%y%m%d%H%M%S"))), ACTION_EVENTO))
    except ErroDistribuicao as exc:
        return [{"chave": c, "ok": False, "c_stat": "", "x_motivo": str(exc)} for c in alvo]
    por_chave = {i.chave: i for i in itens}
    with open(_registro(armazenamento.pasta), "a", encoding="utf-8") as arq:
        for c in alvo:
            i = por_chave.get(c)
            item = {"data": momento.isoformat(timespec="seconds"), "cnpj": cnpj, "chave": c,
                    "ok": bool(i and i.ok), "c_stat": i.c_stat if i else c_stat,
                    "x_motivo": i.x_motivo if i else x_motivo, "protocolo": i.protocolo if i else ""}
            arq.write(json.dumps(item, ensure_ascii=False) + "\n")
            resultado.append(item)
    return resultado
