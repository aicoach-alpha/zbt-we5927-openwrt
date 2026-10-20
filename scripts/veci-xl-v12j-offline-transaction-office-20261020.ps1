# VeCI XL v12j — one scoped, offline transaction simulation on office router.
# Two candidate APKs copied temporarily to /tmp; no install, no service restart.
$ErrorActionPreference = 'Stop'
$dir = 'C:\veci-build\xl-native-candidates-v12i\dist'
$router = 'root@192.168.1.1'
$xl = Join-Path $dir 'veci-telco-xl-native-0.3.8-r2-mipsel_24kc.apk'
$id = Join-Path $dir 'veci-telco-indonesia-0.2.2-r2-mipsel_24kc.apk'
$rollX = Join-Path $dir 'rollback\veci-telco-xl-native-0.3.7-r1-mipsel_24kc.apk'
$rollI = Join-Path $dir 'rollback\veci-telco-indonesia-0.2.1-r1-mipsel_24kc.apk'
$checks = @(
    @($xl,'801b421569f6cd18ade2bfc3a86c7e61e333e680dfc41e29edffd3cdd0793f37'),
    @($id,'da3d5d9da1bdc684170d75773a03562f7dcca672a3d3d8dd1575969ad4d65866'),
    @($rollX,'bfea7ec575c5c6c3e0d4865f4dcc3e08db0a76defa8e960009d45d55478bfbc0'),
    @($rollI,'191061f9b6625c6f419779be707204542b0e2c133f21d94355dc70a60b8eaab7')
)
function Fail([string]$code) { Write-Output ('XL_V12J_OFFICE=' + $code); exit 1 }
foreach ($entry in $checks) {
    if (-not (Test-Path -LiteralPath $entry[0] -PathType Leaf)) { Fail 'missing_signed_artifact' }
    if ((Get-FileHash -LiteralPath $entry[0] -Algorithm SHA256).Hash.ToLowerInvariant() -ne $entry[1]) {
        Fail 'artifact_digest_mismatch'
    }
}
Write-Output 'XL_V12J_OFFICE_SHA256=pass'
$remX = '/tmp/veci-xl-native-0.3.8-r2-v12j.apk'
$remI = '/tmp/veci-telco-indonesia-0.2.2-r2-v12j.apk'
# Copy only the two signed upgrades. Reconstructed rollbacks stay safely on office PC.
& scp -O $xl ($router + ':' + $remX)
if ($LASTEXITCODE -ne 0) { Fail 'xl_staging_failed' }
& scp -O $id ($router + ':' + $remI)
if ($LASTEXITCODE -ne 0) { Fail 'indonesia_staging_failed' }
$remoteScript = 'https://raw.githubusercontent.com/aicoach-alpha/zbt-we5927-openwrt/b19d454d7fb8e7507463544902194d9f81bd6492/scripts/veci-xl-v12j-offline-transaction-simulate-20261020.sh'
$command = 'wget -qO /tmp/veci-xl-v12j-simulate.sh ' + $remoteScript + ' && sh -n /tmp/veci-xl-v12j-simulate.sh && sh /tmp/veci-xl-v12j-simulate.sh'
$messages = @(& ssh $router $command)
$exitCode = $LASTEXITCODE
foreach ($line in $messages) { Write-Output $line }
# The only router mutation during v12j is transient staging in /tmp.
$cleanup = 'rm -f /tmp/veci-xl-native-0.3.8-r2-v12j.apk /tmp/veci-telco-indonesia-0.2.2-r2-v12j.apk /tmp/veci-xl-v12j-simulate.sh'
& ssh $router $cleanup | Out-Null
if ($LASTEXITCODE -ne 0) { Fail 'staging_cleanup_failed' }
if ($exitCode -ne 0 -or $messages -notcontains 'XL_V12J_SIMULATE=pass') {
    Fail 'transaction_simulation_blocked'
}
Write-Output 'XL_V12J_OFFICE=pass'
Write-Output 'XL_V12J_INSTALL=not_attempted'
Write-Output 'XL_V12J_PRODUCTION=unchanged'
