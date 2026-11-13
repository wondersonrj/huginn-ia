# HUGINN IA — Oracle direto (primeira fase)

O conector utiliza python-oracledb Thin, sem OCI/Oracle Client. Requer conectividade TCP com o listener Oracle e Service Name correto.

## Configuração no Windows (PowerShell)
Configure variáveis de ambiente **na sessão local**, sem enviar credenciais ao GitHub:
```powershell
$env:HUGINN_ORACLE_HOST="IP_OU_HOST"
$env:HUGINN_ORACLE_PORT="1521"
$env:HUGINN_ORACLE_SERVICE="SERVICE_NAME"
$env:HUGINN_ORACLE_USER="USUARIO_READONLY"
$env:HUGINN_ORACLE_PASSWORD="SENHA_LOCAL"
```
Não coloque senhas em commits, prints, logs ou mensagens de chat.

## Segurança
1. Solicite ao DBA uma conta com somente SELECT nas tabelas explicitamente autorizadas.
2. O conector inicia transação read-only, além das restrições do usuário.
3. Não habilitar endpoints de consulta SQL arbitrária.
4. O teste de conexão executa apenas SELECT 1 FROM DUAL.
5. O endpoint local `POST /api/oracle/testar` recebe host, porta, serviço, usuário e senha apenas para a tentativa atual; não persiste credenciais nem retorna mensagens internas do driver.
6. Antes de conectar a um cliente real, validar permissões, topologia de rede e tabelas WinThor.

## TOTVS Cloud
Será implementado em etapa posterior conforme acesso autorizado e restrições do ambiente.

## Tela de configuração e teste

Com backend e frontend iniciados conforme README, abra a seção **Conexão Oracle direta** no painel (ou use o menu lateral). Preencha Host ou IP, Porta (1521 por padrão), Service Name, Usuário de leitura e Senha. Clique em **Testar conexão Oracle**. A senha é apagada após cada tentativa; os campos não são gravados em disco ou localStorage. Alterar um campo invalida o resultado anterior. O teste não mantém uma conexão aberta nem configura uma integração persistente.

O backend deve rodar na máquina com acesso TCP ao listener. Este endpoint é destinado ao desenvolvimento local, aceita clientes de loopback e origens locais conhecidas; não o exponha à Internet. Uma implantação compartilhada requer autenticação e HTTPS. Use uma conta autorizada pelo DBA com somente SELECT. O formulário não carrega senhas do ambiente; a configuração por variáveis continua disponível para uso direto do módulo Python.

O teste limita a conexão TCP a 5 segundos, sem novas tentativas, e cada chamada Oracle a 5 segundos. O navegador encerra a espera após 20 segundos; interromper essa espera não cancela imediatamente uma operação já iniciada no servidor. A sessão sempre é fechada após o teste, inclusive em falhas, sem commit.

## Validação automatizada

Na raiz: `.venv/bin/python -m pytest -q`. Os testes do conector usam mocks do driver para conferir ordem exata dos comandos de leitura, fechamento em sucesso/falha, ausência de commit e proteção de credenciais nas respostas. Não exigem nem acessam um Oracle real. Em `frontend`, execute `npm run build`.

Uma conexão real só pode ser confirmada com endereço, Service Name, conta de leitura e acesso de rede fornecidos com segurança no ambiente do operador. Não envie senhas em chat ou commits.

## Diagnóstico das tabelas WinThor

O botão **Diagnosticar tabelas WinThor** usa `POST /api/oracle/diagnostico`.
A consulta é fixa e parametrizada: lê somente nomes de proprietário, tabela,
coluna e tipo em `ALL_TAB_COLUMNS` e `ALL_TABLES`, para `PCPRODUT`, `PCFORNEC`,
`PCPRODFILIAL`, `PCPRODFORNEC`, `PCNFENT`, `PCMOV` e `PCPEDIDO`. Não aceita SQL,
nomes extras ou consulta de registros comerciais. Usa a mesma transação de
somente leitura e fecha a sessão sem commit, também em caso de erro.

Tabelas homônimas de proprietários diferentes são exibidas separadamente.
Somente tabelas visíveis no dicionário ao usuário são identificadas; sinônimos
e views não são resolvidos como tabelas. “Não visível” não comprova inexistência:
pode ser falta de permissão. Nenhuma permissão é concedida pelo aplicativo.
Editar a configuração limpa o diagnóstico anterior; a senha é apagada após
cada tentativa e deve ser preenchida novamente para repetir a operação.

A suíte inclui verificação da consulta exata, parâmetros autorizados, ausência
de commits, separação de proprietários, erro/fechamento e restrições da API.
Resultados Oracle de sucesso foram simulados; não substituem validação real.
