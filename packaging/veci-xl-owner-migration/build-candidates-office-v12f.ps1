# VeCI XL v12f: signed, staged-only same-name APK candidate build on office laptop.
# Never changes the router and never uploads captured binaries/credentials.
$ErrorActionPreference = 'Stop'
$source = 'C:\veci-build\xl-native-origin\staged-v12b'
$build = 'C:\veci-build\xl-native-candidates-v12f'
$dist = Join-Path $build 'dist'
$keys = 'C:\veci-build\keys'
$report = Join-Path $source 'inventory-v12d.json'
$builder = Join-Path $build 'build-in-docker-v12f.sh'
$url = 'https://raw.githubusercontent.com/aicoach-alpha/zbt-we5927-openwrt/1ea58b3d176e17467cec5074cb335b9cf0458b9a/packaging/veci-xl-owner-migration/build-candidates-in-docker-v12f.sh'
function Fail([string]$code) { Write-Output ('XL_V12F_OFFICE=' + $code); exit 1 }
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
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { Fail 'docker_missing' }
foreach ($key in @('veci-meter-r2-rsa.key','veci-meter-r2-rsa.pem')) {
    if (-not (Test-Path -LiteralPath (Join-Path $keys $key) -PathType Leaf)) { Fail 'local_signing_key_missing' }
}
if (Test-Path -LiteralPath $build) { Fail 'build_directory_exists' }
New-Item -ItemType Directory -Path $build | Out-Null
New-Item -ItemType Directory -Path $dist | Out-Null
& curl.exe --fail --silent --show-error --location $url --output $builder
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $builder -PathType Leaf)) { Fail 'builder_download_failed' }
$sourceMount = 'type=bind,source=' + $source + ',target=/source,readonly'
$keysMount = 'type=bind,source=' + $keys + ',target=/keys,readonly'
$buildMount = 'type=bind,source=' + $build + ',target=/build,readonly'
$distMount = 'type=bind,source=' + $dist + ',target=/dist'
& docker run --rm --mount $sourceMount --mount $keysMount --mount $buildMount --mount $distMount alpine:edge sh /build/build-in-docker-v12f.sh
if ($LASTEXITCODE -ne 0) { Fail 'signed_candidate_build_failed' }
$expected = @('veci-telco-xl-native-0.3.8-r1-mipsel_24kc.apk','veci-telco-indonesia-0.2.2-r1-mipsel_24kc.apk')
foreach ($name in $expected) {
    $file = Join-Path $dist $name
    if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { Fail 'signed_candidate_missing' }
    Write-Output ('XL_V12F_CANDIDATE=' + $name)
    Write-Output ('XL_V12F_CANDIDATE_SHA256=' + (Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLowerInvariant())
}
Write-Output 'XL_V12F_OFFICE=pass'
Write-Output 'XL_V12F_INSTALL=blocked_original_maintainer_scripts_unrecovered'
Write-Output ('XL_V12F_DIST=' + $dist)
Write-Output 'XL_V12F_ROUTER=unchanged'
