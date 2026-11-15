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

## Primeiro fluxo funcional WinThor — issue #18

[Implementação, instalação Windows, schema, API e aceite](WINTHOR_MVP.md).
Reutiliza o conector Thin e a interface existentes para pesquisar somente código
e nome de produtos/fornecedores. A consulta valida metadados por owner explícito,
usa binds, paginação limitada e transação read-only. Novos endpoints e os
avulsos legados de Oracle exigem token local; as consultas mantêm a senha Oracle
somente na configuração do servidor. Auditoria registra metadados de operação,
sem filtros, credenciais ou resultados comerciais.

A demonstração usa dados sintéticos identificados. Mocks e CI não confirmam
schema, rede, credenciais ou conta de leitura de um cliente. O ensaio Oracle
real depende de autorização do DBA e de configuração local segura; não solicitar
segredos em issues. Não há SEFAZ, escrita ERP, comparação NF-e automática,
publicação, merge ou mudança de proteções. O fluxo da #9 continua parcialmente
pendente para conciliação/consultas adicionais.

Changelog: #18 acrescenta o catálogo funcional, autenticação local, auditoria,
validação do schema e testes de UI/API. O histórico e inventário da fábrica
continuam vinculados à #10; não se confunde MVP demonstrado com produção aprovada.

## Conexões persistentes Windows — issue #21

[Instalação, primeira configuração, recuperação e limitações](CONEXOES_SALVAS.md).
Implementação autorizada pelo comentário de encaminhamento da #21, em branch
dedicada a partir da main. A escolha técnica é DPAPI CurrentUser com ACL privada
por usuário/instalação, separando metadados e blob binário de senha, fora do
pacote e dos backups do atualizador. Sem chave genérica ou fallback em texto puro.

Cadastro não seleciona, teste não cria sessão persistente, reinício exige seleção
explícita. PRODUÇÃO exige confirmação e é exibida distintamente. Revisões do
perfil são verificadas também nas consultas; editar/excluir invalida seleção.
O ambiente legado pode ser importado apenas por ação explícita, sem devolver a
senha. Token local, controles loopback/Origin/Host, schema e binds da #18 ficam
preservados. Testes Windows verificam DPAPI/ACL e reinício sem Oracle real.

Registro issue → branch → PR e evidências finais constam na descrição do PR que
referencia #21; [histórico de decisões](FABRICA_APLICACOES/HISTORICO_COMPLETO.md).
Não houve merge, release, alteração de produção ou homologação em banco real.

## Instalador e primeira execução — #23, dependências #20/#21

[Guia final de instalação e suporte](INSTALACAO_WINDOWS.md). Implementação
incremental sobre o PR #22 ainda aberto, sem duplicar nem integrar o cofre.
A revisão deve respeitar a ordem #22 → PR instalador e retargetar para main
somente após integração humana da dependência, com CI revalidada.

O MVP acrescenta Inno Setup por usuário, launcher Win32 nativo, atalhos,
desinstalação com manter/remover, token aleatório DPAPI automático, sessão
HttpOnly vinculada ao SID Windows do cliente, porta gerenciada e reabertura
por prova HMAC de instalação/versão. Não exige PowerShell/Python/Node/OCI ou
reboot do operador, nem mata serviços alheios. Oracle permanece read-only.

A #20 é atendida por artifacts rastreáveis de PR e push/main, distinguindo
pré-merge de pós-merge. Não há Authenticode autorizado: o EXE é de homologação
não assinado, sem release/tag/publicação. SHA256 não substitui assinatura.
Windows CI exercita instalação/uso/reinstalação/upgrade/reabertura/conflitos e
remoção. Homologação Oracle real continua pendente. IDs e artifacts do run
final ficam na descrição do PR; não se presume execução por abrir issue.
