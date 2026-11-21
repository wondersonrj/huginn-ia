"""Motor do Consultor Fiscal: sugestao, validacao, guia e dica de venda por item.

Somente orientacao. Toda saida leva o AVISO_CONTADOR e o ato legal ao lado.
"""
from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from .modelos import (Atividade, Beneficio, Confianca, DicaVenda, ItemNota, NotaResumo,
                      PerfilCliente, Regime, ResultadoItem, StatusValidacao, Sugestao,
                      TributacaoAtual, Validacao)
from .regras import (IMPORTADO, INICIO_CBS_PLENA, INTERESTADUAL, ORIGENS_IMPORTADAS, UFS_DICA,
                     ListaProdutos, regra, regra_geral)

CENT = Decimal("0.01")
ZERO = Decimal("0")

# CFOP do emitente que indicam mercadoria vendida/transferida/bonificada ao cliente.
_CFOP_MERCADORIA = {str(c) for c in (
    *range(5101, 5125), *range(6101, 6125), *range(5401, 5406), *range(6401, 6406),
    *range(5151, 5157), *range(6151, 6157), 5910, 6910,
)}


def _q(v: Decimal) -> Decimal:
    return v.quantize(CENT, rounding=ROUND_HALF_UP)


def sugerir(item: ItemNota, nota: NotaResumo, perfil: PerfilCliente,
            listas: dict[Beneficio, ListaProdutos]) -> Sugestao:
    d = nota.data_emissao
    obs: list[str] = []
    cesta = listas.get(Beneficio.CESTA_BASICA)
    conv = listas.get(Beneficio.CONV_100_97)
    desc_cesta = cesta.contem(item.ncm) if cesta else None
    desc_conv = conv.contem(item.ncm) if conv else None
    if cesta and (motivo := cesta.motivo_exclusao(item.ncm)):
        obs.append(f"NCM excluido da cesta basica pelo contador: {motivo}.")

    lista_usada: ListaProdutos | None = None
    r = None
    if desc_conv and perfil.beneficio(Beneficio.CONV_100_97, d) and regra("RJ-CONV100-ISENTO", d):
        r, lista_usada = regra("RJ-CONV100-ISENTO", d), conv
        obs.append(f"Insumo agropecuario: {desc_conv}. Confirme a destinacao do produto.")
        if perfil.beneficio(Beneficio.RIOLOG, d):
            obs.append("Cliente tambem no RIOLOG: confirme com o contador a compatibilidade.")
    elif perfil.beneficio(Beneficio.RIOLOG, d):
        if perfil.atividade == Atividade.ATACADO_EXCLUSIVO:
            r = regra("RJ-RIOLOG-7" if desc_cesta else "RJ-RIOLOG-12", d)
            lista_usada = cesta if desc_cesta else None
            obs.append("Carga do RIOLOG inclui a parcela do fundo; confira o termo de acordo.")
        else:
            obs.append("RIOLOG nao aplicado: a atividade cadastrada nao e atacadista exclusiva.")
    if r is None and desc_cesta and perfil.beneficio(Beneficio.CESTA_BASICA, d):
        r, lista_usada = regra("RJ-CESTA-7", d), cesta
        obs.append(f"Cesta basica: {desc_cesta}.")
    if r is None:
        r = regra_geral(d)
        obs.append("Aliquota geral: o HUGINN nao verifica aliquotas especificas por NCM fora das "
                   "listas do contador.")

    carga = r.carga if r.carga is not None else ZERO

    # Confianca
    if perfil.regime == Regime.SIMPLES or perfil.contador is None:
        confianca = Confianca.BAIXA
    elif r.tipo == "geral" or (lista_usada is not None and not lista_usada.aprovada):
        confianca = Confianca.MEDIA
    else:
        confianca = Confianca.ALTA
    if lista_usada is not None and not lista_usada.aprovada:
        obs.append("Lista de produtos ainda nao aprovada pelo contador.")

    credito_txt, credito_val = _credito_icms(item, nota, perfil, r.tipo, carga)
    return Sugestao(
        regra=r.codigo, tipo=r.tipo, carga_icms_saida_interna=carga,
        beneficio=r.beneficio.value if r.beneficio else None, ato=r.ato, url=r.url,
        confianca=confianca, credito_icms_entrada=credito_txt,
        credito_icms_estimado=credito_val, pis_cofins_cbs=_pis_cofins_cbs(perfil, d),
        observacoes=obs,
    )


