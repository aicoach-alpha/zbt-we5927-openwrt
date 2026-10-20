# VeCI v12m: build a signed local APKv3 feed from v12k LIVE binaries.
# Office laptop only. No SSH, reinstallation or production changes.
$ErrorActionPreference = 'Stop'
$inputDir = 'C:\veci-build\xl-native-candidates-v12i\dist'
$feed = 'C:\veci-build\xl-native-feed-v12m'
$keyDir = 'C:\veci-build\keys'
$baseUrl = 'https://raw.githubusercontent.com/aicoach-alpha/zbt-we5927-openwrt/9c44214f5bdaf74ee523f24ace9239a25228a0dd/packaging/veci-xl-owner-migration/build-offline-feed-v12m.sh'
function Fail([string]$reason) { Write-Output ('XL_V12M_OFFICE=' + $reason); exit 1 }
$items = @(
    @{
      Source='veci-telco-xl-native-0.3.8-r2-mipsel_24kc.apk';
      Target='veci-telco-xl-native-0.3.8-r2.apk';
      Hash='801b421569f6cd18ade2bfc3a86c7e61e333e680dfc41e29edffd3cdd0793f37'
    },
    @{
      Source='veci-telco-indonesia-0.2.2-r2-mipsel_24kc.apk';
      Target='veci-telco-indonesia-0.2.2-r2.apk';
      Hash='da3d5d9da1bdc684170d75773a03562f7dcca672a3d3d8dd1575969ad4d65866'
    }
)
if (Test-Path -LiteralPath $feed) { Fail 'feed_already_exists' }
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { Fail 'docker_missing' }
foreach ($name in @('veci-meter-r2-rsa.key','veci-meter-r2-rsa.pem')) {
    if (-not (Test-Path -LiteralPath (Join-Path $keyDir $name) -PathType Leaf)) { Fail 'signer_missing' }
}
foreach ($item in $items) {
    $f = Join-Path $inputDir $item.Source
    if (-not (Test-Path -LiteralPath $f -PathType Leaf)) { Fail 'candidate_missing' }
    if ((Get-FileHash -LiteralPath $f -Algorithm SHA256).Hash.ToLowerInvariant() -ne $item.Hash) {
        Fail 'candidate_sha256_mismatch'
    }
}
New-Item -ItemType Directory -Path $feed | Out-Null
foreach ($item in $items) {
    Copy-Item -LiteralPath (Join-Path $inputDir $item.Source) -Destination (Join-Path $feed $item.Target)
}
$script = Join-Path $feed 'build-offline-feed-v12m.sh'
& curl.exe -fLsS $baseUrl -o $script
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $script -PathType Leaf)) { Fail 'feed_builder_fetch_failed' }
$repoMount = 'type=bind,source=' + $feed + ',target=/repo'
$keysMount = 'type=bind,source=' + $keyDir + ',target=/keys,readonly'
& docker run --rm --network none --mount $repoMount --mount $keysMount alpine:edge sh /repo/build-offline-feed-v12m.sh
if ($LASTEXITCODE -ne 0) { Fail 'feed_build_failed' }
$index = Join-Path $feed 'Packages.adb'
if (-not (Test-Path -LiteralPath $index -PathType Leaf)) { Fail 'index_not_generated' }
Write-Output 'XL_V12M_OFFICE=pass'
Write-Output 'XL_V12M_REPO_ARCHIVES=2'
Write-Output ('XL_V12M_INDEX_SHA256=' + (Get-FileHash -LiteralPath $index -Algorithm SHA256).Hash.ToLowerInvariant())
Write-Output ('XL_V12M_FEED_PATH=' + $feed)
Write-Output 'XL_V12M_WORLD=unchanged'
Write-Output 'XL_V12M_INSTALL=not_attempted'
Write-Output 'XL_V12M_ROUTER=unchanged'
