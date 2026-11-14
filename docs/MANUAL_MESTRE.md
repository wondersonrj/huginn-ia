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

## Fase 2 e índice navegável — issues #14 e #10

A fábrica propõe agora fila manual segura AutoDev → Codex, com contrato,
deduplicação, limite de um incidente por workflow/SHA e sem agente autônomo.
[Arquitetura, tokens, fontes oficiais, limites e ensaio #14](AUTODEV.md#fase-2--issue-14-fila-segura-para-codex).

- [Histórico, decisões e incidentes](FABRICA_APLICACOES/HISTORICO_COMPLETO.md).
- [Inventário de issues/PRs, branches, commits, estados e datas](FABRICA_APLICACOES/MATRIZ_ISSUES_PRS.md).
- [Guia de reprodução](FABRICA_APLICACOES/GUIA_REPRODUCAO.md).
- [Operação diária e manutenção](FABRICA_APLICACOES/OPERACAO_E_MANUTENCAO.md).

O #7 já está integrado. O ensaio descartável #15 produziu falha observada e issue
#16 pelo workflow real da main. O código novo preparou o handoff de #16 por CLI
nesta sessão e deduplicou uma segunda execução. O PR de solução deriva desse
commit, remove o teste deliberado e executa CI real. Este é um teste de fallback,
não evidência de API autônoma Codex ou de workflow novo já implantado na main.

### Changelog documental

- #8 → PR #11: política estrita, atualização com lease e revalidação imutável.
- #12 → PR #13: aprovação humana pendente, pausa explícita e evidência sanitizada.
- #14: integração manual segura, contrato v1, ensaio controlado e índice contínuo
  da #10. Inventário da coleta incluído; custos, ações humanas anteriores sem
  evidência e futura API/credencial permanecem explicitamente não verificados.

A [issue #10](https://github.com/wondersonrj/huginn-ia/issues/10) continua aberta
para consolidação integral. Não se muda seu estado só por criar documentação.
Nenhuma página deste manual autoriza merge, produção ou credenciais adicionais.
