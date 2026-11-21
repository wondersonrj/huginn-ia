"""Testes do Consultor Fiscal. NCMs e listas aqui sao DADOS DE TESTE, nao a lista legal."""
from __future__ import annotations

import json
from datetime import date
from decimal import Decimal as D

import pytest

from app.fiscal import consultor, devolutiva
from app.fiscal.modelos import (AVISO_CONTADOR, Atividade, Beneficio, BeneficioCliente, Confianca,
                                Contador, ItemNota, NotaResumo, PerfilCliente, Regime,
                                StatusValidacao, TributacaoAtual)
from app.fiscal.nfe import ErroNFe, ler_nfe
from app.fiscal.perfil import carregar_perfis, perfil_bloqueado, validar_perfil
from app.fiscal.regras import ListaProdutos, carregar_lista, regra_geral

CONT = Contador("Contador Teste", "RJ-000000/O")
CHAVE = "33261100000000000191550010000000011000000010"


def perfil(regime=Regime.REAL, atividade=Atividade.VAREJO, *ben, contador=CONT, uf="RJ", **kw):
    return PerfilCliente("00000000000191", uf, regime, atividade, list(ben), contador, **kw)


def item(n=1, ncm="10063021", v=D("1000"), p_icms=D("12"), cfop="6102", orig="0", **kw):
    return ItemNota(n, f"P{n}", "Produto teste", ncm, cfop, orig, v, D("0"), "00", "",
                    p_icms, v * p_icms / 100, **kw)


def nota(*itens, d=date(2026, 11, 20), crt="3"):
    return NotaResumo(CHAVE, d, "11111111000111", "SP", crt, "00000000000191", "RJ", tuple(itens))


LISTAS = {
    Beneficio.CESTA_BASICA: ListaProdutos(Beneficio.CESTA_BASICA, {"1006": "arroz (teste)"},
                                          "Contador Teste", date(2026, 11, 1),
                                          {"10061092": "arroz integral nao e cesta (teste)"}),
    Beneficio.CONV_100_97: ListaProdutos(Beneficio.CONV_100_97, {"2309": "racao (teste)"}),
}
CESTA = BeneficioCliente(Beneficio.CESTA_BASICA)
RIOLOG = BeneficioCliente(Beneficio.RIOLOG, "TERMO-1", date(2024, 1, 1))
CONV = BeneficioCliente(Beneficio.CONV_100_97, "Conv 100/97", fim=date(2027, 12, 31))


# ---------- regras e listas
def test_aliquota_geral_rj_por_data():
    assert regra_geral(date(2024, 3, 19)).carga == D("20")
    assert regra_geral(date(2024, 3, 20)).carga == D("22")


def test_lista_prefixo_e_exclusao():
    l = LISTAS[Beneficio.CESTA_BASICA]
    assert l.contem("1006.30.21") == "arroz (teste)"
    assert l.contem("10061092") is None
    assert "integral" in l.motivo_exclusao("10061092")
    assert l.aprovada and not LISTAS[Beneficio.CONV_100_97].aprovada


def test_carregar_lista_rejeita_ncm_invalido(tmp_path):
    arq = tmp_path / "l.json"
    arq.write_text(json.dumps({"beneficio": "CESTA_BASICA", "ncms": {"1": "x"}}), encoding="utf-8")
    with pytest.raises(ValueError):
        carregar_lista(arq)


# ---------- sugestao
def test_cesta_basica_reduz_para_7_e_anula_credito_proporcional():
    s = consultor.sugerir(item(), nota(item()), perfil(Regime.REAL, Atividade.VAREJO, CESTA), LISTAS)
    assert (s.regra, s.carga_icms_saida_interna, s.confianca) == ("RJ-CESTA-7", D("7"), Confianca.ALTA)
    assert s.credito_icms_estimado == D("70.00")       # 120 x 7/12
    assert "anulacao proporcional" in s.credito_icms_entrada


def test_sem_beneficio_usa_geral_com_confianca_media():
    s = consultor.sugerir(item(), nota(item()), perfil(), LISTAS)
    assert s.carga_icms_saida_interna == D("22") and s.confianca == Confianca.MEDIA


