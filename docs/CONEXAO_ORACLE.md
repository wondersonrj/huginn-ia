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
5. Este módulo ainda não está exposto como endpoint HTTP; credenciais permanecem apenas no processo local.
6. Antes de conectar a um cliente real, validar permissões, topologia de rede e tabelas WinThor.

## TOTVS Cloud
Será implementado em etapa posterior conforme acesso autorizado e restrições do ambiente.
