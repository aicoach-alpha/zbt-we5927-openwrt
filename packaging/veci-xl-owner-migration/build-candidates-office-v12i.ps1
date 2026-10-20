# VeCI XL v12i: signed, staged-only same-name APK candidate build on office laptop.
# Never changes the router and never uploads captured binaries/credentials.
$ErrorActionPreference = 'Stop'
$source = 'C:\veci-build\xl-native-origin\staged-v12b'
$build = 'C:\veci-build\xl-native-candidates-v12i'
$dist = Join-Path $build 'dist'
$keys = 'C:\veci-build\keys'
$report = Join-Path $source 'inventory-v12d.json'
$hookArchive = 'C:\veci-build\xl-native-origin\veci-xl-v12h-original-hooks-20261020.tar.gz'
$hookSha256 = 'b10ee80013608f6f1f66d234588f3cd708c79e5d8cfc3ffbdf960b07e2a33ca7'
$listFile = Join-Path $source 'meta\veci-telco-indonesia.original.list'
$builder = Join-Path $build 'build-in-docker-v12i.sh'
$url = 'https://raw.githubusercontent.com/aicoach-alpha/zbt-we5927-openwrt/c1b365c3ce12dc2a9fa380e6aa6cbcd92beec451/packaging/veci-xl-owner-migration/build-candidates-in-docker-v12i.sh'
function Fail([string]$code) { Write-Output ('XL_V12I_OFFICE=' + $code); exit 1 }
if (-not (Test-Path -LiteralPath $report -PathType Leaf)) { Fail 'v12d_report_missing' }
try { $receipt = Get-Content -LiteralPath $report -Raw | ConvertFrom-Json }
catch { Fail 'v12d_report_invalid' }
if ($receipt.OriginalSnapshot -ne '6026d5d1d4a9ebb8022470994c9c7d01904cd3fc41095de50e0488955cb6a2f8' -or
    $receipt.NativeXlCopiedFiles -ne 15 -or
    $receipt.TelcoIndonesiaCopiedFiles -ne 6 -or
    $receipt.ExcludedApplicationFilesRemaining -ne 0 -or
    $receipt.OriginalInstallScriptsRecovered -ne $false) {
    Fail 'inventory_contract_mismatch'
}
$quota = Join-Path $source 'payload\veci-telco-indonesia\www\luci-static\resources\view\veci\quota.js'
if (-not (Test-Path -LiteralPath $quota -PathType Leaf)) { Fail 'quota_js_missing' }
if ((Get-FileHash -LiteralPath $quota -Algorithm SHA256).Hash.ToLowerInvariant() -ne
    '4639874ee47a6e8b3f24f1ba4bfb1457bd2e387b6fa95cfa6aabe995a15f8b9f') {
    Fail 'quota_js_digest_mismatch'
}
if (-not (Test-Path -LiteralPath $hookArchive -PathType Leaf)) { Fail 'v12h_hooks_missing' }
if ((Get-FileHash -LiteralPath $hookArchive -Algorithm SHA256).Hash.ToLowerInvariant() -ne $hookSha256) {
    Fail 'v12h_archive_digest_mismatch'
}
if (-not (Test-Path -LiteralPath $listFile -PathType Leaf)) { Fail 'original_package_list_missing' }
if ((Get-FileHash -LiteralPath $listFile -Algorithm SHA256).Hash.ToLowerInvariant() -ne $receipt.OriginalListSha256) {
    Fail 'original_package_list_digest_mismatch'
}
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { Fail 'docker_missing' }
foreach ($key in @('veci-meter-r2-rsa.key','veci-meter-r2-rsa.pem')) {
    if (-not (Test-Path -LiteralPath (Join-Path $keys $key) -PathType Leaf)) { Fail 'local_signing_key_missing' }
}
if (Test-Path -LiteralPath $build) { Fail 'build_directory_exists' }
New-Item -ItemType Directory -Path $build | Out-Null
New-Item -ItemType Directory -Path $dist | Out-Null
$hooks = Join-Path $build 'hooks'
New-Item -ItemType Directory -Path $hooks | Out-Null
& tar.exe -xzf $hookArchive -C $build hooks/post-install.sh hooks/pre-deinstall.sh hooks/post-upgrade.sh
if ($LASTEXITCODE -ne 0) { Fail 'v12h_extract_failed' }
$hookDigests = @{
  'post-install'='10aaaceb1f28a6d7c94833275b7bff3b4f244aa46adb38f335a6234aa07ddad4';
  'pre-deinstall'='5a46723558bc474f6f4e695d0ec30dcbd8a414c701d82d2d480c05dd852d9c62';
  'post-upgrade'='e6cc1bb6d32da1d183ad458231919e55fbab2692a7c5fbd15295ebcab1f6b570'
}
foreach ($kind in $hookDigests.Keys) {
  $file = Join-Path $hooks ($kind + '.sh')
  if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { Fail 'v12h_hook_missing' }
  if ((Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLowerInvariant() -ne $hookDigests[$kind]) {
    Fail 'v12h_hook_digest_mismatch'
  }
}
& curl.exe --fail --silent --show-error --location $url --output $builder
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $builder -PathType Leaf)) { Fail 'builder_download_failed' }
$sourceMount = 'type=bind,source=' + $source + ',target=/source,readonly'
$keysMount = 'type=bind,source=' + $keys + ',target=/keys,readonly'
$buildMount = 'type=bind,source=' + $build + ',target=/build,readonly'
$distMount = 'type=bind,source=' + $dist + ',target=/dist'
$hooksMount = 'type=bind,source=' + $hooks + ',target=/hooks,readonly'
& docker run --rm --mount $sourceMount --mount $keysMount --mount $buildMount --mount $distMount --mount $hooksMount alpine:edge sh /build/build-in-docker-v12i.sh
if ($LASTEXITCODE -ne 0) { Fail 'signed_candidate_build_failed' }
$expected = @('veci-telco-xl-native-0.3.8-r2-mipsel_24kc.apk','veci-telco-indonesia-0.2.2-r2-mipsel_24kc.apk')
foreach ($name in $expected) {
    $file = Join-Path $dist $name
    if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { Fail 'signed_candidate_missing' }
    Write-Output ('XL_V12I_CANDIDATE=' + $name)
    Write-Output ('XL_V12I_CANDIDATE_SHA256=' + (Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLowerInvariant())
}
Write-Output 'XL_V12I_OFFICE=pass'
Write-Output 'XL_V12I_ORIGINAL_INDONESIA_HOOKS=integrated'
Write-Output 'XL_V12I_PACKAGE_LIST=preserved'
Write-Output 'XL_V12I_INSTALL=blocked_pending_rollback_and_dependency_staging'
Write-Output ('XL_V12I_DIST=' + $dist)
Write-Output 'XL_V12I_ROUTER=unchanged'
