# VeCI XL v12q: build signed UI overlay 1.0.1 and optionally guarded production apply.
# Only the office laptop can reach ZBT WE5927. No andre-nas, modem, SMS or USSD.
param([switch]$Apply)
$ErrorActionPreference = 'Stop'
$root = 'C:\veci-build\xl-native-overlay-v12q'
$originalApk = 'C:\veci-build\xl-overlay\dist\veci-xl-native-overlay-1.0.0-r1-mipsel_24kc.apk'
$originalSha256 = '5b418533be9ffdfced4b357bef933934496606f769d400c99df3921116dec486'
$keys = 'C:\veci-build\keys'
$repo = 'https://raw.githubusercontent.com/aicoach-alpha/zbt-we5927-openwrt/'
$oldPrefix = $repo + '68491e24b878efdb06f6226ca6ff5d8f0f0e4ba0/packaging/veci-xl-native-overlay/files/'
$newPrefix = $repo + 'e27eedb235fb98cd4d078839970923b638d20b13/packaging/veci-xl-native-overlay/v12q/files/'
$buildUrl = $repo + '45587266bd67bfe21c13e23964709e50a09fec6c/packaging/veci-xl-native-overlay/v12q/build-in-docker.sh'
$installUrl = $repo + '140a546a8d5d772dc26b2aa62cc511090f695c86/packaging/veci-xl-native-overlay/v12q/guarded-overlay-install.sh'
$router = 'root@192.168.1.1'
$remote = '/tmp/veci-xl-v12q-20261020'
function Fail([string]$reason) { Write-Output ('XL_V12Q_OFFICE=' + $reason); exit 1 }
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { Fail 'docker_missing' }
foreach ($name in @('veci-meter-r2-rsa.key','veci-meter-r2-rsa.pem')) {
 if (-not (Test-Path -LiteralPath (Join-Path $keys $name) -PathType Leaf)) { Fail 'signer_missing' }
}
if (-not (Test-Path -LiteralPath $originalApk -PathType Leaf)) { Fail 'original_signed_rollback_archive_missing' }
if ((Get-FileHash -LiteralPath $originalApk -Algorithm SHA256).Hash.ToLowerInvariant() -ne $originalSha256) {
 Fail 'original_signed_rollback_archive_digest_mismatch'
}
function SafeDirectory([string]$dir) {
 if (Test-Path -LiteralPath $dir) {
  $existing = Get-Item -LiteralPath $dir -Force
  if (-not $existing.PSIsContainer -or
      ($existing.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
    Fail 'existing_directory_unsafe'
  }
 } else {
  New-Item -ItemType Directory -Path $dir | Out-Null
 }
}
SafeDirectory $root
$source = Join-Path $root 'source'
$before = Join-Path $source 'before'
$after = Join-Path $source 'after'
$dist = Join-Path $root 'dist'
foreach ($dir in @($source,$before,$after,$dist)) { SafeDirectory $dir }
Write-Output 'XL_V12Q_OFFICE_STAGE=resume_safe'
# Download immutable GitHub source to a separate temporary workspace; never
# overwrite existing office artifacts, even when previous attempts were partial.
$tempWork = Join-Path $env:TEMP ('veci-xl-v12q-pinned-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $tempWork | Out-Null
function Fetch([string]$url,[string]$dest) {
 $temporary = Join-Path $tempWork ([guid]::NewGuid().ToString('N'))
 & curl.exe -fLsS --retry 2 $url -o $temporary
 if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $temporary -PathType Leaf)) {
  Fail 'pinned_source_download_failed'
 }
 if (Test-Path -LiteralPath $dest) {
  $existing = Get-Item -LiteralPath $dest -Force
  if ($existing.PSIsContainer -or
      ($existing.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
    Fail 'existing_source_path_unsafe'
  }
  if ((Get-FileHash -LiteralPath $dest -Algorithm SHA256).Hash -ne
      (Get-FileHash -LiteralPath $temporary -Algorithm SHA256).Hash) {
    Fail 'existing_source_differs_from_pinned_release'
  }
  Write-Output ('XL_V12Q_SOURCE=reused_' + [IO.Path]::GetFileName($dest))
 } else {
  Copy-Item -LiteralPath $temporary -Destination $dest
 }
}
$names = @('veci-xl-connection-status.js','veci-xl-quota-session-gate','veci-xl-authorized-config-import')
foreach ($name in $names) { Fetch ($oldPrefix + $name) (Join-Path $before $name) }
Fetch ($newPrefix + 'veci-xl-connection-status.js') (Join-Path $after 'veci-xl-connection-status.js')
foreach ($name in @('veci-xl-quota-session-gate','veci-xl-authorized-config-import')) {
 $file = Join-Path $after $name
 $beforeFile = Join-Path $before $name
 if (Test-Path -LiteralPath $file) {
  $existing = Get-Item -LiteralPath $file -Force
  if ($existing.PSIsContainer -or
      ($existing.Attributes -band [IO.FileAttributes]::ReparsePoint) -or
      ((Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash -ne
       (Get-FileHash -LiteralPath $beforeFile -Algorithm SHA256).Hash)) {
    Fail 'existing_helper_source_differs_from_original'
  }
 } else {
  Copy-Item -LiteralPath $beforeFile -Destination $file
 }
}
$build = Join-Path $tempWork 'build-in-docker.sh'
$install = Join-Path $tempWork 'guarded-overlay-install.sh'
Fetch $buildUrl $build
Fetch $installUrl $install
$smount = 'type=bind,source=' + $source + ',target=/source,readonly'
$dmount = 'type=bind,source=' + $dist + ',target=/dist'
$kmount = 'type=bind,source=' + $keys + ',target=/keys,readonly'
$bmount = 'type=bind,source=' + $build + ',target=/builder.sh,readonly'
& docker run --rm --network none --mount $smount --mount $dmount --mount $kmount --mount $bmount alpine:edge sh /builder.sh
if ($LASTEXITCODE -ne 0) { Fail 'apk_build_failed' }
$newApk = Join-Path $dist 'veci-xl-native-overlay-1.0.1-r1-mipsel_24kc.apk'
$oldApk = $originalApk
foreach ($path in @($newApk,$oldApk)) {
 if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { Fail 'signed_apk_missing' }
}
function Hash([string]$file) { return (Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLowerInvariant() }
$oldUI = Hash (Join-Path $before 'veci-xl-connection-status.js')
$newUI = Hash (Join-Path $after 'veci-xl-connection-status.js')
$gate = Hash (Join-Path $after 'veci-xl-quota-session-gate')
$import = Hash (Join-Path $after 'veci-xl-authorized-config-import')
$oldHash = Hash $oldApk
$newHash = Hash $newApk
Write-Output 'XL_V12Q_BUILD=pass'
Write-Output ('XL_V12Q_NEW_APK_SHA256=' + $newHash)
Write-Output ('XL_V12Q_ROLLBACK_APK_SHA256=' + $oldHash)
Write-Output 'XL_V12Q_ROLLBACK=exact_original_signed_archive'
Write-Output ('XL_V12Q_BEFORE_UI_SHA256=' + $oldUI)
Write-Output ('XL_V12Q_AFTER_UI_SHA256=' + $newUI)
if (-not $Apply) {
 Write-Output 'XL_V12Q_PRODUCTION=unchanged'
 Write-Output 'XL_V12Q_OFFICE=build_pass'
 exit 0
}
& ssh $router ('umask 077; if [ -e ' + $remote + ' ]; then exit 5; fi; mkdir -m 700 ' + $remote)
if ($LASTEXITCODE -ne 0) { Fail 'router_staging_exists_or_unavailable' }
& scp -O $newApk $oldApk (Join-Path $keys 'veci-meter-r2-rsa.pem') $install ($router + ':' + $remote + '/')
if ($LASTEXITCODE -ne 0) { Fail 'router_staging_transfer_failed' }
$remoteCommand = 'sh -n ' + $remote + '/guarded-overlay-install.sh && sh ' + $remote + '/guarded-overlay-install.sh apply ' + $oldUI + ' ' + $newUI + ' ' + $gate + ' ' + $import + ' ' + $oldHash + ' ' + $newHash
& ssh $router $remoteCommand
if ($LASTEXITCODE -ne 0) { Fail 'upgrade_blocked_review_router_receipt' }
Write-Output 'XL_V12Q_OFFICE=live_pass'
Write-Output 'XL_V12Q_ROLLBACK_ARCHIVE=retained_on_office'
