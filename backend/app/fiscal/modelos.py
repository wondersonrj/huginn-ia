"""Modelos do Consultor Fiscal HUGINN.

Tudo o que sai daqui e SUGESTAO ORIENTATIVA. A validacao e a parametrizacao
final sao do contador responsavel; o HUGINN nunca grava tributacao no WinThor.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import Enum

AVISO_CONTADOR = (
    "Sugestao orientativa gerada pelo HUGINN. A validacao e a parametrizacao final "
    "sao de responsabilidade do contador responsavel."
)


class Regime(str, Enum):
    SIMPLES = "simples_nacional"
    PRESUMIDO = "lucro_presumido"
    REAL = "lucro_real"


class Atividade(str, Enum):
    ATACADO_EXCLUSIVO = "atacadista_exclusivo"
    ATACADO_VAREJO = "atacado_e_varejo"
    VAREJO = "varejo"
    CD_INDUSTRIA = "cd_industria"


class Beneficio(str, Enum):
    RIOLOG = "RIOLOG"
    CESTA_BASICA = "CESTA_BASICA"
    CONV_100_97 = "CONV_100_97"


class Confianca(str, Enum):
    ALTA = "alta"      # regra legal + lista aprovada pelo contador + perfil completo
    MEDIA = "media"    # regra legal, mas lista ou perfil ainda sem aprovacao
    BAIXA = "baixa"    # falta dado ou depende de analise do contador


class StatusValidacao(str, Enum):
    CONFERE = "confere"
    DIVERGE = "diverge"
    NAO_SE_APLICA = "nao_se_aplica"
    SEM_REGRA = "sem_regra"     # nenhuma regra confirmada: vai para o contador
    PENDENTE = "pendente"       # tributacao do WinThor ainda nao lida


@dataclass(frozen=True)
class Contador:
    nome: str
    crc: str
    email: str = ""

    def texto(self) -> str:
        return f"{self.nome} - CRC {self.crc}".strip()


@dataclass(frozen=True)
class BeneficioCliente:
    codigo: Beneficio
    ato: str = ""                 # n do termo de acordo / ato concessivo
    inicio: date | None = None
    fim: date | None = None

    def vigente(self, d: date) -> bool:
        return (self.inicio is None or d >= self.inicio) and (self.fim is None or d <= self.fim)


@dataclass
class PerfilCliente:
    cnpj: str
    uf: str
    regime: Regime
    atividade: Atividade
    beneficios: list[BeneficioCliente] = field(default_factory=list)
    contador: Contador | None = None
    # Simples Nacional a partir de 2027: True = IBS/CBS no regime regular; False = no DAS; None = nao informado.
    simples_ibs_cbs_regular: bool | None = None

    def beneficio(self, codigo: Beneficio, d: date) -> BeneficioCliente | None:
        for b in self.beneficios:
            if b.codigo == codigo and b.vigente(d):
                return b
        return None


@dataclass(frozen=True)
class ItemNota:
    n_item: int
    cprod: str
    descricao: str
    ncm: str
    cfop: str
    orig: str                      # origem da mercadoria (0..8)
    v_prod: Decimal
    v_desc: Decimal = Decimal("0")
    cst: str = ""                  # CST ICMS (emitente regime normal)
    csosn: str = ""                # CSOSN (emitente Simples)
    p_icms: Decimal = Decimal("0")
    v_icms: Decimal = Decimal("0")
    p_cred_sn: Decimal = Decimal("0")
    v_cred_sn: Decimal = Decimal("0")

    @property
    def valor_liquido(self) -> Decimal:
        return self.v_prod - self.v_desc


@dataclass(frozen=True)
class NotaResumo:
    chave: str
    data_emissao: date
    cnpj_emit: str
    uf_emit: str
    crt_emit: str                  # 1/4 = Simples; 2 = Simples excesso; 3 = normal
    cnpj_dest: str
    uf_dest: str
    itens: tuple[ItemNota, ...]

    @property
    def emitente_simples(self) -> bool:
        return self.crt_emit in ("1", "4")

    @property
    def interestadual(self) -> bool:
        return self.uf_emit != self.uf_dest


@dataclass(frozen=True)
class TributacaoAtual:
    """O que esta parametrizado hoje no WinThor para o item (lido pelo HUGINN XML)."""
    carga_icms_saida_interna: Decimal   # % efetivo na saida interna (com FECP)


@dataclass
class Sugestao:
    regra: str
    tipo: str                          # geral | reducao_base | aliquota_riolog | isencao
    carga_icms_saida_interna: Decimal
    beneficio: str | None
    ato: str
    url: str
    confianca: Confianca
    credito_icms_entrada: str
    credito_icms_estimado: Decimal | None
    pis_cofins_cbs: str
    observacoes: list[str] = field(default_factory=list)


@dataclass
class Validacao:
    status: StatusValidacao
    carga_winthor: Decimal | None = None
    diferenca_estimada: Decimal | None = None
    detalhe: str = ""


@dataclass(frozen=True)
class DicaVenda:
    uf: str
    aliquota: Decimal
    base_legal: str
    observacao: str


@dataclass
class ResultadoItem:
    item: ItemNota
    sugestao: Sugestao
    validacao: Validacao
    guia: list[str]
    dicas: list[DicaVenda]


@dataclass(frozen=True)
class Alerta:
    nivel: str          # info | alerta | bloqueio
    codigo: str
    mensagem: str
