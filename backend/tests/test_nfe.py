from app.main import parse_nfe
import pytest

XML = b"""<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe"><NFe><infNFe Id="NFe123"><ide><nNF>12</nNF><serie>1</serie></ide><emit><CNPJ>12345678000190</CNPJ><xNome>Fornecedor Demo</xNome></emit><det nItem="1"><prod><cProd>ABC</cProd><xProd>Produto Demo</xProd><NCM>12345678</NCM><CFOP>5102</CFOP><qCom>2</qCom><vUnCom>10.50</vUnCom><vProd>21.00</vProd></prod></det></infNFe></NFe></nfeProc>"""

def test_parse():
    n = parse_nfe(XML)
    assert n["numero"] == "12"
    assert n["emitente"]["cnpj"] == "12345678000190"
    assert n["itens"][0]["valor_total"] == "21.00"

def test_invalid():
    with pytest.raises(ValueError):
        parse_nfe(b"<broken>")
