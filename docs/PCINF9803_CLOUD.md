# PCINF9803 e Smart Connector: diagnóstico HTTPS e integração controlada

## Para quem está na máquina do conector

Não é necessário escolher IP nem abrir porta agora.

1. Abra **Iniciar → Configurar Smart Connector**.
2. Leia os campos **IP de escuta API** e **Porta API**. O padrão do PR #37 é
   `127.0.0.1` e `8765`. Não compartilhe senha Oracle nem token.
3. Se esses valores estiverem no padrão, o conector está acessível apenas naquela
   máquina. Isso não é erro de Oracle; o acesso pelo Cloud exige uma rota HTTPS.
4. Peça ao administrador de rede/TOTVS um endereço HTTPS autorizado para esse
   conector. Não troque para IP aleatório nem encaminhe portas no roteador.

A URL não é criada simplesmente digitando um nome. O administrador precisa
provisionar DNS, rota e certificado. Exemplo ilustrativo (não é endereço real):
`https://conector.exemplo.invalid:8765`. Certificado deve ser válido para o nome,
e a sessão WinThor precisa alcançar o destino. Não publique Oracle na internet.

## Estado real e dependências

Revisão do PR #37 no commit `495dbe82c7c6b6e07b4432815944c77e6aa60308`:

| Item | Implementação inspecionada |
| --- | --- |
| Serviço | `HUGINNSmartConnector`, automático, LocalService |
| Autenticação | Bearer obrigatório, inclusive health |
| Health | `GET /health`, status/versão; não garante Oracle |
| Teste Oracle | `GET /oracle/test`, `SELECT 1 FROM DUAL`, Thin/read only |
| Relógio Oracle | `GET /oracle/server-time`, `SELECT SYSTIMESTAMP FROM DUAL` |
| Escuta | `127.0.0.1:8765` por padrão |
| HTTPS | Certificado/chave PEM; interface externa exige TLS e autorização explícita; TLS 1.2+ |
| Segredos | DPAPI LocalMachine + DACL SYSTEM/Administradores/LocalService no servidor |
| Financeiro | Nenhuma operação dos cinco módulos está implementada no PR #37 |

A Issue #38 confirma, pelo relato do usuário, instalação externa e conexão Oracle
funcionando. **Isso não comprova Cloud → conector**. Não recebemos endereço HTTPS,
acesso à sessão WinThor, fontes Delphi/DFM/DPROJ nem SQL original do PCINF9803.
A busca no repositório e releases não encontrou esses fontes. Portanto não houve
teste real dessa rota, nem bloqueio de rede observado, nem aprovação de um plano
de rede. O registro de impedimentos distingue ausência de acesso de falha de rede:
[ISSUE_38_EVIDENCIAS.json](incidentes/ISSUE_38_EVIDENCIAS.json).

Este PR depende do PR #37 e usa sua branch como base para manter a revisão
incremental. Não faz merge dessa dependência nem declara a Issue #38 concluída.

## Rodar diagnóstico dentro da sessão WinThor Cloud

1. Obtenha a URL HTTPS final e o token em canal seguro com o administrador.
2. Baixe o artefato **HUGINN-Cloud-Diagnostics-<run>** do workflow **Cloud HTTPS
   diagnostics and contracts**. Extraia `HUGINN_Cloud_Diagnostics.zip` inteiro.
3. Copie essa pasta **para a sessão Windows em que PCINF9803.EXE roda**. Executar
   na máquina externa ou no computador pessoal não valida a origem Cloud.
4. Abra `DIAGNOSTICAR_CLOUD.cmd`. Digite a URL, depois o token na entrada oculta.
   Se política de scripts bloquear, solicite liberação/assinatura ao administrador;
   não use ExecutionPolicy Bypass nem desative controles da sessão.
5. Registre resultado JSON, data, operador e confirmação da sessão de origem.
   O relatório não guarda token, senha, cabeçalhos, corpo de resposta ou exceção
   bruta; o nome do destino é parte da evidência e pode ser interno/confidencial.

Também é possível executar no Windows PowerShell 5.1 ou PowerShell Windows:

```powershell
.\Test-HuginnCloud.ps1 -BaseUrl https://conector.exemplo.invalid:8765
# Só após autorização para SELECT 1 no Oracle externo:
.\Test-HuginnCloud.ps1 -BaseUrl https://conector.exemplo.invalid:8765 -OracleReadTest
```

O token não é parâmetro nem variável de ambiente. Não informe senha Oracle no
Cloud. Não execute com transcrição/captura de entrada habilitada. O teste Oracle
é opt-in e usa exclusivamente a operação real `/oracle/test`.

