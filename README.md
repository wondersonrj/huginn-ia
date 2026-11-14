# HUGINN IA — MVP NF-e
Plataforma de análise preliminar de NF-e para TOTVS WinThor. **Análise de XML com teste opcional de conexão Oracle somente leitura; sem acesso à SEFAZ.**

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
- Sem consultas SEFAZ, sem SQL livre e sem escrita no Oracle.
- Tela de teste Oracle direto, sem persistir credenciais e sem consultar tabelas WinThor. Consulte [Conexão Oracle](docs/CONEXAO_ORACLE.md).

## Próximos passos
Validar schema real do WinThor com consultas parametrizadas em usuário read-only, mapear fornecedores/produtos e integrar Distribuição DF-e com certificado e controle de NSU. Adicionar autenticação e isolamento multi-tenant antes de produção.

## Windows portátil

Pacote e instruções: [Empacotamento Windows x64](packaging/windows/README.md).
Extraia o ZIP completo e abra `INICIAR_HUGINN.bat`; a interface e a API iniciam
juntas em `http://127.0.0.1:8000`, com abertura automática do navegador.
Não exige instalação de Python, Node.js ou Oracle Client no cliente.
O teste Oracle não grava no WinThor e não persiste credenciais.

## Atualizações seguras Windows

O supervisor, o fluxo de aprovação por tag e os testes de recuperação estão
em [Atualizações Windows](docs/ATUALIZACOES_WINDOWS.md). O bootstrap de
**desenvolvimento mantém a atualização desativada** até configuração das chaves,
aprovação de release e evidência Windows. Push em `main` não faz deploy para clientes.

Procedimento de chaves, canais e aprovação: [Distribuição por GitHub Releases](docs/DISTRIBUICAO_RELEASES.md). Publicar uma release não habilita atualizações de clientes.

Preparação administrativa automatizada do canal de testes: [cliques no GitHub](docs/PREPARAR_TESTES_PELO_GITHUB.md). Chaves privadas ficam nos cofres protegidos, sem artefatos; produção e clientes permanecem desativados.

O fluxo de testes suporta administrador único: despacho manual com `PREPARAR TESTES SEM PRODUCAO`, aprovação pelo próprio dono, PR e CI obrigatórios, sem habilitar produção.

O fluxo de atualização segura de branches e revalidação dos checks está em
[docs/AUTODEV.md](docs/AUTODEV.md).
