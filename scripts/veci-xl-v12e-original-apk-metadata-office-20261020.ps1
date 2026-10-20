# VeCI XL v12e - recover original APKv3 build hooks and dependency metadata.
# Office laptop only. Read existing C:\veci-build artifacts; never SSH or modify router.
$ErrorActionPreference = 'Stop'
$base = 'C:\veci-build'
$staged = Join-Path $base 'xl-native-origin\staged-v12b'
$report = Join-Path $staged 'original-apk-metadata-v12e.json'
$archiveReport = Join-Path $staged 'inventory-v12d.json'
$originDir = Join-Path $staged 'original-apk-v12e'
$originals = @(
    @{ Name='veci-telco-xl-native'; Version='0.3.7-r1' },
    @{ Name='veci-telco-indonesia'; Version='0.2.1-r1' }
)
function Fail([string]$code) {
    Write-Output ('XL_V12E=' + $code)
    exit 1
}
if (-not (Test-Path -LiteralPath $archiveReport -PathType Leaf)) { Fail 'v12d_inventory_missing' }
if (Test-Path -LiteralPath $report) { Fail 'metadata_already_collected' }
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { Fail 'docker_unavailable' }
$found = @()
$allApks = @(Get-ChildItem -LiteralPath $base -Recurse -File -Filter '*.apk' -ErrorAction SilentlyContinue)
foreach ($pkg in $originals) {
    $rx = '^' + [regex]::Escape($pkg.Name + '-' + $pkg.Version) + '(?:-mipsel_24kc)?\.apk$'
    $candidates = @($allApks | Where-Object { $_.Name -match $rx })
    Write-Output ('XL_V12E_PACKAGE=' + $pkg.Name)
    Write-Output ('XL_V12E_ORIGINAL_CANDIDATES=' + $candidates.Count)
    if ($candidates.Count -ne 1) { continue }
    $target = $candidates[0].FullName
    $hash = (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash.ToLowerInvariant()
    $found += [PSCustomObject]@{
       Name = $pkg.Name
       Version = $pkg.Version
       OriginalPath = $candidates[0].FullName
       StagedPath = $target
       Sha256 = $hash
    }
}
if ($found.Count -ne 2) {
    Write-Output 'XL_V12E_ORIGINAL_APK=incomplete'
    Write-Output 'XL_V12E_BUILD=blocked_until_both_original_apks_available'
    Write-Output 'XL_V12E_ROUTER=unchanged'
    exit 0
}
if (Test-Path -LiteralPath $originDir) { Fail 'original_staging_already_exists' }
New-Item -ItemType Directory -Path $originDir | Out-Null
foreach ($pkg in $found) {
    $target = Join-Path $originDir ($pkg.Name + '.apk')
    Copy-Item -LiteralPath $pkg.StagedPath -Destination $target
}
$mount = 'type=bind,source=' + $originDir + ',target=/original,readonly'
$metadata = @()
foreach ($pkg in $found) {
    $jsonText = & docker run --rm --mount $mount alpine:edge apk adbdump --format json ('/original/' + $pkg.Name + '.apk')
    if ($LASTEXITCODE -ne 0 -or -not $jsonText) { Fail 'original_apk_metadata_unreadable' }
    $raw = ($jsonText -join [environment]::NewLine)
    try { $parsed = $raw | ConvertFrom-Json } catch { Fail 'original_apk_json_invalid' }
    if (-not $parsed.info -or $parsed.info.name -ne $pkg.Name -or
        $parsed.info.version -ne $pkg.Version) { Fail 'original_apk_identity_mismatch' }
    if ($parsed.info.arch -notin @('mipsel_24kc','noarch','all')) { Fail 'original_apk_arch_mismatch' }
    $scriptKinds = @()
    if ($parsed.scripts) { $scriptKinds = @($parsed.scripts.PSObject.Properties.Name) }
    $allowedKinds = @('pre-install','post-install','pre-deinstall','post-deinstall','pre-upgrade','post-upgrade','trigger')
    foreach ($kind in $scriptKinds) {
        if ($kind -notin $allowedKinds) { Fail 'unrecognized_apk_script_type' }
    }
    $outJson = Join-Path $originDir ($pkg.Name + '-metadata.json')
    $raw | Set-Content -LiteralPath $outJson -Encoding utf8
    $metadata += [PSCustomObject]@{
        Name=$pkg.Name; Version=$pkg.Version; Arch=$parsed.info.arch;
        Sha256=$pkg.Sha256; OriginalMetadataPath=$outJson;
        OriginalScriptKinds=$scriptKinds;
        OriginalDependencyCount=@($parsed.info.depends).Count;
        OriginalTriggerCount=@($parsed.info.triggers).Count
    }
    Write-Output ('XL_V12E_' + $pkg.Name + '_SCRIPTS=' + ($scriptKinds -join ','))
    Write-Output ('XL_V12E_' + $pkg.Name + '_SHA256=' + $pkg.Sha256)
}
@{
 SourceV12d = $archiveReport
 OriginalPackages = $metadata
 RebuildSourceReady = $true
 ProductionUpgradePermitted = $false
} | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $report -Encoding UTF8
Write-Output 'XL_V12E=pass'
Write-Output 'XL_V12E_ORIGINAL_METADATA=collected'
Write-Output 'XL_V12E_INSTALL_SCRIPTS=identified_without_execution'
Write-Output ('XL_V12E_REPORT=' + $report)
Write-Output 'XL_V12E_NEXT=build_same_name_candidate_APKs'
Write-Output 'XL_V12E_ROUTER=unchanged'
