# Targeted native XL two-owner inventory: device APK manifests + original packages on office PC.
# Read-only; no apk installation, deletion or service restart.
$ErrorActionPreference = 'Stop'
$script = 'https://raw.githubusercontent.com/aicoach-alpha/zbt-we5927-openwrt/8894cf244216005198c08fbc838a1d80d411dc11/scripts/veci-xl-two-owner-package-inventory-20261020.sh'
$cmd = "wget -qO /tmp/veci-xl-owners-inventory.sh $script && sh -n /tmp/veci-xl-owners-inventory.sh && sh /tmp/veci-xl-owners-inventory.sh"
& ssh root@192.168.1.1 $cmd
if ($LASTEXITCODE -ne 0) {
  Write-Output 'XL_OWNER_OFFICE=router_inventory_failed'
  exit 1
}
Write-Output 'XL_OWNER_OFFICE=router_inventory_complete'
$roots = @('C:\veci-build',"$env:USERPROFILE\Downloads")
$seen = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
$total = 0
foreach ($root in $roots) {
  if (-not (Test-Path -LiteralPath $root -PathType Container)) { continue }
  $files = Get-ChildItem -LiteralPath $root -File -Filter '*.apk' -Recurse -ErrorAction SilentlyContinue |
     Where-Object { $_.Name -match '^veci-telco-(?:xl-native|indonesia)-.*[.]apk$' }
  foreach ($file in $files) {
    if (-not $seen.Add($file.FullName)) { continue }
    if ($file.Length -lt 200 -or $file.Length -gt 1048576) { continue }
    $sha = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    Write-Output ('XL_OWNER_OFFICE_APK=' + $file.FullName)
    Write-Output ('XL_OWNER_OFFICE_SHA256=' + $sha)
    Write-Output ('XL_OWNER_OFFICE_BYTES=' + $file.Length)
    $total++
  }
}
Write-Output ('XL_OWNER_OFFICE_APK_COUNT=' + $total)
Write-Output 'XL_OWNER_ROUTER_MODIFICATIONS=none'
Write-Output 'XL_OWNER_PRODUCTION=unchanged'
