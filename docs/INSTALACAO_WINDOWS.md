# Instalação Windows — MVP guiado #23

## Estado e dependências

O PR #22 (issue #21) foi integrado por squash na main em
`7cbf8e2918de80d7a7a2ac848ea1ee55ee294808`. O PR #24 foi reaplicado sobre
essa main, contendo somente o incremento do instalador e sua estabilização.
O cofre e as conexões já integrados são reutilizados, sem duplicar seus commits.
A base do PR é main; a CI Windows e o instalador devem ser revalidados nessa base.
Nenhum merge ou release é executado por este trabalho.

A #20 pede entrega rastreável após merge. O workflow Windows installer homologation
produz o instalador tanto em PR quanto em push na main, com commit/canal/checksum.
**Artifact de PR é homologação pré-merge, não release nem prova de commit integrado.**
Para pós-merge, escolher o run de push/main e comparar INSTALLER-INFO.source_commit
com o commit integrado. Esta tarefa não publica tags/releases ou ativa produção.

Assinatura Authenticode ainda não foi configurada/autorizada. O EXE de homologação
é **não assinado** e INSTALLER-INFO declara isso. Não se afirma publisher verificado,
não se instala certificado autoassinado e não se recomenda desabilitar SmartScreen,
Defender ou políticas da empresa. Distribuição comercial exige certificado/serviço
de assinatura e autorização próprios. SHA256 é integridade, não assinatura do editor.

## Usuário final: instalar e abrir

Requisitos: Windows 10/11 x64 ou Windows Server 2019+ com Desktop Experience e
Chrome/Edge moderno já disponível. Não suporta Server Core sem navegador/desktop.
Não exige Python, Node, OCI, PowerShell, edição de JSON ou reboot. Não instala
serviços Windows nem altera outros serviços/portas/firewall.

1. A partir do run de CI aprovado indicado no PR, baixe o artifact
   HUGINN-IA-Setup-homologation-SHA. Extraia o ZIP de artifact do GitHub; dentro,
   abra **HUGINN-IA-Setup.exe**. Acesso a artifacts pode exigir login GitHub.
2. Confira versão, canal TESTE e build no assistente, compatíveis com a evidência
   do fornecedor. Não execute arquivo não verificado; política corporativa pode
   bloquear binários não assinados nesta fase de homologação.
3. Siga o assistente. Por padrão instala somente para o usuário em
   LocalAppData/Programs/HUGINN IA, sem solicitar administrador. Escolha o atalho
   de desktop, se desejado. Menu Iniciar e desinstalador são criados.
4. Ao concluir, selecione **Abrir HUGINN IA e configurar a conexão**. Em próximas
   aberturas, use o atalho. Não é necessário digitar token.
5. No navegador, abra **Configurações → Central de Conexões** pela barra lateral.
   A lista é carregada automaticamente no acesso Windows. Cadastre
   nome, TESTE/PRODUÇÃO, host, porta, Service Name, usuário SELECT-only, schema e
   senha. Peça os dados ao DBA, somente no dispositivo. Não envie credenciais
   a suporte, GitHub ou chat. A senha é protegida por DPAPI CurrentUser.
6. Teste o perfil (somente DUAL), selecione/confirmando ambiente, verifique a
   conexão. Em **Diagnóstico e Suporte**, confira a estrutura. Depois use os
   módulos **Produtos** e **Fornecedores**, separados na barra lateral.
   Seleção não abre conexão permanente; cada operação abre/fecha sessão read-only.
   PRODUÇÃO é rótulo escolhido pelo operador, com confirmação; não valida sozinho
   a identidade do banco nem autoriza escrita/release. CI só usa dados sintéticos.
7. Após reiniciar o app, carregue/selecione o perfil salvo sem reentrar senha.
   A seleção não é restaurada silenciosamente. [Cofre e migração](CONEXOES_SALVAS.md).

Sem Oracle autorizado, a interface identifica a simulação, sem alegar conexão
real. Falhas de rede/listener/permissão/schema têm mensagens sanitizadas. Oracle
real e topologia TOTVS Cloud permanecem pendentes de homologação autorizada.

## Token automático e sessão do navegador

