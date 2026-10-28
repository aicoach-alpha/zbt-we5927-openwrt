# VeCI v13 — guarded LTE watchdog frequency change (office Windows PC).
# Scope: only two UCI keys on 192.168.1.1, backup and one watchdog service restart.
param(
 [ValidateSet('Apply','Status','Rollback')][string]$Action='Apply'
)
$ErrorActionPreference='Stop'
$router='root@192.168.1.1'
$script='/tmp/veci-v13-lte-fast-reconnect-20261028.sh'
$local=Join-Path $env:TEMP 'veci-v13-lte-fast-reconnect-20261028.sh'
$url='https://raw.githubusercontent.com/aicoach-alpha/zbt-we5927-openwrt/f00abdfe65440d838a7dbc8ccb9200ca4a443a2f/scripts/veci-v13-lte-fast-reconnect-20261028.sh'
function Fail([string]$reason) { Write-Output ('VECI_FAST_RECONNECT_OFFICE='+$reason); exit 1 }
& curl.exe --fail --location --silent --show-error $url --output $local
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $local -PathType Leaf)) {
 Fail 'pinned_script_download_failed'
}
& scp.exe -O $local ($router+':'+$script)
if ($LASTEXITCODE -ne 0) { Fail 'router_script_transfer_failed' }
$mode=if($Action -eq 'Apply'){'--apply'}elseif($Action -eq 'Rollback'){'--rollback'}else{'--status'}
Write-Output ('VECI_FAST_RECONNECT_REQUEST='+$Action)
if ($Action -eq 'Apply') {
 Write-Output 'VECI_FAST_RECONNECT_NOTE=one_targeted_watchdog_restart_may_briefly_interrupt_lte'
}
& ssh.exe $router ('sh -n '+$script+' && sh '+$script+' '+$mode)
if ($LASTEXITCODE -ne 0) { Fail 'router_action_failed_review_receipt_before_retry' }
Write-Output ('VECI_FAST_RECONNECT_OFFICE='+$Action.ToLowerInvariant()+'_completed')