def test_riolog_atacadista_7_na_cesta_12_nos_demais():
    p = perfil(Regime.REAL, Atividade.ATACADO_EXCLUSIVO, RIOLOG, CESTA)
    assert consultor.sugerir(item(), nota(item()), p, LISTAS).carga_icms_saida_interna == D("7")
    outro = item(ncm="84713012")
    s = consultor.sugerir(outro, nota(outro), p, LISTAS)
    assert (s.regra, s.carga_icms_saida_interna) == ("RJ-RIOLOG-12", D("12"))


def test_riolog_nao_aplica_se_nao_for_atacadista_exclusivo():
    p = perfil(Regime.REAL, Atividade.ATACADO_VAREJO, RIOLOG)
    outro = item(ncm="84713012")
    s = consultor.sugerir(outro, nota(outro), p, LISTAS)
    assert s.regra == "RJ-GERAL-20"
    assert any("RIOLOG nao aplicado" in o for o in s.observacoes)


def test_conv_100_97_isencao_lista_nao_aprovada_e_vencimento():
    p = perfil(Regime.REAL, Atividade.VAREJO, CONV)
    racao = item(ncm="23099010")
    s = consultor.sugerir(racao, nota(racao), p, LISTAS)
    assert s.tipo == "isencao" and s.carga_icms_saida_interna == 0
    assert s.confianca == Confianca.MEDIA and s.credito_icms_estimado is None
    depois = nota(racao, d=date(2028, 1, 2))
    assert consultor.sugerir(racao, depois, p, LISTAS).tipo == "geral"


def test_fornecedor_simples_credito_do_xml():
    it = item(v_cred_sn=D("31.50"))
    s = consultor.sugerir(it, nota(it, crt="1"), perfil(), LISTAS)
    assert s.credito_icms_estimado == D("31.50")


def test_cliente_simples_baixa_confianca_e_sem_regra():
    p = perfil(Regime.SIMPLES, Atividade.VAREJO, CESTA)
    r = consultor.analisar(nota(item()), p, LISTAS, {1: TributacaoAtual(D("7"))})[0]
    assert r.sugestao.confianca == Confianca.BAIXA
    assert r.validacao.status == StatusValidacao.SEM_REGRA


def test_pis_cofins_por_regime_e_2027():
    n26, n27 = nota(item()), nota(item(), d=date(2027, 2, 1))
    assert "nao cumulativo" in consultor.sugerir(item(), n26, perfil(Regime.REAL), LISTAS).pis_cofins_cbs
    assert "sem credito" in consultor.sugerir(item(), n26, perfil(Regime.PRESUMIDO), LISTAS).pis_cofins_cbs
    assert "CBS" in consultor.sugerir(item(), n27, perfil(Regime.PRESUMIDO), LISTAS).pis_cofins_cbs
    p = perfil(Regime.SIMPLES, simples_ibs_cbs_regular=True)
    assert "regime regular" in consultor.sugerir(item(), n27, p, LISTAS).pis_cofins_cbs


# ---------- validacao e guia
def test_validacao_diverge_com_valor_estimado():
    p = perfil(Regime.REAL, Atividade.VAREJO, CESTA)
    r = consultor.analisar(nota(item()), p, LISTAS, {1: TributacaoAtual(D("22"))})[0]
    assert r.validacao.status == StatusValidacao.DIVERGE
    assert r.validacao.diferenca_estimada == D("150.00")    # (22-7)% de 1000
    assert any("Reanalise" in g for g in r.guia)


def test_validacao_confere_pendente_e_cfop():
    p = perfil(Regime.REAL, Atividade.VAREJO, CESTA)
    assert consultor.analisar(nota(item()), p, LISTAS, {1: TributacaoAtual(D("7"))})[0] \
        .validacao.status == StatusValidacao.CONFERE
    assert consultor.analisar(nota(item()), p, LISTAS)[0].validacao.status == StatusValidacao.PENDENTE
    dev = item(cfop="6202")
    assert consultor.analisar(nota(dev), p, LISTAS)[0].validacao.status == StatusValidacao.NAO_SE_APLICA


