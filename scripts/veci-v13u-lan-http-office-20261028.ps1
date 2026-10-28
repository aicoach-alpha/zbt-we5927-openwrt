# VeCI v13u: LAN-only HTTP primary with HTTPS retained, one direct + one HTTP dummy login check.
# No real credentials, no firewall, LTE, modem, or router reboot.
param([ValidateSet('Apply','Status','Rollback')][string]$Action='Apply')
$ErrorActionPreference='Stop'
$router='root@192.168.1.1'
$script='/tmp/veci-v13u-lan-http-login-20261028.sh'
$local=Join-Path $env:TEMP 'veci-v13u-lan-http-login-20261028.sh'
$url='https://raw.githubusercontent.com/aicoach-alpha/zbt-we5927-openwrt/7573cb2073d58c0bdff53341851e493130d88d33/scripts/veci-v13u-lan-http-login-20261028.sh'
function Fail([string]$why) { Write-Output ('VECI_V13U_OFFICE='+$why); exit 1 }
& curl.exe -fLsS $url -o $local
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $local -PathType Leaf)) {
 Fail 'pinned_router_script_unavailable'
}
& scp.exe -O $local ($router+':'+$script)
if ($LASTEXITCODE -ne 0) { Fail 'router_script_transfer_failed' }
$mode=if($Action -eq 'Apply'){'--apply'}elseif($Action -eq 'Rollback'){'--rollback'}else{'--status'}
Write-Output ('VECI_V13U_ACTION='+$Action)
if ($Action -eq 'Apply') {
 Write-Output 'VECI_V13U_WARNING=HTTP_only_on_trusted_LAN_password_not_encrypted'
 Write-Output 'VECI_V13U_UHTTPD_RESTART=one_brief_web_admin_interruption_possible'
}
& ssh.exe $router ('sh -n '+$script+' && sh '+$script+' '+$mode)
if ($LASTEXITCODE -ne 0) { Fail 'router_action_failed_no_repeat_review_output' }
if ($Action -ne 'Apply') { Write-Output 'VECI_V13U_OFFICE=command_completed'; exit 0 }
# One safe HTTP login RPC comparison after reconfiguring uhttpd.
$payload='{"jsonrpc":"2.0","id":743,"method":"call","params":["00000000000000000000000000000000","session","login",{"username":"__veci_probe_nonexistent__","password":"__invalid_probe_no_secret__"}]}'
$body=Join-Path $env:TEMP 'veci-v13u-lan-only-probe.json'
$response=Join-Path $env:TEMP 'veci-v13u-lan-only-response.json'
try {
 [IO.File]::WriteAllText($body,$payload,(New-Object System.Text.UTF8Encoding($false)))
 $args=@('--silent','--show-error','--noproxy','*','--max-time','10','--connect-timeout','3','--output',$response,'--write-out','http=%{http_code};seconds=%{time_total};redirect=%{redirect_url}','--header','Content-Type: application/json','--data-binary',('@'+$body),'http://192.168.1.1/ubus')
 $line=& curl.exe @args
 $status=$LASTEXITCODE
 Write-Output ('VECI_V13U_HTTP_PROBE='+($line -join '').Trim())
 if ($status -ne 0) {
  Write-Output ('VECI_V13U_HTTP_LOGIN=not_responding_exit_'+$status)
 } else {
  try {
   $obj=Get-Content -LiteralPath $response -Raw | ConvertFrom-Json
   if ($null -ne $obj.result -and $obj.result.Count -gt 0) {
    $code=$obj.result[0]
    Write-Output ('VECI_V13U_HTTP_UBUS_CODE='+$code)
    if ($code -eq 0) {
      Write-Output 'VECI_V13U_HTTP_LOGIN=unexpected_dummy_accepted'
    } else {
      Write-Output 'VECI_V13U_HTTP_LOGIN=responded_to_invalid_credentials'
    }
   } else { Write-Output 'VECI_V13U_HTTP_LOGIN=unexpected_rpc_payload' }
  } catch { Write-Output 'VECI_V13U_HTTP_LOGIN=unparseable_response' }
 }
} finally {
 Remove-Item -LiteralPath $body,$response -Force -ErrorAction SilentlyContinue
}
Write-Output 'VECI_V13U_LAN_URL=http://192.168.1.1/veci/'
Write-Output 'VECI_V13U_OFFICE=apply_complete_check_login_receipt'
