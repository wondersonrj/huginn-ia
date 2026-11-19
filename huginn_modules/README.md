# HUGINN — fundações XML Automático e Revisor

Implementação inicial isolada, sem acoplamento ao backend existente. **Não é aplicação completa**.

## Revisor
`revisor/audit.py` implementa regras determinísticas de CNPJ, RCA, CEP, duplicidade, carteira, fornecedor também cliente, preço/custo e embalagem. A importação de dados de WinThor exige **mapeamento homologado dos campos e consultas Oracle**. Os nomes no payload são contratos propostos, não garantia de colunas na instalação. Resultados são somente alertas. Sem SQL de alteração.

## XML
`xml_automatico/package.py` monta ZIP com XML original byte a byte, análise e hashes SHA-256. A verificação é de integridade interna, **não é validação de assinatura digital, chave de acesso ou autenticidade fiscal**. O consumo no Delphi e a integração nativa WinThor permanecem pendentes.

## Próximas implementações
- Exportador Delphi 12/UniDAC read-only, SQL por versão e filiais.
- API FastAPI de upload com autenticação, isolamento de tenant, limites e armazenamento seguro.
- Interface React HUGINN com resultados e evidências.
- Consultas externas oficiais com tratamento de indisponibilidade.
- Testes com dados sintéticos, CI, e homologação Oracle real.
- NF-e DF-e NSU, certificado A1, controle de manifestação e fluxo fiscal autorizado.

Nenhum UPDATE/INSERT/DELETE em cadastros WinThor; nenhum merge ou deploy automático.
