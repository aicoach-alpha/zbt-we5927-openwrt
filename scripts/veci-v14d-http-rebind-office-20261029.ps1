# VeCI v14d: restore LAN-bound HTTP after boot; preserve HTTPS login, LTE and rpcd.
$ErrorActionPreference='Stop'
$router='root@192.168.1.1'
$remote='/tmp/veci-v14d-lan-http-boot-rebind-20261029.sh'
$local=Join-Path $env:TEMP 'veci-v14d-lan-http-boot-rebind-20261029.sh'
$url='https://raw.githubusercontent.com/aicoach-alpha/zbt-we5927-openwrt/4a3871e0af47e28cf5cafe2b8161602697d1337d/scripts/veci-v14d-lan-http-boot-rebind-20261029.sh'
function Fail([string]$reason) { Write-Output ('VECI_V14D_OFFICE='+$reason); exit 1 }
Write-Output 'VECI_V14D_OFFICE_STAGE=fetch'
& curl.exe --fail --location --silent --show-error --max-time 15 $url --output $local
if($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $local -PathType Leaf)) { Fail 'source_download_failed' }
Write-Output 'VECI_V14D_OFFICE_STAGE=upload'
& scp.exe -O -o ConnectTimeout=8 $local ($router+':'+$remote)
if($LASTEXITCODE -ne 0) { Fail 'scp_failed' }
Write-Output 'VECI_V14D_OFFICE_STAGE=apply_and_single_integrity'
& ssh.exe -o ConnectTimeout=8 $router ('sh -n '+$remote+' && sh '+$remote+' --apply')
if($LASTEXITCODE -ne 0) { Fail 'router_preflight_or_apply_failed_no_blind_retry' }
# Verify both administrative transports after the single scoped uhttpd restart.
Write-Output 'VECI_V14D_OFFICE_STAGE=post_apply_transport_integrity'
$http=& curl.exe --silent --show-error --noproxy '*' --connect-timeout 3 --max-time 8 --output NUL --write-out 'http=%{http_code};seconds=%{time_total};redirect=%{redirect_url}' 'http://192.168.1.1/veci/'
$httpExit=$LASTEXITCODE
Write-Output ('VECI_V14D_HTTP_PAGE='+($http -join '').Trim())
if($httpExit -ne 0 -or -not (($http -join '') -match 'http=200;')) { Fail 'http_not_200_or_not_reachable' }
$https=& curl.exe --silent --show-error --insecure --noproxy '*' --connect-timeout 3 --max-time 8 --output NUL --write-out 'http=%{http_code};seconds=%{time_total}' 'https://192.168.1.1/veci/'
$httpsExit=$LASTEXITCODE
Write-Output ('VECI_V14D_HTTPS_PAGE='+($https -join '').Trim())
if($httpsExit -ne 0 -or -not (($https -join '') -match 'http=200;')) { Fail 'https_fallback_failed_review_no_retry' }
# One anonymous POST checks HTTP ubus transport without sending any credentials.
$req=Join-Path $env:TEMP 'veci-v14d-http-ubus.req'
$resp=Join-Path $env:TEMP 'veci-v14d-http-ubus.resp'
try {
 $body='{"jsonrpc":"2.0","id":901,"method":"call","params":["00000000000000000000000000000000","session","access",{"scope":"ubus","object":"session","function":"login"}]}'
 [IO.File]::WriteAllText($req,$body,(New-Object System.Text.UTF8Encoding($false)))
 $code=& curl.exe --silent --show-error --noproxy '*' --connect-timeout 3 --max-time 8 --output $resp --write-out 'http=%{http_code};seconds=%{time_total}' --header 'Content-Type: application/json' --data-binary ('@'+$req) 'http://192.168.1.1/ubus'
 $exitCode=$LASTEXITCODE
 Write-Output ('VECI_V14D_HTTP_UBUS='+($code -join '').Trim())
 if($exitCode -ne 0 -or -not (($code -join '') -match 'http=200;')) { Fail 'http_ubus_post_transport_failed' }
 try {
  $json=Get-Content -LiteralPath $resp -Raw | ConvertFrom-Json
  if($json.jsonrpc -ne '2.0' -or $null -eq $json.result) { Fail 'http_ubus_unexpected_json' }
 } catch { Fail 'http_ubus_invalid_json' }
 Write-Output 'VECI_V14D_HTTP_UBUS_RPC=responding_without_credentials'
} finally {
 Remove-Item -LiteralPath $req,$resp -Force -ErrorAction SilentlyContinue
}
Write-Output 'VECI_V14D_LOGIN=manual_browser_confirmation_required'
Write-Output 'VECI_V14D_OFFICE=live_http_transport_pass'
