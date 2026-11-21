"""Consultor Fiscal pela linha de comando (o servico usa as mesmas funcoes).

python -m app.fiscal.cli --xml nota.xml --perfis perfis.json --listas pasta_listas [--saida pasta]
                         [--winthor atual.json]

atual.json (opcional, lido do WinThor pelo HUGINN XML): {"1": 22, "2": 7}  -> nItem: carga %.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

from . import consultor, devolutiva
from .modelos import TributacaoAtual
from .nfe import ler_nfe
from .perfil import carregar_perfis, perfil_bloqueado, validar_perfil
from .regras import carregar_listas


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="HUGINN Consultor Fiscal (sugestao orientativa)")
    ap.add_argument("--xml", required=True, type=Path)
    ap.add_argument("--perfis", required=True, type=Path)
    ap.add_argument("--listas", required=True, type=Path)
    ap.add_argument("--saida", type=Path)
    ap.add_argument("--winthor", type=Path)
    a = ap.parse_args(argv)

    dados = a.xml.read_bytes()
    nota = ler_nfe(dados)
    perfis = carregar_perfis(a.perfis)
    perfil = perfis.get(nota.cnpj_dest)
    if perfil is None:
        print(f"Destinatario {nota.cnpj_dest} sem perfil cadastrado.", file=sys.stderr)
        return 2
    alertas = validar_perfil(perfil, date.today())
    if perfil_bloqueado(alertas):
        for al in alertas:
            print(f"[{al.nivel}] {al.mensagem}", file=sys.stderr)
        return 3
    atuais = {}
    if a.winthor:
        atuais = {int(k): TributacaoAtual(Decimal(str(v)))
                  for k, v in json.loads(a.winthor.read_text(encoding="utf-8")).items()}
    resultados = consultor.analisar(nota, perfil, carregar_listas(a.listas), atuais)
    doc = devolutiva.montar(nota, perfil, hashlib.sha256(dados).hexdigest(), resultados, alertas)
    if a.saida:
        print(devolutiva.gravar(doc, a.saida))
    else:
        devolutiva.validar_devolutiva(doc)
        print(json.dumps(doc, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
