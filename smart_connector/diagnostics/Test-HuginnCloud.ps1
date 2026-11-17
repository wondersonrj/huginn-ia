[CmdletBinding()]
param(
    [string]$BaseUrl,
    [ValidateRange(1,30)][int]$TimeoutSeconds = 5,
    [switch]$OracleReadTest
)
$ErrorActionPreference = 'Stop'
Import-Module "$PSScriptRoot/Huginn.CloudDiagnostics.psm1" -Force
try {
    if (-not $BaseUrl) { $BaseUrl = Read-Host 'Endereco HTTPS fornecido pelo administrador (sem token)' }
    # No token parameter, env var, transcript output or plaintext config file.
    $token = Read-Host 'Token Bearer (entrada oculta)' -AsSecureString
    $report = Test-HuginnCloud -BaseUrl $BaseUrl -Token $token -TimeoutSeconds $TimeoutSeconds -OracleReadTest:$OracleReadTest
    $report | ConvertTo-Json -Depth 8
    if (-not $report.authenticated_https -or ($OracleReadTest -and $report.oracle_read -ne 'ok')) { exit 2 }
} catch {
    Write-Error 'Diagnóstico não executado. Confira origem HTTPS sem segredos, token e política de execução. Nenhuma exceção bruta foi registrada.'
    exit 1
} finally {
    if ($token) { $token.Dispose() }
}
