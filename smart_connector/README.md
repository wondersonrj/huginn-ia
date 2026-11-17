# HUGINN Smart Connector 0.2.1

Serviço Windows x64 independente do aplicativo desktop HUGINN IA. Oferece API
Oracle de leitura usando **python-oracledb Thin**, sem OCI, Oracle Client, Python,
PyInstaller ou Inno Setup instalados pelo cliente. Windows 10/11 e Windows Server
2019+ x64, com permissão administrativa para instalar. Porta local padrão: 8765.

## Origem e estado da entrega

Não havia fontes ou ZIP do **Smart Connector v0.2.0** neste repositório na base
`ee87f523c80b78ecefd300dc5191c8943c16b7ff`. Os instaladores anteriores em
`packaging/windows` pertencem ao aplicativo desktop HUGINN IA. Este diretório é
uma implementação nova e revisável do contrato da Issue #36; não é apresentado
como importação nem migração comprovada de um ZIP externo não disponibilizado.

O Setup é um **candidato para validação**, sem assinatura Authenticode. Não está
homologado para TOTVS Cloud. Apenas uma execução bem-sucedida do workflow
**Smart Connector Windows Setup** com a etapa de testes Windows aprovada permite
afirmar que aquele commit gerou e passou nos testes automatizados do instalador.
Oracle real, sessão WinThor Cloud, SmartScreen e instalação em VM limpa do cliente
são validações separadas, ainda necessárias. CI não recebe credenciais Oracle.

## Baixar e instalar

1. Abra **Actions → Smart Connector Windows Setup → execução verde do commit/PR**.
2. Em **Artifacts**, baixe `HUGINN-Smart-Connector-0.2.1-Windows-<run_id>` e extraia.
   Os artefatos ficam disponíveis por 30 dias; requerem acesso ao GitHub. Não use
   artefatos de outros workflows como se fossem o Smart Connector.
3. Confira `Get-FileHash .\HUGINN_Smart_Connector_Setup.exe -Algorithm SHA256`
   contra o arquivo `.exe.sha256` recebido pelo canal confiável do projeto. Hash
   não substitui assinatura digital nem autenticação da origem.
4. Execute `HUGINN_Smart_Connector_Setup.exe` como administrador. O assistente
   permite informar host Oracle, porta, **Service Name**, usuário e senha.
   Use uma conta dedicada com apenas os grants SELECT estritamente necessários.
5. Mantenha `127.0.0.1` e porta 8765 inicialmente. O token da API é gerado com
   aleatoriedade criptográfica; o campo mascarado permite selecionar/copiar
   para o cliente autorizado. Não envie o token em URL ou logs.
6. Clique **Testar Oracle** (faz conexão Thin e `SELECT 1 FROM DUAL`) e **Salvar**.
   É possível instalar sem Oracle configurado para validar somente serviço/API.
   O serviço `HUGINNSmartConnector` inicia automaticamente como **LocalService**.

O menu Iniciar oferece **Configurar Smart Connector**, que solicita elevação UAC.
Após alterações, reinicie em `services.msc`. Configuração inválida não é salva.
Em instalação silenciosa (`/VERYSILENT /SUPPRESSMSGBOXES /NORESTART`), o assistente
não abre e somente valores locais seguros são inicializados. Configure depois
pela interface; senhas nunca são recebidas por argumento de linha de comando.

## API e segurança

Todas as operações GET exigem `Authorization: Bearer <token>`, inclusive health.
Não há CORS, endpoint de configuração remota, execução de SQL informado pelo
cliente, escrita ou proxy genérico para banco.

| Rota | Resultado |
| --- | --- |
| `/health` | Estado do processo, versão e presença de configuração Oracle; não garante conexão Oracle |
| `/oracle/test` | `SELECT 1 FROM DUAL`, sessão read only, resposta 503 genérica em falha |
| `/oracle/server-time` | `SELECT SYSTIMESTAMP FROM DUAL`, leitura fixa autorizada |

Exemplo em PowerShell, com token obtido em canal seguro e mantido em memória:

```powershell
Invoke-RestMethod http://127.0.0.1:8765/health -Headers @{ Authorization = "Bearer $token" }
```

SQL adicional exige alteração revisada da allowlist no código e novos testes.
Cada conexão verifica modo Thin, aplica `SET TRANSACTION READ ONLY`, timeout TCP
de 5 s e timeout de chamada de 5 s; não confie nisso para substituir grants do
DBA. A API não retorna exceções brutas do driver. Não registra paths de requisição,
cabeçalhos, SQL, senhas ou resultados. Logs rotacionam em 1 MiB com cinco backups.

Configuração inteira, incluindo senha Oracle e token, fica em
`%ProgramData%\HUGINN\SmartConnector\config.dpapi`, criptografada com Windows
DPAPI **LocalMachine**. A ACL remove herança e autoriza somente SYSTEM,
Administradores e LocalService. A proteção depende tanto de DPAPI quanto da ACL:
administradores e processos da conta LocalService estão dentro da fronteira de
confiança. Não troque a conta do serviço sem revisar ACL e modelo de segurança.
O diretório Program Files é protegido por ACL padrão do Windows. Não coloque
chaves TLS em diretórios graváveis por usuários comuns. Dê à LocalService leitura
somente do certificado/chave e proteja a chave de todos os demais usuários.

