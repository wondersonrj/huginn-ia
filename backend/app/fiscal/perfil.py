"""Perfil fiscal do cliente (um por CNPJ): leitura do JSON do instalador e travas."""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

from .modelos import (Alerta, Atividade, Beneficio, BeneficioCliente, Contador, PerfilCliente,
                      Regime)

DIAS_AVISO_VENCIMENTO = 30


def perfil_de_dict(d: dict) -> PerfilCliente:
    contador = d.get("contador") or None
    return PerfilCliente(
        cnpj=str(d["cnpj"]).strip().upper(),
        uf=str(d["uf"]).strip().upper(),
        regime=Regime(d["regime"]),
        atividade=Atividade(d["atividade"]),
        beneficios=[
            BeneficioCliente(
                codigo=Beneficio(b["codigo"]),
                ato=str(b.get("ato", "")),
                inicio=date.fromisoformat(b["inicio"]) if b.get("inicio") else None,
                fim=date.fromisoformat(b["fim"]) if b.get("fim") else None,
            )
            for b in d.get("beneficios", [])
        ],
        contador=Contador(contador["nome"], contador["crc"], contador.get("email", ""))
        if contador and contador.get("nome") and contador.get("crc") else None,
        simples_ibs_cbs_regular=d.get("simples_ibs_cbs_regular"),
    )


def carregar_perfis(caminho: Path) -> dict[str, PerfilCliente]:
    """Arquivo do instalador: {"perfis": [ {...}, ... ]} -> {cnpj: perfil}."""
    dados = json.loads(Path(caminho).read_text(encoding="utf-8"))
    perfis = [perfil_de_dict(p) for p in dados.get("perfis", [])]
    return {p.cnpj: p for p in perfis}


def validar_perfil(p: PerfilCliente, hoje: date) -> list[Alerta]:
    """Travas do cadastro. 'bloqueio' = o Consultor nao sugere ate corrigir."""
    alertas: list[Alerta] = []
    if p.contador is None:
        alertas.append(Alerta("bloqueio", "SEM_CONTADOR",
                              "Cadastre o contador responsavel (nome e CRC). Sem ele o HUGINN "
                              "nao emite sugestao tributaria."))
    if p.uf != "RJ":
        alertas.append(Alerta("bloqueio", "UF_SEM_REGRAS",
                              f"Ainda nao ha regras do HUGINN para {p.uf}. Inicio: somente RJ."))

    codigos = [b.codigo for b in p.beneficios]
    if Beneficio.RIOLOG in codigos:
        if p.atividade != Atividade.ATACADO_EXCLUSIVO:
            alertas.append(Alerta("alerta", "RIOLOG_ATIVIDADE",
                                  "O RIOLOG vale para atividade exclusivamente atacadista "
                                  "(Decreto 49.122/2024). Confirme com o contador."))
        alertas.append(Alerta("info", "RIOLOG_RENUNCIA",
                              "A adesao ao RIOLOG implica renuncia a outros regimes diferenciados "
                              "do RJ. Confirme com o contador que nao ha outro ativo."))
        if not next(b for b in p.beneficios if b.codigo == Beneficio.RIOLOG).ato:
            alertas.append(Alerta("alerta", "RIOLOG_SEM_TERMO",
                                  "Informe o numero do termo de acordo do RIOLOG."))

    if p.regime == Regime.SIMPLES and p.beneficios:
        alertas.append(Alerta("alerta", "SIMPLES_BENEFICIO",
                              "Cliente do Simples Nacional: a aplicacao de beneficios estaduais "
                              "fica 'a confirmar pelo contador'. O HUGINN nao presume."))
    if p.regime == Regime.SIMPLES and p.simples_ibs_cbs_regular is None and hoje.year >= 2026:
        alertas.append(Alerta("info", "SIMPLES_OPCAO_IBS_CBS",
                              "Informe se o cliente recolhe IBS/CBS no DAS ou no regime regular "
                              "a partir de 2027."))

    for b in p.beneficios:
        if b.fim is None:
            continue
        if b.fim < hoje:
            alertas.append(Alerta("alerta", f"{b.codigo.value}_VENCIDO",
                                  f"{b.codigo.value} venceu em {b.fim:%d/%m/%Y} e deixou de ser sugerido."))
        elif b.fim <= hoje + timedelta(days=DIAS_AVISO_VENCIMENTO):
            alertas.append(Alerta("alerta", f"{b.codigo.value}_VENCENDO",
                                  f"{b.codigo.value} vence em {b.fim:%d/%m/%Y}. Verifique a renovacao."))
    return alertas


def perfil_bloqueado(alertas: list[Alerta]) -> bool:
    return any(a.nivel == "bloqueio" for a in alertas)
