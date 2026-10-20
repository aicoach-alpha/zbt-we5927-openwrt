# VeCI XL v12d: reconcile exactly two excluded entries from the v12b snapshot.
# Preserve LuCI quota.js byte-for-byte. The .list file is OpenWrt build metadata.
$ErrorActionPreference = 'Stop'
$root = 'C:\veci-build\xl-native-origin\staged-v12b'
$meta = Join-Path $root 'meta'
$localQuota = Join-Path $root 'payload\veci-telco-indonesia\www\luci-static\resources\view\veci\quota.js'
$localList = Join-Path $meta 'veci-telco-indonesia.original.list'
$existingReport = Join-Path $root 'inventory.json'
$report = Join-Path $root 'inventory-v12d.json'
$router = 'root@192.168.1.1'
$remoteQuota = '/www/luci-static/resources/view/veci/quota.js'
$remoteList = '/lib/apk/packages/veci-telco-indonesia.list'
function Fail([string]$code) { Write-Output ('XL_V12D=' + $code); exit 1 }
if (-not (Test-Path -LiteralPath $existingReport -PathType Leaf)) { Fail 'v12c_inventory_missing' }
if (Test-Path -LiteralPath $report) { Fail 'already_reconciled' }
if (Test-Path -LiteralPath $localQuota) { Fail 'quota_stage_already_present' }
if (Test-Path -LiteralPath $localList) { Fail 'apk_list_stage_already_present' }
$excluded = Join-Path $meta 'veci-telco-indonesia.excluded-paths'
if (-not (Test-Path -LiteralPath $excluded -PathType Leaf)) { Fail 'exclusions_missing' }
$excludedPaths = @(Get-Content -LiteralPath $excluded | Where-Object { $_.Length -gt 0 } | Sort-Object)
$expectedPaths = @('lib/apk/packages/veci-telco-indonesia.list', 'www/luci-static/resources/view/veci/quota.js') | Sort-Object
if (@(Compare-Object $excludedPaths $expectedPaths).Count -gt 0 -or $excludedPaths.Count -ne 2) {
  Fail 'unexpected_excluded_paths'
}
$tmp = Join-Path $root 'v12d-temp'
if (Test-Path -LiteralPath $tmp) { Fail 'temporary_dir_exists' }
New-Item -ItemType Directory -Path $tmp | Out-Null
try {
  $remoteCommand = 'set -e; for f in /www/luci-static/resources/view/veci/quota.js /lib/apk/packages/veci-telco-indonesia.list; do test -f "$f" && test ! -L "$f" || exit 22; apk info -W "$f"; sha256sum "$f"; done'
  $lines = @(& ssh $router $remoteCommand)
  if ($LASTEXITCODE -ne 0) { Fail 'remote_file_preflight_failed' }
  $owners = @($lines | Where-Object { $_ -match ' is owned by veci-telco-indonesia-' })
  if ($owners.Count -ne 2) { Fail 'remote_file_owner_mismatch' }
  $hashes = @{}
  foreach ($line in $lines) {
    if ($line -match '^([0-9a-f]{64})\s+(/\S+)$') { $hashes[$Matches[2]] = $Matches[1] }
  }
  if ($hashes.Count -ne 2 -or -not $hashes.ContainsKey($remoteQuota) -or -not $hashes.ContainsKey($remoteList)) {
    Fail 'remote_hash_receipt_missing'
  }
  & scp -O ($router + ':' + $remoteQuota) ($router + ':' + $remoteList) $tmp
  if ($LASTEXITCODE -ne 0) { Fail 'source_copy_failed' }
  $tmpQuota = Join-Path $tmp 'quota.js'
  $tmpList = Join-Path $tmp 'veci-telco-indonesia.list'
  if (-not (Test-Path -LiteralPath $tmpQuota -PathType Leaf) -or -not (Test-Path -LiteralPath $tmpList -PathType Leaf)) {
    Fail 'copied_source_missing'
  }
  if ((Get-FileHash -LiteralPath $tmpQuota -Algorithm SHA256).Hash.ToLowerInvariant() -ne $hashes[$remoteQuota]) {
    Fail 'quota_hash_mismatch'
  }
  if ((Get-FileHash -LiteralPath $tmpList -Algorithm SHA256).Hash.ToLowerInvariant() -ne $hashes[$remoteList]) {
    Fail 'package_list_hash_mismatch'
  }
  New-Item -ItemType Directory -Force -Path (Split-Path -Parent $localQuota) | Out-Null
  Move-Item -LiteralPath $tmpQuota -Destination $localQuota
  Move-Item -LiteralPath $tmpList -Destination $localList
  $record = [ordered]@{
    OriginalSnapshot = '6026d5d1d4a9ebb8022470994c9c7d01904cd3fc41095de50e0488955cb6a2f8'
    NativeXlCopiedFiles = 15
    TelcoIndonesiaCopiedFiles = 6
    ExcludedApplicationFilesRemaining = 0
    BuildGeneratedManifest = 'lib/apk/packages/veci-telco-indonesia.list'
    QuotaJsSha256 = $hashes[$remoteQuota]
    OriginalListSha256 = $hashes[$remoteList]
    OriginalInstallScriptsRecovered = $false
    SameNameApkInstallPermitted = $false
  }
  $record | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $report -Encoding UTF8
  Write-Output 'XL_V12D=pass'
  Write-Output 'XL_V12D_INTEGRITY=pass'
  Write-Output 'XL_V12D_NATIVE_FILES=15'
  Write-Output 'XL_V12D_INDONESIA_FILES=6'
  Write-Output 'XL_V12D_EXCLUDED_APPLICATION_FILES=0'
  Write-Output 'XL_V12D_PACKAGE_LIST=preserved_as_metadata'
  Write-Output ('XL_V12D_QUOTA_JS_SHA256=' + $hashes[$remoteQuota])
  Write-Output ('XL_V12D_REPORT=' + $report)
  Write-Output 'XL_V12D_NEXT=complete_upgrade_build_source_and_reconcile_install_scripts'
  Write-Output 'XL_V12D_ROUTER=unchanged'
} finally {
  if (Test-Path -LiteralPath $tmp) { Remove-Item -LiteralPath $tmp -Force -Recurse }
}
