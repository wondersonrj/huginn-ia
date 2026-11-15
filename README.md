# HUGINN IA — consultas WinThor e análise NF-e
Plataforma de análise preliminar de NF-e para TOTVS WinThor. **Consulta de produtos e fornecedores em Oracle somente leitura (ou simulação identificada), análise de XML e nenhuma integração SEFAZ.**

## Iniciar
Requer Python 3.12+ e Node 20+. Para as consultas/diagnósticos Oracle, configure
o token local antes de iniciar; siga [a configuração segura](docs/WINTHOR_MVP.md).

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
- Consultas parametrizadas de produtos/fornecedores com schema validado e token local. Modo demo identificado, sem banco. **Não há conciliação automática de XML com WinThor.**
- Sem consultas SEFAZ, sem SQL livre e sem escrita no Oracle.
- Tela de teste Oracle direto, sem persistir credenciais e sem consultar tabelas WinThor. Consulte [Conexão Oracle](docs/CONEXAO_ORACLE.md).

## Próximos passos
Homologar as consultas com um schema Oracle autorizado, implementar conciliação de itens e integrar Distribuição DF-e com certificado e controle de NSU. Adicionar autenticação e isolamento multi-tenant antes de produção.

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
O [manual mestre da fábrica](docs/MANUAL_MESTRE.md) reúne os limites de autoridade
e o procedimento para workflows que aguardam aprovação humana.
A fase 2 usa [handoff manual seguro ao Codex](docs/AUTODEV.md#fase-2--issue-14-fila-segura-para-codex),
com [histórico e guias da fábrica](docs/FABRICA_APLICACOES/HISTORICO_COMPLETO.md).

## Consultar produtos e fornecedores

Configure um token local (32+ caracteres), mantenha HUGINN_WINTHOR_MODE=demo para
a demonstração e informe esse token em **Consultas WinThor**. O modo Oracle usa
credenciais somente no servidor e schema validado antes da leitura.
[Instalação Windows, configuração segura e limitações](docs/WINTHOR_MVP.md).
Não houve conexão Oracle real nesta entrega; o aceite automático usa dados sintéticos.

## Conexões salvas no Windows

O [gerenciador local de conexões](docs/CONEXOES_SALVAS.md) cadastra, edita, testa,
seleciona e exclui perfis TESTE/PRODUÇÃO com senha protegida por DPAPI no usuário
Windows. Após reiniciar, selecione a conexão salva sem reentrar a senha Oracle.
A seleção é explícita e as consultas continuam somente leitura.

## Instalador Windows de homologação (#23)

[Instalação guiada, abertura com um clique e suporte](docs/INSTALACAO_WINDOWS.md):
HUGINN-IA-Setup.exe por usuário, runtime incluído, token DPAPI automático e
configuração Oracle na interface. PR incremental sobre main após o squash de #22, sem merge
ou release automática; assinatura Authenticode ainda indisponível.

## Atualizar uma instalação existente (#27)

O Setup encontra a instalação do mesmo usuário e substitui os arquivos no mesmo
diretório, preservando perfis/token DPAPI e configurações. Não desinstale antes.
[Backup, instância ativa, rollback, portáteis e recuperação](docs/INSTALACAO_WINDOWS.md#atualizar-instalações-anteriores--27--setup-031).
Sem reiniciar o Windows, merge ou release automática.

## Interface empresarial 0.4.0

Navegação lateral, dashboard, NF-e, produtos e fornecedores separados, única
Central de Conexões e catálogo de funcionalidades com relatórios sanitizados.
[Guia do operador e documentação técnica](docs/INTERFACE_EMPRESARIAL.md) ·
[Imagens antes/depois](docs/screenshots/issue-29/README.md).
