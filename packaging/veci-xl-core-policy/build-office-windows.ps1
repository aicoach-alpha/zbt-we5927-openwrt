# Build a signed XL Core Policy APK using the previously captured router source.
# Office laptop only; no router modification, no firmware flashing.
$ErrorActionPreference = 'Stop'
$core = 'C:\veci-build\xl-core-source'
$archive = Join-Path $core 'veci-xl-core-source-20261020.tar.gz'
$work = 'C:\veci-build\xl-core-policy'
$keys = 'C:\veci-build\keys'
$package = 'veci-xl-core-policy-0.1.0-r1-mipsel_24kc.apk'
$output = Join-Path (Join-Path $work 'dist') $package
$expectedArchive = '4d6831523d92fd0e674f0406c6b758100c11f62d6cd54267f3a623946b31a795'
$expected = @{
 'usr/libexec/rpcd/veci.xl' = 'b21b357bb9f9c03be9520c5199c1ba5a8329c03fcda95b45bc75206c916cbfb6'
 'usr/libexec/rpcd/veci.quota' = '86a40eba12f3faa27fbff3c75375454004167a0798dff9f808786b7631922f5d'
 'usr/share/rpcd/acl.d/veci-xl-owner.json' = '38618a27befe26cc278ef96be1fc3dac995d5e6ad5eb8ab91808ce7f2705999d'
 'usr/libexec/veci-xl-session-clear' = '57fbfab54810ce116b1b4410ce3f921839fa8f10a535ec009a89ede8c60ebb81'
}
function Fail([string]$reason) {
 Write-Output ('XL_CORE_BUILD=' + $reason)
 exit 1
}
if (-not (Test-Path -LiteralPath $archive -PathType Leaf)) { Fail 'archive_not_found' }
if ((Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expectedArchive) { Fail 'source_archive_mismatch' }
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { Fail 'docker_unavailable' }
if (-not (Test-Path -LiteralPath (Join-Path $keys 'veci-meter-r2-rsa.key') -PathType Leaf)) { Fail 'signing_key_missing' }
if (-not (Test-Path -LiteralPath (Join-Path $keys 'veci-meter-r2-rsa.pem') -PathType Leaf)) { Fail 'signing_public_key_missing' }
if (Test-Path -LiteralPath $output) { Fail 'output_already_exists' }
foreach ($entry in $expected.GetEnumerator()) {
 $file = Join-Path $core ($entry.Key.Replace('/', '\'))
 if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { Fail 'captured_source_missing' }
 if ((Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLowerInvariant() -ne $entry.Value) {
  Fail 'captured_source_hash_mismatch'
 }
}
New-Item -ItemType Directory -Force -Path $work, (Join-Path $work 'source'), (Join-Path $work 'dist') | Out-Null
if (Test-Path (Join-Path $work 'source\usr')) { Fail 'staging_source_already_present' }
Copy-Item -LiteralPath (Join-Path $core 'usr') -Destination (Join-Path $work 'source') -Recurse
$scriptPath = Join-Path $work 'build-in-docker.sh'
& curl.exe --fail --silent --show-error --location 'https://raw.githubusercontent.com/aicoach-alpha/zbt-we5927-openwrt/b0f719ce6970bcf228e02287ea3ec99f8f2b9a47/packaging/veci-xl-core-policy/build-in-docker.sh' --output $scriptPath
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $scriptPath -PathType Leaf)) { Fail 'builder_download_failed' }
$workMount = 'type=bind,source=' + $work + ',target=/work'
$keyMount = 'type=bind,source=' + $keys + ',target=/work/keys,readonly'
& docker run --rm --mount $workMount --mount $keyMount alpine:edge sh /work/build-in-docker.sh
if ($LASTEXITCODE -ne 0) { Fail 'docker_build_failed' }
if (-not (Test-Path -LiteralPath $output -PathType Leaf)) { Fail 'apk_missing' }
Write-Output 'XL_CORE_BUILD=pass'
Write-Output 'XL_CORE_SIGNATURE=pass'
Write-Output 'XL_CORE_ARCH=mipsel_24kc'
Write-Output ('XL_CORE_APK_SHA256=' + (Get-FileHash -LiteralPath $output -Algorithm SHA256).Hash.ToLowerInvariant())
Write-Output ('XL_CORE_APK_PATH=' + $output)
Write-Output 'XL_CORE_ROUTER=unchanged'