# ---------- dica de venda
def test_dica_venda_rj_sp_mg_es_e_importado():
    p = perfil(Regime.REAL, Atividade.VAREJO, CESTA)
    r = consultor.analisar(nota(item()), p, LISTAS)[0]
    assert {d.uf: d.aliquota for d in r.dicas} == {"RJ": D("7"), "SP": D("12"), "MG": D("12"), "ES": D("7")}
    imp = item(orig="1")
    r2 = consultor.analisar(nota(imp), p, LISTAS)[0]
    assert all(d.aliquota == D("4") for d in r2.dicas if d.uf != "RJ")
    assert all("contador" in d.observacao for d in r2.dicas)


# ---------- perfil
def test_perfil_sem_contador_bloqueia_e_riolog_alerta():
    alertas = validar_perfil(perfil(Regime.REAL, Atividade.VAREJO, BeneficioCliente(Beneficio.RIOLOG),
                                    contador=None), date(2026, 11, 21))
    codigos = {a.codigo for a in alertas}
    assert perfil_bloqueado(alertas)
    assert {"SEM_CONTADOR", "RIOLOG_ATIVIDADE", "RIOLOG_RENUNCIA", "RIOLOG_SEM_TERMO"} <= codigos


def test_perfil_vencendo_vencido_e_uf():
    b = BeneficioCliente(Beneficio.CONV_100_97, fim=date(2026, 12, 10))
    assert "CONV_100_97_VENCENDO" in {a.codigo for a in validar_perfil(perfil(Regime.REAL, Atividade.VAREJO, b), date(2026, 11, 21))}
    assert "CONV_100_97_VENCIDO" in {a.codigo for a in validar_perfil(perfil(Regime.REAL, Atividade.VAREJO, b), date(2027, 1, 1))}
    assert perfil_bloqueado(validar_perfil(perfil(uf="SP"), date(2026, 11, 21)))


def test_carregar_perfis_modelo():
    from pathlib import Path
    arq = Path(__file__).parents[1] / "app" / "fiscal" / "exemplos" / "perfis_modelo.json"
    perfis = carregar_perfis(arq)
    p = perfis["00000000000191"]
    assert p.regime == Regime.REAL and p.contador is not None and len(p.beneficios) == 3


# ---------- XML e contrato
XML = f"""<?xml version="1.0" encoding="UTF-8"?>
<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe"><NFe><infNFe Id="NFe{CHAVE}" versao="4.00">
<ide><mod>55</mod><dhEmi>2026-11-20T10:00:00-03:00</dhEmi></ide>
<emit><CNPJ>11111111000111</CNPJ><enderEmit><UF>SP</UF></enderEmit><CRT>3</CRT></emit>
<dest><CNPJ>00000000000191</CNPJ><enderDest><UF>RJ</UF></enderDest></dest>
<det nItem="1"><prod><cProd>A1</cProd><xProd>ARROZ TESTE</xProd><NCM>10063021</NCM><CFOP>6102</CFOP>
<vProd>1000.00</vProd><vDesc>0.00</vDesc></prod><imposto><ICMS><ICMS00><orig>0</orig><CST>00</CST>
<pICMS>12.00</pICMS><vICMS>120.00</vICMS></ICMS00></ICMS></imposto></det>
</infNFe></NFe></nfeProc>""".encode()


def test_ler_nfe_e_recusa_dtd():
    n = ler_nfe(XML)
    assert n.chave == CHAVE and n.itens[0].p_icms == D("12.00") and n.interestadual
    with pytest.raises(ErroNFe):
        ler_nfe(b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "b">]><x>&a;</x>')


def test_devolutiva_contrato_e_gravacao(tmp_path):
    n = ler_nfe(XML)
    p = perfil(Regime.REAL, Atividade.VAREJO, CESTA)
    res = consultor.analisar(n, p, LISTAS, {1: TributacaoAtual(D("22"))})
    doc = devolutiva.montar(n, p, "ab" * 32, res, [])
    assert doc["aviso"] == AVISO_CONTADOR and doc["versao"] == "1.1"
    assert doc["resumo"]["diverge"] == 1 and doc["resumo"]["diferenca_estimada_total"] == 150.0
    arq = devolutiva.gravar(doc, tmp_path)
    assert json.loads(arq.read_text(encoding="utf-8"))["itens"][0]["sugestao"]["regra"] == "RJ-CESTA-7"
    doc["aviso"] = " "
    with pytest.raises(ValueError):
        devolutiva.validar_devolutiva(doc)
