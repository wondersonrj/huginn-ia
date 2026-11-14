# Manual mestre da fábrica HUGINN

## Fluxo de desenvolvimento e limite de autoridade

Uma solicitação explícita ao agente autoriza investigação, implementação,
testes e abertura de PR. Uma issue criada ou atribuída não prova que o Codex
foi acionado. Mudanças entram por PR e verificações obrigatórias; não há merge
automático. A main, assinaturas, environments e aprovações são preservados.

A atualização automática de branches e a validação imutável estão descritas em
[AutoDev](AUTODEV.md). O controlador executa somente código da main confiável;
os testes executam o SHA do PR com contents:read, sem herdar segredos. Um run
verde do controlador não equivale a testes verdes do PR.

## Incidente de aprovação #12

O [registro técnico](AUTODEV.md#incidente-12-aprovação-pendente-antes-dos-jobs)
e a [evidência sanitizada](incidentes/ISSUE_12_EVIDENCIAS.json) mostram três runs
do PR #7 em action_required com a mensagem de aprovação pendente do mantenedor.
O refresh atualizou a branch, mas não despachou validação naquela passagem.
Não há testes aprovados no novo head na coleta inicial.

A correção proposta pausa o controlador diante desse estado e informa o clique
mínimo de aprovação ao proprietário. A automação não aprova a si própria nem
usa dispatch para contornar a decisão humana. APIs de políticas responderam 403;
não se atribui a causa a uma configuração administrativa que não foi lida.
Após revisão e aprovação explícita dos workflows pelo mantenedor, conferir os
jobs e o required portable no SHA correto. O teste real de falha do triage só
ocorre depois da integração manual do PR #7.

## Distribuição e produção

[Distribuição assinada](DISTRIBUICAO_RELEASES.md),
[preparação de testes](PREPARAR_TESTES_PELO_GITHUB.md) e
[atualizações Windows](ATUALIZACOES_WINDOWS.md) documentam controles independentes.
Aprovar workflows de CI não autoriza release, secrets de assinatura, deployment
ou ativação de clientes. Produção continua sujeita à autorização humana própria.
