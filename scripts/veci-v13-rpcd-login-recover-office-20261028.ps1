# VeCI login recovery v13: restart only rpcd, then one dummy login response check.
# No password, config changes, modem, LTE or router reboot.
$ErrorActionPreference='Stop'
$router='root@192.168.1.1'
Write-Output 'VECI_LOGIN_RECOVERY=rpcd_targeted_restart'
& ssh.exe $router 'if [ -x /etc/init.d/rpcd ] && pidof ubusd >/dev/null && pidof uhttpd >/dev/null; then /etc/init.d/rpcd restart; else echo VECI_LOGIN_RECOVERY=unsafe_prerequisite; exit 3; fi'
if ($LASTEXITCODE -ne 0) { Write-Output 'VECI_LOGIN_RECOVERY=restart_failed'; exit 1 }
# Bounded single probe with invalid credentials proves responsiveness, not actual login.
$payload='{"jsonrpc":"2.0","id":742,"method":"call","params":["00000000000000000000000000000000","session","login",{"username":"__veci_probe_nonexistent__","password":"__invalid_probe_no_secret__"}]}'
$body=Join-Path $env:TEMP 'veci-v13-rpcd-recovery-probe.json'
$out=Join-Path $env:TEMP 'veci-v13-rpcd-recovery-result.json'
try {
 [IO.File]::WriteAllText($body,$payload,(New-Object System.Text.UTF8Encoding($false)))
 $result=& curl.exe --silent --show-error --insecure --max-time 12 --connect-timeout 3 --output $out --write-out 'http=%{http_code};seconds=%{time_total}' --header 'Content-Type: application/json' --data-binary ('@'+$body) 'https://192.168.1.1/ubus'
 $rc=$LASTEXITCODE
 Write-Output ('VECI_LOGIN_RPCD_HTTP='+($result -join '').Trim())
 if ($rc -ne 0) { Write-Output ('VECI_LOGIN_RPCD_RESULT=still_unresponsive_exit_'+$rc); exit 2 }
 try {
  $j=Get-Content -LiteralPath $out -Raw | ConvertFrom-Json
  if ($null -ne $j.result -and $j.result.Count -gt 0) {
   $code=$j.result[0]
   Write-Output ('VECI_LOGIN_RPCD_UBUS_CODE='+$code)
   Write-Output 'VECI_LOGIN_RPCD_RESULT=responding_rejected_dummy'
  } else {
   Write-Output 'VECI_LOGIN_RPCD_RESULT=unexpected_response'
   exit 3
  }
 } catch {
  Write-Output 'VECI_LOGIN_RPCD_RESULT=invalid_json'
  exit 3
 }
} finally {
 Remove-Item $body,$out -Force -ErrorAction SilentlyContinue
}
