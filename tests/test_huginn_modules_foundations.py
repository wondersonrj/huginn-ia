import io
import unittest
import zipfile
from huginn_modules.revisor.audit import valid_cnpj, audit_clients, audit_products
from huginn_modules.revisor.sql_catalog import build_selects, build_product_query
from huginn_modules.xml_automatico.package import build_package, verify_package

class TestRevisor(unittest.TestCase):
    def test_cnpj(self):
        self.assertTrue(valid_cnpj("11.222.333/0001-81"))
        self.assertFalse(valid_cnpj("11.222.333/0001-82"))
    def test_duplicate_client(self):
        rows = [{"codcli":1,"cgcent":"11.222.333/0001-81","codusur1":3},
                {"codcli":2,"cgcent":"11.222.333/0001-81","codusur1":4}]
        self.assertEqual(sum(x.rule=="cnpj_duplicado" for x in audit_clients(rows)),2)
    def test_missing_price_cost(self):
        result = audit_products([{"codprod":1}],[],[],[])
        self.assertEqual({x.rule for x in result},{"preco_nao_localizado","custo_nao_localizado"})
    def test_catalog_blocks_missing_fields(self):
        with self.assertRaises(ValueError):
            build_selects({"PCCLIENT":{"CODCLI"}})
        with self.assertRaises(ValueError):
            build_product_query({})

class TestXML(unittest.TestCase):
    def test_roundtrip(self):
        xml=b'<NFe xmlns="http://www.portalfiscal.inf.br/nfe"/>'
        data=build_package(xml,{"status":"pendente"})
        self.assertEqual(verify_package(data)["schema"],"huginn-xml-1")
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            self.assertEqual(z.read("nota.xml"),xml)
    def test_reject_non_nfe(self):
        with self.assertRaises(ValueError):
            build_package(b"<html/>",{})
    def test_reject_dtd(self):
        with self.assertRaises(ValueError):
            build_package(b'<!DOCTYPE NFe><NFe/>',{})

if __name__=="__main__":
    unittest.main()
