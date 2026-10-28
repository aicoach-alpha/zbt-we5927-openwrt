# v13v safe replacement for the blocked v13u script.
# No ubus calls, no real credentials, no modem/LTE/rpcd action.
param([ValidateSet('Apply','Status','Rollback')][string]$Action='Apply')
$ErrorActionPreference='Stop'
$router='root@192.168.1.1'
$remote='/tmp/veci-v13v-http-no-auth-blocker-20261028.sh'
$local=Join-Path $env:TEMP 'veci-v13v-http-no-auth-blocker-20261028.sh'
$url='https://raw.githubusercontent.com/aicoach-alpha/zbt-we5927-openwrt/feb6c6bec41403561bf871c8c19277ed85bd3735/scripts/veci-v13v-http-no-auth-blocker-20261028.sh'
function Fail([string]$reason){ Write-Output ('VECI_V13V_OFFICE='+$reason); exit 1 }
Write-Output 'VECI_V13V_OFFICE_STAGE=downloading_pinned_script'
& curl.exe --fail --location --silent --show-error --max-time 15 $url --output $local
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $local -PathType Leaf)){
 Fail 'script_download_failed'
}
Write-Output 'VECI_V13V_OFFICE_STAGE=staging_router_script'
& scp.exe -O -o ConnectTimeout=8 $local ($router+':'+$remote)
if ($LASTEXITCODE -ne 0){ Fail 'router_script_transfer_failed' }
$mode=if($Action -eq 'Status'){'--status'}elseif($Action -eq 'Rollback'){'--rollback'}else{'--apply'}
Write-Output ('VECI_V13V_OFFICE_ACTION='+$Action)
Write-Output 'VECI_V13V_NO_UBUS_LOGIN_PROBE=true'
& ssh.exe -o ConnectTimeout=8 $router ('sh -n '+$remote+' && sh '+$remote+' '+$mode)
if ($LASTEXITCODE -ne 0){ Fail 'router_script_stopped_review_output_no_retry' }
if ($Action -ne 'Apply'){
 Write-Output 'VECI_V13V_OFFICE=command_complete'
 exit 0
}
# Single public static page fetch checks the new HTTP listener; no password.
$response=& curl.exe --silent --show-error --noproxy '*' --max-time 6 --connect-timeout 3 --output NUL --write-out 'http=%{http_code};seconds=%{time_total};redirect=%{redirect_url}' 'http://192.168.1.1/veci/'
$rc=$LASTEXITCODE
Write-Output ('VECI_V13V_HTTP_PAGE='+($response -join '').Trim())
if ($rc -ne 0){ Fail ('http_page_unreachable_exit_'+$rc) }
if (-not (($response -join '') -match 'http=(200|301|302|303|307|308);')){
 Fail 'http_page_unexpected_response'
}
Write-Output 'VECI_V13V_LAN_HTTP=reachable'
Write-Output 'VECI_V13V_LOGIN=not_yet_verified'
Write-Output 'VECI_V13V_OFFICE=http_enabled_integrity_pass'