O launcher gera 256 bits aleatórios na primeira abertura Windows e persiste
somente DPAPI binário no diretório privado do usuário/instalação. O token principal
nunca vai a URL, JSON, logs, parâmetros de processo, JavaScript, localStorage ou
sessionStorage. O backend o recebe internamente na memória do processo.

Para acesso pelo navegador, /api/local-session exige Origin/Host exatos, POST
JSON e **SID do processo cliente TCP igual ao usuário do servidor Windows**.
Usa GetExtendedTcpTable e token do processo; se a verificação falhar, recusa sem
fallback anônimo/Origin-only ou campo de token técnico. Assim, outro usuário local
não ganha acesso só por conhecer a porta. Código malicioso executando como o
mesmo usuário/admin/SYSTEM continua fora da proteção de DPAPI, como na #21.

A sessão é um cookie aleatório efêmero, HttpOnly, SameSite=Strict, path /api,
com prazo máximo de 12h e sem Expires/Max-Age persistentes. Não contém o token
principal; JavaScript não o lê. É HTTP somente loopback, não TLS. SID/Origin são
revalidados nas requisições por cookie. Cookies não têm isolamento nativo por
porta: o nome distingue instalação/porta, e a verificação de SID é obrigatória.
O navegador pode restaurar cookies de sessão; encerrar o processo invalida todas
as sessões em memória. Não é SSO/multiusuário nem defesa contra máquina comprometida.

**Recriar acesso local** solicita confirmação, encerra apenas HUGINN e regenera o
token na próxima abertura pelo atalho, mantendo conexões. Se o blob do token estiver
corrompido, o launcher oferece recuperação por confirmação nativa; só recria com
o processo anterior fechado e lock disponível. Não pede edição de arquivo/token.
Se uma sessão expirar, feche e abra pelo atalho para renovar acesso Windows.

O modo de desenvolvimento/portátil anterior continua aceitando o token manual
explicitamente configurado; a experiência instalada usa --desktop internamente.
Não há modo automático sem verificação Windows em Linux/macOS.

## Reabertura e conflito de porta

O supervisor mantém lock e mutex por instalação. Ao reabrir, consulta somente
loopback, compara instalação/versão/porta e valida desafio fresco HMAC com o token
DPAPI antes de abrir a UI existente. Resposta HTTP 200 isolada não comprova identidade.
Redirects/proxies são recusados. Não encerra processos encontrados na porta.

A porta 8000 é preferida. Se estiver ocupada por terceiro, o modo desktop escolhe
uma porta livre gerenciada e constrói os endereços/allowlists do backend a partir
do socket real. Não exige configuração de porta ou reboot. Reabertura usa o
endereço validado, não uma aba de serviço alheio. Falha de identidade é erro
seguro, não permissão para matar processos, trocar DNS ou afrouxar autenticação.
O modo portátil legado conserva o comportamento anterior para compatibilidade.

Use **Encerrar HUGINN** no navegador antes de instalar/atualizar/desinstalar. Fechar
somente a aba não encerra o backend. Um instalador diante do mutex ativo interrompe
e orienta a fechar o próprio app. Nunca solicita reboot para liberar arquivos nem
usa Restart Manager para encerrar outros programas.

## Atualização, rollback e desinstalação

O atualizador existente continua exigindo manifesto Ed25519, hash, versão/canal,
aprovação humana e rollback; publicação/atualizações de clientes permanecem
DESATIVADAS no bootstrap de homologação. Não substituímos esse controle por CI.

O instalador permite reinstalar e fazer manutenção **da mesma família de runtime**.
Runtime é imutável; se o runtime_id divergir, orienta instalação separada, sem
sobrescrever o runtime anterior. A ativação da versão é atômica após health check
local da nova versão; falha preserva o ponteiro anterior. App anterior de família
instalador-aware permanece disponível para recuperação. Não se promete migração
in-place de bootstrap portátil pré-#23 nem rollback entre runtimes incompatíveis.

Na desinstalação interativa, escolha manter ou remover dados. Manter preserva
conexões/token privados para reinstalar na mesma pasta/usuário. Remover apaga o
cofre e estado dessa instalação, sem tocar no Oracle; será necessário recadastrar.
O padrão silencioso preserva; remoção silenciosa requer REMOVEDATA=1 explícito
(somente para administração/testes, não é passo do usuário final).

