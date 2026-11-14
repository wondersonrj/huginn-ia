# Conexões Oracle salvas — issue #21

## Fluxo mínimo Windows

1. Inicie o HUGINN como o usuário Windows que utilizará a conexão. Mantenha o
   token local configurado conforme [o MVP](WINTHOR_MVP.md); ele continua sendo
   a autorização do operador, separado da senha Oracle. Não execute como serviço
   SYSTEM ou com uma conta compartilhada entre operadores.
2. Informe o token em Consultas WinThor e clique **Carregar conexões salvas**.
3. Cadastre nome único, ambiente TESTE/PRODUÇÃO, host, porta, Service Name,
   usuário SELECT-only, schema WinThor em maiúsculas e senha. **Salvar conexão**
   não conecta nem seleciona. Em cadastro sem senha, só os metadados são salvos;
   o destino não pode ser testado/selecionado até informar uma senha válida.
4. **Testar** confirma apenas DUAL, com timeout e sessão encerrada sem commit.
   Não cria conexão persistente, não valida produtos/fornecedores e não seleciona
   o perfil. A interface registra o último teste apenas durante o processo atual,
   com data/hora, sem afirmar que a rede continuará disponível.
5. **Selecionar** confirma o destino. PRODUÇÃO exige confirmação explícita na
   interface e no servidor. O rótulo é declarado pelo operador: não certifica
   sozinho a identidade do banco. Esta implementação não alterou banco de produção.
6. Clique **Verificar conexão WinThor**, depois pesquise produtos/fornecedores.
   A seleção fornece configuração e senha ao servidor; cada operação abre sua
   própria sessão de leitura, valida schema e encerra a conexão. A API de consulta
   devolve somente a identidade/nome/ambiente do perfil, nunca sua senha.
7. Reinicie o aplicativo na mesma pasta/usuário e carregue a lista. Os perfis e
   senhas permanecem salvos; **a seleção não é restaurada automaticamente**.
   Selecione e confirme novamente, sem redigitar os dados Oracle.

O token de acesso da #18 permanece na memória da página e precisa ser informado
na nova sessão. Esta entrega evita reentrada da configuração/senha Oracle, não
implementa login Windows/SSO ou persistência do token HTTP. Encerrar acesso limpa
os dados da página; não exclui perfis nem encerra o processo.

## Edição e exclusão

Editar nunca carrega a senha no formulário. Campo vazio conserva o segredo
existente; uma nova senha o substitui. **Remover senha** apaga o blob do perfil,
mas preserva os metadados. **Excluir** remove perfil e senha. Não há SQL de
alteração da conta Oracle; nenhuma dessas ações muda dados no ERP.

Salvar, editar ou excluir invalida a seleção e o último teste relevante. Todas
as mutações usam id e revisão; uma aba desatualizada recebe 409 e deve recarregar.
Consultas enviam id/revisão do perfil selecionado. Troca de destino em outra aba,
edição ou exclusão impedem novas consultas no contexto antigo, sem seguir o novo
perfil silenciosamente. Uma operação já autorizada e com configuração capturada
pode terminar no destino antigo; mudar/excluir o perfil não cancela instantaneamente
um SELECT que já começou. A resposta identifica o perfil efetivamente usado.

Até 50 perfis por instalação. Os nomes são únicos sem distinguir maiúsculas ou
espaços nas extremidades. Não há compartilhamento entre instalações/usuários.

## Armazenamento e fronteiras de segurança

No Windows, usa **CryptProtectData / CryptUnprotectData (DPAPI CurrentUser)**,
com UI_FORBIDDEN e sem LOCAL_MACHINE. A entropia vincula o blob a usuário,
instalação e identificadores do perfil/segredo. Uma senha UTF-8 é protegida
como bytes e gravada em arquivo binário .dpapi separado; não é serializada em
profiles.json, base64 no JSON, logs ou frontend storage. O segredo só existe
em memória durante salvar/testar/consultar. Buffers nativos são zerados antes
de liberar; cópias gerenciadas em Python/JavaScript não têm garantia de apagamento
criptográfico. Isso não é “criptografia universal” nem defesa contra código
malicioso executando como o mesmo usuário ou administrador/SYSTEM.

