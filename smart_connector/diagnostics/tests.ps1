$ErrorActionPreference = 'Stop'
Import-Module "$PSScriptRoot/Huginn.CloudDiagnostics.psm1" -Force
$module = Get-Module Huginn.CloudDiagnostics
& $module {
    function Assert($Condition, $Message) { if (-not $Condition) { throw $Message } }
    Assert ((Get-HuginnOrigin 'https://example.invalid:8765/') -eq 'https://example.invalid:8765') 'origin'
    foreach ($url in @('http://host', 'https://user:secret@host', 'https://host/?token=secret',
                       'https://host/#secret', 'https://host/health', "https://host/`n")) {
        $rejected = $false
        try { Get-HuginnOrigin $url | Out-Null } catch { $rejected = $true }
        Assert $rejected 'unsafe origin accepted'
    }
    foreach ($entry in @{12002='timeout';12007='dns_failed';12029='connection_failed';
                         12175='tls_validation_failed';12045='tls_untrusted_chain';12166='proxy_configuration_failed'}.GetEnumerator()) {
        Assert ((Get-HuginnFailure ([int]$entry.Key)) -eq $entry.Value) 'classification'
    }
    $script:FakeResponse = @{ status=200;failure=$null;body=([PSCustomObject]@{status='ok';version='0.2.1'}) }
    function script:Invoke-HuginnRequest { param($Url,$Token,$TimeoutMs) return $script:FakeResponse }
    $token = ConvertTo-SecureString ('synthetic-secret-' + ('x' * 32)) -AsPlainText -Force
    try {
        foreach ($entry in @{200='ok';401='authentication_rejected';403='permission_denied';
                             302='redirect_rejected';407='proxy_authentication_required';503='service_or_oracle_unavailable'}.GetEnumerator()) {
            $script:FakeResponse.status = [int]$entry.Key
            $report = Test-HuginnCloud 'https://127.0.0.1:1' $token -TimeoutSeconds 1
            Assert ($report.stages[-1].result -eq $entry.Value) 'HTTP classification'
            $serialized = $report | ConvertTo-Json -Depth 8
            Assert (-not $serialized.Contains('synthetic-secret')) 'secret leaked'
        }
        $script:FakeResponse.status = 200
        $script:FakeResponse.body = [PSCustomObject]@{html='not a connector'}
        $report = Test-HuginnCloud 'https://127.0.0.1:1' $token -TimeoutSeconds 1
        Assert (-not $report.authenticated_https) 'invalid body accepted'
        $script:FakeResponse.failure = 'timeout'
        $report = Test-HuginnCloud 'https://127.0.0.1:1' $token -TimeoutSeconds 1
        Assert ($report.stages[-1].result -eq 'timeout') 'timeout'
        $script:FakeResponse.failure = $null
        $script:FakeResponse.body = [PSCustomObject]@{status='ok';version='0.2.1'}
        $report = Test-HuginnCloud 'https://127.0.0.1:1' $token -TimeoutSeconds 1
        Assert $report.authenticated_https 'explicit reconnect after failure'
    } finally { $token.Dispose() }
}
Write-Host 'Diagnostic policy, errors, timeouts, explicit reconnect and redaction: PASS'
