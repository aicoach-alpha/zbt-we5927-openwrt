# VeCI v13: conditional one-shot auth recovery on office Windows laptop.
# No real credentials; the intentionally invalid login must be rejected rapidly.
$ErrorActionPreference='Stop'
$router='root@192.168.1.1'
$remote='/tmp/veci-v13-conditional-login-recovery-20261028.sh'
$local=Join-Path $env:TEMP 'veci-v13-conditional-login-recovery-20261028.sh'
$url='https://raw.githubusercontent.com/aicoach-alpha/zbt-we5927-openwrt/81587bebec2d8af410ef1f7f41dac6222dd71997/scripts/veci-v13-conditional-login-recovery-20261028.sh'
function Fail([string]$reason){ Write-Output ('VECI_AUTH_OFFICE='+$reason); exit 1 }
& curl.exe --fail --location --silent --show-error $url --output $local
if($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $local -PathType Leaf)){
 Fail 'pinned_source_download_failed'
}
& scp.exe -O $local ($router+':'+$remote)
if($LASTEXITCODE -ne 0){ Fail 'router_staging_failed' }
function Router-Action([string]$action){
 $result=@(& ssh.exe $router ('sh -n '+$remote+' && sh '+$remote+' '+$action))
 if($LASTEXITCODE -ne 0){ Fail ('router_'+$action+'_failed_review_output') }
 foreach($line in $result){ Write-Output $line }
}
function Probe-Https{
 $payloadFile=Join-Path $env:TEMP 'veci-v13-auth-dummy-request.json'
 $responseFile=Join-Path $env:TEMP 'veci-v13-auth-dummy-response.json'
 $payload='{"jsonrpc":"2.0","id":902,"method":"call","params":["00000000000000000000000000000000","session","login",{"username":"__veci_nonexistent_probe__","password":"__deliberately_invalid__"}]}'
 try{
  [IO.File]::WriteAllText($payloadFile,$payload,(New-Object System.Text.UTF8Encoding($false)))
  $curlOutput=@(& curl.exe --silent --show-error --insecure --max-time 9 --connect-timeout 3 --output $responseFile --write-out 'http=%{http_code};seconds=%{time_total}' --header 'Content-Type: application/json' --data-binary ('@'+$payloadFile) https://192.168.1.1/ubus)
  $code=$LASTEXITCODE
  if($code -ne 0){ return 'timeout_or_transport_error' }
  $obj=Get-Content -LiteralPath $responseFile -Raw | ConvertFrom-Json
  if($null -ne $obj.result -and $obj.result.Count -gt 0 -and [int]$obj.result[0] -eq 6){
   return 'denied_fast'
  }
  return 'unexpected_http_result'
 } catch { return 'invalid_http_response' }
 finally { Remove-Item -LiteralPath $payloadFile,$responseFile -ErrorAction SilentlyContinue -Force }
}
Write-Output 'VECI_AUTH_PLAN=conditional_backend_then_https_recovery'
$localStatus=@(Router-Action 'inspect')
$localStatus | ForEach-Object { Write-Output $_ }
if($localStatus -contains 'VECI_AUTH_LOCAL=timeout'){
 Write-Output 'VECI_AUTH_DECISION=rpcd_unresponsive_recover_only_rpcd'
 @(Router-Action 'recover-rpcd') | ForEach-Object { Write-Output $_ }
} elseif($localStatus -contains 'VECI_AUTH_LOCAL=denied_fast'){
 Write-Output 'VECI_AUTH_DECISION=rpcd_responding_preserve_service'
} else { Fail 'rpcd_status_unexpected_no_mutation' }
$httpStatus=Probe-Https
Write-Output ('VECI_AUTH_HTTPS='+$httpStatus)
if($httpStatus -eq 'denied_fast'){
 Write-Output 'VECI_AUTH_UHTTPD=preserved'
 Write-Output 'VECI_AUTH_DUMMY_LOGIN_PATH=responsive'
 Write-Output 'VECI_AUTH_OFFICE=rpc_path_pass'
 Write-Output 'VECI_AUTH_NEXT=try_one_normal_veci_login'
 exit 0
}
if($httpStatus -ne 'timeout_or_transport_error'){ Fail 'unexpected_https_result_no_restart' }
Write-Output 'VECI_AUTH_DECISION=https_bridge_timeout_restart_uhttpd_once'
@(Router-Action 'recover-uhttpd') | ForEach-Object { Write-Output $_ }
Start-Sleep -Seconds 2
$after=Probe-Https
Write-Output ('VECI_AUTH_HTTPS_AFTER='+$after)
if($after -ne 'denied_fast'){ Fail 'http_auth_still_unresponsive_after_restart' }
Write-Output 'VECI_AUTH_DUMMY_LOGIN_PATH=responsive'
Write-Output 'VECI_AUTH_OFFICE=rpc_path_pass'
Write-Output 'VECI_AUTH_NEXT=try_one_normal_veci_login'
