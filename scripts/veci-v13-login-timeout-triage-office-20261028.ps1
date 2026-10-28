# VeCI v13: inspect captured frontend login source and one dummy ubus login.
# No actual credentials, no router writes, no service restart.
$ErrorActionPreference = 'Stop'
$workspace = 'C:\veci-build\veci-v13-readonly-20261028'
$archive = Join-Path $workspace 'veci-v13-ui-source-20261028.tar.gz'
$expected = '1813a12623758fe662eda06eb7c90a4dbbfb85572304ec4b4551381d928b3e15'
function Fail([string]$reason) { Write-Output ('VECI_LOGIN_TRIAGE=' + $reason); exit 1 }
if (-not (Test-Path -LiteralPath $archive -PathType Leaf)) { Fail 'source_archive_not_found' }
if ((Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expected) {
 Fail 'archive_digest_changed'
}
Write-Output 'VECI_LOGIN_ARCHIVE=verified_original'
$names = @(& tar.exe -tzf $archive)
if ($LASTEXITCODE -ne 0) { Fail 'archive_list_failed' }
foreach ($path in @('veci/js/lib/api.js','veci/js/app.js','veci/index.html')) {
 if (-not ($names -contains $path)) {
  Write-Output ('VECI_LOGIN_SOURCE_MISSING=' + $path)
  continue
 }
 $raw = @(& tar.exe -xOzf $archive $path)
 if ($LASTEXITCODE -ne 0) { Fail 'archive_extract_failed' }
 $lines = @(($raw -join [char]10) -split [char]10)
 $indices = New-Object 'System.Collections.Generic.HashSet[int]'
 for ($i=0; $i -lt $lines.Count; $i++) {
  if ($lines[$i] -match '(?i)session[.]login|timed[ -]?out|AbortController|fetch[(]|/ubus|login[(]|timeout|loginForm|loginButton') {
   for ($j=[Math]::Max(0,$i-3); $j -le [Math]::Min($lines.Count-1,$i+4); $j++) {
    [void]$indices.Add([int]$j)
   }
  }
 }
 $ordered = @($indices | Sort-Object | Select-Object -First 100)
 Write-Output ('=== VECI_LOGIN_SOURCE=' + $path + ';selected_lines=' + $ordered.Count + ' ===')
 foreach ($i in $ordered) {
  $line = $lines[$i]
  $line = $line -replace '(?i)(api[_-]?key|token|secret)\s*[:=]\s*["''][^"'']{12,}["'']', '$1: "[REDACTED]"'
  Write-Output ('L' + ($i+1) + ': ' + $line)
 }
}
# One invalid synthetic login on local HTTPS; no user password is sent.
$payloadFile = Join-Path $env:TEMP 'veci-v13-dummy-login-probe.json'
$responseFile = Join-Path $env:TEMP 'veci-v13-dummy-login-response.json'
$payload = '{"jsonrpc":"2.0","id":741,"method":"call","params":["00000000000000000000000000000000","session","login",{"username":"__veci_probe_nonexistent__","password":"__invalid_probe_no_secret__"}]}'
[IO.File]::WriteAllText($payloadFile,$payload,(New-Object System.Text.UTF8Encoding($false)))
Write-Output 'VECI_LOGIN_DUMMY_PROBE=begin_one_request'
try {
 $curlArgs = @('--silent','--show-error','--insecure','--max-time','12','--connect-timeout','4','--output',$responseFile,'--write-out','http=%{http_code};seconds=%{time_total}','--header','Content-Type: application/json','--data-binary',('@'+$payloadFile),'https://192.168.1.1/ubus')
 $http = & curl.exe @curlArgs
 $rc = $LASTEXITCODE
 Write-Output ('VECI_LOGIN_DUMMY_HTTP=' + ($http -join '').Trim())
 if ($rc -ne 0) {
  Write-Output ('VECI_LOGIN_DUMMY_TRANSPORT=failed_exit_' + $rc)
 } else {
  try {
   $parsed = Get-Content -LiteralPath $responseFile -Raw | ConvertFrom-Json
   if ($null -ne $parsed.result -and $parsed.result.Count -gt 0) {
    Write-Output ('VECI_LOGIN_DUMMY_UBUS_CODE=' + $parsed.result[0])
   } else { Write-Output 'VECI_LOGIN_DUMMY_UBUS_CODE=missing_result' }
  } catch { Write-Output 'VECI_LOGIN_DUMMY_UBUS_CODE=invalid_json' }
 }
} finally {
 Remove-Item -LiteralPath $payloadFile,$responseFile -Force -ErrorAction SilentlyContinue
}
Write-Output 'VECI_LOGIN_TRIAGE=read_only_complete'
Write-Output 'VECI_LOGIN_PRODUCTION=unchanged'
