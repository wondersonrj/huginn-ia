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

## Linux / ambiente na nuvem

Na raiz do repositório:
```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements.txt
.venv/bin/python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000
```
Em outro terminal:
```bash
cd frontend
npm ci
npm run dev
```
Se o cache padrão do npm não for gravável, acrescente `--cache /workspace/.npm-cache` ao `npm ci`.

## Validação

Na raiz, execute `.venv/bin/python -m pytest -q`. Os testes usam XML sintético e a API em memória, sem acesso ao WinThor, Oracle ou SEFAZ. A importação rejeita valores numéricos inválidos ou não finitos com HTTP 422.

Em `frontend`, execute `npm run build` para verificar TypeScript e gerar o build de produção. Para conferir a integração, mantenha os dois serviços acima ativos, importe um XML de demonstração pela interface e confirme os itens exibidos. Um XML inválido deve mostrar uma mensagem de erro e permitir novo envio.

## Escopo
- Importação local de XML NF-e (nfeProc ou NFe) e análise estrutural.
- Identificação de emitente, itens, NCM, CFOP e valores; sinalização de cadastro pendente.
- Dados de demonstração identificados. **Não há comparação real com WinThor.**
- Sem consultas SEFAZ, sem credenciais, sem SQL livre e sem escrita no Oracle.

## Próximos passos
Validar schema real do WinThor com consultas parametrizadas em usuário read-only, mapear fornecedores/produtos e integrar Distribuição DF-e com certificado e controle de NSU. Adicionar autenticação e isolamento multi-tenant antes de produção.
