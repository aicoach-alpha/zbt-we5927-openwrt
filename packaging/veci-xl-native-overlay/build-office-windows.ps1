# VeCI XL signed APK v3 build: office Windows laptop + Docker Desktop only.
# No router login, no modem changes, no OTP, and private key never uploaded.
$ErrorActionPreference = 'Stop'
$workspace = 'C:\veci-build\xl-overlay'
$keyDir = 'C:\veci-build\keys'
$signKey = Join-Path $keyDir 'veci-meter-r2-rsa.key'
$pubKey = Join-Path $keyDir 'veci-meter-r2-rsa.pem'
$apkName = 'veci-xl-native-overlay-1.0.0-r1-mipsel_24kc.apk'
$apkPath = Join-Path $workspace ('dist\' + $apkName)
$revision = '68491e24b878efdb06f6226ca6ff5d8f0f0e4ba0'
$prefix = 'https://raw.githubusercontent.com/aicoach-alpha/zbt-we5927-openwrt/' + $revision + '/packaging/veci-xl-native-overlay/'
function Fail([string] $code) {
  Write-Output ('XL_APK_BUILD=' + $code)
  exit 1
}
if (-not (Test-Path -LiteralPath $signKey -PathType Leaf)) { Fail 'signing_key_missing' }
if (-not (Test-Path -LiteralPath $pubKey -PathType Leaf)) { Fail 'signing_public_key_missing' }
if (-not (Get-Command 'docker' -ErrorAction SilentlyContinue)) { Fail 'docker_unavailable' }
if (Test-Path -LiteralPath $apkPath) { Fail 'output_already_exists' }
$filesDir = Join-Path $workspace 'files'
New-Item -ItemType Directory -Force -Path $workspace, $filesDir, (Join-Path $workspace 'dist') | Out-Null
$sourceFiles = @(
 'veci-xl-connection-status.js',
 'veci-xl-quota-session-gate',
 'veci-xl-authorized-config-import'
)
foreach ($name in $sourceFiles) {
  $destination = Join-Path $filesDir $name
  & curl.exe --fail --silent --show-error --location --retry 2 ($prefix + 'files/' + $name) --output $destination
  if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $destination -PathType Leaf)) {
    Fail ('download_failed_' + $name)
  }
}
$builder = Join-Path $workspace 'build-in-docker.sh'
& curl.exe --fail --silent --show-error --location --retry 2 ($prefix + 'build-in-docker.sh') --output $builder
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $builder -PathType Leaf)) { Fail 'builder_download_failed' }
$workMount = 'type=bind,source=' + $workspace + ',target=/work'
$keysMount = 'type=bind,source=' + $keyDir + ',target=/work/keys,readonly'
& docker run --rm --mount $workMount --mount $keysMount alpine:edge sh /work/build-in-docker.sh
if ($LASTEXITCODE -ne 0) { Fail 'docker_build_failed' }
if (-not (Test-Path -LiteralPath $apkPath -PathType Leaf)) { Fail 'artifact_missing' }
$hash = (Get-FileHash -LiteralPath $apkPath -Algorithm SHA256).Hash.ToLowerInvariant()
Write-Output 'XL_APK_WINDOWS=built'
Write-Output ('XL_APK_ARCH=mipsel_24kc')
Write-Output ('XL_APK_SHA256=' + $hash)
Write-Output ('XL_APK_PATH=' + $apkPath)
Write-Output 'XL_APK_ROUTER=unchanged'
