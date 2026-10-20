# Capture only the installed source code of native XL RPCs from the office-connected router.
# Output remains on this laptop; do NOT upload the archive to a public repository.
$ErrorActionPreference = 'Stop'
$target = 'C:\veci-build\xl-core-source'
$archive = Join-Path $target 'veci-xl-core-source-20261020.tar.gz'
$router = 'root@192.168.1.1'
$sourceUrl = 'https://raw.githubusercontent.com/aicoach-alpha/zbt-we5927-openwrt/b3806b2dc402dd026112fe398bd1dab9d9180146/scripts/veci-xl-core-source-export-20261020.sh'
function Fail([string]$code) { Write-Output ('XL_CORE_CAPTURE=' + $code); exit 1 }
if (Test-Path -LiteralPath $archive) { Fail 'snapshot_already_exists' }
New-Item -ItemType Directory -Force -Path $target | Out-Null
$remote = 'wget -qO /tmp/veci-xl-core-export.sh ' + $sourceUrl + ' && sh -n /tmp/veci-xl-core-export.sh && sh /tmp/veci-xl-core-export.sh'
$output = @(& ssh $router $remote)
if ($LASTEXITCODE -ne 0) { Fail 'router_export_failed' }
$checksum = $null
foreach ($line in $output) {
  if ($line -match '^XL_CORE_SHA256=([0-9a-f]{64})$') { $checksum = $Matches[1] }
}
if (-not $checksum -or -not ($output -contains 'XL_CORE_EXPORT=ready')) { Fail 'receipt_invalid' }
& scp -O ($router + ':/tmp/veci-xl-core-source-20261020.tar.gz') $archive
if ($LASTEXITCODE -ne 0) { Fail 'archive_copy_failed' }
if ((Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant() -ne $checksum) {
  Remove-Item -LiteralPath $archive -Force
  Fail 'archive_checksum_mismatch'
}
$expected = @(
  'usr/libexec/rpcd/veci.xl',
  'usr/libexec/rpcd/veci.quota',
  'usr/share/rpcd/acl.d/veci-xl-owner.json',
  'usr/libexec/veci-xl-session-clear'
)
$members = @(& tar.exe -tf $archive)
if ($LASTEXITCODE -ne 0) { Fail 'tar_list_failed' }
if (($members.Count -ne 4) -or (@(Compare-Object ($expected | Sort-Object) ($members | Sort-Object))).Count -ne 0) {
  Fail 'unexpected_archive_contents'
}
& tar.exe -xzf $archive -C $target
if ($LASTEXITCODE -ne 0) { Fail 'extract_failed' }
$rpcXl = Join-Path $target 'usr/libexec/rpcd/veci.xl'
$rpcQuota = Join-Path $target 'usr/libexec/rpcd/veci.quota'
$acl = Join-Path $target 'usr/share/rpcd/acl.d/veci-xl-owner.json'
$clear = Join-Path $target 'usr/libexec/veci-xl-session-clear'
foreach ($file in @($rpcXl, $rpcQuota, $acl, $clear)) {
  if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { Fail 'source_file_missing' }
}
if (-not (Select-String -LiteralPath $rpcXl -SimpleMatch -Quiet 'logout) logout_local ;;')) { Fail 'logout_source_missing' }
if (-not (Select-String -LiteralPath $rpcQuota -SimpleMatch -Quiet '/usr/libexec/veci-xl-quota-session-gate --status')) { Fail 'quota_gate_source_missing' }
try {
  $ownerAcl = Get-Content -LiteralPath $acl -Raw | ConvertFrom-Json
} catch {
  Fail 'acl_parse_failed'
}
if (-not (Select-String -LiteralPath $acl -SimpleMatch -Quiet '"logout"')) { Fail 'acl_logout_missing' }
Write-Output 'XL_CORE_CAPTURE=pass'
Write-Output 'XL_CORE_SOURCE=collected'
Write-Output 'XL_CORE_INTEGRITY=pass'
Write-Output ('XL_CORE_SHA256=' + $checksum)
Write-Output ('XL_CORE_ARCHIVE=' + $archive)
Write-Output 'XL_CORE_PRODUCTION=unchanged'
