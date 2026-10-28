# VeCI v13x: exact stale process cleanup and one LAN-only HTTP cutover.
# Password supplied only to SSH by user; no VeCI login or ubus authentication probes.
$ErrorActionPreference='Stop'
$target='root@192.168.1.1'
$remote='/tmp/veci-v13x-safe-orphan-cleanup-http-20261028.sh'
$local=Join-Path $env:TEMP 'veci-v13x-safe-orphan-cleanup-http-20261028.sh'
$url='https://raw.githubusercontent.com/aicoach-alpha/zbt-we5927-openwrt/37a3437ad2ee73a5ac1aa7332ab68370209e8bef/scripts/veci-v13x-safe-orphan-cleanup-http-20261028.sh'
function Fail([string]$reason){ Write-Output ('VECI_V13X_OFFICE='+$reason); exit 1 }
Write-Output 'VECI_V13X_OFFICE_STAGE=fetch'
& curl.exe --fail --location --silent --show-error --max-time 12 $url --output $local
if($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $local -PathType Leaf)){ Fail 'source_download_failed' }
Write-Output 'VECI_V13X_OFFICE_STAGE=upload'
& scp.exe -O -o ConnectTimeout=8 $local ($target+':'+$remote)
if($LASTEXITCODE -ne 0){ Fail 'upload_failed' }
Write-Output 'VECI_V13X_OFFICE_STAGE=exact_orphan_cleanup_and_http_apply'
& ssh.exe -o ConnectTimeout=8 $target ('sh -n '+$remote+' && sh '+$remote)
if($LASTEXITCODE -ne 0){ Fail 'router_stopped_no_blind_retry' }
Write-Output 'VECI_V13X_OFFICE_STAGE=one_anonymous_http_page_check'
$receipt=& curl.exe --silent --show-error --noproxy '*' --connect-timeout 3 --max-time 6 --output NUL --write-out 'http=%{http_code};seconds=%{time_total};redirect=%{redirect_url}' 'http://192.168.1.1/veci/'
$rc=$LASTEXITCODE
Write-Output ('VECI_V13X_HTTP_PAGE='+($receipt -join '').Trim())
if($rc -ne 0){ Fail ('http_unreachable_exit_'+$rc) }
if(-not (($receipt -join '') -match 'http=200;')){ Fail 'http_page_not_200_or_redirected' }
Write-Output 'VECI_V13X_HTTP=reachable'
Write-Output 'VECI_V13X_LOGIN=not_yet_verified'
Write-Output 'VECI_V13X_OFFICE=http_cutover_integrity_pass'
