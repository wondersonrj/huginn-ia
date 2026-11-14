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

## Incidente #12: aprovação pendente antes dos jobs

Investigação em 14/11/2026. Evidência sanitizada:
[ISSUE_12_EVIDENCIAS.json](incidentes/ISSUE_12_EVIDENCIAS.json).
Os três runs abaixo são de **pull_request**, não de workflow_dispatch:

| Workflow | Run | Resultado | Jobs |
| --- | --- | --- | --- |
| Quality gates | [43624333390](https://github.com/wondersonrj/huginn-ia/actions/runs/43624333390) | action_required | 0 |
| Immutable validation | [43624333601](https://github.com/wondersonrj/huginn-ia/actions/runs/43624333601) | action_required | 0 |
| Windows portable | [43624333649](https://github.com/wondersonrj/huginn-ia/actions/runs/43624333649) | action_required | 0 |

As três páginas públicas dizem exatamente: **“This workflow is awaiting approval
from a maintainer in #7”**. Esta é a causa comprovada da ausência de jobs:
o GitHub exige aprovação do workflow antes de executar o código. Não é uma
falha dos testes, conflito de merge ou aprovação de deployment. Os endpoints
pending_deployments estão vazios. O endpoint de logs consultado retornou 404.

O PR é interno, do proprietário `wondersonrj`, com author_association OWNER;
os três eventos têm ator e triggering_actor `github-actions[bot]`, após a
atualização automática. Não se deve inferir que o PR é de um fork ou atribuir
o bloqueio a uma configuração específica de contribuidores: as três APIs de
políticas (`actions/permissions`, `actions/permissions/workflow` e
`actions/permissions/fork-pr-contributor-approval`) responderam 403. A mensagem
da interface comprova a aprovação pendente, mas não revela qual configuração
interna provocou esse requisito para o evento do bot. Essa limitação permanece
explícita, sem tentar mudar políticas.

### O que o refresh realmente executou

O run [43624310820](https://github.com/wondersonrj/huginn-ia/actions/runs/43624310820)
foi um push na main `12b147ad3780025ce816c6fd092380cef5d68c6a`, com job refresh
132536638929 aprovado. A atualização colocou o PR #7 no head
`3e9280e9b17aa31060dcc8d9e2598c982a9e43e9`, contendo essa main. A função retorna
imediatamente após update-branch, por ser uma operação assíncrona. O próximo
passo depende de outra execução agendada ou manual do controlador.

Na coleta de 18:08 UTC (15:08 em São Paulo), a API listou **zero** runs de
workflow_dispatch do workflow imutável e somente esse run do refresh. Portanto
não houve dispatch comprovado, nem evidência de recusa de autorização de um
dispatch: ele não foi tentado nesse caminho. O sucesso do controlador só
comprova a atualização. A ausência da segunda passagem naquele intervalo não
prova defeito no cron, que não tem garantia de execução pontual pelo GitHub.

O status REST do novo head está vazio. O PR está mergeable, mas bloqueado.
O required `portable`, vinculado ao GitHub Actions 15368 e com política estrita,
continua exigido. Não há evidência de testes aprovados para esse head nem de
PR #7 liberado pelo GitHub. Os resultados anteriores do PR #11 não aprovam #7.

### Correção proposta e comportamento após integração

- Antes de atualizar ou despachar, o controlador procura runs dos três workflows
  de PR com action_required, conferindo número do PR, SHA e origem interna.
  Bloqueios de outro PR/SHA/workflow não são usados como autorização ou resultado.
- Se houver bloqueio, registra comentário deduplicado com links e orientação ao
  mantenedor e retorna approval_required. Não atualiza novamente a branch,
  não chama a API de aprovação, não despacha outra validação e não publica status.
  Um dispatch que também termine action_required recebe o mesmo tratamento,
  sem ser convertido em falha de teste ou reexecutado indefinidamente.
- O resumo de Actions e stdout distinguem update_requested,
  dispatch_requested, approval_required, validation_in_progress e resultado
  verificado. Erros de API agora encerram o controlador com código 1, em vez
  de um sucesso silencioso. O controlador verde não substitui os required checks.
- Runs de pull_request passam a ter nome com PR/SHA, em vez de autodev---;
  a identidade usada para reconciliar workflow_dispatch continua inalterada.
- Depois da aprovação humana, a passagem seguinte reavalia os metadados atuais.
  Só retoma dispatch/reconciliação se não houver bloqueio. Mantém lease, execução
  em SHA imutável, validação de ator/definição e exigência dos quatro jobs reais.

Essa correção só passa a reger a automação após revisão e merge manual. A versão
atualmente na main ainda não possui a parada explícita por action_required;
esta investigação não a executou nem alterou sua configuração. Não é possível
prometer interrupção global da versão antiga apenas abrindo um PR.

### Etapa humana necessária — interrompida nesta investigação

O proprietário/mantenedor deve abrir o [PR #7](https://github.com/wondersonrj/huginn-ia/pull/7),
conferir Files changed e os workflows no head indicado, e abrir cada run acima.
Na faixa de aprovação pendente, clicar em **Approve and run workflows**
(**Aprovar e executar workflows**) se exibido. Se a aprovação estiver agrupada
no PR, revisar os workflows listados e confirmar apenas o grupo correspondente.
Não é **Review deployments / Approve and deploy** e não autoriza produção.
Se o botão não aparecer, um mantenedor com acesso deve inspecionar o motivo na
interface; não conceder PAT, instalar App, reduzir regras ou alterar Settings.

Esta aprovação não foi realizada nem simulada. Nenhum dispatch/rerun alternativo
foi provocado para superar o bloqueio. Após a aprovação, conferir jobs reais,
SHA, required portable e estado de merge no GitHub; só o GitHub pode confirmar
a liberação. O teste de falha controlada do triage continua adiado até o merge
manual do PR #7. A invocação atual do agente foi explícita no chat para a issue
#12; isso não demonstra integração automática entre issues e Codex.

### Validação da correção

A suíte local passou com **167 testes aprovados e 1 ignorado**. Os 24 contratos
do controlador cobrem aprovação pendente em PR e dispatch, ausência de update,
dispatch e status durante bloqueio, comentário deduplicado, retomada após
aprovação, SHA/origem divergentes e saída não zero em erro de API, além dos
casos originais. O teste ignorado depende do compartilhamento nativo de arquivos
Windows. Build frontend e actionlint 1.7.12 passaram localmente; a auditoria npm
de produção encontrou zero vulnerabilidades. A CI remota deve ser conferida
também no PR da correção. Esses testes simulados não são aprovação dos runs do #7.
