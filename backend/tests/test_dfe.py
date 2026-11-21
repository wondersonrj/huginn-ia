"""Captura DF-e (NFeDistribuicaoDFe) com respostas simuladas da SEFAZ. Sem rede."""
import base64
import gzip
from datetime import datetime, timedelta

import pytest

from app.dfe.armazenamento import Armazenamento
from app.dfe.distribuicao import (ErroDistribuicao, envelope_soap, ler_retorno, montar_cons_chave,
                                  montar_dist_nsu, normalizar_cnpj)
from app.dfe.estado import EstadoCNPJ, RepositorioEstado
from app.dfe.sincronizador import sincronizar

CNPJ = "11222333000181"
CHAVE_A = "33261144555666000181550010000010011123456789"
CHAVE_B = "33261144555666000181550010000010021123456780"
NS = 'xmlns="http://www.portalfiscal.inf.br/nfe"'

PROC = (f'<?xml version="1.0" encoding="UTF-8"?><nfeProc {NS} versao="4.00"><NFe><infNFe Id="NFe{CHAVE_A}" versao="4.00">'
        '<ide><dhEmi>2026-11-20T10:00:00-03:00</dhEmi></ide><emit><CNPJ>44555666000181</CNPJ><xNome>FORNECEDOR DEMO</xNome></emit>'
        '<total><ICMSTot><vNF>150.00</vNF></ICMSTot></total></infNFe></NFe></nfeProc>').encode()
RES = (f'<resNFe {NS} versao="1.01"><chNFe>{CHAVE_B}</chNFe><CNPJ>44555666000181</CNPJ><xNome>FORNECEDOR DEMO</xNome>'
       '<dhEmi>2026-11-20T11:00:00-03:00</dhEmi><vNF>99.90</vNF><cSitNFe>1</cSitNFe></resNFe>').encode()
EVT = (f'<resEvento {NS} versao="1.01"><chNFe>{CHAVE_A}</chNFe><tpEvento>110111</tpEvento></resEvento>').encode()


def doczip(nsu, schema, xml):
    return f'<docZip NSU="{nsu:015d}" schema="{schema}">{base64.b64encode(gzip.compress(xml)).decode()}</docZip>'


def resposta(c_stat, motivo, ult, maxi, docs=()):
    lote = f"<loteDistDFeInt>{''.join(docs)}</loteDistDFeInt>" if docs else ""
    ret = (f'<retDistDFeInt {NS} versao="1.01"><tpAmb>1</tpAmb><verAplic>T</verAplic><cStat>{c_stat}</cStat>'
           f"<xMotivo>{motivo}</xMotivo><dhResp>2026-11-21T20:00:00-03:00</dhResp>"
           f"<ultNSU>{ult:015d}</ultNSU><maxNSU>{maxi:015d}</maxNSU>{lote}</retDistDFeInt>")
    return ('<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope"><soap:Body>'
            '<nfeDistDFeInteresseResponse xmlns="http://www.portalfiscal.inf.br/nfe/wsdl/NFeDistribuicaoDFe">'
            f"<nfeDistDFeInteresseResult>{ret}</nfeDistDFeInteresseResult></nfeDistDFeInteresseResponse>"
            "</soap:Body></soap:Envelope>").encode()


class FakeSefaz:
    def __init__(self, respostas):
        self.respostas = list(respostas)
        self.pedidos = []

    def enviar(self, url, envelope, action=None):
        self.pedidos.append((url, envelope.decode()))
        if not self.respostas:
            raise AssertionError("consulta a mais na SEFAZ")
        return self.respostas.pop(0)


class Relogio:
    def __init__(self):
        self.t = datetime(2026, 11, 21, 20, 0, 0)

    def __call__(self):
        return self.t


def test_montagem_dist_nsu_e_envelope():
    xml = montar_dist_nsu(1, "RJ", "11.222.333/0001-81", 0)
    assert "<cUFAutor>33</cUFAutor>" in xml and "<CNPJ>11222333000181</CNPJ>" in xml
    assert "<ultNSU>000000000000000</ultNSU>" in xml
    env = envelope_soap(xml).decode()
    assert "nfeDistDFeInteresse" in env and "nfeDadosMsg" in env and "soap12:Envelope" in env


