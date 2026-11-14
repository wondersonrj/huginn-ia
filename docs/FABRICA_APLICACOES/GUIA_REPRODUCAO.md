# Reprodução segura da fábrica

## Pré-requisitos e ordem

1. Criar repositório com main e conta GitHub protegida. Revisar regras de PR,
   proibição de force-push/exclusão e required portable do GitHub Actions. Em
   fábrica existente, consultar e preservar rulesets: não executar migração
   administrativa só para fazer CI passar.
2. Instalar backend Python 3.12 e frontend Node 20/22, fixar dependências e
   executar pytest/build/audit. Criar quality gates com token somente de leitura.
3. Preparar empacotamento Windows e CI portable, sem publicação. Validar runtime
   real, smoke, navegador, atualização e rollback. Não confundir Linux com Windows.
4. Integrar por revisão o refresh/revalidate. Seu controlador fica na main e não
   executa código/artefatos do PR. Usar lease e SHA imutável; tratar conflitos e
   action_required sem bypass. Um token de escrita não vai para os testes.
5. Integrar o triage/handoff desta proposta. Usar concurrency por SHA, somente
   metadata REST e filtro de PR interno. Não habilitar issues/opened para chamar
   um agente automaticamente. O workflow privilegiado usa a definição da main.
6. Validar a fila com o ensaio abaixo. Somente depois considerar qualquer nova
   integração Codex: autorização de credenciais/orçamento e revisão de isolamento
   são trabalhos separados. A fila manual não exige OPENAI_API_KEY.
7. Distribuição é etapa independente: seguir os manuais de chaves, environments e
   assinatura. Não executar preparação, tags ou releases como parte deste ensaio.

## Ensaio reproduzível

- Em branch descartável interna e PR draft para main, incluir um pytest que
  falhe deliberadamente com mensagem fixa, sem I/O nem credenciais. Não alterar
  workflows/proteções para forçar o resultado. Não integrar o commit de falha.
- Aguardar o run quality gates terminar failure e o workflow_run triage da main
  concluir. Verificar a issue real criada, SHA e autoria do bot.
- Após integração desta proposta, a issue já contém o contrato. Antes disso,
  reproduzir como a #14: operador autorizado executa o CLI novo sobre o run e a
  issue legada autenticada, usando --preview antes de --existing-issue.
- Repetir o comando: exigir already_queued na mesma issue. Uma mudança de
  assinatura no mesmo head exige budget_exhausted; testar isso por mock para
  não fabricar incidentes reais. Testar forks, permissões e texto hostil por
  contrato isolado, sem criar forks/credenciais de teste.
- Conferir que a issue declara manual_codex_handoff e awaiting_human_start.
  Iniciar tarefa humana explícita apenas depois da revisão, registrar ID/link
  verdadeiro; atribuição ou comentário não provam execução.
- A correção deve usar a branch indicada, remover a falha e abrir PR para main.
  Aguardar Python/frontend/audit/Windows verdes no novo head. Falha na correção
  não chama outro agente. Encerrar o PR descartável sem merge e registrar os IDs.

Comandos de validação local, na raiz:

```sh
python -m pip install -r backend/requirements.txt
python -m pytest -q
npm ci --prefix frontend
npm run build --prefix frontend
npm audit --prefix frontend --omit=dev --audit-level=high
actionlint -shellcheck= -pyflakes=
git diff --check
```

Não copiar tokens para scripts ou exemplos. Na operação de Actions, GH_TOKEN
recebe apenas github.token nos passos de API; checkout não persiste credenciais.
Os requisitos administrativos/segredos de distribuição são documentados em
[Distribuição](../DISTRIBUICAO_RELEASES.md), não são necessários para a fila.