def _credito_icms(item: ItemNota, nota: NotaResumo, perfil: PerfilCliente, tipo: str,
                  carga: Decimal) -> tuple[str, Decimal | None]:
    if perfil.regime == Regime.SIMPLES:
        return "Cliente do Simples Nacional: nao toma credito de ICMS (recolhe no DAS).", ZERO
    if tipo == "isencao":
        return ("Saida isenta: em regra o credito da entrada e estornado, salvo manutencao "
                "prevista (Lei RJ 9.269/2021; Consulta 86/2024). Verificar com o contador.", None)
    if nota.emitente_simples:
        return ("Fornecedor do Simples: credito limitado ao valor informado no XML "
                "(LC 123/2006, art. 23).", _q(item.v_cred_sn))
    if tipo == "aliquota_riolog":
        return "Credito conforme o termo de acordo do RIOLOG. Verificar com o contador.", None
    if tipo == "reducao_base" and item.p_icms > carga and item.p_icms > 0:
        return ("Saida com reducao de base: anulacao proporcional do credito, limitado a "
                f"{carga}% (SEFAZ-RJ, cesta basica).", _q(item.v_icms * carga / item.p_icms))
    return "Credito do ICMS destacado na nota.", _q(item.v_icms)


def _pis_cofins_cbs(perfil: PerfilCliente, d: date) -> str:
    if d >= INICIO_CBS_PLENA:
        if perfil.regime == Regime.SIMPLES:
            if perfil.simples_ibs_cbs_regular is True:
                return "IBS/CBS no regime regular: credito na entrada (LC 214/2025)."
            if perfil.simples_ibs_cbs_regular is False:
                return "IBS/CBS recolhidos no DAS: sem credito na entrada."
            return "Opcao de IBS/CBS do Simples nao informada: definir com o contador."
        return ("PIS/Cofins extintos; CBS com credito na entrada conforme LC 214/2025. "
                "Verificar com o contador.")
    base = {
        Regime.REAL: ("Lucro Real (PIS/Cofins nao cumulativo): credito na compra para revenda, "
                      "exceto monofasicos, aliquota zero ou suspensao."),
        Regime.PRESUMIDO: "Lucro Presumido (PIS/Cofins cumulativo): sem credito na entrada.",
        Regime.SIMPLES: "Simples Nacional: PIS/Cofins no DAS, sem credito na entrada.",
    }[perfil.regime]
    if d.year == 2026:
        base += " Em 2026, CBS 0,9% e IBS 0,1% sao apenas de teste."
    return base


def validar(sug: Sugestao, item: ItemNota, perfil: PerfilCliente,
            atual: TributacaoAtual | None) -> Validacao:
    if item.cfop not in _CFOP_MERCADORIA:
        return Validacao(StatusValidacao.NAO_SE_APLICA,
                         detalhe=f"CFOP {item.cfop} nao indica mercadoria para revenda.")
    if perfil.regime == Regime.SIMPLES:
        return Validacao(StatusValidacao.SEM_REGRA,
                         detalhe="Simples Nacional: a tributacao deve ser definida pelo contador.")
    if atual is None:
        return Validacao(StatusValidacao.PENDENTE,
                         detalhe="Tributacao do WinThor ainda nao lida para este produto.")
    if atual.carga_icms_saida_interna == sug.carga_icms_saida_interna:
        return Validacao(StatusValidacao.CONFERE, carga_winthor=atual.carga_icms_saida_interna,
                         diferenca_estimada=ZERO, detalhe="WinThor igual a sugestao.")
    dif = _q((atual.carga_icms_saida_interna - sug.carga_icms_saida_interna) / 100
             * item.valor_liquido)
    sentido = "a mais" if dif > 0 else "a menos"
    return Validacao(
        StatusValidacao.DIVERGE, carga_winthor=atual.carga_icms_saida_interna,
        diferenca_estimada=dif,
        detalhe=(f"WinThor {atual.carga_icms_saida_interna}% x sugestao "
                 f"{sug.carga_icms_saida_interna}%: cerca de R$ {abs(dif)} {sentido} "
                 "na revenda deste item (estimativa sobre o valor da nota, sem margem)."),
    )