Se metadados/conexões estiverem irrecuperáveis, encerre HUGINN, desinstale escolhendo
remover os dados e reinstale; não é necessário editar JSON ou ampliar ACLs. Antes,
confirme que pode recadastrar os dados com o DBA. Não inclua o cofre em artefatos
ou backups de suporte. Troca de usuário/caminho exige recadastro, conforme #21.

## Evidência e suporte

CI Windows instala realmente o EXE em pasta limpa, reinstala, exercita navegador
sem token manual, DPAPI, conflito com serviço alheio, reabertura/múltiplas instâncias,
upgrade sintético e desinstalação manter/remover. Testa mocks/ausência de Oracle,
não homologação com cliente. Testes de rollback Ed25519 existentes permanecem.
Os IDs de runs/artifacts e SHA finais são registrados no PR, sem inventar sucesso
por mera existência do workflow. Só artifacts de jobs aprovados são entregues.

Para suporte, informe versão/canal/build, mensagem sanitizada e etapa que falhou.
Não anexe token, Cookie/Authorization, blobs DPAPI, senha, DSN ou dados de cliente.
Acesso Windows indisponível deve ser resolvido no próprio usuário/instalação;
não executar como SYSTEM, desabilitar controles ou reiniciar o servidor.

O primeiro ensaio Windows compilou MSVC/Inno com sucesso e detectou uma regressão
no diagnóstico legado com Origin válido (conflito de nome de função). A correção
preserva a allowlist e ganhou teste específico; artifacts não são entregues
a partir daquele run falho. Os IDs finais aprovados ficam no PR.

O modo instalado conserva logs sanitizados em state/diagnostics.jsonl (códigos
fixos de abertura/identidade) e state/audit.jsonl (auditoria estruturada da #18,
com rotação e ACL privada). Não redireciona stderr bruto do driver para suporte.
Compartilhe somente esses arquivos após revisão; nunca o diretório state inteiro,
cofre, request.json ou tokens. O fechamento de console não é necessário para
coletar diagnóstico, e o instalador não registra corpos/credenciais.

A estabilização adicional verifica no smoke Windows DUAL, diagnóstico e resultados
de produtos/fornecedores na UI usando um driver sintético apenas na instalação
descartável de CI. O instalador disponibilizado não contém esse driver. A prova de
identidade inclui o commit do build e é obrigatória também na primeira abertura.
Esta evidência não confirma conectividade nem permissões de um Oracle real.

## Atualizar instalações anteriores — #27 / Setup 0.3.1

Execute somente o Setup novo, **no mesmo usuário Windows da instalação anterior**.
O assistente encontra o AppId HUGINN IA no registro HKCU de 64 bits, recupera a
pasta usada anteriormente e mostra versão ativa → nova versão. Verifique o resumo
e clique em Instalar. Não desinstale primeiro, não use PowerShell e não mova a pasta:
o caminho canônico é parte da identidade das conexões e do token DPAPI.

O próprio Inno atualiza a instalação no mesmo diretório, mantendo o mesmo AppId,
atalhos e um catálogo de desinstalação. Não executamos dois desinstaladores nem
apagamos a versão anterior antes de confirmar a nova. Se HUGINN estiver aberto,
o Setup valida desafio HMAC de instalação/versão/build com o token DPAPI e usa
uma sessão local vinculada ao SID Windows para solicitar encerramento. Aguarda
liberação do lock, saída do backend e do executável próprio; não usa taskkill,
PIDs recebidos de arquivo, encerramento de serviços ou reboot. Falha de identidade
bloqueia a migração; encerre somente seu HUGINN pela interface e tente novamente.

Durante a cópia o Setup mantém um lock de SO que impede outro supervisor de
iniciar. O launcher novo reconhece manutenção incompleta e orienta aguardar ou
repetir o Setup. Instalações/runtime/canal incompatíveis, downgrade da versão
ativa ou tentativa de mudar o diretório registrado são recusados preservando
os dados. Atualização remota pendente deve ser recuperada pelo próprio HUGINN
antes de executar o Setup; não combinamos dois journals de atualização.

### Dados, backups e recuperação

As conexões, senha DPAPI, token e configurações não são recriados. O cofre permanece
em LocalAppData/HUGINN/Connections, com o mesmo usuário, entropia e identidade.
Depois que o aplicativo reabre, selecione novamente o destino salvo; PRODUÇÃO
continua exigindo confirmação explícita. Não é preciso redigitar a senha salva.
O health check da migração não conecta ao Oracle nem altera permissões ou dados.

