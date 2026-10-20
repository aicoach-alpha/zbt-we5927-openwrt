# VeCI XL v12o: immutable signed APKv3 release feed publisher.
# Default input captures the current v12n LIVE baseline. Office only, no SSH.
param(
 [string]$NativeApk = 'C:\veci-build\xl-native-feed-v12m\veci-telco-xl-native-0.3.8-r2.apk',
 [string]$IndonesiaApk = 'C:\veci-build\xl-native-feed-v12m\veci-telco-indonesia-0.2.2-r2.apk'
)
$ErrorActionPreference = 'Stop'
$keyDir = 'C:\veci-build\keys'
$outputBase = 'C:\veci-build\xl-native-feed-releases'
$url = 'https://raw.githubusercontent.com/aicoach-alpha/zbt-we5927-openwrt/d00c5e4d8cf88c01c4c77c0994cd69b3154b9dd7/packaging/veci-xl-owner-migration/build-versioned-feed-v12o.sh'
function Fail([string]$code) { Write-Output ('XL_V12O_OFFICE=' + $code); exit 1 }
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { Fail 'docker_missing' }
foreach ($name in @('veci-meter-r2-rsa.key','veci-meter-r2-rsa.pem')) {
 if (-not (Test-Path -LiteralPath (Join-Path $keyDir $name) -PathType Leaf)) { Fail 'key_missing' }
}
foreach ($p in @($NativeApk,$IndonesiaApk)) {
 if (-not (Test-Path -LiteralPath $p -PathType Leaf)) { Fail 'source_apk_missing' }
 $item = Get-Item -LiteralPath $p -Force
 if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { Fail 'source_symlink_rejected' }
}
$n = [IO.Path]::GetFileName($NativeApk)
$i = [IO.Path]::GetFileName($IndonesiaApk)
if ($n -notmatch '^veci-telco-xl-native-([0-9]+\.[0-9]+\.[0-9]+-r[0-9]+)(?:-mipsel_24kc)?\.apk$') { Fail 'invalid_native_filename' }
$nativeVersion = $Matches[1]
if ($i -notmatch '^veci-telco-indonesia-([0-9]+\.[0-9]+\.[0-9]+-r[0-9]+)(?:-mipsel_24kc)?\.apk$') { Fail 'invalid_indonesia_filename' }
$indonesiaVersion = $Matches[1]
$nativeOut = 'veci-telco-xl-native-' + $nativeVersion + '.apk'
$indonesiaOut = 'veci-telco-indonesia-' + $indonesiaVersion + '.apk'
$releaseName = 'native-' + $nativeVersion + '__indonesia-' + $indonesiaVersion
$out = Join-Path $outputBase $releaseName
if (Test-Path -LiteralPath $out) { Fail 'release_already_exists_do_not_overwrite' }
if (-not (Test-Path -LiteralPath $outputBase)) { New-Item -ItemType Directory -Path $outputBase | Out-Null }
New-Item -ItemType Directory -Path $out | Out-Null
$items = @(
 @{Source=$NativeApk; Target=$nativeOut},
 @{Source=$IndonesiaApk; Target=$indonesiaOut}
)
foreach ($item in $items) {
 $sourceHash = (Get-FileHash -LiteralPath $item.Source -Algorithm SHA256).Hash.ToLowerInvariant()
 $dest = Join-Path $out $item.Target
 Copy-Item -LiteralPath $item.Source -Destination $dest
 if ((Get-FileHash -LiteralPath $dest -Algorithm SHA256).Hash.ToLowerInvariant() -ne $sourceHash) {
  Fail 'staged_apk_sha256_mismatch'
 }
}
$manifest = Join-Path $out 'release-files.txt'
$utf8 = New-Object System.Text.UTF8Encoding $false
$lf = [string][char]10
[IO.File]::WriteAllText($manifest, $nativeOut + $lf + $indonesiaOut + $lf, $utf8)
$builder = Join-Path $env:TEMP 'veci-xl-v12o-builder.sh'
& curl.exe -fLsS $url -o $builder
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $builder -PathType Leaf)) { Fail 'builder_fetch_failed' }
$repoMount = 'type=bind,source=' + $out + ',target=/release'
$keysMount = 'type=bind,source=' + $keyDir + ',target=/keys,readonly'
$scriptMount = 'type=bind,source=' + $builder + ',target=/builder.sh,readonly'
& docker run --rm --network none --mount $repoMount --mount $keysMount --mount $scriptMount alpine:edge sh /builder.sh
if ($LASTEXITCODE -ne 0) { Fail 'signed_index_build_failed' }
$index = Join-Path $out 'Packages.adb'
if (-not (Test-Path -LiteralPath $index -PathType Leaf)) { Fail 'index_missing' }
$indexHash = (Get-FileHash -LiteralPath $index -Algorithm SHA256).Hash.ToLowerInvariant()
$lines = @(
 'schema=1',
 ('native_version=' + $nativeVersion),
 ('indonesia_version=' + $indonesiaVersion),
 ('native_sha256=' + (Get-FileHash -LiteralPath (Join-Path $out $nativeOut) -Algorithm SHA256).Hash.ToLowerInvariant()),
 ('indonesia_sha256=' + (Get-FileHash -LiteralPath (Join-Path $out $indonesiaOut) -Algorithm SHA256).Hash.ToLowerInvariant()),
 ('index_sha256=' + $indexHash),
 'deployment=not_attempted'
)
[IO.File]::WriteAllText((Join-Path $out 'release-receipt.txt'), ([string]::Join($lf,$lines) + $lf), $utf8)
Write-Output 'XL_V12O_OFFICE=pass'
Write-Output ('XL_V12O_NATIVE_VERSION=' + $nativeVersion)
Write-Output ('XL_V12O_INDONESIA_VERSION=' + $indonesiaVersion)
Write-Output ('XL_V12O_INDEX_SHA256=' + $indexHash)
Write-Output ('XL_V12O_RELEASE_PATH=' + $out)
Write-Output 'XL_V12O_PRODUCTION=unchanged'
