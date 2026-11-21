"""Figuras tributarias do WinThor (PCTRIBUT) ligadas por PCTABTRIB.

Confirmado no dicionario do banco (21/11/2026):
- PCTABTRIB PK = (CODPROD, CODFILIALNF, UFDESTINO) -> CODST; sem FK para PCTRIBUT.
- PCTRIBUT PK = CODST; SITTRIBUT (CST), CODICM (% ICMS), PERCBASERED, ALIQICMSFECP,
  DTINICIOVIGENCIA / DTFIMVIGENCIA, MENSAGEM.

HIPOTESE (a confirmar com uma NF-e de venda): PERCBASERED e o % da base que FICA
(base reduzida PARA x%) e a carga efetiva e (CODICM + FECP) x PERCBASERED / 100,
com FECP = ALIQICMSFECP ou, em branco, o FECP padrao da UF (RJ: 2%).
Ex.: (20 + 2) x 54,5455% = 12,00%.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

FECP_PADRAO = {"RJ": Decimal("2")}
CST_COM_REDUCAO = {"20", "70"}
CST_SIMPLES = {"101", "102", "103", "201", "202", "203", "300", "400", "500", "900"}
TOLERANCIA_CARGA = Decimal("0.01")


@dataclass(frozen=True)
class Figura:
    codst: int
    mensagem: str
    sittribut: str
    codicm: Decimal | None
    percbasered: Decimal | None
    aliqicmsfecp: Decimal | None
    dt_inicio: date | None = None
    dt_fim: date | None = None
    qt_produtos: int = 0

    @property
    def cst(self) -> str:
        return (self.sittribut or "").strip()

    def fecp(self, uf: str) -> tuple[Decimal, bool]:
        """(FECP usado, veio do padrao da UF?)."""
        if self.aliqicmsfecp is not None:
            return self.aliqicmsfecp, False
        return FECP_PADRAO.get(uf, Decimal("0")), True

    def carga_efetiva(self, uf: str) -> Decimal:
        if not self.codicm:
            return Decimal("0")
        fecp, _ = self.fecp(uf)
        base = (self.percbasered if self.percbasered else Decimal("100")) / 100
        return ((self.codicm + fecp) * base).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class Achado:
    nivel: str        # info | alerta | pendencia
    codst: int
    codigo: str
    mensagem: str


def auditar(figuras: list[Figura], uf: str, regime_normal: bool = True,
            hoje: date | None = None) -> list[Achado]:
    """Revisa as figuras usadas pela filial. So orientacao: quem corrige e o contador."""
    hoje = hoje or date.today()
    out: list[Achado] = []
    for f in figuras:
        txt = (f.mensagem or "").upper()
        if "SEM USO" in txt and f.qt_produtos > 0:
            out.append(Achado("pendencia", f.codst, "FIGURA_SEM_USO_EM_USO",
                              f"Figura {f.codst} esta descrita como 'SEM USO', mas {f.qt_produtos} "
                              "produto(s) apontam para ela."))
        if regime_normal and f.cst in CST_SIMPLES:
            out.append(Achado("pendencia", f.codst, "CSOSN_EM_REGIME_NORMAL",
                              f"Figura {f.codst} usa {f.cst}, codigo do Simples Nacional (CSOSN), "
                              "em empresa do regime normal."))
        if f.cst in CST_COM_REDUCAO and not f.percbasered:
            out.append(Achado("alerta", f.codst, "CST_REDUCAO_SEM_PERCENTUAL",
                              f"Figura {f.codst} tem CST {f.cst} (com reducao) e nao tem % de base reduzida."))
        _, padrao = f.fecp(uf)
        if padrao and f.codicm and uf in FECP_PADRAO:
            out.append(Achado("info", f.codst, "FECP_EM_BRANCO",
                              f"Figura {f.codst} sem FECP informado; o HUGINN considerou "
                              f"{FECP_PADRAO[uf]}% (padrao {uf}). Confirmar."))
        if f.dt_fim and f.dt_fim < hoje and f.qt_produtos > 0:
            out.append(Achado("pendencia", f.codst, "FIGURA_VENCIDA",
                              f"Figura {f.codst} venceu em {f.dt_fim:%d/%m/%Y} e ainda tem produtos."))

    # Mesma carga e CST, figuras diferentes: candidatas a padronizar.
    grupos: dict[tuple, list[Figura]] = defaultdict(list)
    for f in figuras:
        if f.codicm:
            grupos[(f.cst, f.carga_efetiva(uf).quantize(Decimal("0.1")))].append(f)
    for (cst, carga), fs in grupos.items():
        percs = {f.percbasered for f in fs}
        if len(percs) > 1:
            for f in fs:
                exata = f.carga_efetiva(uf)
                if abs(exata - carga) > TOLERANCIA_CARGA or exata != exata.quantize(Decimal("0.1")):
                    out.append(Achado("info", f.codst, "ARREDONDAMENTO_BASE",
                                      f"Figura {f.codst}: % base {f.percbasered} da carga {exata}%; "
                                      f"outras figuras CST {cst} chegam a {carga}% exatos."))
    return out


def figura_sugerida(figuras: list[Figura], uf: str, cst_aceitos: set[str],
                    carga: Decimal) -> Figura | None:
    """Figura ja existente que entrega a carga sugerida (a mais usada)."""
    candidatas = [f for f in figuras if f.cst in cst_aceitos
                  and abs(f.carga_efetiva(uf) - carga) <= TOLERANCIA_CARGA
                  and "SEM USO" not in (f.mensagem or "").upper()]
    return max(candidatas, key=lambda f: f.qt_produtos, default=None)
