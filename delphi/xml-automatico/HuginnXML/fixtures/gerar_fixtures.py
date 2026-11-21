"""Gera as fixtures FICTICIAS do HUGINN XML Automatico.

Todos os CNPJs, GTINs e chaves sao inventados, mas com digitos verificadores
validos, para exercitar as regras do motor. Nao ha assinatura digital: as
notas nao sao documentos fiscais reais.

Uso:  python gerar_fixtures.py   (gera os .xml nesta pasta e imprime os SHA-256)
"""
from __future__ import annotations

import hashlib
from pathlib import Path

PASTA = Path(__file__).resolve().parent
NS = "http://www.portalfiscal.inf.br/nfe"


def dv_cnpj(base12: str) -> str:
    def dig(s: str, pesos: list[int]) -> str:
        r = sum(int(a) * b for a, b in zip(s, pesos)) % 11
        return "0" if r < 2 else str(11 - r)
    d1 = dig(base12, [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
    d2 = dig(base12 + d1, [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
    return base12 + d1 + d2


def gtin13(base12: str) -> str:
    soma = sum(int(d) * (3 if i % 2 else 1) for i, d in enumerate(base12))
    return base12 + str((10 - soma % 10) % 10)


def dv_chave(c43: str) -> str:
    pesos = [2, 3, 4, 5, 6, 7, 8, 9]
    soma = sum(int(d) * pesos[i % 8] for i, d in enumerate(reversed(c43)))
    r = soma % 11
    return c43 + ("0" if r < 2 else str(11 - r))


# --- cadastro ficticio (o provedor de demonstracao usa os MESMOS valores) ---
CNPJ_FILIAL_1 = dv_cnpj("112223330001")
CNPJ_FILIAL_2 = dv_cnpj("112223330002")
CNPJ_FILIAL_AMBIGUA = dv_cnpj("112223330003")   # filiais 3 e 4
CNPJ_OUTRA_EMPRESA = dv_cnpj("998887770001")
CNPJ_FORNEC_101 = dv_cnpj("445556660001")
CNPJ_FORNEC_DUP = dv_cnpj("445556660002")       # fornecedores 102 e 103
CNPJ_FORNEC_AUSENTE = dv_cnpj("778889990001")

G = {k: gtin13("200000" + k + "00") for k in ("1001", "1003", "1006", "1007", "1008", "9999")}
GTIN_DV_ERRADO = G["1001"][:-1] + str((int(G["1001"][-1]) + 1) % 10)


def chave(cnpj: str, nnf: int, serie: int = 1, cnf: int = 12345678) -> str:
    c43 = f"35{2611}{cnpj}55{serie:03d}{nnf:09d}1{cnf:08d}"
    return dv_chave(c43)


def item(n, cprod, cean, xprod, ncm, ucom, q, vun, cest="", vdesc=0.0):
    vprod = round(q * vun, 2)
    vicms = round(vprod * 0.18, 2)
    cest_xml = f"<CEST>{cest}</CEST>" if cest else ""
    desc_xml = f"<vDesc>{vdesc:.2f}</vDesc>" if vdesc else ""
    xml = (
        f'<det nItem="{n}"><prod><cProd>{cprod}</cProd><cEAN>{cean}</cEAN>'
        f"<xProd>{xprod}</xProd><NCM>{ncm}</NCM>{cest_xml}<CFOP>5102</CFOP>"
        f"<uCom>{ucom}</uCom><qCom>{q:.4f}</qCom><vUnCom>{vun:.10f}</vUnCom>"
        f"<vProd>{vprod:.2f}</vProd><cEANTrib>{cean}</cEANTrib><uTrib>{ucom}</uTrib>"
        f"<qTrib>{q:.4f}</qTrib><vUnTrib>{vun:.10f}</vUnTrib>{desc_xml}<indTot>1</indTot></prod>"
        f"<imposto><ICMS><ICMS00><orig>0</orig><CST>00</CST><modBC>3</modBC>"
        f"<vBC>{vprod:.2f}</vBC><pICMS>18.00</pICMS><vICMS>{vicms:.2f}</vICMS></ICMS00></ICMS>"
        f"</imposto></det>"
    )
    return xml, vprod, vicms


def nota(nome_arq, emit_cnpj, emit_nome, dest_cnpj, nnf, itens, *, ch=None, extra=""):
    ch = ch or chave(emit_cnpj, nnf)
    dets, tot, icms = [], 0.0, 0.0
    for it in itens:
        x, v, i = item(*it[:8], **(it[8] if len(it) > 8 else {}))
        dets.append(x)
        tot += v
        icms += i
    xml = (
        f'<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<nfeProc xmlns="{NS}" versao="4.00"><NFe xmlns="{NS}">'
        f'<infNFe Id="NFe{ch}" versao="4.00"><ide><cUF>35</cUF><cNF>12345678</cNF>'
        f"<natOp>VENDA DE MERCADORIA</natOp><mod>55</mod><serie>1</serie><nNF>{nnf}</nNF>"
        f"<dhEmi>2026-11-20T10:15:00-03:00</dhEmi><tpNF>1</tpNF><idDest>1</idDest>"
        f"<tpAmb>2</tpAmb><finNFe>1</finNFe></ide>"
        f"<emit><CNPJ>{emit_cnpj}</CNPJ><xNome>{emit_nome}</xNome><IE>111111111111</IE>"
        f"<enderEmit><UF>SP</UF></enderEmit><CRT>3</CRT></emit>"
        f"<dest><CNPJ>{dest_cnpj}</CNPJ><xNome>HUGINN DEMO COMERCIO LTDA</xNome>"
        f"<IE>222222222222</IE></dest>"
        + "".join(dets)
        + f"<total><ICMSTot><vBC>{tot:.2f}</vBC><vICMS>{icms:.2f}</vICMS><vST>0.00</vST>"
        f"<vProd>{tot:.2f}</vProd><vIPI>0.00</vIPI><vNF>{tot:.2f}</vNF></ICMSTot></total>"
        f"</infNFe></NFe>"
        f'<protNFe versao="4.00"><infProt><tpAmb>2</tpAmb><chNFe>{ch}</chNFe>'
        f"<dhRecbto>2026-11-20T10:16:00-03:00</dhRecbto><nProt>135260000000001</nProt>"
        f"<cStat>100</cStat><xMotivo>Autorizado o uso da NF-e</xMotivo></infProt></protNFe>"
        f"</nfeProc>{extra}\n"
    )
    (PASTA / nome_arq).write_bytes(xml.encode("utf-8"))
    return ch, xml


F101 = "FORNECEDOR DEMO ALIMENTOS LTDA"
ITENS_MISTA = [
    (1, "F-ARROZ", G["1001"], "ARROZ DEMO TIPO 1 5KG", "10063021", "UN", 10, 25.90),
    (2, "FAB-200", "SEM GTIN", "FEIJAO DEMO CARIOCA 1KG", "07133319", "UN", 20, 8.40),
    (3, "FAB-300", G["1003"], "MILHO DEMO 500G", "10059010", "UN", 12, 4.10),
    (4, "FAB-999", G["9999"], "PRODUTO NOVO DEMO 1L", "22029900", "UN", 6, 9.90),
    (5, "FAB-500", "SEM GTIN", "OLEO DEMO SOJA 900ML CX20", "15079011", "CX", 2, 124.00),
    (6, "F-ACUCAR", G["1006"], "ACUCAR DEMO 1KG FARDO", "17019900", "FD", 5, 40.00),
    (7, "FAB-700", G["1007"], "CAFE DEMO 500G", "09012100", "UN", 8, 18.00, {"cest": "1709600"}),
    (8, "FAB-800", G["1008"], "MACARRAO DEMO 500G", "19023000", "UN", 30, 3.55),
    (9, "FAB-900", GTIN_DV_ERRADO, "BISCOITO DEMO 200G", "19053100", "UN", 24, 2.30),
]

saidas = {}
saidas["nfe_valida_mista.xml"], xml_mista = nota(
    "nfe_valida_mista.xml", CNPJ_FORNEC_101, F101, CNPJ_FILIAL_1, 1001, ITENS_MISTA)

# Mesma chave, bytes diferentes (comentario ao final): deve gerar conflito de hash.
ch_mista = saidas["nfe_valida_mista.xml"]
nota("nfe_mesma_chave_bytes_diferentes.xml", CNPJ_FORNEC_101, F101, CNPJ_FILIAL_1, 1001,
     ITENS_MISTA, ch=ch_mista, extra="<!-- copia alterada -->")

saidas["nfe_fornecedor_ausente.xml"], _ = nota(
    "nfe_fornecedor_ausente.xml", CNPJ_FORNEC_AUSENTE, "FORNECEDOR NOVO DEMO SA",
    CNPJ_FILIAL_1, 2001, [ITENS_MISTA[0], ITENS_MISTA[1]])
saidas["nfe_filial_ambigua.xml"], _ = nota(
    "nfe_filial_ambigua.xml", CNPJ_FORNEC_101, F101, CNPJ_FILIAL_AMBIGUA, 3001, [ITENS_MISTA[0]])
saidas["nfe_ja_lancada.xml"], _ = nota(
    "nfe_ja_lancada.xml", CNPJ_FORNEC_101, F101, CNPJ_FILIAL_1, 4001, [ITENS_MISTA[0]])
saidas["nfe_fornecedor_duplicado.xml"], _ = nota(
    "nfe_fornecedor_duplicado.xml", CNPJ_FORNEC_DUP, "FORNECEDOR DUPLICADO DEMO",
    CNPJ_FILIAL_1, 5001, [ITENS_MISTA[0]])
saidas["nfe_destinatario_outra_empresa.xml"], _ = nota(
    "nfe_destinatario_outra_empresa.xml", CNPJ_FORNEC_101, F101, CNPJ_OUTRA_EMPRESA, 6001,
    [ITENS_MISTA[0]])
saidas["nfe_filial_2.xml"], _ = nota(
    "nfe_filial_2.xml", CNPJ_FORNEC_101, F101, CNPJ_FILIAL_2, 7001, [ITENS_MISTA[0]])

# Chave com DV errado.
ch_ok = chave(CNPJ_FORNEC_101, 8001)
ch_errada = ch_ok[:-1] + str((int(ch_ok[-1]) + 1) % 10)
nota("nfe_chave_dv_invalida.xml", CNPJ_FORNEC_101, F101, CNPJ_FILIAL_1, 8001,
     [ITENS_MISTA[0]], ch=ch_errada)

(PASTA / "nfe_invalida.xml").write_bytes(xml_mista[: len(xml_mista) // 2].encode("utf-8"))
(PASTA / "nfe_com_dtd.xml").write_bytes(
    b'<?xml version="1.0"?>\n<!DOCTYPE nfeProc [<!ENTITY x SYSTEM "file:///c:/windows/win.ini">]>\n'
    b'<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe">&x;</nfeProc>\n')
(PASTA / "evento_cancelamento.xml").write_bytes((
    f'<?xml version="1.0" encoding="UTF-8"?>\n<procEventoNFe xmlns="{NS}" versao="1.00">'
    f'<evento versao="1.00"><infEvento Id="ID110111{ch_mista}01"><chNFe>{ch_mista}</chNFe>'
    f"<tpEvento>110111</tpEvento><detEvento versao=\"1.00\"><descEvento>Cancelamento</descEvento>"
    f"</detEvento></infEvento></evento></procEventoNFe>\n").encode("utf-8"))

if __name__ == "__main__":
    print("CNPJ_FILIAL_1", CNPJ_FILIAL_1)
    print("CNPJ_FILIAL_2", CNPJ_FILIAL_2)
    print("CNPJ_FILIAL_AMBIGUA", CNPJ_FILIAL_AMBIGUA)
    print("CNPJ_OUTRA_EMPRESA", CNPJ_OUTRA_EMPRESA)
    print("CNPJ_FORNEC_101", CNPJ_FORNEC_101)
    print("CNPJ_FORNEC_DUP", CNPJ_FORNEC_DUP)
    print("CNPJ_FORNEC_AUSENTE", CNPJ_FORNEC_AUSENTE)
    for k, v in G.items():
        print("GTIN", k, v)
    print("GTIN_DV_ERRADO", GTIN_DV_ERRADO)
    for nome, ch in saidas.items():
        print("CHAVE", nome, ch)
    print("CHAVE_DV_ERRADA", ch_errada)
    for arq in sorted(PASTA.glob("*.xml")):
        print("SHA256", arq.name, hashlib.sha256(arq.read_bytes()).hexdigest())
