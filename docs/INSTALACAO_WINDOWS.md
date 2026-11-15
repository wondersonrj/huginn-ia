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
5. No navegador, Conexões Oracle salvas é carregado automaticamente. Cadastre
   nome, TESTE/PRODUÇÃO, host, porta, Service Name, usuário SELECT-only, schema e
   senha. Peça os dados ao DBA, somente no dispositivo. Não envie credenciais
   a suporte, GitHub ou chat. A senha é protegida por DPAPI CurrentUser.
6. Teste o perfil (somente DUAL), selecione/confirmando ambiente, verifique a
   conexão e confira a estrutura. Só então pesquise produtos/fornecedores.
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
