# HUGINN IA — MVP NF-e
Plataforma de análise preliminar de NF-e para TOTVS WinThor. **Demo sem acesso ao Oracle ou à SEFAZ.**

## Iniciar
Requer Python 3.12+ e Node 20+.

Backend (na raiz):
```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --reload --port 8000
```
Frontend (outro terminal):
```powershell
cd frontend
npm install
npm run dev
```
Acesse http://localhost:5173. Documentação API: http://localhost:8000/docs.

## Escopo
- Importação local de XML NF-e (nfeProc ou NFe) e análise estrutural.
- Identificação de emitente, itens, NCM, CFOP e valores; sinalização de cadastro pendente.
- Dados de demonstração identificados. **Não há comparação real com WinThor.**
- Sem consultas SEFAZ, sem credenciais, sem SQL livre e sem escrita no Oracle.

## Próximos passos
Validar schema real do WinThor com consultas parametrizadas em usuário read-only, mapear fornecedores/produtos e integrar Distribuição DF-e com certificado e controle de NSU. Adicionar autenticação e isolamento multi-tenant antes de produção.
