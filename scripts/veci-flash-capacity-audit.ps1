# One command Windows operator audit of running WE5927 firmware partition capacity without touching router settings.
# No package installation, firmware flashing, network changes, or sensitive-data collection.
[CmdletBinding()]
param([ValidatePattern('^[A-Za-z0-9.-]+$')][string]$RouterHost)
$ErrorActionPreference = 'Stop'
$Url='https://raw.githubusercontent.com/aicoach-alpha/zbt-we5927-openwrt/feat/veci-default-ui/scripts/veci-flash-capacity-audit.sh'
$ExpectedSha256='1013a3196f4c4a1a9e50441fb2213add693ed3114918ee76e731c5ee10b21843'
$Work=Join-Path $env:TEMP ('veci-flash-audit-'+[guid]::NewGuid().ToString('N'))
$Remote='/tmp/veci-flash-audit-'+[guid]::NewGuid().ToString('N').Substring(0,12)+'.sh'
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
    $Shell=Join-Path $Work 'veci-flash-capacity-audit.sh'
    Write-Host '[1/4] Download and verify immutable VeCI flash-capacity script'
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
    Write-Host '[3/4] Run read-only flash partition capacity inspection'
    & scp.exe '-O' @SSHOpts $Shell ('root@'+$RouterHost+':'+$Remote)
    if ($LASTEXITCODE -ne 0) {throw 'Could not stage audit in router volatile /tmp'}
    $auditOutput = & ssh.exe @SSHOpts ('root@'+$RouterHost) ('sh '+$Remote) 2>&1
    $auditExitCode = $LASTEXITCODE
    $report = ($auditOutput | Out-String).Trim()
    if (-not $report) {throw 'The flash capacity audit returned no report'}
    Write-Host $report
    $Documents=[Environment]::GetFolderPath('MyDocuments')
    if (-not $Documents) {$Documents=$env:USERPROFILE}
    $Dir=Join-Path $Documents 'VeCI-audits'
    New-Item -ItemType Directory -Path $Dir -Force | Out-Null
    $File=Join-Path $Dir ($RouterHost+'-'+(Get-Date -Format 'yyyyMMdd-HHmmss')+'-flash-capacity.txt')
    Set-Content -LiteralPath $File -Value $report -Encoding UTF8
    Write-Host ('[4/4] Report saved: '+$File)
    if ($auditExitCode -ne 0) {
        Write-Warning ('FLASH AUDIT BLOCKED (exit '+$auditExitCode+'). No firmware changes were made.')
    } elseif ($report -match 'MTD_GATE=PROFILE_LIMIT_FITS_REPORTED_PARTITION') {
        Write-Host 'PARTITION CHECK PASSED. Flash remains prohibited until the finished image, backup, recovery and hardware UAT are verified.'
    } else {
        Write-Warning 'FLASH AUDIT UNKNOWN. Do not flash firmware.'
    }
} finally {
    # Limited to our own generated path; clean up temporary audit script, not router services.
    if ($RouterHost -match '^[A-Za-z0-9.-]+$' -and $Remote -match '^/tmp/veci-flash-audit-[0-9a-f]{12}\.sh$') {
        try { & ssh.exe @SSHOpts ('root@'+$RouterHost) ('rm -f '+$Remote) 2>$null | Out-Null } catch {}
    }
    if (Test-Path -LiteralPath $Work) {Remove-Item -LiteralPath $Work -Recurse -Force -ErrorAction SilentlyContinue}
}