O diagnóstico usa **WinHTTP**, como o adaptador Delphi, proxy pré-configurado do
Windows, timeout por fase de 1–30 s (padrão 5), TLS 1.2 com validação normal de
cadeia/hostname/validade e redirects desativados. Não envia automaticamente
credenciais Windows. Não aceita credenciais, query, fragmento ou caminho na URL.
WinHTTP pode ter proxy diferente do navegador, de variáveis de ambiente e do
aplicativo HUGINN desktop. Confirme com TI a política WinHTTP da sessão, inclusive
autenticação de proxy. Não se infere sucesso a partir do navegador de outra máquina.

Sondagens DNS/TCP diretas são informativas: um proxy pode resolver/alcançar o
destino mesmo quando elas falham. Não bloqueiam o teste HTTPS. Cada fase tem
timeout próprio, portanto o tempo total pode exceder o valor de uma fase.

| Resultado | Próxima ação |
| --- | --- |
| `ok` em HTTPS autenticado | Origem testada alcançou health; ainda não valida relatório/Oracle |
| `dns_failed` | Confira DNS dentro da sessão e resolução pelo proxy |
| `connection_failed`, `timeout` | TI deve conferir porta, rota privada, VPN, firewall e proxy |
| `tls_*` | Corrija cadeia, nome, validade ou certificado cliente conforme o administrador; nunca ignore TLS |
| `proxy_configuration_failed`, HTTP 407 | Administrador deve configurar o proxy autorizado na sessão |
| HTTP 401 | Token rejeitado; reconfigure pelo canal seguro |
| HTTP 403 | Acesso negado; revisar política/escopo; não alternar automaticamente ao Oracle local |
| `redirect_rejected` | Configure a origem HTTPS final; Bearer não é encaminhado ao destino do redirect |
| HTTP 404 | Rota/proxy ou versão incompatível; o diagnóstico só exige o health original |
| HTTP 503 | Serviço/Oracle indisponível; health e teste Oracle têm significados diferentes |
| `invalid_response` | Conteúdo não corresponde ao contrato; não usar HTML de login como evidência de health |

Não há retry automático. Após correção, o operador executa novamente; cada chamada
cria um transporte novo, sem mudar modo local, credenciais Oracle ou regras de rede.

## Plano de rede para aprovação (ainda não aprovado)

O responsável de TI/TOTVS deve preencher e aprovar antes de alegar funcionamento:

- Origem: sessão/servidor WinThor autorizado e política WinHTTP/proxy.
- Destino: DNS privado/final, IP da máquina externa, porta e responsável.
- Rota: VPN privada, reverse proxy seguro ou túnel gerenciado permitido pelas
  políticas; não exposição pública direta do conector.
- TLS: certificado e cadeia confiáveis na sessão Cloud, hostname correto,
  renovação e proteção/leitura da chave pela conta de serviço.
- Firewall: apenas origens e porta HTTPS aprovadas; Oracle permanece externo ao
  executável Cloud. Nenhuma regra é criada por esta entrega.
- Evidência: execução do diagnóstico dentro da sessão Cloud, aprovação e teste
  de leitura Oracle autorizado. Guardar resultado sem segredos.

Não foram alterados firewall, proxy, trust store de cliente, NAT, certificado de
produção ou licenciamento TOTVS. As alterações temporárias de trust no CI usam
certificados sintéticos do teste e são removidas ao terminar.

## Contrato versionado: o que existe e o que ainda depende do SQL

Este PR adiciona `GET /api/v1/capabilities`, autenticado, versão de contrato `1.0`.
Ele anuncia os três endpoints diagnósticos reais e informa `available: false`
para vendas, contas a receber, contas a pagar, Livro Caixa e Evolução Diária.
O PR #37 original retorna 404 nessa rota nova; não trate isso como falha de rede.
Não foi inventado um endpoint financeiro funcional nem retornado saldo zero falso.

`smart_connector/contracts/reports_v1.py` define **proposta de entrada**, sem rota
ativa nem executor Oracle: filial numérica explícita, datas ISO inclusivas com no
máximo 31 dias, limite 1–200, página 1–1000 e offset máximo de 10.000. Rejeita SQL,
campos desconhecidos, parâmetros repetidos, datas inválidas e filial/módulo fora
do escopo fornecido pelo servidor. Esse escopo nunca pode vir do cliente.