def test_validacoes_de_entrada():
    with pytest.raises(ErroDistribuicao):
        montar_dist_nsu(1, "XX", CNPJ, 0)
    with pytest.raises(ErroDistribuicao):
        montar_cons_chave(1, "RJ", CNPJ, "123")
    with pytest.raises(ErroDistribuicao):
        normalizar_cnpj("<script>")
    assert normalizar_cnpj("12.abc.345/0001-95") == "12ABC3450001" + "95"   # CNPJ alfanumerico


def test_le_retorno_e_classifica_documentos():
    r = ler_retorno(resposta(138, "Documento localizado", 3, 3,
                             [doczip(1, "procNFe_v4.00.xsd", PROC), doczip(2, "resNFe_v1.01.xsd", RES),
                              doczip(3, "resEvento_1.01.xsd", EVT)]))
    assert (r.c_stat, r.ult_nsu, r.max_nsu) == ("138", "000000000000003", "000000000000003")
    tipos = [(d.tipo, d.chave) for d in r.documentos]
    assert tipos == [("procNFe", CHAVE_A), ("resNFe", CHAVE_B), ("resEvento", CHAVE_A)]
    assert r.documentos[0].conteudo == PROC            # bytes preservados
    assert r.documentos[1].valor == "99.90" and r.documentos[1].situacao == "1"


def test_rejeita_xml_com_dtd_no_documento():
    perigoso = b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY e SYSTEM "file:///etc/passwd">]><resNFe>&e;</resNFe>'
    with pytest.raises(ErroDistribuicao):
        ler_retorno(resposta(138, "ok", 1, 1, [doczip(1, "resNFe_v1.01.xsd", perigoso)]))


def test_ciclo_baixa_grava_e_espera_uma_hora(tmp_path):
    relogio = Relogio()
    repo, arm = RepositorioEstado(tmp_path / "estado.json"), Armazenamento(tmp_path / "dfe")
    sefaz = FakeSefaz([
        resposta(138, "Documento localizado", 2, 3, [doczip(1, "procNFe_v4.00.xsd", PROC), doczip(2, "resNFe_v1.01.xsd", RES)]),
        resposta(138, "Documento localizado", 3, 3, [doczip(3, "resEvento_1.01.xsd", EVT)]),
    ])
    res = sincronizar(CNPJ, "RJ", 1, sefaz, repo, arm, agora=relogio)
    assert (res.lotes, res.completos, res.resumos, res.eventos) == (2, 1, 1, 1)
    assert res.ult_nsu == "000000000000003" and res.proxima == "2026-11-21T21:00:00"
    assert "<ultNSU>000000000000002</ultNSU>" in sefaz.pedidos[1][1]       # segue o ultNSU devolvido
    assert (tmp_path / "dfe" / "Entrada" / f"{CHAVE_A}-procNFe.xml").read_bytes() == PROC
    assert [p["chave"] for p in arm.resumos_pendentes()] == [CHAVE_B]
    # Dentro da hora: nao consulta de novo (FakeSefaz falharia se consultasse).
    relogio.t += timedelta(minutes=59)
    res2 = sincronizar(CNPJ, "RJ", 1, sefaz, repo, arm, agora=relogio)
    assert not res2.consultou and "Aguardar" in res2.mensagem


def test_137_e_656_bloqueiam_por_uma_hora(tmp_path):
    relogio = Relogio()
    repo, arm = RepositorioEstado(tmp_path / "e.json"), Armazenamento(tmp_path / "d")
    res = sincronizar(CNPJ, "RJ", 1, FakeSefaz([resposta(137, "Nenhum documento localizado", 0, 0)]), repo, arm, agora=relogio)
    assert res.c_stat == "137" and res.proxima == "2026-11-21T21:00:00"
    relogio.t += timedelta(hours=1, seconds=1)
    res = sincronizar(CNPJ, "RJ", 1, FakeSefaz([resposta(656, "Consumo Indevido", 5, 9)]), repo, arm, agora=relogio)
    assert res.c_stat == "656" and repo.obter(CNPJ).ult_nsu == "000000000000005"
    assert res.proxima == (relogio.t + timedelta(hours=1)).isoformat(timespec="seconds")


