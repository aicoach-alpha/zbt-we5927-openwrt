# VeCI v12m: build a signed local APKv3 feed from v12k LIVE binaries.
# Office laptop only. No SSH, reinstallation or production changes.
$ErrorActionPreference = 'Stop'
$inputDir = 'C:\veci-build\xl-native-candidates-v12i\dist'
$feed = 'C:\veci-build\xl-native-feed-v12m'
$keyDir = 'C:\veci-build\keys'
$baseUrl = 'https://raw.githubusercontent.com/aicoach-alpha/zbt-we5927-openwrt/5c248a0d718c817dcd0c28c55a4d237f9076ce6b/packaging/veci-xl-owner-migration/build-offline-feed-v12m.sh'
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
if (Test-Path -LiteralPath $feed) {
    $existing = Get-Item -LiteralPath $feed -Force
    if (-not $existing.PSIsContainer -or
        ($existing.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
        Fail 'existing_feed_path_unsafe'
    }
    Write-Output 'XL_V12M_FEED=resume_existing_directory'
} else {
    New-Item -ItemType Directory -Path $feed | Out-Null
    Write-Output 'XL_V12M_FEED=new_directory'
}
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
foreach ($item in $items) {
    $target = Join-Path $feed $item.Target
    if (Test-Path -LiteralPath $target) {
        $existingFile = Get-Item -LiteralPath $target -Force
        if ($existingFile.PSIsContainer -or
            ($existingFile.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            Fail 'existing_candidate_path_unsafe'
        }
        if ((Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToLowerInvariant() -ne $item.Hash) {
            Fail 'existing_candidate_hash_mismatch'
        }
    } else {
        Copy-Item -LiteralPath (Join-Path $inputDir $item.Source) -Destination $target
        if ((Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToLowerInvariant() -ne $item.Hash) {
            Fail 'copied_candidate_hash_mismatch'
        }
    }
}
# Fetch the pinned builder outside the feed; no existing feed files are overwritten.
$script = Join-Path $env:TEMP 'veci-xl-build-offline-feed-v12m-resume.sh'
& curl.exe -fLsS $baseUrl -o $script
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $script -PathType Leaf)) { Fail 'feed_builder_fetch_failed' }
$repoMount = 'type=bind,source=' + $feed + ',target=/repo'
$keysMount = 'type=bind,source=' + $keyDir + ',target=/keys,readonly'
$scriptMount = 'type=bind,source=' + $script + ',target=/builder-v12m.sh,readonly'
& docker run --rm --network none --mount $repoMount --mount $keysMount --mount $scriptMount alpine:edge sh /builder-v12m.sh
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
