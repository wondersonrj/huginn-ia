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
inicialmente empilhada sobre o PR #22. Após seu squash na main, o incremento
do instalador foi reaplicado sobre a main, sem duplicar os commits do cofre.
O PR #24 agora tem main como base e requer CI revalidada nessa composição.

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

Entrega em revisão: [PR #24](https://github.com/wondersonrj/huginn-ia/pull/24),
reutilizando o [PR #22](https://github.com/wondersonrj/huginn-ia/pull/22), já integrado por squash.
Validação local: 286 testes aprovados, dois exclusivos Windows ignorados no Linux;
build TypeScript/Vite, auditoria npm (zero vulnerabilidades) e actionlint aprovados.
A CI Windows validou onboarding, DPAPI, cookies/SID, múltiplas aberturas, upgrade e
preservação de terceiro na porta 8000; o ciclo final e artifact rastreável ficam
registrados no PR. Aberturas concorrentes aguardam locks temporários sem recriar
um token corrompido. O teste de desinstalação usa o modo síncrono do Inno para
não reinstalar enquanto seu processo temporário ainda remove arquivos.

### Estabilização #23 — complemento de 15/11/2026

O primeiro smoke instalado parava no listener indisponível: gerar EXE e testar
falha de rede não comprovava DUAL/metadados/consultas na UI. O smoke agora instala
o artifact original, confirma a falha Oracle real sem driver substituído e só
então adiciona um double de driver na **cópia descartável** instalada da versão de
upgrade. Esse arquivo não entra no pacote nem existe flag de ativação no produto.
A execução passa por DPAPI real, sessão Windows/SID real, UI, backend em modo
Oracle (mesmo herdando `demo`), DUAL, metadados e binds CODPROD/PCPRODUT e
CODFORNEC/PCFORNEC. O double recusa SQL inesperado e commit. Não é banco Oracle
real: homologação no ambiente autorizado continua pendente, sem solicitar senhas.

A matriz cobre senha inválida, listener indisponível, timeout de conexão/consulta,
owner incorreto, ausência de SELECT, troca de conexão/contexto antigo, senha
removida, reinício, upgrade/rollback e desinstalação. O teste herda propositalmente
um token curto; o launcher deve substituí-lo pelo token DPAPI de 256 bits. A prova
HMAC é verificada também na primeira abertura e passa a vincular o commit do build:
backend com token divergente ou pacote antigo não pode ser aberto silenciosamente.
Sem conexão selecionada após reiniciar, o cofre gerenciado impede fallback demo.
O evento sanitizado `identity_rejected` permite identificar a recusa sem divulgar
segredos. Resultados finais e artifact da execução estão no PR #24, atualizado
incrementalmente em vez de abrir um PR duplicado sobre o mesmo trabalho.

Evidência da estabilização: [run Windows 43676264209](https://github.com/wondersonrj/huginn-ia/actions/runs/43676264209),
head `75ba14f06382ae668065a6ecbaa5fb04b9d5281d`, merge de teste
`67ade67ef24582209009d5ebd3a1b27fdd79de0e`: **288 aprovados, 1 ignorado** no
Windows; **287 aprovados, 2 ignorados** no Linux. Backend, frontend e auditoria
aprovados. Ambos os smoke tests emitiram PASS, incluindo consultas na UI e
matriz negativa descrita acima. [Artifact homologação](https://github.com/wondersonrj/huginn-ia/actions/runs/43676264209/artifacts/14145559304)
com EXE, SHA256 e INSTALLER-INFO, sem Authenticode. O PR #24 registra também a
reexecução após esta atualização documental. Não houve Oracle real, merge,
release, mudança de proteções ou publicação em produção.

### Consolidação pós-squash do PR #22

Base atual: main `7cbf8e2918de80d7a7a2ac848ea1ee55ee294808`. Reaplicados
somente os nove commits de instalador/estabilização posteriores ao antigo head
`03781bd8` da #21. A árvore do squash era idêntica àquela dependência; a
reaplicação não apresentou conflitos. Os commits originais da #21 não integram
o histórico incremental do PR #24. Removido o gatilho da branch intermediária
da CI Windows: revisão de PR agora usa main. Documentos deixam de exigir
integração/retarget pendentes. Resultados da revalidação Windows e artifact
consolidado são registrados no PR #24; as evidências anteriores acima são
históricas, não substituem esta reexecução. Nenhum merge/release autorizado.

## Issue #25 — diagnóstico Oracle e preparação de atualização

Base main após #24; sem intervenção em Oracle/servidor de produção. O incidente
real é DUAL OK e catálogo recusado; sua causa específica depende do relatório
sanitizado do ambiente. A investigação comprovou no código o JOIN obrigatório com
ALL_TABLES (exclusão de views) e mensagem genérica que confundia owner/metadados/
colunas/privilégios. [Diagnóstico e recuperação](DIAGNOSTICO_ORACLE.md) documenta
SELECT sem linhas, owners candidatos, sinônimos e confirmação explícita do owner,
sem conceder grants nem escolher outro destino automaticamente.

Nova versão de homologação 0.3.0: consultas read-only continuam restritas a
PCPRODUT/PCFORNEC, binds e limites. Cofre/perfil existentes são preservados.
Updater agora prepara validação de commit assinado e identidade por versão ativa.
[Plano e bloqueio de ativação](ATUALIZACOES_WINDOWS.md): auto-update/publicação
continuam desativados; é preciso infraestrutura de assinatura e aprovação real.
Bootstrap antigo não pode ser trocado remotamente por código que ele não confia;
instalador de transição na mesma pasta/usuário preserva dados. Updates posteriores
compatíveis podem dispensar reinstalação após habilitação autorizada.

Testes reproduzem a diferença DUAL/catalogo, metadados não visíveis, SELECT negado,
owner incorreto, colunas/tipos inválidos e descoberta sem mutação. CI Windows
inclui instalador/UI e update desktop assinado de commits distintos, perda de rede,
rollback e preservação byte a byte de DPAPI. Resultados finais, commit, PR e
artifact são registrados no PR que referencia #25. Testes fake não homologam
Oracle real; não houve merge, release ou ativação em produção.

Entrega #25: [PR #26](https://github.com/wondersonrj/huginn-ia/pull/26).
Primeira evidência Windows concluída: [run 43742587109](https://github.com/wondersonrj/huginn-ia/actions/runs/43742587109),
head `67e7aaf`: **301 aprovados, 1 ignorado**; Linux **300 aprovados, 2 ignorados**.
Smoke desktop: update assinado 0.3.0→0.3.1 (commit distinto), perda de rede sem
encerrar a versão atual, falha 0.3.2→rollback 0.3.1; perfil/token DPAPI preservados
byte a byte. Smoke instalado: DUAL, metadados e CODPROD/CODFORNEC na UI com driver
sintético, matriz negativa, reinstalação/upgrade e uninstall aprovados. Build web,
auditoria, actionlint e diff check aprovados. Nova checagem visual confirma
DUAL OK + owner errado, relatório parcial e owners não selecionados; reexecução
final do HEAD/documentação e artifact 0.3.0 rastreável constam no PR #26.
Oracle real do cliente não foi acessado nem declarado homologado.

## Issue #27 — substituição segura pelo Setup Windows

[PR #28](https://github.com/wondersonrj/huginn-ia/pull/28), base main pós-#26,
Setup de homologação 0.3.1. [Guia de atualização/recuperação](INSTALACAO_WINDOWS.md#atualizar-instalações-anteriores--27--setup-031).
Auditoria: AppId Inno já estável e registro HKCU suportavam in-place, mas a antiga
ativação só preservava o apontador da versão; não recuperava o bootstrap após
sobrescrita. A antiga limpeza recursiva na desinstalação também atingia arquivos
não catalogados. Não executamos o desinstalador anterior: Inno substitui os arquivos
na pasta registrada, mantendo identidade DPAPI e catálogo/atalhos.

Novo preflight executado pelo runtime temporário do próprio Setup valida família,
usuário/diretório, versão ativa e compatibilidade. Usa DPAPI/HMAC + sessão SID
para encerrar somente a instância própria, aguarda backend/launcher e mantém lock
até hash/health/commit ou rollback. Backup privado inclui binários substituídos,
configurações/apontador, registro/atalhos e ciphertext DPAPI; sem exportação de
senha/token. Falha restaura a instalação anterior; nova execução do Setup recupera
transação pendente. Corrigido o reconhecimento de dados preservados pós-uninstall,
sem exigir remoção manual de pastas. Versão ativa mais nova impede downgrade.

Portátil compatível pode ser convertido na própria pasta quando não há instalação
registrada; cópias em outras pastas permanecem separadas/intocadas. Não há varredura
de discos, migração entre usuários/caminhos nem encerramento sem prova. Os perfis
salvos permanecem; selecionar destino/confirmar PRODUÇÃO após reinício continua
obrigatório. Manter dados é padrão no uninstall; remoção explícita inclui backup
privado e cofre, sem limpeza recursiva de arquivos extras no diretório do programa.

Testes unitários cobrem integridade, recuperação, cofre, diretório registrado,
symlinks, downgrade ativo e HMAC forjado. CI Windows usa EXEs históricos reais
0.2.0/0.3.0, ZIP portátil, instância ativa, backup/cópia/health, instalação quebrada,
rollback, recuperação de interrupção, atalho/registro e uninstall keep/remove.
Os resultados finais e artifact rastreável são registrados no PR #28. Sem merge,
release, publicação, instalação remota, reboot ou alterações no Oracle do cliente.
