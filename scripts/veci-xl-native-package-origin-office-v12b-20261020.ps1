# VeCI XL v12b — one targeted APK manifest/payload capture from office laptop.
# No install, OTP, service restart, firmware flash, or public upload.
$ErrorActionPreference = 'Stop'
$dir = 'C:\veci-build\xl-native-origin'
$out = Join-Path $dir 'veci-xl-package-origin-v12b-20261020.tar.gz'
$hostName = 'root@192.168.1.1'
$exporter = 'https://raw.githubusercontent.com/aicoach-alpha/zbt-we5927-openwrt/25a65babad857e54cbf0b834aa5d4dcf2678abd5/scripts/veci-xl-native-package-origin-export-v12b-20261020.sh'
function Fail([string]$reason) { Write-Output ('XL_ORIGIN_V12B_CAPTURE=' + $reason); exit 1 }
if (Test-Path -LiteralPath $out) { Fail 'already_captured' }
New-Item -ItemType Directory -Force -Path $dir | Out-Null
$remoteCommand = 'wget -qO /tmp/veci-xl-origin-export-v12b.sh ' + $exporter + ' && sh -n /tmp/veci-xl-origin-export-v12b.sh && sh /tmp/veci-xl-origin-export-v12b.sh'
$receipt = @(& ssh $hostName $remoteCommand)
if ($LASTEXITCODE -ne 0) {
  $receipt | Where-Object { $_ -like 'XL_ORIGIN*' } | ForEach-Object { Write-Output $_ }
  Fail 'router_export_failed'
}
$hash = $null
foreach ($line in $receipt) {
  if ($line -match '^XL_ORIGIN_SHA256=([0-9a-f]{64})$') { $hash = $Matches[1] }
}
if ($receipt -notcontains 'XL_ORIGIN_V12B=ready' -or -not $hash) { Fail 'invalid_receipt' }
& scp -O ($hostName + ':/tmp/veci-xl-package-origin-v12b-20261020.tar.gz') $out
if ($LASTEXITCODE -ne 0) { Fail 'archive_copy_failed' }
$localHash = (Get-FileHash -LiteralPath $out -Algorithm SHA256).Hash.ToLowerInvariant()
if ($localHash -ne $hash) {
  Remove-Item -LiteralPath $out -Force
  Fail 'archive_hash_mismatch'
}
$members = @(& tar.exe -tzf $out)
if ($LASTEXITCODE -ne 0 -or $members.Count -lt 8) { Fail 'archive_manifest_missing' }
foreach ($member in $members) {
  $m = $member.TrimEnd('/')
  if ($m -notmatch '^(meta|payload)(/|$)' -or
      $m -match '(^|/)\.\.(/|$)' -or $m -match '^/' -or
      $m.Contains('\')) { Fail 'unsafe_archive_member' }
}
foreach ($line in $receipt) {
  if ($line -match '^XL_ORIGIN_(VECI_.*_(FILES|EXCLUDED)=|BYTES=|CONTENT=|PRIVATE_CONFIG=|PACKAGE_SCRIPTS=|ROUTER=)') {
    Write-Output $line
  }
}
Write-Output 'XL_ORIGIN_V12B_CAPTURE=pass'
Write-Output 'XL_ORIGIN_V12B_INTEGRITY=pass'
Write-Output ('XL_ORIGIN_V12B_SHA256=' + $hash)
Write-Output ('XL_ORIGIN_V12B_ARCHIVE=' + $out)
Write-Output 'XL_ORIGIN_NEXT=review_manifest_before_rebuilding_native_packages'
