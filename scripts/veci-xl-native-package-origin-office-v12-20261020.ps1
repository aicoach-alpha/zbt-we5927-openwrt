# VeCI XL v12: fetch original installed-package payload only to office laptop.
# Uses root@192.168.1.1; no GitHub upload, APK modifications or firmware flashing.
$ErrorActionPreference = 'Stop'
$folder = 'C:\veci-build\xl-native-origin'
$archive = Join-Path $folder 'veci-xl-package-origin-20261020.tar.gz'
$shaUrl = 'https://raw.githubusercontent.com/aicoach-alpha/zbt-we5927-openwrt/2e2f8c56f2c5115fc41bf6b7a30d65ee2bafe909/scripts/veci-xl-native-package-origin-export-v12-20261020.sh'
$router = 'root@192.168.1.1'
function Fail([string]$reason) { Write-Output ('XL_ORIGIN_CAPTURE=' + $reason); exit 1 }
if (Test-Path -LiteralPath $archive) { Fail 'local_snapshot_exists' }
New-Item -ItemType Directory -Force -Path $folder | Out-Null
$remote = 'wget -qO /tmp/veci-xl-package-origin-v12.sh ' + $shaUrl + ' && sh -n /tmp/veci-xl-package-origin-v12.sh && sh /tmp/veci-xl-package-origin-v12.sh'
$receipt = @(& ssh $router $remote)
if ($LASTEXITCODE -ne 0) {
 $receipt | Where-Object { $_ -like 'XL_ORIGIN=*' } | ForEach-Object { Write-Output $_ }
 Fail 'router_capture_failed'
}
$hash = $null
foreach ($line in $receipt) {
 if ($line -match '^XL_ORIGIN_SHA256=([0-9a-f]{64})$') { $hash = $Matches[1] }
}
if (-not $hash -or $receipt -notcontains 'XL_ORIGIN=ready') { Fail 'receipt_missing' }
& scp -O ($router + ':/tmp/veci-xl-package-origin-20261020.tar.gz') $archive
if ($LASTEXITCODE -ne 0) { Fail 'scp_failed' }
$actual = (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actual -ne $hash) {
 Remove-Item -LiteralPath $archive -Force
 Fail 'checksum_failed'
}
$members = @(& tar.exe -tzf $archive)
if ($LASTEXITCODE -ne 0 -or $members.Count -lt 8) { Fail 'manifest_unavailable' }
foreach ($member in $members) {
 $p = $member.TrimEnd('/')
 if ($p -notmatch '^(meta|payload)(/|$)' -or $p -match '(^|/)\.\.(/|$)' -or $p -match '^/') {
  Fail 'unsafe_archive_manifest'
 }
}
# Keep original package payload private on the office laptop.
foreach ($line in $receipt) {
 if ($line -match '^XL_ORIGIN_(VECI_|BYTES=|INSTALL_SCRIPTS=|CONTENT=|ROUTER=)') { Write-Output $line }
}
Write-Output 'XL_ORIGIN_CAPTURE=pass'
Write-Output 'XL_ORIGIN_INTEGRITY=pass'
Write-Output ('XL_ORIGIN_SHA256=' + $hash)
Write-Output ('XL_ORIGIN_LOCAL_ARCHIVE=' + $archive)
Write-Output 'XL_ORIGIN_PACKAGE_REBUILD=needs_metadata_review'
Write-Output 'XL_ORIGIN_ROUTER=unchanged'
