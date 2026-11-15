# HUGINN IA — consultas WinThor somente leitura (#18)

## Entrega e evidência disponível

A interface oferece status autenticado, produtos, fornecedores, filtros por
código/nome, paginação e diagnóstico da estrutura. Reutiliza React/TypeScript,
FastAPI, python-oracledb e o pacote Windows existentes. Não integra SEFAZ,
entradas NF-e, custos/pedidos nem faz conciliação automática do XML com o ERP.

**Não houve conexão a Oracle real nesta implementação:** não foram fornecidos
credenciais, schema ou rede de um ambiente autorizado. O aceite usa o modo
simulado explícito, permitido na issue #18. Seus 55 produtos e 27 fornecedores
são sintéticos. Nesse modo, conectado=false, modo=simulado e a tela informa
“SIMULAÇÃO — dados fictícios, sem Oracle”. Nenhum schema de cliente está confirmado.
Resultados reais só podem ser afirmados depois do ensaio autorizado abaixo.

## Configuração segura e inicialização

Use uma sessão local do sistema operacional pertencente ao operador autorizado.
Não use setx, arquivo .env versionado, argumentos de linha de comando com senhas,
URL de conexão na interface, tickets ou chat para transmitir credenciais.
O backend recebe configuração exclusivamente por variáveis de ambiente; o modo
não pode ser trocado por uma requisição HTTP. Não há cache/persistência de senha
pela aplicação. Variáveis de ambiente ficam na memória do processo e são
acessíveis a processos/administradores autorizados do sistema: não equivalem a
um cofre criptográfico. Proteja a estação e encerre a sessão ao terminar.

| Variável | Valor / requisito |
| --- | --- |
| HUGINN_API_TOKEN | token aleatório de pelo menos 32 caracteres, exclusivo desta estação; obrigatório inclusive na simulação |
| HUGINN_WINTHOR_MODE | demo (padrão) ou oracle; valor desconhecido bloqueia a API |
| HUGINN_ORACLE_HOST | host/IP IPv4 ou DNS autorizado, sem URL/DSN |
| HUGINN_ORACLE_PORT | porta TCP 1–65535; padrão 1521 |
| HUGINN_ORACLE_SERVICE | Service Name confirmado pelo DBA, não SID |
| HUGINN_ORACLE_USER | conta com CREATE SESSION e somente SELECT nas tabelas autorizadas |
| HUGINN_ORACLE_PASSWORD | segredo informado localmente; nunca devolvido à interface |
| HUGINN_ORACLE_OWNER | schema explícito em maiúsculas, identificador convencional de até 30 caracteres; obrigatório em oracle |

### Windows portátil

1. Gere um token aleatório em seu gerenciador de senhas. Mantenha-o disponível
   para informar novamente no campo da interface. Não use a senha do Oracle como token.
2. Abra PowerShell na pasta extraída do pacote e carregue o token sem exibi-lo:

```powershell
function Ler-SegredoLocal([string]$Mensagem) {
    $valor = Read-Host $Mensagem -AsSecureString
    $cred = New-Object System.Management.Automation.PSCredential('local', $valor)
    return $cred.GetNetworkCredential().Password
}
$env:HUGINN_API_TOKEN = Ler-SegredoLocal 'Token local aleatorio (32+ caracteres)'
$env:HUGINN_WINTHOR_MODE = 'demo'
.\INICIAR_HUGINN.bat
```

3. Abra http://127.0.0.1:8000, informe o mesmo token em **Consultas WinThor** e
   clique **Verificar conexão WinThor**. Pesquise produtos/fornecedores. A senha
   Oracle não é solicitada por essa seção e não atravessa o navegador.
4. Para banco autorizado, encerre a aplicação e configure na mesma sessão:

```powershell
$env:HUGINN_WINTHOR_MODE = 'oracle'
$env:HUGINN_ORACLE_HOST = 'HOST_AUTORIZADO'
$env:HUGINN_ORACLE_PORT = '1521'
$env:HUGINN_ORACLE_SERVICE = 'SERVICE_NAME_CONFIRMADO'
$env:HUGINN_ORACLE_USER = 'CONTA_SELECT'
$env:HUGINN_ORACLE_OWNER = 'SCHEMA_CONFIRMADO'
$env:HUGINN_ORACLE_PASSWORD = Ler-SegredoLocal 'Senha Oracle (nao exibir)'
.\INICIAR_HUGINN.bat
```

5. Ao terminar, Ctrl+C encerra o servidor; feche o PowerShell para descartar as
   variáveis. **Encerrar acesso** limpa token/resultados da página, mas não
   remove configuração do processo nem encerra o servidor. Rotação do token
   exige alterar a variável e reiniciar. Recarregar a página também perde acesso.

O pacote não exige Python, Node ou Oracle Client instalados no cliente. O driver
Thin é obrigatório; não se chama init_oracle_client nem se aceita Thick já
inicializado no processo. A preparação de um novo pacote usa o CI habitual;
esta tarefa não publica release nem reconfigura um cliente existente.