O assistente só permite escuta fora de `127.0.0.1` com autorização explícita e
certificado/chave PEM TLS. O serviço exige TLS 1.2+ e falha fechado se não conseguir
carregar o certificado. Use certificado válido para o hostname utilizado pelo
cliente. Nenhuma regra de firewall, NAT ou publicação de internet é criada.

## Oracle 19c e WinThor TOTVS Cloud

Oracle 19c é compatível com python-oracledb Thin, sujeito a autenticação e rede
compatíveis. Confirme com DBA: Service Name correto (não SID), listener alcançável,
verificador de senha suportado (11G/12C; contas somente 10G exigem atualização),
e política de criptografia. Native Network Encryption/checksumming obrigatório e
autenticação externa dependente de OCI não são atendidos por este pacote Thin;
alinhe uma conexão TCPS/TLS suportada com o DBA em vez de instalar OCI como remendo.
Para TCPS, esta versão precisa de extensão revisada da configuração Oracle; os
campos atuais configuram conexão TCP. Não desabilite política de segurança do banco.

O conector roda na máquina externa com acesso autorizado ao Oracle. A aplicação
Delphi PCINF9803.EXE/FireDAC não é alterada por esta entrega: ela ou outra rotina
deverá consumir a API, em vez de tentar carregar OCI no TOTVS Cloud. O cliente
HTTP deve enviar o token, validar certificado e lidar com 401/503 e timeouts.

Antes de autorizar uso remoto:

1. Obtenha aprovação do administrador TOTVS/rede e identifique DNS e rota privada,
   VPN ou túnel autorizado da sessão Cloud até o conector.
2. Configure certificado/chave, IP privado de escuta e autorização no assistente.
3. Restrinja firewall da máquina à porta HTTPS escolhida e às origens autorizadas.
   Não exponha diretamente à internet. Não encaminhe a porta Oracle ao Cloud.
4. Teste `/health` via **HTTPS a partir da sessão WinThor Cloud**, com validação
   de certificado e token; depois `/oracle/test` contra Oracle autorizado.
5. Registre Windows/Oracle, data, versão/commit, evidência sem segredos, resultado
   e responsável. Só esse processo pode subsidiar homologação TOTVS Cloud.

## Atualização, desinstalação e rollback

Execute o novo Setup como administrador no mesmo diretório. Ele para o serviço,
substitui o programa, preserva configuração/token/logs em ProgramData e inicia
novamente com inicialização automática. A configuração é carregada no início do
serviço. Não há migração presumida de outro produto ou kit externo v0.2.0.

Antes de atualizar, mantenha uma cópia confiável do Setup anterior e backup
administrativo do diretório ProgramData. A cópia DPAPI só é recuperável na mesma
máquina/contexto Windows: para migrar de máquina, reconfigure credenciais pela UI.
Se o Setup falhar, veja o log do instalador em `%TEMP%` e o Visualizador de Eventos,
confira portas, configuração, permissões e TLS. Reinstale o Setup anterior na mesma
pasta e reinicie o serviço. Rollback é **operado pelo administrador**, não automático;
não restaura alterações Oracle. Teste antes de qualquer janela de produção.

Em Aplicativos/Programas, desinstale **HUGINN Smart Connector**. O desinstalador
para e remove o serviço e os binários. Por padrão preserva dados para reinstalação;
na interface há confirmação opcional para apagar configuração, credenciais e logs.
Desinstalação silenciosa preserva os dados. Para apagar explicitamente em operação
silenciosa use `unins000.exe /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /PURGEDATA=1`.
A remoção dos backups deve seguir a política da organização.

## Build e evidências

O workflow `smart-connector-windows.yml` usa `windows-latest`, CPython 3.12.10 x64,
dependências/build/testes fixados e hashes de wheels em `windows/requirements.lock`,
PyInstaller 6.16.0 e Inno Setup 6.4.3 validado por SHA-256. O cliente recebe o
runtime e as DLLs no instalador. A imagem `windows-latest` pode mudar: as versões
de ferramentas/dependências são reproduzíveis, mas não se promete binário idêntico
bit a bit (timestamps e imagem do runner influenciam).

CI verifica autenticação, allowlist, redaction, bloqueio remoto/TLS, DPAPI e ACL;
compila Setup; instala sem Python/OCI no PATH do instalador; executa o runtime
embutido; verifica serviço automático LocalService e health autenticado; testa
stop/start, atualização de fixture sintética com metadata 0.2.0 para 0.2.1,
preservação de configuração/token/logs e desinstalação/reinstalação. Essa fixture
usa o código atual, não comprova migração do kit externo. O runner tem ferramentas
de build instaladas; não equivale a uma VM Windows recém-instalada. O relatório
`windows-test-results.json` documenta essas limitações e os testes não realizados.

Para validação independente, use VM Windows x64 limpa sem Python ou Oracle Client,
instale exclusivamente o Setup e repita instalação/configuração/serviço/health,
reinicialização da máquina, atualização e desinstalação. Teste também o assistente
interativo, UAC, TLS com certificado da organização e a remoção opcional de dados.

Fontes: `config.py` (DPAPI/ACL), `api.py` (HTTP/TLS/Oracle), `wizard.py` (UI),
`entry.py` e `maintenance.py` (SCM), `windows/connector.iss`, `windows/build.ps1`,
`windows/smoke.py`, `tests/test_connector.py`. Para testes locais sem Windows:
`python -m pytest -q -o pythonpath=. smart_connector/tests` (DPAPI é pulado).