O diretório é obtido por API Windows, sem aceitar caminho vindo do navegador:

`LocalAppData/HUGINN/Connections/<SHA256 do caminho canônico da instalação>`

No portátil, a instalação é a pasta que contém state/ e versions/. Em desenvolvimento,
é a raiz do projeto. Atualizar a versão no mesmo local preserva a identidade;
mover/copiar para outro caminho cria outra instalação e não migra a credencial.
A conta Windows é o usuário do **processo servidor**, não uma identidade individual
inferida do navegador. Não hospedar o mesmo servidor para usuários diferentes.

Arquivos e diretório têm DACL protegida substituída integralmente para usuário
atual e SYSTEM, sem ACEs herdadas ou explícitas de outros usuários. Reparse points,
symlinks, identidade/instalação divergentes, versão/formato desconhecidos e
permissões que não possam ser aplicadas causam bloqueio. As ACLs não impedem
administradores de tomar posse; a proteção depende também do Windows e da conta.

profiles.json contém só nome/ambiente, dados de destino, schema, id/revisão e
referência opaca ao blob. Esses metadados operacionais ainda podem ser confidenciais:
não são um arquivo público e ficam sob a mesma ACL. Não há senha/DSN no log,
resposta de API ou marcador de suporte. Nenhum endpoint exporta cofre, backup ou
senha. O diretório está fora do pacote, Git e state/ do atualizador. Builds e
artefatos CI contêm código e fixtures sintéticas, não a pasta LocalAppData.
Backups do atualizador são ponteiros/versões e não incluem o cofre. Exclua a pasta
de cofre de exports/backups de suporte; backups administrativos do sistema estão
fora do controle da aplicação e precisam de política própria de exclusão.

Gravações usam arquivo temporário protegido + fsync + replace, UUID para novos
blobs e bloqueio de arquivo/processo. Nenhuma senha é escrita em temporário claro.
Remoção usa unlink, sem promessa de eliminação forense em SSD/backups. Queda entre
etapas pode deixar blob **criptografado** órfão; metadados ausentes com blobs
remanescentes bloqueiam o uso, em vez de adivinhar destino/segredo. Erros de disco
podem ocorrer depois da alteração lógica; recarregar a lista antes de repetir.

## Autorização e API

Todas as operações são POST JSON com o token local, cliente loopback, Host exato
e Origin local quando presente, como na #18. O token autoriza operações de
configuração e leitura deste operador; não há perfis administrativos separados,
SSO, multiusuário ou proteção contra máquina já comprometida. Não expor a porta
à rede/Internet. Corpos são limitados a 8192 bytes, campos desconhecidos recusados,
respostas no-store. Senhas de entrada usam SecretStr e erros não refletem valores.

| /api/connections/ | Corpo / operação |
| --- | --- |
| list | {} → metadados, password_saved, último teste pontual e seleção; nunca segredo |
| save | metadados completos, password opcional; id/revision obrigatórios para editar |
| select | id, revision, confirm_environment igual ao ambiente salvo |
| test | mesma referência/confirmação; SELECT 1 FROM DUAL, sem selecionar |
| remove-password | id, revision; remove só a credencial |
| delete | id, revision; remove perfil e credencial |
| import-environment | name, environment; lê configuração/senha só no servidor e salva protegido |
| environment | confirm="USAR CONFIGURACAO DO AMBIENTE"; opta explicitamente pelo legado |

A seleção é por processo e não é persistida. Se já existe um catálogo gerenciado,
reiniciar, excluir todos os perfis ou perder a senha não ativa o ambiente/demo
silenciosamente. 409 pede seleção/revisão/confirmação; 503 indica indisponibilidade
de proteção/arquivo/segredo; 422 rejeita dados inválidos; 502 sanitiza falha Oracle.
Os catálogos da #18 aceitam connection_id e connection_revision. Em perfil salvo,
ambos são obrigatórios e devem coincidir com a seleção; para legado, são omitidos.

