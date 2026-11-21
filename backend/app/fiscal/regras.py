"""Catalogo de regras fiscais versionado (RJ) e listas de produtos aprovadas pelo contador.

Cada regra carrega o ato legal, o link consultado e a vigencia. A data de emissao
da nota escolhe a regra. Listas de NCM NAO sao inventadas aqui: vem de um JSON
mantido pelo contador do cliente (ver exemplos/lista_modelo.json).

Fontes consultadas em 21/11/2026 (ver docs do escopo):
- Aliquota geral RJ 20% + 2% FECP: portal.fazenda.rj.gov.br/pagamentos/aliquotas-internas/
- Cesta basica: Lei RJ 4.892/2006 e Decreto 32.161/2002; carga 7%; anulacao proporcional do credito.
- RIOLOG: Lei 9.025/2020, Decreto 47.437/2020 (7% cesta basica / 12% demais, atacadista).
- Convenio ICMS 100/97: Resolucao SEF 2.884/1997; prorrogado ate 31/12/2027 (Convenio 79/2025).
- Interestaduais: Resolucao do Senado 22/1989 (12% / 7%) e 13/2012 (4% importados).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path

from .modelos import Beneficio

VERSAO_REGRAS = "RJ-2026.11"
INICIO_CBS_PLENA = date(2027, 1, 1)


@dataclass(frozen=True)
class Regra:
    codigo: str
    descricao: str
    carga: Decimal | None          # carga efetiva na saida interna (com FECP), None = isencao
    tipo: str
    ato: str
    url: str
    inicio: date | None = None
    fim: date | None = None
    beneficio: Beneficio | None = None

    def vigente(self, d: date) -> bool:
        return (self.inicio is None or d >= self.inicio) and (self.fim is None or d <= self.fim)


REGRAS_RJ: tuple[Regra, ...] = (
    Regra("RJ-GERAL-18", "Aliquota geral RJ (antes de 20/03/2024)", Decimal("20"), "geral",
          "Lei RJ 2.657/1996 + FECP", "https://portal.fazenda.rj.gov.br/pagamentos/aliquotas-internas/",
          fim=date(2024, 3, 19)),
    Regra("RJ-GERAL-20", "Aliquota geral RJ: 20% ICMS + 2% FECP", Decimal("22"), "geral",
          "Lei RJ 2.657/1996, Lei 10.253/2023 + FECP",
          "https://portal.fazenda.rj.gov.br/pagamentos/aliquotas-internas/",
          inicio=date(2024, 3, 20)),
    Regra("RJ-CESTA-7", "Cesta basica: carga de 7% por reducao de base de calculo", Decimal("7"),
          "reducao_base", "Lei RJ 4.892/2006; Decreto 32.161/2002",
          "https://portal.fazenda.rj.gov.br/icms/cesta-basica/", beneficio=Beneficio.CESTA_BASICA),
    Regra("RJ-RIOLOG-7", "RIOLOG: atacadista, produto da cesta basica", Decimal("7"),
          "aliquota_riolog", "Lei RJ 9.025/2020; Decreto 47.437/2020",
          "https://www.legisweb.com.br/legislacao/?id=422476",
          inicio=date(2020, 9, 1), beneficio=Beneficio.RIOLOG),
    Regra("RJ-RIOLOG-12", "RIOLOG: atacadista, demais produtos", Decimal("12"),
          "aliquota_riolog", "Lei RJ 9.025/2020; Decreto 47.437/2020",
          "https://www.legisweb.com.br/legislacao/?id=422476",
          inicio=date(2020, 9, 1), beneficio=Beneficio.RIOLOG),
    Regra("RJ-CONV100-ISENTO", "Insumo agropecuario (Conv. ICMS 100/97): isencao interna", None,
          "isencao", "Convenio ICMS 100/97; Resolucao SEF 2.884/1997; Convenio 79/2025",
          "https://www.legisweb.com.br/legislacao/?id=346311",
          fim=date(2027, 12, 31), beneficio=Beneficio.CONV_100_97),
)

INTERESTADUAL = {
    "SP": (Decimal("12"), "Resolucao do Senado 22/1989"),
    "MG": (Decimal("12"), "Resolucao do Senado 22/1989"),
    "ES": (Decimal("7"), "Resolucao do Senado 22/1989"),
}
IMPORTADO = (Decimal("4"), "Resolucao do Senado 13/2012")
ORIGENS_IMPORTADAS = {"1", "2", "3", "8"}   # 6 e 7 (sem similar, CAMEX) ficam fora da 13/2012
UFS_DICA = ("RJ", "SP", "MG", "ES")


def regra(codigo: str, d: date) -> Regra | None:
    for r in REGRAS_RJ:
        if r.codigo == codigo and r.vigente(d):
            return r
    return None


def regra_geral(d: date) -> Regra:
    for r in REGRAS_RJ:
        if r.tipo == "geral" and r.vigente(d):
            return r
    raise LookupError("sem regra geral vigente")


@dataclass
class ListaProdutos:
    """Lista de NCMs de um beneficio, mantida pelo contador do cliente.

    Um NCM da lista pode ter 2 a 8 digitos (prefixo). `aprovada_por` vazio = lista
    em rascunho: o HUGINN usa, mas com confianca media.
    """
    beneficio: Beneficio
    ncms: dict[str, str] = field(default_factory=dict)     # prefixo -> descricao legal
    aprovada_por: str = ""
    aprovada_em: date | None = None
    excluidos: dict[str, str] = field(default_factory=dict)  # prefixo -> motivo (ex.: arroz integral)

    @property
    def aprovada(self) -> bool:
        return bool(self.aprovada_por) and self.aprovada_em is not None

    def contem(self, ncm: str) -> str | None:
        """Devolve a descricao legal se o NCM esta na lista (e nao foi excluido)."""
        n = "".join(c for c in ncm if c.isdigit())
        if any(n.startswith(p) for p in self.excluidos):
            return None
        melhor = ""
        for p in self.ncms:
            if n.startswith(p) and len(p) > len(melhor):
                melhor = p
        return self.ncms[melhor] if melhor else None

    def motivo_exclusao(self, ncm: str) -> str | None:
        n = "".join(c for c in ncm if c.isdigit())
        for p, motivo in self.excluidos.items():
            if n.startswith(p):
                return motivo
        return None


def carregar_lista(caminho: Path) -> ListaProdutos:
    dados = json.loads(Path(caminho).read_text(encoding="utf-8"))
    aprovada_em = dados.get("aprovada_em") or None
    lista = ListaProdutos(
        beneficio=Beneficio(dados["beneficio"]),
        ncms={_ncm(k): str(v) for k, v in dados.get("ncms", {}).items()},
        aprovada_por=str(dados.get("aprovada_por", "")).strip(),
        aprovada_em=date.fromisoformat(aprovada_em) if aprovada_em else None,
        excluidos={_ncm(k): str(v) for k, v in dados.get("excluidos", {}).items()},
    )
    return lista


def carregar_listas(pasta: Path) -> dict[Beneficio, ListaProdutos]:
    listas: dict[Beneficio, ListaProdutos] = {}
    for arq in sorted(Path(pasta).glob("*.json")):
        lista = carregar_lista(arq)
        listas[lista.beneficio] = lista
    return listas


def _ncm(valor: str) -> str:
    n = "".join(c for c in str(valor) if c.isdigit())
    if not 2 <= len(n) <= 8:
        raise ValueError(f"NCM invalido na lista: {valor!r}")
    return n