Antes de ativar qualquer relatório, obter SQL original, binds, filtros e regras
de cada módulo (datas de emissão/vencimento/baixa, cancelamentos, devoluções,
filial, permissões/licenciamento, arredondamento e totalização). Revisar com DBA
e responsável funcional. Definir colunas/tipos e ordenação determinística da
resposta, consultas fixas/binds, limites, timeout, paginação e plano de execução.
Não usar nomes de tabelas ou saldos supostos. A conta Oracle deve continuar SELECT
somente; token diagnóstico atual não constitui autorização comercial por filial.

## Delphi 10 Seattle: base de integração sem alterar FireDAC

Foram adicionadas unidades independentes em `smart_connector/delphi`:

- `Huginn.CloudTransport.pas`: interface HTTP e implementação WinHTTP, somente
  origens HTTPS e quatro rotas conhecidas, Bearer em cabeçalho, erros fixos sem
  segredos, redirects bloqueados, validação TLS do Windows e timeout por fase.
- `Huginn.Credentials.pas`: token da API no Credential Manager do **usuário
  Windows atual**; sem INI/JSON alternativo em texto puro e sem senha Oracle.
  Administradores/processos do mesmo usuário fazem parte da fronteira de confiança.
- `Huginn.ConnectionMode.pas`: seleção explícita `cmFireDACLocal` ou
  `cmHuginnCloud`, fontes injetadas; falha Cloud é propagada, nunca troca para
  FireDAC automaticamente. Não importa FireDAC nem modifica DataModule global.
- `tests/CloudTransportSmoke.dpr`: console para testar seleção/regressão sintética
  e, opcionalmente, health real com token já provisionado no cofre.

Integração a fazer **nos fontes originais**: manter inicialização/licenciamento,
layout e fonte local; adicionar seletor explícito de modo; no modo Cloud, não
inicializar conexão OCI; encapsular consultas locais existentes em implementação
de `IResumoGerencialSource`; adaptar DTOs aos mesmos datasets somente após contrato
de resposta aprovado. `OpenModule` é um ponto de integração, não um relatório pronto.
A UI deve solicitar confirmação do operador para voltar ao modo FireDAC local.

Para provisionar token, validar origem por `THuginnCloudTransport.Create`, obter
o token em controle com `PasswordChar`, chamar `SaveCloudToken(Origin, Token)` e
limpar o controle em seguida. Persistir somente URL/timeout/mode não secretos na
configuração já usada pelo cliente. Nunca passar token por argumento ao EXE.
Executar chamadas fora da thread de UI; cada chamada gerencia COM e cria WinHTTP
novo. Não registrar `Exception.Message` de componentes externos ou corpos HTTP.

Build no **RAD Studio/Delphi 10 Seattle licenciado**, Developer Command Prompt:

```bat
cd smart_connector\delphi\tests
dcc32 -B CloudTransportSmoke.dpr
CloudTransportSmoke.exe
rem Opcional, apenas na origem autorizada e com credencial ja provisionada:
CloudTransportSmoke.exe --probe https://conector.exemplo.invalid:8765
```

Repetir com `dcc64 -B` se a distribuição original usar Win64. Não trocar a
arquitetura da rotina local para tentar corrigir OCI no Cloud. Delphi/SDK e
fontes originais não estão disponíveis no ambiente CI; **compilação Delphi não
foi executada nem alegada**. Os fontes são uma base de integração para revisão,
não o PCINF9803 compilado. A aplicação local existente não foi modificada.

## Testes e checklist de homologação

CI usa dados sintéticos, sem segredos/Oracle de cliente: contratos, autorização,
limites, regressão dos endpoints, TLS e WinHTTP real contra servidor HTTPS local,
rejeição de cadeia não confiável, aceitação após trust temporário do certificado
do teste, 401, reconnect explícito, proxy/timeout/redirect classificados e
redaction. Testes sintéticos de proxy/timeout não comprovam a rede TOTVS real.
O workflow do instalador do PR #37 continua cobrindo serviço e ciclo de vida.

- [ ] URL/rota/TLS aprovados por TI/TOTVS e token entregue em canal seguro.
- [ ] Diagnóstico registrado dentro da mesma sessão Cloud do PCINF9803.
- [ ] Oracle autorizado via `/oracle/test`, sem credenciais Oracle no Cloud.
- [ ] Fontes Delphi e SQL originais revisados; licenciamento/layout preservados.
- [ ] DCC32/DCC64 Seattle compilados; teste local FireDAC antes/depois idêntico.
- [ ] Contratos de resposta e escopos de filial/módulo aprovados no servidor.
- [ ] Cinco módulos comparados com resultados locais usando dados autorizados.
- [ ] Falhas, timeout, reconnect e retorno **explícito** ao local exercitados.
- [ ] Evidências sem segredos e responsáveis registrados antes da homologação.