### Desenvolvimento Linux/Windows a partir do código

Instale Python 3.12 e Node 20/22. Crie ambiente virtual, instale
backend/requirements.txt e execute npm ci em frontend. Configure o token e as
variáveis na sessão local antes do servidor. Em Bash, `read -r -s` permite ler
segredos sem colocá-los no histórico; exporte a variável sem imprimir seu valor.
Não cole valores em comandos registrados por ferramentas compartilhadas.

```sh
python -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 --no-access-log
# Em outro terminal: npm run dev --prefix frontend
```

Use somente localhost/127.0.0.1 nas portas 8000 ou 5173. O proxy Vite encaminha
/api ao backend local. Não há suporte a hospedagem pública ou multiusuário nesta
entrega. O token autoriza o operador local; não é login individual, RBAC, SSO ou
trilha inviolável de autoria por pessoa. Não exponha listener Oracle ou backend
à Internet. Em TOTVS Cloud, conectividade privada/VPN, firewall/IP autorizado,
Service Name e política de criptografia/autenticação precisam de liberação do
DBA/provedor; o mesmo Thin é usado. Essa topologia não foi validada aqui.

## Estrutura e SQL de leitura

Mapeamentos candidatos, **verificados em runtime antes de cada consulta**:

| Cadastro | Tabela | Código exigido | Nome exigido |
| --- | --- | --- | --- |
| Produtos | PCPRODUT | CODPROD, NUMBER | DESCRICAO, VARCHAR2/NVARCHAR2/CHAR/NCHAR |
| Fornecedores | PCFORNEC | CODFORNEC, NUMBER | FORNECEDOR, VARCHAR2/NVARCHAR2/CHAR/NCHAR |

Não são nomes universalmente confirmados de todas as instalações WinThor. Antes
de ler registros, o backend consulta ALL_TAB_COLUMNS com JOIN ALL_TABLES,
owner/tabela/colunas vinculados por parâmetros. Schema ausente, sem SELECT,
coluna divergente ou tipo incompatível resulta em 409, sem leitura comercial.
Homônimos não são misturados; owner é obrigatório. Não resolve sinônimos/views,
identificadores citados em minúsculas ou schema alternativo automaticamente.
Se o schema real divergir, registrar apenas metadados autorizados e revisar o
mapeamento em novo PR; nunca aceitar nomes/SQL enviados pelo navegador.

O SELECT comercial retorna exclusivamente código e nome, qualificados pelo
schema validado e nomes fixos. Código, texto, offset e limite são binds.
O filtro de texto procura substring sem distinção de maiúsculas; %, _ e barra
invertida são escapados como literais. Não remove acentos. A ordenação é por
código e nome; cada página é uma nova transação, portanto mudanças externas no
ERP podem deslocar registros entre páginas. Não há snapshot compartilhado,
COUNT total, exportação nem cache de resultados. Busca por código e nome
simultâneos usa AND.

Tamanho 1–50 (20 padrão), página 1–100, código inteiro 1–9999999999, nome até
80 caracteres. OFFSET/FETCH NEXT limitam a consulta a tamanho+1; fetchmany
permite calcular próxima página sem ler todos os registros. Limite_atingido
indica o teto da página 100. Consultas amplas podem exigir índices/análise pelo
DBA; o aplicativo não cria índices nem altera schema.

Toda conexão configura SET TRANSACTION READ ONLY antes do SELECT, timeout de
chamada de 5000ms, conexão TCP de 5s, sem retries. Fecha em finally, inclusive em
falha, sem commit. Isso é proteção adicional: o DBA deve garantir privilégios
somente leitura, sem DML/DDL, pacotes com escrita ou privilégios administrativos.
O aplicativo não concede permissões nem comprova sozinho a ausência de todos
os privilégios da conta. Timeout é por chamada/roundtrip, não prazo global do
endpoint. Cancelar o fetch no navegador após 30s não cancela imediatamente o
trabalho do driver, que continua sujeito aos limites e ao fechamento da sessão.
O formulário avulso legado conserva seu timeout de navegador de 20s.

## API autenticada e auditoria

Todas as operações abaixo usam POST, Authorization: Bearer no header e JSON;
filtragem nunca passa na query string. Token e dados não são persistidos em
localStorage/sessionStorage ou cookies. Nenhum endpoint devolve o token/senha,
host, DSN ou mensagem bruta do driver. Respostas Oracle recebem Cache-Control:
no-store. Além do token, são exigidos cliente loopback, Host exato local e Origin
local quando presente. Falhas de autenticação não chegam ao driver. Isso limita
ataques de sites externos e DNS rebinding; não protege contra uma estação já
comprometida ou administrador do sistema.

| Endpoint | Corpo | Resultado |
| --- | --- | --- |
| /api/winthor/health | {} | modo, disponibilidade e confirmação DUAL (conectado=false em demo) |
| /api/winthor/diagnostico | {} | duas estruturas candidatas; validade real somente após metadata Oracle |
| /api/winthor/produtos | codigo, nome, pagina, tamanho opcionais | itens codigo/nome, pagina, tamanho, tem_proxima, limite_atingido |
| /api/winthor/fornecedores | mesmos filtros | mesmo contrato para fornecedores |