A auditoria existente registra UUID, ação fixa, horário, status e duração, sem
nomes dos perfis, host, usuário, senha, blobs ou corpo de requisições. Não é uma
trilha imutável e depende da retenção local descrita em WINTHOR_MVP.md. Não ativar
logs HTTP/driver de debug com corpos/autorização em máquina de cliente.

## Migração e fallback

Sem catálogo prévio, a configuração por ambiente da #18 continua funcionando.
Não há importação automática, seleção implícita nem cópia do segredo para o
navegador. Para migrar, mantenha HUGINN_WINTHOR_MODE=oracle e os dados válidos no
servidor; informe nome/ambiente e use **Salvar configuração do ambiente**.
Depois carregue, selecione e homologue o perfil. A importação não apaga as
variáveis nem conecta. Quando confirmado o perfil, remova as antigas variáveis
Oracle da sessão de inicialização para evitar uso legado acidental.

**Usar configuração por ambiente** exige confirmação e vale só até reiniciar.
O destino aparece como não classificado, nunca como TESTE presumido. Não é um
fallback automático de segredo. Versões anteriores à #21 não conhecem a seleção;
um rollback antigo exige atenção às variáveis legadas e não descriptografa este
cofre. Não copiar a senha para arquivo/JSON para viabilizar rollback.

Em Linux/macOS, a lista informa supported=false e a persistência é recusada;
permanece o caminho anterior por ambiente. Não há emulação/injeção de cipher por
configuração HTTP/variável. Os ciphers portáveis existem exclusivamente nos testes.

## Recuperação e homologação

- Senha ausente/corrompida com metadados válidos: editar e informar nova senha,
  depois selecionar novamente. A aplicação não tenta recuperar a senha em claro.
- Metadata corrompida, usuário trocado ou perda das chaves DPAPI: feche o servidor,
  verifique conta/instalação/permissões. Se não houver recuperação autorizada do
  perfil Windows, descarte o diretório privado desta instalação e recadastre.
  Não ampliar ACLs, exportar blobs para suporte ou assumir que a cópia de outra
  conta funcionará. Remova variáveis Oracle legadas antes de recomeçar.
- Mudança de caminho, reinstalação em outra pasta ou outro usuário: recadastre
  nessa instalação. Não há migração silenciosa da confiança Windows.
- Perfis PRODUÇÃO de exemplo são apenas rótulos sintéticos dos testes. Esta tarefa
  não configurou, testou nem alterou produção. A homologação Oracle real segue
  pendente de rede/conta SELECT-only autorizada pelo DBA, sem credenciais públicas.

Os testes cobrem mocks sem Oracle, reboot/reinstanciação, troca de identidade/
entropia/instalação, corrupção, senha ausente, remoção/substituição, falha atômica,
conflitos de revisão, token/Origin/Host e consultas reais do módulo com driver
simulado. No Windows CI, um teste usa **DPAPI real**, processo independente e ACL
real; não utiliza Oracle. O navegador Windows cobre CRUD e seleção com confirmação,
sem fazer chamadas ao banco para perfis salvos sintéticos. O Linux não comprova
DPAPI Windows. IDs/SHAs e resultados finais ficam no PR da #21.

## Registro de validação desta proposta

Local Linux: 270 testes aprovados, 2 ignorados (DPAPI nativo e compartilhamento
de arquivo nativo Windows). Build TypeScript/Vite, auditoria npm de produção
(zero vulnerabilidades), actionlint 1.7.12 e git diff --check aprovados. Chromium
sobre o pacote de produção passou com API demo real, mostrando o caminho sem
persistência no Linux e mantendo as regressões de consultas/XML/atualização.
O caminho Windows nativo é registrado com run/SHA na descrição do PR. Não se
usa aprovação Linux como evidência de DPAPI, ACL Windows ou Oracle real.

No primeiro run Windows do PR, DPAPI e recuperação em processo novo passaram;
a validação textual de ACL falhou porque icacls gerou UTF-16 sem BOM e usa aliases
de SID. O teste foi corrigido para consultar a DACL real via WinAPI, exigir flag
protegida, duas ACEs de acesso total e exatamente os SIDs do usuário e SYSTEM em
diretório/arquivos. Não foi removido teste nem flexibilizada a política.
