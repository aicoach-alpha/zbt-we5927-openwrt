# One command Windows operator audit of running WE5927 app / signed feed compatibility.
# No package installation, firmware flash, configuration changes, or secrets collection.
[CmdletBinding()]
param([ValidatePattern('^[A-Za-z0-9.-]+$')][string]$RouterHost)
$ErrorActionPreference = 'Stop'
$Url='https://raw.githubusercontent.com/aicoach-alpha/zbt-we5927-openwrt/feat/veci-default-ui/scripts/veci-apps-readiness.sh'
$ExpectedSha256='3c8d987c270b03f5cdd12c485174ef918a24056a471f05da6c31463db1678b0e'
$Work=Join-Path $env:TEMP ('veci-apps-audit-'+[guid]::NewGuid().ToString('N'))
$Remote='/tmp/veci-apps-audit-'+[guid]::NewGuid().ToString('N').Substring(0,12)+'.sh'
$SSHOpts=@('-o','StrictHostKeyChecking=ask','-o','ConnectTimeout=10')
function Run-Ssh([string]$Command) {
    $output = & ssh.exe @SSHOpts ('root@'+$RouterHost) $Command 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw ('SSH returned '+$LASTEXITCODE+': '+(($output | Out-String).Trim()))
    }
    return ($output | Out-String).Trim()
}
try {
    if (-not $RouterHost) {
        $gateways=@(Get-NetIPConfiguration | ForEach-Object {$_.IPv4DefaultGateway.NextHop} |
            Where-Object {$_ -match '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$'} | Select-Object -Unique)
        if ($gateways.Count -eq 1) {
            $value=Read-Host ('Router IP (Enter for detected gateway '+$gateways[0]+')')
            $RouterHost=if ([string]::IsNullOrWhiteSpace($value)) {$gateways[0]} else {$value.Trim()}
        } else {
            $RouterHost=(Read-Host 'Enter your WE5927 router IP').Trim()
        }
    }
    if ($RouterHost -notmatch '^[A-Za-z0-9.-]+$') {throw 'Invalid router host'}
    if (-not (Get-Command ssh.exe -ErrorAction SilentlyContinue)) {throw 'Windows OpenSSH ssh.exe missing'}
    if (-not (Get-Command scp.exe -ErrorAction SilentlyContinue)) {throw 'Windows OpenSSH scp.exe missing'}
    New-Item -ItemType Directory -Path $Work -Force | Out-Null
    $Shell=Join-Path $Work 'veci-apps-readiness.sh'
    Write-Host '[1/4] Download and verify immutable VeCI app-readiness script'
    Invoke-WebRequest -Uri $Url -OutFile $Shell -UseBasicParsing
    $hash=(Get-FileHash -LiteralPath $Shell -Algorithm SHA256).Hash
    if ($hash -ine $ExpectedSha256) {throw ('STOP: audit checksum mismatch: '+$hash)}
    Write-Host ('PASS SHA256: '+$hash)
    Write-Host '[2/4] Verify WE5927 router and OpenWrt target (read-only)'
    $board=(Run-Ssh 'ubus call system board') | ConvertFrom-Json
    if ($board.board_name -ne 'zbtlink,zbt-we5927' -or $board.release.target -ne 'ramips/mt76x8') {
        throw ('STOP: wrong router '+$board.board_name+' / '+$board.release.target)
    }
    Write-Host ('PASS '+$board.board_name)
    Write-Host '[3/4] Run read-only app, kernel, and signed-feed inspection'
    & scp.exe '-O' @SSHOpts $Shell ('root@'+$RouterHost+':'+$Remote)
    if ($LASTEXITCODE -ne 0) {throw 'Could not stage audit in router volatile /tmp'}
    $report=Run-Ssh ('sh '+$Remote)
    Write-Host $report
    $Documents=[Environment]::GetFolderPath('MyDocuments')
    if (-not $Documents) {$Documents=$env:USERPROFILE}
    $Dir=Join-Path $Documents 'VeCI-audits'
    New-Item -ItemType Directory -Path $Dir -Force | Out-Null
    $File=Join-Path $Dir ($RouterHost+'-'+(Get-Date -Format 'yyyyMMdd-HHmmss')+'-apps-readiness.txt')
    Set-Content -LiteralPath $File -Value $report -Encoding UTF8
    Write-Host ('[4/4] Report saved: '+$File)
    if ($report -match 'APPS_INSTALL_GATE=SIGNED_FEED_READY') {
        Write-Host 'PASS: matching signed feed verified. No install was performed.'
    } else {
        Write-Warning 'INSTALL BLOCKED: signed feed / firmware / dependencies are not yet confirmed. No install was attempted.'
    }
} finally {
    # Limited to our own generated path; clean up temporary audit script, not router services.
    if ($RouterHost -match '^[A-Za-z0-9.-]+$' -and $Remote -match '^/tmp/veci-apps-audit-[0-9a-f]{12}\.sh$') {
        try { & ssh.exe @SSHOpts ('root@'+$RouterHost) ('rm -f '+$Remote) 2>$null | Out-Null } catch {}
    }
    if (Test-Path -LiteralPath $Work) {Remove-Item -LiteralPath $Work -Recurse -Force -ErrorAction SilentlyContinue}
}
