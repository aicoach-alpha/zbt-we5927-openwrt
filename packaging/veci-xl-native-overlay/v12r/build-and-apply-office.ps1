# VeCI XL v12r: build signed UI overlay 1.0.1 and optionally guarded production apply.
# Only the office laptop can reach ZBT WE5927. No andre-nas, modem, SMS or USSD.
param([switch]$Apply)
$ErrorActionPreference = 'Stop'
$root = 'C:\veci-build\xl-native-overlay-v12r'
$originalApk = 'C:\veci-build\xl-native-overlay-v12q\dist\veci-xl-native-overlay-1.0.1-r1-mipsel_24kc.apk'
$originalSha256 = 'bc34bcee7996f5ce40e27ac46a9bb40f290c55a3b53857e14d233c5f30c0a34e'
$keys = 'C:\veci-build\keys'
$repo = 'https://raw.githubusercontent.com/aicoach-alpha/zbt-we5927-openwrt/'
$oldPrefix = $repo + '68491e24b878efdb06f6226ca6ff5d8f0f0e4ba0/packaging/veci-xl-native-overlay/files/'
$oldUiUrl = $repo + 'e27eedb235fb98cd4d078839970923b638d20b13/packaging/veci-xl-native-overlay/v12q/files/veci-xl-connection-status.js'
$newPrefix = $repo + '6df22e19eec6d238c10c39ac7d2753e45fff742f/packaging/veci-xl-native-overlay/v12r/files/'
$buildUrl = $repo + '8d75d503c720501bcde8f3e7317b87d318e270c9/packaging/veci-xl-native-overlay/v12r/build-in-docker.sh'
$installUrl = $repo + 'bd6a2fc6787b899d82cd05a96d8acfa8b894f7a2/packaging/veci-xl-native-overlay/v12r/guarded-overlay-install.sh'
$router = 'root@192.168.1.1'
$remote = '/tmp/veci-xl-v12r-20261021'
function Fail([string]$reason) { Write-Output ('XL_V12R_OFFICE=' + $reason); exit 1 }
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { Fail 'docker_missing' }
# Docker CLI can exist while Docker Desktop's Linux daemon is stopped.
# Do this before staging/building anything; never fall back to remote engines.
function LinuxEngineReady {
 try {
  $ostype = & docker info --format '{{.OSType}}' 2>$null
  return ($LASTEXITCODE -eq 0 -and (($ostype -join '').Trim() -eq 'linux'))
 } catch { return $false }
}
if (-not (LinuxEngineReady)) {
 $desktop = Join-Path $env:ProgramFiles 'Docker\Docker\Docker Desktop.exe'
 if (-not (Test-Path -LiteralPath $desktop -PathType Leaf)) {
  Fail 'docker_linux_engine_offline_start_docker_desktop_manually'
 }
 Write-Output 'XL_V12R_DOCKER=starting_docker_desktop'
 try {
  Start-Process -FilePath $desktop -ErrorAction Stop | Out-Null
 } catch { Fail 'docker_desktop_start_failed' }
 $ready = $false
 for ($attempt = 0; $attempt -lt 45; $attempt++) {
  if (LinuxEngineReady) { $ready = $true; break }
  Start-Sleep -Seconds 2
 }
 if (-not $ready) { Fail 'docker_linux_engine_not_ready_check_docker_desktop' }
}
Write-Output 'XL_V12R_DOCKER=linux_engine_ready'
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
Write-Output 'XL_V12R_OFFICE_STAGE=resume_safe'
# Download immutable GitHub source to a separate temporary workspace; never
# overwrite existing office artifacts, even when previous attempts were partial.
$tempWork = Join-Path $env:TEMP ('veci-xl-v12r-pinned-' + [guid]::NewGuid().ToString('N'))
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
  Write-Output ('XL_V12R_SOURCE=reused_' + [IO.Path]::GetFileName($dest))
 } else {
  Copy-Item -LiteralPath $temporary -Destination $dest
 }
}
$names = @('veci-xl-connection-status.js','veci-xl-quota-session-gate','veci-xl-authorized-config-import')
Fetch $oldUiUrl (Join-Path $before 'veci-xl-connection-status.js')
foreach ($name in @('veci-xl-quota-session-gate','veci-xl-authorized-config-import')) {
 Fetch ($oldPrefix + $name) (Join-Path $before $name)
}
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
$newApk = Join-Path $dist 'veci-xl-native-overlay-1.0.2-r1-mipsel_24kc.apk'
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
Write-Output 'XL_V12R_BUILD=pass'
Write-Output ('XL_V12R_NEW_APK_SHA256=' + $newHash)
Write-Output ('XL_V12R_ROLLBACK_APK_SHA256=' + $oldHash)
Write-Output 'XL_V12R_ROLLBACK=exact_original_signed_archive'
Write-Output ('XL_V12R_BEFORE_UI_SHA256=' + $oldUI)
Write-Output ('XL_V12R_AFTER_UI_SHA256=' + $newUI)
if (-not $Apply) {
 Write-Output 'XL_V12R_PRODUCTION=unchanged'
 Write-Output 'XL_V12R_OFFICE=build_pass'
 exit 0
}
& ssh $router ('umask 077; if [ -e ' + $remote + ' ]; then [ -d ' + $remote + ' ] && [ ! -L ' + $remote + ' ] && [ ! -e ' + $remote + '/backup ]; else mkdir -m 700 ' + $remote + '; fi')
if ($LASTEXITCODE -ne 0) { Fail 'router_staging_exists_or_unavailable' }
& scp -O $newApk $oldApk (Join-Path $keys 'veci-meter-r2-rsa.pem') $install ($router + ':' + $remote + '/')
if ($LASTEXITCODE -ne 0) { Fail 'router_staging_transfer_failed' }
$remoteCommand = 'sh -n ' + $remote + '/guarded-overlay-install.sh && sh ' + $remote + '/guarded-overlay-install.sh apply ' + $oldUI + ' ' + $newUI + ' ' + $gate + ' ' + $import + ' ' + $oldHash + ' ' + $newHash
& ssh $router $remoteCommand
if ($LASTEXITCODE -ne 0) { Fail 'upgrade_blocked_review_router_receipt' }
Write-Output 'XL_V12R_OFFICE=live_pass'
Write-Output 'XL_V12R_ROLLBACK_ARCHIVE=retained_on_office'
