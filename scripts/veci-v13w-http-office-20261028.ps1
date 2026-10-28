# v13w: replace interrupted v13v. No internal login/RPC/netlink/IP check.
param([ValidateSet('Apply','Rollback')][string]$Action='Apply')
$ErrorActionPreference='Stop'
$router='root@192.168.1.1'
$remote='/tmp/veci-v13w-http-without-lan-probe-20261028.sh'
$local=Join-Path $env:TEMP 'veci-v13w-http-without-lan-probe-20261028.sh'
$url='https://raw.githubusercontent.com/aicoach-alpha/zbt-we5927-openwrt/00590af2c5156d8b8e5c1765d298d82ea2f1564b/scripts/veci-v13w-http-without-lan-probe-20261028.sh'
function Fail([string]$why){Write-Output ('VECI_V13W_OFFICE='+$why);exit 1}
Write-Output 'VECI_V13W_STAGE=download'
& curl.exe --silent --show-error --fail --location --max-time 15 $url --output $local
if($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $local -PathType Leaf)){Fail 'download_failed'}
Write-Output 'VECI_V13W_STAGE=upload'
& scp.exe -O -o ConnectTimeout=8 $local ($router+':'+$remote)
if($LASTEXITCODE -ne 0){Fail 'scp_failed'}
$mode=if($Action -eq 'Rollback'){'--rollback'}else{'--apply'}
Write-Output ('VECI_V13W_ACTION='+$Action)
Write-Output 'VECI_V13W_HTTP_SCOPE=LAN_only_no_ubus_login_no_network_ip_check'
& ssh.exe -o ConnectTimeout=8 $router ('sh -n '+$remote+' && sh '+$remote+' '+$mode)
if($LASTEXITCODE -ne 0){Fail 'router_stopped_no_blind_retry'}
if($Action -eq 'Rollback'){Write-Output 'VECI_V13W_OFFICE=rollback_reported';exit 0}
# Exactly one anonymous static page GET, with a bounded timeout and redirects rejected.
$result=& curl.exe --silent --show-error --noproxy '*' --connect-timeout 3 --max-time 6 --output NUL --write-out 'http=%{http_code};seconds=%{time_total}' 'http://192.168.1.1/veci/'
$rc=$LASTEXITCODE
Write-Output ('VECI_V13W_HTTP_PAGE='+($result -join '').Trim())
if($rc -ne 0){Fail ('http_get_failed_exit_'+$rc)}
if(-not (($result -join '') -match 'http=200;')){Fail 'http_page_not_200'}
Write-Output 'VECI_V13W_HTTP=reachable'
Write-Output 'VECI_V13W_LOGIN=not_yet_verified'
Write-Output 'VECI_V13W_OFFICE=http_live_integrity_pass'