def guia(sug: Sugestao, val: Validacao) -> list[str]:
    s = val.status
    if s == StatusValidacao.CONFERE:
        return ["Nada a ajustar. Guarde a evidencia (este relatorio) para o contador."]
    if s == StatusValidacao.NAO_SE_APLICA:
        return ["Confirme o tipo de operacao com o fiscal; o HUGINN so sugere para mercadoria."]
    if s == StatusValidacao.SEM_REGRA:
        return ["Envie o item ao contador responsavel para definir a tributacao.",
                "Depois de parametrizado, reanalise a nota no HUGINN."]
    passos = []
    if sug.beneficio:
        passos.append(f"Confirme com o contador que o produto esta no beneficio {sug.beneficio} "
                      f"({sug.ato}).")
    if s == StatusValidacao.PENDENTE:
        passos.append("Abra a nota no HUGINN XML conectado ao WinThor para ler a tributacao atual.")
    else:
        passos.append("Ajuste a tributacao do produto na rotina de tributacao do WinThor usada "
                      "pelo cliente, com o aval do contador.")
    passos.append("Reanalise a nota no HUGINN: o item deve ficar em 'confere'.")
    return passos


def dicas_venda(item: ItemNota, sug: Sugestao, perfil: PerfilCliente, d: date) -> list[DicaVenda]:
    dicas: list[DicaVenda] = []
    extra = "ST e DIFAL no destino: verificar com o contador."
    if perfil.regime == Regime.SIMPLES:
        extra = "Simples Nacional: ICMS no DAS. " + extra
    for uf in UFS_DICA:
        if uf == perfil.uf:
            obs = "Isencao interna." if sug.tipo == "isencao" else "Carga interna sugerida."
            dicas.append(DicaVenda(uf, sug.carga_icms_saida_interna, sug.ato, obs + " " + extra))
            continue
        aliq, base = INTERESTADUAL[uf]
        obs = extra
        if item.orig in ORIGENS_IMPORTADAS:
            aliq, base = IMPORTADO
            obs = f"Origem {item.orig} (importado). " + extra
        if sug.beneficio == Beneficio.RIOLOG.value:
            obs += " RIOLOG: pode haver credito presumido na saida interestadual (termo de acordo)."
        if sug.beneficio == Beneficio.CONV_100_97.value:
            obs += " Conv. 100/97: reducao de base na interestadual conforme a destinacao."
        dicas.append(DicaVenda(uf, aliq, base, obs.strip()))
    return dicas


def analisar(nota: NotaResumo, perfil: PerfilCliente, listas: dict[Beneficio, ListaProdutos],
             atuais: dict[int, TributacaoAtual] | None = None) -> list[ResultadoItem]:
    atuais = atuais or {}
    out: list[ResultadoItem] = []
    for item in nota.itens:
        sug = sugerir(item, nota, perfil, listas)
        val = validar(sug, item, perfil, atuais.get(item.n_item))
        out.append(ResultadoItem(item, sug, val, guia(sug, val),
                                 dicas_venda(item, sug, perfil, nota.data_emissao)))
    return out