Antes de copiar arquivos, o Setup cria `.installer-backup` na própria instalação,
com ACL privada do usuário/SYSTEM. Guarda os binários que serão substituídos,
configurações/apontador, registro e atalhos, mais cópias dos blobs já criptografados
e metadados do cofre. Não exporta senha/token em claro. Conserva somente o último
backup reconhecido; uma pasta/arquivo desconhecido dentro desse espaço interrompe
a rotação sem ser apagado. A migração seguinte prepara outro antes de alterar a instalação.

Todos os novos arquivos catalogados são verificados por SHA256 e a nova aplicação
precisa confirmar sua versão HTTP em uma porta própria de teste. Somente então
concluímos a transação. Falha de cópia/integridade/saúde restaura binários,
apontador, registro e atalhos anteriores, sem remover arquivos extras do
usuário. O Setup nunca altera o cofre/preferências em uso e o rollback não
sobrescreve edições de dados que o usuário possa ter feito após uma interrupção;
as cópias criptografadas permanecem privadas para suporte. É possível abrir novamente o HUGINN anterior pelo atalho após rollback.

Se faltar energia ou o Setup for interrompido, execute o Setup novamente **na
mesma pasta/usuário**. Ele recupera a transação pendente antes de fazer nova cópia.
Se o backup estiver corrompido, sem espaço ou bloqueado por outro processo, a
recuperação é recusada; preserve a pasta e procure suporte. Não apague o backup,
state, runtime ou versões e não reinicie o Windows para tentar liberar arquivos.
Backup com identidade/SID diferente, junction/symlink, UNC e unidade de rede são
recusados. Não copie o backup para outro usuário ou caminho.

Não envie `.installer-backup`, cofre, logs completos ou arquivos de configuração
ao GitHub/chat: podem conter metadados privados e ciphertext. Informações de
suporte devem limitar-se à versão e ao código fixo exibido pelo assistente.

### Cópias portáteis e desinstalação

Não pesquisamos nem removemos cópias em discos/pastas arbitrários. Uma instalação
registrada tem prioridade e é atualizada onde está. Uma cópia portátil em outra
pasta continua separada e intocada. Sem instalação registrada, é possível selecionar
no assistente a própria pasta portátil de família/runtime compatíveis; a conversão
no mesmo local mantém a identidade DPAPI, se já existente. Portáteis antigos sem
protocolo de identidade/token persistido devem ser fechados pelo seu próprio
inicializador antes de converter. Não inventamos credenciais que não estavam
salvas nem migramos segredos de outro usuário/instalação.

Na desinstalação final, **manter dados** continua sendo o padrão. Mantém cofre,
preferências e backup privado para reinstalar na mesma pasta/usuário. O Setup
reconhece esse estado mesmo que só tenham restado configurações, cache e arquivos
do usuário. Remover dados é uma decisão explícita e remove também o backup privado.
O novo Setup substitui o catálogo antigo de uninstall para não herdar ações
recursivas das versões antigas. O desinstalador usa os arquivos catalogados pelo
Inno e uma lista fixa dos arquivos de runtime do pacote: não faz mais remoção
recursiva de runtime/versions, evitando apagar arquivos extras do usuário. Pastas,
cache Python, payloads anteriores de recuperação e arquivos não catalogados podem permanecer; não são outra instalação
ativa. A opção de remover dados nunca apaga o Oracle ou documentos extras.

### Validação

CI compila EXEs dos commits reais de 0.2.0 e 0.3.0 e testa atualização/reinstalação
para 0.3.1. Também converte um ZIP portátil 0.2.0 compatível, preservando uma segunda
cópia portátil. Com DPAPI/SID reais verifica bytes de perfis/token, preferências,
atalhos/registro, descriptor forjado apontando para serviço alheio, instância ativa,
falha de um EXE depois da cópia, rollback e recuperação de transação interrompida.
Desinstala mantendo/removendo dados e confirma preservação de arquivos extras e
serviço na porta 8000. Consultas Oracle usam driver sintético somente na cópia
descartável de CI; não comprovam o Oracle do cliente. Runs/artifact finais no PR #28.
