# Preparação do canal de testes — administrador único

O workflow `Prepare test distribution` automatiza proteções adicionais, criação
dos cofres de testes/recuperação, geração Ed25519 em memória, armazenamento dos
segredos via stdin do gh, criação de PR só com a pública e verificação criptográfica
dos dois cofres. Não grava privadas em disco, logs, artefatos ou outputs. Não troca
chaves existentes nem altera regras desconhecidas. Migra somente a regra legada
HUGINN reconhecida para o modelo de administrador único, mantendo PR e CI obrigatórios. Remove o secret administrativo
usado nessa preparação, inclusive em falha; o token deve ser revogado pelo titular.

Produção permanece bloqueada: nenhuma chave de produção é gerada, seu environment
não é alterado e `HUGINN_PRODUCTION_RELEASES_APPROVED` não é definido. O workflow
de release recusa produção enquanto essa autorização não for explicitamente
configurada no futuro. A instalação existente e o ZIP distribuído não são tocados.

## Intervenções inevitáveis do titular

### A. Autorizar uma única operação administrativa

1. No GitHub, avatar → **Settings → Developer settings → Personal access tokens →
   Fine-grained tokens → Generate new token**.
2. Nome `HUGINN-distribution-bootstrap`; **Expiration: Custom**, data do dia seguinte; **Resource owner:
   wondersonrj**; **Repository access: Only select repositories → huginn-ia**.
3. Em **Repository permissions**, escolha **Read and write** para **Administration**,
   **Environments**, **Contents** e **Pull requests**. Metadata fica read automaticamente.
   Gere e copie o token para o próximo formulário, nunca para código/chat.
4. No repositório, **Settings → Environments → New environment**, nome
   `distribution-bootstrap`, **Configure environment**.
5. Ative **Required reviewers**, selecione somente **wondersonrj**, deixe
   **Prevent self-review desmarcado** e salve. Desmarque **Allow administrators to bypass
   configured protection rules** quando essa opção estiver disponível.
6. Em **Deployment branches and tags**, selecione **Selected branches and tags →
   Add deployment branch or tag rule → Branch**, padrão `main`, e adicione.
7. Em **Environment secrets → Add environment secret**, nome
   `HUGINN_DISTRIBUTION_ADMIN_TOKEN`, cole o token e salve.

A API não permite que um workflow obtenha autoridade administrativa que o titular
não concedeu. Também não expõe a configuração de bypass de administradores em
REST/GraphQL; esse ajuste de interface continua manual. Não use token clássico
com acesso a todos os repositórios nem crie o token como secret aberto do repositório.

O próprio administrador confirma e aprova as execuções. Não é necessário convidar
outra pessoa. O token deve pertencer a `wondersonrj`; a automação rejeita outro
ator, token de outro titular, ref diferente de main ou confirmação ausente.

### B. Executar e aprovar a preparação

1. **Actions → Prepare test distribution → Run workflow**; branch `main`;
   campo `confirmation`: digite exatamente `PREPARAR TESTES SEM PRODUCAO`; clique **Run workflow**.
2. O próprio administrador deve abrir a execução → **Review deployments**, selecionar
   `distribution-bootstrap` e **Approve and deploy**.
3. O workflow adiciona regras de main (PR obrigatório, zero aprovações de terceiros, CI `portable`, sem
   force-push/exclusão) e torna tags `v*` imutáveis (sem atualização/exclusão).
   Só a regra antiga HUGINN exatamente reconhecida pode migrar de 1 aprovação para 0, com aprovação do último push desativada; checks, proibição de bypass, force-push e exclusão são preservados. Regras desconhecidas/personalizadas não são sobrescritas. Criação de tags continua possível, mas
   releases só aceitam commits pertencentes à main revisada e aprovação humana.
4. Ele cria `windows-release-teste` e `windows-signing-recovery`, restritos a main,
   com aprovação manual do administrador (`wondersonrj`) e autoaprovação de deployment permitida. A mudança dos revisores de teste/recuperação é autorizada pela confirmação explícita; produção não é alterada. Se um environment já
   existir, preserva espera/customizações; políticas de branches mais
   amplas ou estado de chave desconhecido causam parada segura para revisão.
