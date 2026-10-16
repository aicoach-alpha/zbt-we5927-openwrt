# VeCI HTTPS certificate inspection from Windows PowerShell 5.1+
# READ-ONLY: TLS handshake to 192.168.1.1:443. No browser bypass.
# NO credential submission, NO certificate installation or router modification.
# The callback accepts untrusted certificates ONLY in this disposable,
# unauthenticated diagnostic connection so their public metadata can be read.
[CmdletBinding()]
param(
  [ValidatePattern('^192\.168\.1\.1$')]
  [string]$RouterIP = '192.168.1.1'
)
$ErrorActionPreference = 'Stop'
$tcp = $null
$tls = $null
$script:observedCertificate = $null
$script:observedPolicy = 'unknown'
try {
  $tcp = New-Object System.Net.Sockets.TcpClient
  $async = $tcp.BeginConnect($RouterIP, 443, $null, $null)
  if (-not $async.AsyncWaitHandle.WaitOne(6000)) {
    throw 'router_https_port_timeout'
  }
  $tcp.EndConnect($async)
  $tcp.ReceiveTimeout = 6000
  $tcp.SendTimeout = 6000
  $callback = [System.Net.Security.RemoteCertificateValidationCallback] {
    param($sender, $cert, $chain, $errors)
    if ($null -ne $cert) {
      $script:observedCertificate =
        [System.Security.Cryptography.X509Certificates.X509Certificate2]::new($cert)
    }
    $script:observedPolicy = [string]$errors
    # Inspection only: no GET, POST, cookie, password, OTP, or SSH.
    return $true
  }
  $tls = [System.Net.Security.SslStream]::new($tcp.GetStream(), $false, $callback)
  $tls.ReadTimeout = 6000
  $tls.WriteTimeout = 6000
  $tls.AuthenticateAsClient($RouterIP)
  if ($null -eq $script:observedCertificate) {
    throw 'no_peer_certificate'
  }
  $leaf = $script:observedCertificate
  $san = $leaf.Extensions | Where-Object { $_.Oid.Value -eq '2.5.29.17' } | Select-Object -First 1
  $sanDetails = if ($null -ne $san) {
    ([string]$san.Format($false) -replace '[\r\n]+', ' ').Trim()
  } else { '' }
  $sanIP = if ($null -eq $san) { 'missing' }
    elseif ($sanDetails -match '(?i)IP Address\s*[=:]\s*192\.168\.1\.1(?![0-9])') { 'present' }
    else { 'not_detected_in_windows_formatted_san' }
  $valid = if ([DateTime]::UtcNow -ge $leaf.NotBefore.ToUniversalTime() -and
               [DateTime]::UtcNow -le $leaf.NotAfter.ToUniversalTime()) {
    'within_dates'
  } else { 'outside_dates' }
  Write-Output 'VECI_TLS_WINDOWS_AUDIT=pass'
  Write-Output "VECI_TLS_SERVER=$($RouterIP):443"
  Write-Output "VECI_TLS_PROTOCOL=$($tls.SslProtocol)"
  Write-Output "VECI_TLS_WINDOWS_POLICY=$script:observedPolicy"
  Write-Output "VECI_TLS_IP_SAN=$sanIP"
  Write-Output "VECI_TLS_CERT_SUBJECT=$($leaf.Subject)"
  Write-Output "VECI_TLS_CERT_ISSUER=$($leaf.Issuer)"
  Write-Output "VECI_TLS_CERT_SELF_ISSUED=$($leaf.Subject -eq $leaf.Issuer)"
  Write-Output "VECI_TLS_CERT_VALIDITY=$valid"
  Write-Output "VECI_TLS_NOT_BEFORE=$($leaf.NotBefore.ToString('yyyy-MM-dd'))"
  Write-Output "VECI_TLS_NOT_AFTER=$($leaf.NotAfter.ToString('yyyy-MM-dd'))"
  Write-Output "VECI_TLS_THUMBPRINT=$($leaf.Thumbprint)"
  Write-Output "VECI_TLS_SAN_PUBLIC_NAMES=$sanDetails"
  Write-Output 'VECI_TLS_PASSWORD_SENT=false'
  Write-Output 'VECI_TLS_CERTIFICATE_TRUST_CHANGED=false'
  Write-Output 'VECI_TLS_ROUTER_CHANGED=false'
} catch {
  $reason = [string]$_.Exception.Message
  $reason = if ($reason -eq 'router_https_port_timeout') {
    'https_port_timeout'
  } elseif ($reason -eq 'no_peer_certificate') {
    'no_server_certificate'
  } else {
    'tls_connection_or_handshake_failed'
  }
  Write-Output 'VECI_TLS_WINDOWS_AUDIT=blocked'
  Write-Output "VECI_TLS_WINDOWS_REASON=$reason"
  exit 1
} finally {
  if ($null -ne $tls) { $tls.Dispose() }
  if ($null -ne $tcp) { $tcp.Dispose() }
  $script:observedCertificate = $null
}
