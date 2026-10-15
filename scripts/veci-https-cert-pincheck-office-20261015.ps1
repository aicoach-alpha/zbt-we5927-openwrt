# VeCI HTTPS certificate pin verification from the authorized OFFICE laptop.
# Read-only: fetch public server certificate over pinned SSH and compare it
# with the certificate actually served at 192.168.1.1:443. No browser changes,
# credentials beyond the SSH login, trust-store edits, or private key reads.
$ErrorActionPreference = 'Stop'
$Target = '192.168.1.1'
$Ssl = $null
$Tcp = $null
$Cert = $null
$RouterCert = $null
$script:ObservedPolicyErrors = $null

function Fingerprint([System.Security.Cryptography.X509Certificates.X509Certificate2] $Item) {
    $Digest = [System.Security.Cryptography.SHA256]::Create()
    try { return [BitConverter]::ToString($Digest.ComputeHash($Item.RawData)).Replace('-', '') }
    finally { $Digest.Dispose() }
}
try {
    if (-not (Get-Command ssh.exe -ErrorAction SilentlyContinue)) {
        throw 'SSH_NOT_FOUND'
    }
    # Only the PUBLIC cert path from uhttpd configuration, never the key.
    $ReadPublicCert = 'crt=$(uci -q get uhttpd.main.cert); test -n "$crt" && test -r "$crt" && cat "$crt"'
    $Lines = & ssh.exe -o StrictHostKeyChecking=yes -o ConnectTimeout=8 "root@$Target" $ReadPublicCert
    if ($LASTEXITCODE -ne 0) { throw 'SSH_CERT_READ_FAILED' }
    $Pem = [string]::Join([Environment]::NewLine, [string[]]$Lines)
    $Match = [regex]::Match($Pem, '-----BEGIN CERTIFICATE-----\s*([A-Za-z0-9+/\s=]+?)\s*-----END CERTIFICATE-----')
    if (-not $Match.Success) { throw 'ROUTER_CERTIFICATE_NOT_PEM' }
    $Der = [Convert]::FromBase64String(($Match.Groups[1].Value -replace '\s', ''))
    $RouterCert = [System.Security.Cryptography.X509Certificates.X509Certificate2]::new($Der)
    $RouterSha = Fingerprint $RouterCert

    $Tcp = New-Object System.Net.Sockets.TcpClient
    $Async = $Tcp.BeginConnect($Target, 443, $null, $null)
    if (-not $Async.AsyncWaitHandle.WaitOne(8000)) { throw 'HTTPS_CONNECT_TIMEOUT' }
    $Tcp.EndConnect($Async)
    $Callback = [System.Net.Security.RemoteCertificateValidationCallback]{
        param($sender,$remote,$chain,$errors)
        # Diagnostic capture ONLY: accept handshake to inspect the remote
        # public certificate. NO HTTP request or account secret is sent.
        $script:ObservedPolicyErrors = $errors
        return $true
    }
    $Ssl = [System.Net.Security.SslStream]::new($Tcp.GetStream(), $false, $Callback)
    $Ssl.ReadTimeout = 8000
    $Ssl.WriteTimeout = 8000
    $Ssl.AuthenticateAsClient($Target)
    if (-not $Ssl.IsAuthenticated -or -not $Ssl.RemoteCertificate) {
        throw 'HTTPS_HANDSHAKE_FAILED'
    }
    $Cert = [System.Security.Cryptography.X509Certificates.X509Certificate2]::new($Ssl.RemoteCertificate)
    $ServedSha = Fingerprint $Cert
    $Protocol = $Ssl.SslProtocol.ToString()
    if ($RouterSha -ne $ServedSha) { throw 'HTTPS_CERTIFICATE_MISMATCH' }
    if ($Protocol -notin @('Tls12', 'Tls13')) { throw 'TLS_PROTOCOL_TOO_OLD' }
    $Now = Get-Date
    if ($Now -lt $Cert.NotBefore -or $Now -gt $Cert.NotAfter) { throw 'HTTPS_CERTIFICATE_EXPIRED_OR_NOT_YET_VALID' }

    Write-Output 'VECI_HTTPS_CERT_PIN=pass'
    Write-Output ('VECI_HTTPS_TLS_PROTOCOL=' + $Protocol)
    Write-Output ('VECI_HTTPS_CERT_SHA256=' + $ServedSha)
    Write-Output ('VECI_HTTPS_CERT_NOT_AFTER=' + $Cert.NotAfter.ToString('yyyy-MM-dd'))
    Write-Output ('VECI_HTTPS_BROWSER_TRUST=' + $script:ObservedPolicyErrors.ToString())
    Write-Output 'VECI_HTTPS_CERT_PIN_MODE=read_only'
    Write-Output 'VECI_HTTPS_HTTP_MODIFIED=false'
} catch {
    Write-Output 'VECI_HTTPS_CERT_PIN=blocked'
    Write-Output ('VECI_HTTPS_REASON=' + $_.Exception.Message)
    exit 1
} finally {
    if ($Cert) { $Cert.Dispose() }
    if ($RouterCert) { $RouterCert.Dispose() }
    if ($Ssl) { $Ssl.Dispose() }
    if ($Tcp) { $Tcp.Dispose() }
}