5. Em **Settings → Environments → windows-release-teste** e
   **windows-signing-recovery**, desmarque **Allow administrators to bypass
   configured protection rules**, se disponível, sem remover outras proteções.
6. Volte à execução → **Review deployments** e aprove os environments de testes e
   recuperação. Cada job verifica o segredo real contra a pública proposta e
   publica apenas o fingerprint/resultado, com checks separados no PR.

Não há cópia exportável de privada. O cofre de recuperação é um segundo secret
protegido dentro do GitHub, não um backup offline independente do provedor. Se
ambos os cofres forem perdidos, será necessário novo bootstrap com nova confiança,
por procedimento aprovado; nunca há rotação silenciosa em clientes.

### C. Revisar a mudança de confiança e encerrar o acesso administrativo

1. **Pull requests** → abra **Review test-channel public signing key — clients
   remain disabled**. Confira **Files changed**: somente a pública do canal
   `teste` em `packaging/windows/release-public-keys.json`; produção intacta.
2. Compare o fingerprint do resumo de **Prepare test distribution** com os jobs
   de verificação. Aguarde CI `portable`, `test-signing-vault` e
   `test-signing-recovery` verdes. O próprio administrador confere **Files changed**, os fingerprints e os três checks. Depois clique em **Merge pull request**. Não é necessário nem possível aprovar o próprio PR; zero aprovações formais são exigidas, mas o PR e os checks continuam obrigatórios.
   Não force o merge nem ignore proteções.
3. Avatar → **Settings → Developer settings → Personal access tokens → Fine-grained
   tokens → HUGINN-distribution-bootstrap → Delete**. O workflow já remove o secret,
   mas a revogação do token pessoal só pode ser feita pelo titular (ou expiração).

### D. Gerar a primeira release durável de testes, quando desejado

**Actions → Prepare test release → Run workflow**, branch `main`, versão nova
(padrão `0.3.0`), marque **confirm_test_release**, **Run workflow**. Aguarda CI do commit exato, cria tag imutável e
aciona `Windows portable build` com canal teste e **enable_client_updates=false**.
Depois dos testes, o administrador abre a execução de `Windows portable build` →
**Review deployments → windows-release-teste → Approve and deploy**. O pipeline
assina e publica uma prerelease; não habilita produção nem clientes.

A ativação de clientes fica para autorização posterior. Não mude nenhuma variável
ou opção de produção neste procedimento.

## Limites e execução desta tarefa

A preparação administrativa real aguarda as autorizações acima; ela não foi
executada com um token do titular nesta sessão. Scripts, proteção conservadora,
reuso de chaves, ausência de material privado em outputs e verificação dos cofres
são cobertos por testes automatizados. O fluxo continua falhando fechado quando
faltam credenciais ou há um estado existente que não pode ser verificado.

## Migração e compensações de segurança

A separação de duas pessoas foi substituída, por decisão explícita, por autoria
restrita ao dono do repositório, despacho manual, frase exata de confirmação antes
de carregar segredos, aprovações manuais de deployment pelo próprio administrador,
PR sem merge automático, CI obrigatório, tags imutáveis e assinatura Ed25519/SHA256.
Isso não equivale a controle de duas pessoas; proteja a conta com 2FA/passkey.

A regra v1 gerada pelo HUGINN é identificada por nome e fingerprint de política.
Somente `required_approving_review_count` (1→0) e `require_last_push_approval`
(true→false) são modificados; nenhuma outra regra ou bypass é removido. Um ruleset
v2 mantém PR/checks/proteção contra force-push e exclusão. Regras adicionais
personalizadas que ainda exigirem outra pessoa requerem revisão manual em
**Settings → Rules → Rulesets**; o workflow para em vez de removê-las globalmente.

Produção segue bloqueada pela variável de autorização e pela ausência de nova
ativação. A mudança para administrador único não altera assinatura, hash,
proteções das chaves, confirmação do operador no Windows nem instalações atuais.
