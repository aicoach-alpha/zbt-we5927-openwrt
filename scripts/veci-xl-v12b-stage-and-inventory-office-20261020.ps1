# VeCI v12c: inspect and stage the already captured installed APK manifest.
# Read-only archive analysis on the office laptop; no SSH or APK deployment.
$ErrorActionPreference = 'Stop'
$archive = 'C:\veci-build\xl-native-origin\veci-xl-package-origin-v12b-20261020.tar.gz'
$sha = '6026d5d1d4a9ebb8022470994c9c7d01904cd3fc41095de50e0488955cb6a2f8'
$base = 'C:\veci-build\xl-native-origin\staged-v12b'
function Fail([string] $reason) {
  Write-Output ('XL_V12C_STAGE=' + $reason)
  exit 1
}
if (-not (Test-Path -LiteralPath $archive -PathType Leaf)) { Fail 'archive_missing' }
if ((Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant() -ne $sha) {
  Fail 'archive_digest_mismatch'
}
if (Test-Path -LiteralPath $base) { Fail 'staging_already_exists' }
$members = @(& tar.exe -tzf $archive)
if ($LASTEXITCODE -ne 0 -or $members.Count -lt 8) { Fail 'archive_manifest_missing' }
foreach ($member in $members) {
  $p = $member.TrimEnd('/')
  if ($p -notmatch '^(meta|payload)(/|$)' -or
      $p -match '(^|/)\.\.(/|$)' -or
      $p -match '^/' -or $p.Contains('\') -or
      $p -match '(^|/)\.(?:/|$)') { Fail 'unsafe_archive_path' }
}
New-Item -ItemType Directory -Path $base | Out-Null
& tar.exe -xzf $archive -C $base
if ($LASTEXITCODE -ne 0) { Fail 'extract_failed' }
$meta = Join-Path $base 'meta'
$countsFile = Join-Path $meta 'counts.txt'
if (-not (Test-Path -LiteralPath $countsFile -PathType Leaf)) { Fail 'counts_missing' }
$packages = @('veci-telco-xl-native', 'veci-telco-indonesia')
$all = @()
foreach ($name in $packages) {
  $manifest = Join-Path $meta ($name + '.paths')
  $exclude = Join-Path $meta ($name + '.excluded-paths')
  if (-not (Test-Path -LiteralPath $manifest -PathType Leaf)) { Fail 'package_paths_missing' }
  $listed = @(Get-Content -LiteralPath $manifest | Where-Object { $_.Length -gt 0 })
  $excluded = @()
  if (Test-Path -LiteralPath $exclude -PathType Leaf) {
    $excluded = @(Get-Content -LiteralPath $exclude | Where-Object { $_.Length -gt 0 })
  }
  foreach ($path in $listed) {
    if ($path -notmatch '^(usr/|www/veci/|etc/init.d/veci-|etc/hotplug.d/|etc/uci-defaults/)' -or
        $path -match '(^|/)\.\.(/|$)' -or $path.Contains('\')) {
      Fail 'unsafe_captured_path'
    }
    $staged = Join-Path (Join-Path (Join-Path $base 'payload') $name) ($path.Replace('/', '\'))
    if (-not (Test-Path -LiteralPath $staged -PathType Leaf)) { Fail 'captured_file_missing' }
  }
  $row = [PSCustomObject]@{
    Package = $name
    Captured = $listed.Count
    Excluded = $excluded.Count
    ExcludedPaths = $excluded
  }
  $all += $row
  Write-Output ('XL_V12C_PACKAGE=' + $name)
  Write-Output ('XL_V12C_CAPTURED=' + $listed.Count)
  Write-Output ('XL_V12C_EXCLUDED=' + $excluded.Count)
  foreach ($path in $excluded) {
    # Path only. Never show file contents or extract excluded credentials.
    Write-Output ('XL_V12C_EXCLUDED_PATH=' + $path)
  }
}
$counts = @(Get-Content -LiteralPath $countsFile | Where-Object { $_.Length -gt 0 })
if ($counts.Count -ne 2) { Fail 'package_count_mismatch' }
$expected = @{'veci-telco-xl-native'=15; 'veci-telco-indonesia'=5}
foreach ($row in $all) {
  if ($row.Captured -ne $expected[$row.Package]) { Fail 'unexpected_file_inventory' }
}
$record = [ordered]@{
  SourceArchiveSha256 = $sha
  Packages = @($all)
  CompletePayload = (($all | Measure-Object -Property Excluded -Sum).Sum -eq 0)
  InstallScriptsRecovered = $false
  Installable = $false
}
$report = Join-Path $base 'inventory.json'
$record | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $report -Encoding UTF8
Write-Output 'XL_V12C_STAGE=pass'
Write-Output 'XL_V12C_SOURCE_INTEGRITY=pass'
Write-Output ('XL_V12C_REPORT=' + $report)
Write-Output 'XL_V12C_PACKAGE_INSTALL=blocked_pending_original_scripts_and_exclusions'
Write-Output 'XL_V12C_ROUTER=unchanged'
