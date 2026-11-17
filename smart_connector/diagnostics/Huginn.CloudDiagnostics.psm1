Set-StrictMode -Version Latest

function Get-HuginnOrigin {
    param([string]$BaseUrl)
    $uri = $null
    if (-not [Uri]::TryCreate($BaseUrl, [UriKind]::Absolute, [ref]$uri) -or
        $uri.Scheme -ne 'https' -or $uri.UserInfo -or $uri.Query -or $uri.Fragment -or
        $uri.AbsolutePath -ne '/' -or -not $uri.Host -or $BaseUrl -match '[\x00-\x20]') {
        throw 'Use somente a origem HTTPS, sem caminho, credenciais, query ou fragmento.'
    }
    return $uri.GetLeftPart([UriPartial]::Authority)
}

function Get-HuginnFailure {
    param([int]$Code)
    switch ($Code -band 65535) {
        12002 { return 'timeout' }
        12007 { return 'dns_failed' }
        12029 { return 'connection_failed' }
        12030 { return 'connection_interrupted' }
        12037 { return 'tls_certificate_expired' }
        12038 { return 'tls_hostname_mismatch' }
        12044 { return 'tls_client_certificate_required' }
        12045 { return 'tls_untrusted_chain' }
        12175 { return 'tls_validation_failed' }
        12166 { return 'proxy_configuration_failed' }
        12167 { return 'proxy_configuration_failed' }
        default { return 'transport_failed' }
    }
}

function Invoke-HuginnRequest {
    param([string]$Url, [string]$Token, [int]$TimeoutMs)
    $request = $null
    try {
        # Same Windows WinHTTP stack as the Delphi adapter. No certificate bypass.
        $request = New-Object -ComObject 'WinHttp.WinHttpRequest.5.1'
        $request.SetProxy(0) # WinHTTP preconfigured proxy, not Python/env proxy settings
        $request.SetTimeouts($TimeoutMs, $TimeoutMs, $TimeoutMs, $TimeoutMs)
        $request.Option(6) = $false # Never forward Bearer through a redirect
        $request.Option(9) = 2048 # TLS 1.2; certificate validation stays enabled
        $request.SetAutoLogonPolicy(2) # Do not silently send Windows credentials
        $request.Open('GET', $Url, $false)
        $request.SetRequestHeader('Authorization', 'Bearer ' + $Token)
        $request.SetRequestHeader('Accept', 'application/json')
        $request.Send()
        $status = [int]$request.Status
        $body = $null
        if ($status -eq 200) {
            if ($request.ResponseText.Length -gt 65536) {
                return @{ status = $status; failure = 'invalid_response'; body = $null }
            }
            try { $body = $request.ResponseText | ConvertFrom-Json -ErrorAction Stop }
            catch { return @{ status = $status; failure = 'invalid_response'; body = $null } }
        }
        return @{ status = $status; failure = $null; body = $body }
    } catch {
        $code = $_.Exception.HResult
        # COM wrappers may keep the WinHTTP HRESULT on the inner exception.
        if ($_.Exception.InnerException) { $code = $_.Exception.InnerException.HResult }
        return @{ status = 0; failure = (Get-HuginnFailure $code); body = $null }
    } finally {
        if ($null -ne $request) { [void][Runtime.InteropServices.Marshal]::FinalReleaseComObject($request) }
    }
}

function Get-HuginnHttpResult {
    param($Response, [string]$Kind)
    if ($Response.failure) { return $Response.failure }
    switch ([int]$Response.status) {
        200 {
            $body = $Response.body
            if ($null -eq $body) { return 'invalid_response' }
            $names = @($body.PSObject.Properties | ForEach-Object { $_.Name })
            if ($Kind -eq 'health') {
                if ($names -contains 'status' -and $body.status -eq 'ok' -and
                    $names -contains 'version' -and $body.version -match '^\d+\.\d+\.\d+$') {
                    return 'ok'
                }
            } elseif ($names -contains 'ok' -and $body.ok -eq $true) { return 'ok' }
            return 'invalid_response'
        }
        401 { return 'authentication_rejected' }
        403 { return 'permission_denied' }
        404 { return 'endpoint_not_found' }
        407 { return 'proxy_authentication_required' }
        503 { return 'service_or_oracle_unavailable' }
        default {
            if ($Response.status -ge 300 -and $Response.status -lt 400) { return 'redirect_rejected' }
            return 'http_failed'
        }
    }
}

function Test-HuginnCloud {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory=$true)][string]$BaseUrl,
        [Parameter(Mandatory=$true)][Security.SecureString]$Token,
        [ValidateRange(1,30)][int]$TimeoutSeconds = 5,
        [switch]$OracleReadTest
    )
    $origin = Get-HuginnOrigin $BaseUrl
    $uri = [Uri]$origin
    $timeoutMs = $TimeoutSeconds * 1000
    $stages = @()
    # Direct probes are advisory: a configured proxy can resolve/reach the origin itself.
    try {
        $task = [Net.Dns]::GetHostAddressesAsync($uri.DnsSafeHost)
        if ($task.Wait($timeoutMs) -and $task.Result.Count -gt 0) { $dns = 'ok' } else { $dns = 'timeout' }
    } catch { $dns = 'dns_failed' }
    $stages += @{ stage = 'direct_dns'; result = $dns; advisory = $true }
    $tcp = New-Object Net.Sockets.TcpClient
    try {
        $task = $tcp.ConnectAsync($uri.DnsSafeHost, $uri.Port)
        if ($task.Wait($timeoutMs) -and $tcp.Connected) { $portResult = 'ok' } else { $portResult = 'timeout' }
    } catch { $portResult = 'connection_failed' }
    finally { $tcp.Dispose() }
    $stages += @{ stage = 'direct_tcp'; result = $portResult; advisory = $true }
    $pointer = [IntPtr]::Zero
    $plainToken = $null
    try {
        $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($Token)
        $plainToken = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
        if ($plainToken.Length -lt 32 -or $plainToken -match '[\x00-\x20\x7f]') { throw 'Token inválido.' }
        $response = Invoke-HuginnRequest ($origin + '/health') $plainToken $timeoutMs
        $health = Get-HuginnHttpResult $response 'health'
        $stages += @{ stage = 'https_authenticated_health'; result = $health; http_status = $response.status }
        $oracle = 'not_run'
        if ($OracleReadTest -and $health -eq 'ok') {
            $response = Invoke-HuginnRequest ($origin + '/oracle/test') $plainToken $timeoutMs
            $oracle = Get-HuginnHttpResult $response 'oracle'
            $stages += @{ stage = 'oracle_read_test'; result = $oracle; http_status = $response.status }
        }
    } finally {
        if ($pointer -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer) }
        $plainToken = $null
    }
    # Fixed fields only: no raw response, headers, exceptions, token, IP list or username.
    return [PSCustomObject]@{
        schema_version = '1.0'; origin = $origin; observed_at_utc = [DateTime]::UtcNow.ToString('o')
        execution_origin = 'operator_must_confirm_winthor_session'; proxy = 'winhttp_preconfigured'
        timeout_per_phase_seconds = $TimeoutSeconds; stages = $stages
        authenticated_https = ($health -eq 'ok'); oracle_read = $oracle
        totvs_homologated = $false
    }
}

Export-ModuleMember -Function Test-HuginnCloud
