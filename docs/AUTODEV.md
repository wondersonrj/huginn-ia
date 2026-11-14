# AutoDev: atualização e revalidação segura

## Diagnóstico da issue #8 / PR #7

Consulta em 14/11/2026: PR #7 está `BEHIND`. O head
`c982c9240e19672bcae02da940588f078d0d6543` tem `portable` aprovado pelo
GitHub Actions (App 15368), execução 43621038780. Seu merge commit atual,
`2fcf125f28e2905db8a4a77112073702d3ccbfbc`, não tem check runs.
O status agregado REST está pending com lista de commit statuses vazia:
commit statuses e check runs são APIs diferentes; isso não invalida o check aprovado.

`GET /repos/wondersonrj/huginn-ia/rules/branches/main` confirma regra
27247820 com `strict_required_status_checks_policy: true`, contexto `portable`
e `integration_id: 15368`, além das regras de PR e proteção contra exclusão e
force-push. A regra 27245891 também protege main. A base antiga e164203 já
foi sucedida por dee51ac (PR #5). Portanto o bloqueio observado é branch
atrasada com política estrita, não nome incorreto do check ou App divergente.
A API de proteção clássica respondeu 403; não foi possível inspecioná-la,
nem se presume sua ausência. Nenhuma configuração foi alterada.

## Fluxo

1. `autodev-refresh.yml` executa a cada 15 minutos, em push para main ou
   despacho manual na main. Só faz checkout do SHA confiável da main,
   sem credenciais persistidas, caches ou artefatos do PR.
2. Lista PRs abertos, não draft, internos e direcionados à main. Consulta
   novamente cada PR e compara o head com a base atual. Forks são ignorados.
3. Usa `PUT /pulls/{number}/update-branch` com `expected_head_sha`.
   Sem force-push, rebase ou merge do PR. Conflito vira comentário deduplicado;
   mergeabilidade desconhecida aguarda próxima passagem. Falha de API também
   gera diagnóstico sanitizado. O retorno assíncrono nunca é tratado como
   evidência de que o novo commit já está pronto.
4. Na passagem seguinte, confirma ancestry, identidade e SHA atuais. Dispara
   `autodev-revalidate.yml` explicitamente por `workflow_dispatch` na main,
   com head imutável e base identificados no run-name.
5. A validação reutiliza os workflows confiáveis da main, passando o SHA para
   checkout. Executa Windows portable completo, testes Python, build frontend e
   auditoria npm. Seus tokens têm somente `contents: read`; não herda segredos.
   O workflow Windows de CI contém apenas o job portable, sem job publish,
   environment ou permissões de publicação. A implementação Windows original
   de release permanece intacta.
6. O controlador reconcilia resultados numa passagem posterior. Exige workflow,
   evento, branch main, SHA da definição, ator `github-actions[bot]`, identidade
   PR/head/base e os quatro jobs realmente aprovados. Só então publica o status
   `portable` no head validado, usando o próprio GITHUB_TOKEN do GitHub Actions.
   O link aponta para a execução real. Qualquer job ausente, skipped, cancelado
   ou falho impede sucesso. Falhas geram status failure e comentário sem logs.

Atualizar com `GITHUB_TOKEN` não dispara normalmente eventos push/PR em outros
workflows. O despacho explícito é uma exceção documentada pelo GitHub:
https://docs.github.com/en/actions/how-tos/writing-workflows/choosing-when-your-workflow-runs/triggering-a-workflow
Não se usa rerun de um run antigo: ele mantém o SHA antigo. O mecanismo cria
uma execução nova sobre o novo SHA. Os checks nativos do dispatch pertencem
à main; o commit status do controlador associa o resultado real ao head do PR.
A política estrita exige que esse head contenha main; nova mudança da base
obriga nova atualização e novo teste. Não são fabricados resultados verdes.

## Segurança e limites operacionais

O controlador tem contents/pull-requests/actions/statuses write apenas para
atualizar branches, despachar testes e registrar resultados/comentários. Nunca
executa código do PR ou consome logs/artefatos de workflows não confiáveis.
Não há `pull_request_target`, PAT, GitHub App adicional, segredo novo, instalação,
alteração de ruleset, bypass, aprovação de produção ou deploy automático.
O workflow do PR #7 continua não operacional até seu merge e validação real.

Concorrência global serializa controladores. Uma execução por tupla PR/head/base;
falhas não geram retries infinitos. Novo commit cria nova validação. Comentários
e statuses são deduplicados; paginação não limita a inspeção aos primeiros 100
itens. Se a API não indexar imediatamente um dispatch, pode ocorrer despacho
duplicado numa passagem posterior; ambos executam somente testes de leitura,
sem atualizações recursivas. API failures conservam as proteções e exigem inspeção.
Se a main mudar entre a conferência e o dispatch, o run com SHA divergente não
é aceito. A passagem seguinte usa a base nova. Mudanças concorrentes no head
não são sobrescritas pela lease; status em SHA antigo não aprova SHA novo.

Ativação: revisar e integrar este PR manualmente após required checks. Não há
configuração externa a autorizar. Após merge, acompanhar o primeiro refresh,
a atualização do PR #7, o dispatch e o status no novo head. Não presumir que a
validação local comprova a execução integrada do controlador: ele só existe na
main após integração. Se permissões de Actions forem negadas, investigar o
comentário e solicitar autorização antes de mudar políticas; não usar PAT/bypass.
A assinatura, environments e aprovações existentes continuam exigidos.

## Validação

`python -m pytest -q` inclui contratos de sucesso, falha, conflito, mergeabilidade
pendente, fork, lease concorrente, idempotência, SHA/ator divergentes e dispatch
explícito. `npm ci`, `npm run build` e `npm audit --omit=dev --audit-level=high`
validam o frontend. O PR executa também o pipeline Windows real. Os testes do
controlador usam API simulada para não atualizar PRs ou emitir statuses fictícios.
