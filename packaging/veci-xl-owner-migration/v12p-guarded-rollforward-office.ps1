# VeCI v12p: office-controlled, two-owner signed feed roll-forward.
# Use only for a NEW signed snapshot; v12o has the same versions as production.
param(
 [switch]$Apply,
 [switch]$Rollback,
 [string]$ReleasePath = 'C:\veci-build\xl-native-feed-releases\native-0.3.8-r2__indonesia-0.2.2-r2'
)
$ErrorActionPreference = 'Stop'
$router = 'root@192.168.1.1'
$stage = '/tmp/veci-xl-v12p'
$url = 'https://raw.githubusercontent.com/aicoach-alpha/zbt-we5927-openwrt/bc32f4051eacf0a9ddd51524640bafada14106c8/packaging/veci-xl-owner-migration/v12p-guarded-rollforward.sh'
function Fail([string]$reason) { Write-Output ('XL_V12P_OFFICE=' + $reason); exit 1 }
if ($Apply -eq $Rollback) { Fail 'choose_exactly_one_of_apply_or_rollback' }
$script = Join-Path $env:TEMP 'veci-xl-v12p-guarded-rollforward.sh'
& curl.exe --fail --location --silent --show-error $url --output $script
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $script -PathType Leaf)) { Fail 'installer_download_failed' }
if ($Rollback) {
  & ssh $router ('if [ -e ' + $stage + ' ]; then [ -d ' + $stage + ' ] && [ ! -L ' + $stage + ' ]; else mkdir -m 700 ' + $stage + '; fi')
  if ($LASTEXITCODE -ne 0) { Fail 'rollback_staging_unavailable' }
  & scp -O $script ($router + ':' + $stage + '/rollforward.sh')
  if ($LASTEXITCODE -ne 0) { Fail 'rollback_script_transfer_failed' }
  & ssh $router ('sh -n ' + $stage + '/rollforward.sh && sh ' + $stage + '/rollforward.sh rollback')
  if ($LASTEXITCODE -ne 0) { Fail 'rollback_not_confirmed' }
  Write-Output 'XL_V12P_OFFICE=rollback_command_completed'
  exit 0
}
$receipt = Join-Path $ReleasePath 'release-receipt.txt'
if (-not (Test-Path -LiteralPath $receipt -PathType Leaf)) { Fail 'release_receipt_missing' }
$data = @{}
foreach ($line in (Get-Content -LiteralPath $receipt)) {
 if ($line -notmatch '^([a-z_]+)=(.*)$') { Fail 'release_receipt_invalid' }
 if ($data.ContainsKey($Matches[1])) { Fail 'release_receipt_duplicate_field' }
 $data[$Matches[1]] = $Matches[2]
}
foreach ($key in @('native_version','indonesia_version','native_sha256','indonesia_sha256','index_sha256')) {
 if (-not $data.ContainsKey($key)) { Fail 'release_receipt_incomplete' }
}
foreach ($key in @('native_version','indonesia_version')) {
 if ($data[$key] -notmatch '^[0-9]+\.[0-9]+\.[0-9]+-r[0-9]+$') { Fail 'release_version_invalid' }
}
foreach ($key in @('native_sha256','indonesia_sha256','index_sha256')) {
 if ($data[$key] -notmatch '^[0-9a-f]{64}$') { Fail 'release_digest_invalid' }
}
$native = 'veci-telco-xl-native-' + $data.native_version + '.apk'
$indonesia = 'veci-telco-indonesia-' + $data.indonesia_version + '.apk'
$items = @(
 @{Name=$native;Hash=$data.native_sha256},
 @{Name=$indonesia;Hash=$data.indonesia_sha256},
 @{Name='Packages.adb';Hash=$data.index_sha256}
)
foreach ($item in $items) {
 $file = Join-Path $ReleasePath $item.Name
 if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { Fail 'signed_release_file_missing' }
 $f = Get-Item -LiteralPath $file -Force
 if ($f.Attributes -band [IO.FileAttributes]::ReparsePoint) { Fail 'release_symlink_disallowed' }
 if ((Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLowerInvariant() -ne $item.Hash) {
  Fail 'release_digest_mismatch'
 }
}
Write-Output 'XL_V12P_LOCAL_HASHES=pass'
& ssh $router ('umask 077; if [ -e ' + $stage + ' ]; then exit 4; fi; mkdir -m 700 ' + $stage + ' && mkdir -m 700 ' + $stage + '/feed')
if ($LASTEXITCODE -ne 0) { Fail 'router_staging_exists_or_unavailable' }
foreach ($item in $items) {
 & scp -O (Join-Path $ReleasePath $item.Name) ($router + ':' + $stage + '/feed/' + $item.Name)
 if ($LASTEXITCODE -ne 0) { Fail 'release_transfer_failed' }
}
& scp -O $receipt ($router + ':' + $stage + '/release-receipt.txt')
if ($LASTEXITCODE -ne 0) { Fail 'receipt_transfer_failed' }
& scp -O $script ($router + ':' + $stage + '/rollforward.sh')
if ($LASTEXITCODE -ne 0) { Fail 'script_transfer_failed' }
& ssh $router ('sh -n ' + $stage + '/rollforward.sh && sh ' + $stage + '/rollforward.sh apply')
if ($LASTEXITCODE -ne 0) { Fail 'release_failed_review_output_before_retry' }
Write-Output 'XL_V12P_OFFICE=command_completed'