def test_reprocessar_mesmo_documento_e_idempotente(tmp_path):
    arm = Armazenamento(tmp_path)
    doc = ler_retorno(resposta(138, "ok", 1, 1, [doczip(1, "procNFe_v4.00.xsd", PROC)])).documentos[0]
    assert arm.gravar(doc, CNPJ)[1] == "novo"
    assert arm.gravar(doc, CNPJ)[1] == "igual"
    doc.conteudo = PROC + b"\n"
    caminho, situacao = arm.gravar(doc, CNPJ)
    assert situacao == "conflito" and caminho.name != f"{CHAVE_A}-procNFe.xml"


def test_limite_local_de_consultas_por_hora():
    e = EstadoCNPJ(cnpj=CNPJ)
    agora = datetime(2026, 11, 21, 20, 0)
    for i in range(15):
        e.registrar_consulta(agora + timedelta(seconds=i))
    assert e.pode_consultar(agora + timedelta(minutes=1))[0] is False
    assert e.pode_consultar(agora + timedelta(hours=1, minutes=1))[0] is True


def _pfx_teste(cn, dias=30, senha=b"senha-teste"):
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives.serialization import BestAvailableEncryption, pkcs12
    from cryptography.x509.oid import NameOID
    chave = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    nome = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)])
    from datetime import timezone
    agora = datetime.now(timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(nome).issuer_name(nome).public_key(chave.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(agora - timedelta(days=1))
            .not_valid_after(agora + timedelta(days=dias)).sign(chave, hashes.SHA256()))
    return pkcs12.serialize_key_and_certificates(b"t", chave, cert, None, BestAvailableEncryption(senha))


def test_certificado_a1_carrega_e_identifica_cnpj():
    from app.dfe.transporte import contexto_tls, info_certificado, ler_certificado
    pfx = _pfx_teste("EMPRESA DEMO LTDA:11222333000181")
    _, cert, _ = ler_certificado(pfx, "senha-teste")
    assert info_certificado(cert).cnpj == "11222333000181"
    assert contexto_tls(pfx, "senha-teste") is not None
    with pytest.raises(ErroDistribuicao):
        ler_certificado(pfx, "senha-errada")


def test_certificado_vencido_e_recusado():
    from app.dfe.transporte import contexto_tls
    with pytest.raises(ErroDistribuicao):
        contexto_tls(_pfx_teste("EMPRESA DEMO LTDA:11222333000181", dias=-1), "senha-teste")


def test_transporte_so_aceita_endereco_da_sefaz():
    import ssl
    from app.dfe.transporte import TransporteSefaz
    with pytest.raises(ErroDistribuicao):
        TransporteSefaz(ssl.create_default_context()).enviar("https://exemplo.com/x", b"<x/>")


def test_evento_ciencia_assinado_confere():
    import base64 as b64
    import hashlib
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import padding
    from lxml import etree
    from app.dfe.manifestacao import (NS_DSIG, assinar_evento, envelope_evento, ler_retorno_evento,
                                      montar_evento_ciencia)
    from app.dfe.transporte import ler_certificado
    chave_priv, cert, _ = ler_certificado(_pfx_teste("EMPRESA DEMO LTDA:11222333000181"), "senha-teste")
    xml = assinar_evento(montar_evento_ciencia(1, CNPJ, CHAVE_A, datetime(2026, 11, 21, 20, 10)), chave_priv, cert)
    ev = etree.fromstring(xml.encode())
    ns = {"n": "http://www.portalfiscal.inf.br/nfe", "d": NS_DSIG}
    inf = ev.find("n:infEvento", ns)
    assert inf.get("Id") == f"ID210210{CHAVE_A}01"
    assert inf.findtext("n:dhEvento", namespaces=ns) == "2026-11-21T20:10:00-03:00"
    assert inf.findtext("n:detEvento/n:descEvento", namespaces=ns) == "Ciencia da Operacao"
    # Digest do infEvento (C14N inclusiva) e assinatura RSA-SHA1 do SignedInfo conferem.
    assert ev.findtext("d:Signature/d:SignedInfo/d:Reference/d:DigestValue", namespaces=ns) == \
        b64.b64encode(hashlib.sha1(etree.tostring(inf, method="c14n")).digest()).decode()
    si = ev.find("d:Signature/d:SignedInfo", ns)
    cert.public_key().verify(b64.b64decode(ev.findtext("d:Signature/d:SignatureValue", namespaces=ns)),
                             etree.tostring(si, method="c14n"), padding.PKCS1v15(), hashes.SHA1())
    env = envelope_evento([xml], 7).decode()
    assert "<idLote>7</idLote>" in env and "NFeRecepcaoEvento4" in env
    ret = ('<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope"><soap:Body>'
           f'<retEnvEvento {NS} versao="1.00"><idLote>7</idLote><tpAmb>1</tpAmb><cOrgao>91</cOrgao><cStat>128</cStat>'
           f'<xMotivo>Lote de evento processado</xMotivo><retEvento versao="1.00"><infEvento><tpAmb>1</tpAmb>'
           f'<cOrgao>91</cOrgao><cStat>135</cStat><xMotivo>Evento registrado e vinculado a NF-e</xMotivo>'
           f'<chNFe>{CHAVE_A}</chNFe><tpEvento>210210</tpEvento><nProt>891260000000001</nProt></infEvento>'
           '</retEvento></retEnvEvento></soap:Body></soap:Envelope>').encode()
    c_stat, _, itens = ler_retorno_evento(ret)
    assert c_stat == "128" and itens[0].ok and itens[0].protocolo == "891260000000001"


def test_ciencia_para_resumos_pendentes_sem_reenvio(tmp_path):
    from app.dfe.ciencia import manifestar_pendentes
    from app.dfe.transporte import ler_certificado
    chave_priv, cert, _ = ler_certificado(_pfx_teste("EMPRESA DEMO LTDA:11222333000181"), "senha-teste")
    arm = Armazenamento(tmp_path)
    for d in ler_retorno(resposta(138, "ok", 1, 1, [doczip(1, "resNFe_v1.01.xsd", RES)])).documentos:
        arm.gravar(d, CNPJ)
    ret = ('<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope"><soap:Body>'
           f'<retEnvEvento {NS} versao="1.00"><cStat>128</cStat><xMotivo>Lote processado</xMotivo>'
           f'<retEvento versao="1.00"><infEvento><cStat>135</cStat><xMotivo>Registrado</xMotivo><chNFe>{CHAVE_B}</chNFe>'
           '<nProt>891260000000002</nProt></infEvento></retEvento></retEnvEvento></soap:Body></soap:Envelope>').encode()
    sefaz = FakeSefaz([ret])
    feito = manifestar_pendentes(CNPJ, 1, sefaz, chave_priv, cert, arm, agora=Relogio())
    assert feito[0]["ok"] and feito[0]["chave"] == CHAVE_B and "NFeRecepcaoEvento4" in sefaz.pedidos[0][0]
    assert manifestar_pendentes(CNPJ, 1, sefaz, chave_priv, cert, arm, agora=Relogio()) == []   # nao reenvia


def test_filiais_da_mesma_raiz():
    from app.dfe.filiais import filiais_da_raiz

    class Cur:
        def execute(self, sql, binds):
            self.sql, self.binds = sql, binds

        def fetchall(self):
            return [("1", "MATRIZ", "11.222.333/0001-81", "RJ"), ("2", "FILIAL", "11222333000262", "SP"),
                    ("3", "DUPLICADA", "11222333000262", "SP"), ("4", "LIXO", "123", "RJ")]
    c = Cur()
    f = filiais_da_raiz(c, "winthor", "11222333000181")
    assert c.binds == {"raiz": "11222333"} and '"WINTHOR"."PCFILIAL"' in c.sql
    assert [(x["codigo"], x["cnpj"], x["uf"]) for x in f] == [("1", "11222333000181", "RJ"), ("2", "11222333000262", "SP")]
    with pytest.raises(ErroDistribuicao):
        filiais_da_raiz(c, "x; drop", "11222333000181")
