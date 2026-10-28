# VeCI v13: one read-only router login/source capture, no mutation of production.
# Run in Windows PowerShell on the office laptop that reaches 192.168.1.1.
$ErrorActionPreference = 'Stop'
$target = 'root@192.168.1.1'
$workspace = 'C:\veci-build\veci-v13-readonly-20261028'
$localShell = Join-Path $workspace 'veci-v13-audit.sh'
$archive = Join-Path $workspace 'veci-v13-ui-source-20261028.tar.gz'
$remoteScript = '/tmp/veci-v13-source-login-audit-20261028.sh'
$remoteArchive = '/tmp/veci-v13-ui-source-20261028.tar.gz'
$url = 'https://raw.githubusercontent.com/aicoach-alpha/zbt-we5927-openwrt/165f5010118d596ad199db7e2614f173d7c5277f/scripts/veci-v13-source-login-audit-20261028.sh'
function Fail([string]$reason) { Write-Output ('VECI_V13_OFFICE=' + $reason); exit 1 }
if (-not (Test-Path -LiteralPath $workspace)) {
 New-Item -ItemType Directory -Path $workspace | Out-Null
} else {
 $attr = (Get-Item -LiteralPath $workspace).Attributes
 if ($attr -band [IO.FileAttributes]::ReparsePoint) { Fail 'workspace_link_disallowed' }
}
if (Test-Path -LiteralPath $archive) { Fail 'existing_source_archive_preserved_review_before_retry' }
& curl.exe --fail --location --silent --show-error $url --output $localShell
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $localShell -PathType Leaf)) { Fail 'audit_source_fetch_failed' }
& scp.exe -O $localShell ($target + ':' + $remoteScript)
if ($LASTEXITCODE -ne 0) { Fail 'audit_stage_failed' }
& ssh.exe $target ('sh -n ' + $remoteScript + ' && sh ' + $remoteScript)
if ($LASTEXITCODE -ne 0) { Fail 'router_audit_failed_no_change' }
& scp.exe -O ($target + ':' + $remoteArchive) $archive
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $archive -PathType Leaf)) { Fail 'archive_copy_failed' }
Write-Output ('VECI_V13_LOCAL_SOURCE_ARCHIVE=' + $archive)
Write-Output ('VECI_V13_LOCAL_SOURCE_SHA256=' + (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant())
# One anonymous, read-only HTTP/ubus transport probe; NO login/password sent.
$request = '{"jsonrpc":"2.0","id":1,"method":"call","params":["00000000000000000000000000000000","session","access",{"scope":"ubus","object":"session","function":"login"}]}'
$probeFile = Join-Path $workspace 'http-probe-response.json'
$info = & curl.exe --silent --show-error --insecure --max-time 8 --output $probeFile --write-out 'http=%{http_code};duration=%{time_total}' --header 'Content-Type: application/json' --data $request https://192.168.1.1/ubus
if ($LASTEXITCODE -eq 0) {
 Write-Output ('VECI_V13_HTTPS_UBUS=' + ($info -join '').Trim())
 if ((Get-Content -LiteralPath $probeFile -Raw) -match '"jsonrpc"\s*:\s*"2\.0"') {
  Write-Output 'VECI_V13_HTTP_JSONRPC=responding'
 } else {
  Write-Output 'VECI_V13_HTTP_JSONRPC=unexpected_payload'
 }
} else {
 Write-Output ('VECI_V13_HTTPS_UBUS=network_failure_' + $LASTEXITCODE)
}
Write-Output 'VECI_V13_PRODUCTION=unchanged'
Write-Output 'VECI_V13_OFFICE=read_only_pass'
Write-Output 'VECI_V13_NEXT=upload_only_the_targz_and_paste_terminal_status'
