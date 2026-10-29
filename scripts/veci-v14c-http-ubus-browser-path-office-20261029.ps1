# VeCI v14c — a single credential-free HTTP /ubus POST diagnostic.
# Use on the office Windows PC attached to router LAN. No login or SSH.
# Does not modify router, browser, certificates or credentials.
$ErrorActionPreference = 'Stop'
$base = 'http://192.168.1.1'
$work = Join-Path $env:TEMP 'veci-v14c-http-path'
New-Item -ItemType Directory -Path $work -Force | Out-Null
$pageHeaders = Join-Path $work 'page.headers'
$postHeaders = Join-Path $work 'post.headers'
$postBody = Join-Path $work 'post.response'
$requestFile = Join-Path $work 'post.request'
function StatusLine([string]$name,[string[]]$data,[int]$code) {
  Write-Output ('VECI_V14C_'+$name+'_TRANSPORT_EXIT='+$code)
  Write-Output ('VECI_V14C_'+$name+'_HTTP='+($data -join '').Trim())
}
function SafeHeaders([string]$prefix,[string]$path) {
  if (-not (Test-Path -LiteralPath $path)) { return }
  foreach ($line in (Get-Content -LiteralPath $path)) {
    if ($line -match '^(Location|Content-Security-Policy|Strict-Transport-Security|Access-Control-Allow-Origin):\s*(.*)$') {
      $label = $Matches[1].ToUpperInvariant().Replace('-','_')
      $value = $Matches[2].Trim()
      if ($value.Length -gt 260) { $value = $value.Substring(0,260)+'[truncated]' }
      Write-Output ('VECI_V14C_'+$prefix+'_'+$label+'='+$value)
    }
  }
}
Write-Output 'VECI_V14C_SCOPE=single_local_http_page_and_one_unauthenticated_ubus_access_post'
Write-Output 'VECI_V14C_PASSWORD_USED=false'
try {
  $page = @(& curl.exe --silent --show-error --noproxy '*' --connect-timeout 3 --max-time 8 --dump-header $pageHeaders --output NUL --write-out 'http=%{http_code};seconds=%{time_total};redirect=%{redirect_url}' ($base+'/veci/'))
  $pageExit = $LASTEXITCODE
  StatusLine 'PAGE' $page $pageExit
  SafeHeaders 'PAGE' $pageHeaders
  # No username/password or real SID, no authentication or change of state.
  $payload = '{"jsonrpc":"2.0","id":914,"method":"call","params":["00000000000000000000000000000000","session","access",{"scope":"ubus","object":"session","function":"login"}]}'
  [IO.File]::WriteAllText($requestFile,$payload,(New-Object System.Text.UTF8Encoding($false)))
  $post = @(& curl.exe --silent --show-error --noproxy '*' --connect-timeout 3 --max-time 8 --dump-header $postHeaders --output $postBody --write-out 'http=%{http_code};seconds=%{time_total};redirect=%{redirect_url}' --header 'Content-Type: application/json' --data-binary ('@'+$requestFile) ($base+'/ubus'))
  $postExit = $LASTEXITCODE
  StatusLine 'UBUS_POST' $post $postExit
  SafeHeaders 'UBUS_POST' $postHeaders
  $jsonStatus = 'no_json_response'
  if ($postExit -eq 0 -and (Test-Path -LiteralPath $postBody)) {
    try {
      $j = Get-Content -LiteralPath $postBody -Raw | ConvertFrom-Json
      if ($j.jsonrpc -eq '2.0' -and $null -ne $j.result) {
        $jsonStatus = 'valid_jsonrpc'
        # Never print session IDs, tokens, full RPC bodies, or credentials.
        if ($j.result -is [array] -and $j.result.Count -gt 0) {
          Write-Output ('VECI_V14C_UBUS_RPC_STATUS='+[string]$j.result[0])
        }
      } elseif ($j.jsonrpc -eq '2.0' -and $null -ne $j.error) {
        $jsonStatus = 'jsonrpc_error'
      } else {
        $jsonStatus = 'unexpected_payload'
      }
    } catch { $jsonStatus = 'invalid_json' }
  }
  Write-Output ('VECI_V14C_UBUS_JSON='+$jsonStatus)
  if ($postExit -eq 0 -and $jsonStatus -eq 'valid_jsonrpc' -and ($post -join '') -match 'http=200;') {
    Write-Output 'VECI_V14C_CONCLUSION=LAN_HTTP_UBUS_POST_RESPONDS_INVESTIGATE_FIREFOX_POLICY_OR_REAL_LOGIN_REQUEST'
  } elseif (($post -join '') -match 'http=30[12378];') {
    Write-Output 'VECI_V14C_CONCLUSION=HTTP_UBUS_REDIRECT_OBSERVED'
  } else {
    Write-Output 'VECI_V14C_CONCLUSION=HTTP_UBUS_PATH_NEEDS_SERVER_INSPECTION'
  }
} finally {
  Remove-Item -LiteralPath $pageHeaders,$postHeaders,$postBody,$requestFile -Force -ErrorAction SilentlyContinue
}
Write-Output 'VECI_V14C_ROUTER=unchanged'