Request_id único acompanha resultados e erros (header X-Request-ID nos erros).
JSON desconhecido/SQL arbitrário/campos extras são recusados; corpo até 2048
bytes. 401: token inválido; 403: acesso externo; 409: schema não confirmado;
413/415/422: corpo/filtros inválidos; 503: configuração ausente/inválida;
502: erro Oracle/timeout com orientação fixa. ORA-01017/28000/28001, erros de
listener, falta de SELECT/coluna e timeouts recebem diagnóstico sem texto bruto.

O logger huginn.audit emite uma linha JSON por operação, incluindo recusas:
instante UTC, UUID, ação fixa, modo, status HTTP, quantidade e duração. Não grava
código/nome pesquisado, resultados, usuário/senha, token, DSN ou corpo do erro.
Saída padrão de erro é a trilha local; o operador pode redirecioná-la a arquivo
fora do pacote, com ACL restrita, rotação e retenção definidas pela organização.
A aplicação não armazena log comercial em disco, não envia telemetry e não
fornece auditoria imutável. Não habilitar debug/log bruto de HTTP/driver em cliente.

Os endpoints legados /api/oracle/testar e /api/oracle/diagnostico agora também
exigem o mesmo token e são auditados. Seu formulário avulso envia credenciais
apenas para a tentativa local, limpa a senha e não configura as consultas novas.
Para consultas persistentes, configurar as variáveis do servidor. /api/health
é apenas liveness legado e não comprova conexão Oracle; use o health autenticado.
NF-e/atualizador conservam o escopo anterior e não ganham autorização Oracle.

## Teste de aceite em banco autorizado (pendente)

1. DBA confirma conta de leitura, rede privada, owner, objetos e colunas. Não
   informar credenciais em issue pública. Carregar segredos apenas na estação.
2. Verificar conexão: exigir modo oracle, conectado=true. Conferir estrutura:
   os dois objetos precisam estar validados_no_oracle=true.
3. Consultar códigos conhecidos de teste em produtos/fornecedores, filtrar nomes,
   percorrer páginas, validar valores contra uma consulta SELECT do DBA e obter
   autorização para qualquer evidência. Não anexar registros de clientes ao repo.
4. Testar conta sem SELECT, schema divergente, listener indisponível e token
   incorreto sem liberar privilégio adicional. Confirmar auditoria sem segredos.
5. Registrar data/topologia autorizada, versão Oracle/driver, SHA do pacote e
   resultado agregado (sem credenciais/dados). Nunca marcar BUILD-INFO como
   oracle_real_validated apenas porque mocks, demo ou CI passaram.

A validação automatizada usa fixtures/mocks e proíbe conexões Oracle reais.
O navegador exercita a API demo real, filtros, paginação, fornecedor, vazio,
erro/recuperação, diagnóstico e encerramento do acesso. As rotas avulsas de
Oracle continuam simuladas no navegador. Smoke, atualização/rollback e testes
do runtime são executados no Windows CI; resultados Linux não são evidência de
binários Windows. Os IDs/SHAs finais de CI ficam na descrição do PR da #18.

## Evidência local desta implementação

- Suíte backend: 228 aprovados, 1 ignorado (caso nativo de arquivo em uso Windows).
- TypeScript/Vite, npm audit de produção (zero vulnerabilidades), actionlint
  1.7.12 e git diff --check aprovados.
- ZIP gerado e smoke executado em Linux com Python Linux isolado: startup,
  API, XML, rejeição autenticada de entrada Oracle inválida e porta ocupada.
- Chromium sobre assets de produção e API demo real: consultas, filtros,
  páginas, vazio, erro/recuperação, estrutura simulada, logout, mobile e
  regressões de XML/diagnóstico/atualizador passaram.
- Atualização A→B e rollback de versão quebrada foram exercitados com o
  interpretador Linux; a confirmação de binários Windows depende da CI do PR.

O primeiro ensaio Linux precisou de venv porque o launcher usa -I e não herda
as dependências Python da sessão. O navegador também detectou e levou à
correção de rótulos acessíveis dos seletores. As execuções finais passaram.
Não se guardam logs brutos ou registros de clientes como evidência.

## Perfis persistentes Windows — issue #21

O [gerenciador de conexões salvas](CONEXOES_SALVAS.md) acrescenta senha DPAPI por
usuário/instalação, metadados privados, edição/exclusão e seleção explícita.
A configuração por ambiente acima continua como legado/migração, sem fallback
automático quando um catálogo gerenciado exige seleção ou está corrompido.
As consultas preservam schema validado, binds, SELECT-only e token local.
O teste pontual do perfil não configura uma sessão permanente; após reiniciar,
carregue a lista e selecione novamente sem reentrar a senha Oracle.
