# VeCI Core r4 hot-update from Windows office laptop.
# Downloads the verified bundle, backs up router files to laptop, then patches VeCI Core only.
# This NEVER flashes OpenWrt, installs kernel modules, or touches LTE/HTTP configuration.
[CmdletBinding()]
param(
  [ValidatePattern('^[A-Za-z0-9.-]+$')][string]$RouterHost,
  [switch]$Rollback,
  [string]$BackupFile
)
$ErrorActionPreference = 'Stop'
$ExpectedSha256 = '425b22c09d5ba4d41077f3664c84f314d223d46eefa64c82f77a79c64e0c308c'
$BaseUrl = 'https://raw.githubusercontent.com/aicoach-alpha/zbt-we5927-openwrt/feat/veci-default-ui'
$ArchiveUrl = $BaseUrl + '/releases/veci-core-r4-hotfix/veci-core-r4.tar.gz'
$InstallerUrl = $BaseUrl + '/scripts/veci-core-apply.sh'
$UserFolder = [Environment]::GetFolderPath('MyDocuments')
if (-not $UserFolder) { $UserFolder = $env:USERPROFILE }
$BackupDir = Join-Path $UserFolder 'VeCI-backups'
$Tmp = Join-Path $env:TEMP ('veci-oneclick-' + [guid]::NewGuid().ToString('N'))
$Job = '/tmp/veci-oneclick-' + [guid]::NewGuid().ToString('N').Substring(0, 12)
$SshArgs = @('-o', 'StrictHostKeyChecking=ask', '-o', 'ConnectTimeout=10')
function Run-Ssh([string]$RemoteCommand) {
  $output = & ssh.exe @SshArgs ('root@' + $RouterHost) $RemoteCommand 2>&1
  if ($LASTEXITCODE -ne 0) {
    throw ('Router SSH failed (' + $LASTEXITCODE + '): ' + ($output | Out-String).Trim())
  }
  return (($output | Out-String).Trim())
}
function Run-Scp([string]$From, [string]$To) {
  & scp.exe '-O' @SshArgs $From $To
  if ($LASTEXITCODE -ne 0) {
    throw ('SCP transfer failed (' + $LASTEXITCODE + '). OpenWrt Dropbear requires legacy SCP support (-O).')
  }
}
function Check-Http {
  $response = Invoke-WebRequest -Uri ('http://' + $RouterHost + '/veci/') -UseBasicParsing -TimeoutSec 15 -MaximumRedirection 0
  if ($response.StatusCode -ne 200) { throw 'VeCI HTTP returned an unexpected status.' }
  if ($response.Content -notmatch 'veci|VeCI') { throw 'Unexpected content on VeCI HTTP page.' }
}
try {
  if (-not $RouterHost) {
    $gateways = @(Get-NetIPConfiguration | ForEach-Object { $_.IPv4DefaultGateway.NextHop } |
      Where-Object { $_ -match '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$' } | Select-Object -Unique)
    if ($gateways.Count -eq 1) {
      $candidate = $gateways[0]
      $choice = Read-Host ('Router IP (Enter for detected gateway ' + $candidate + ')')
      if ([string]::IsNullOrWhiteSpace($choice)) { $RouterHost = $candidate } else { $RouterHost = $choice.Trim() }
    } else {
      $RouterHost = (Read-Host 'Enter the router IPv4 reachable from this OFFICE laptop').Trim()
    }
  }
  if ($RouterHost -notmatch '^[A-Za-z0-9.-]+$') { throw 'Invalid router host.' }
  if (-not (Get-Command ssh.exe -ErrorAction SilentlyContinue)) { throw 'Windows OpenSSH ssh.exe not found.' }
  if (-not (Get-Command scp.exe -ErrorAction SilentlyContinue)) { throw 'Windows OpenSSH scp.exe not found.' }
  New-Item -ItemType Directory -Path $Tmp -Force | Out-Null
  New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
  $Archive = Join-Path $Tmp 'veci-core-r4.tar.gz'
  $Installer = Join-Path $Tmp 'veci-core-apply.sh'
  Write-Host '[1/7] Download verified VeCI Core r4 bundle and installer from GitHub'
  Invoke-WebRequest -Uri $ArchiveUrl -OutFile $Archive -UseBasicParsing
  Invoke-WebRequest -Uri $InstallerUrl -OutFile $Installer -UseBasicParsing
  $actual = (Get-FileHash -LiteralPath $Archive -Algorithm SHA256).Hash
  if ($actual -ine $ExpectedSha256) { throw ('STOP: bundle SHA256 mismatch. Got ' + $actual) }
  Write-Host ('PASS: bundle SHA256 ' + $actual)

  Write-Host '[2/7] Check actual office laptop -> router identity (NOT andre-nas)'
  $board = (Run-Ssh 'ubus call system board') | ConvertFrom-Json
  if ($board.board_name -ne 'zbtlink,zbt-we5927' -or $board.release.target -ne 'ramips/mt76x8') {
    throw ('STOP: wrong board/target: ' + $board.board_name + ' / ' + $board.release.target)
  }
  Write-Host ('PASS: ' + $board.board_name)
  if (-not $Rollback) {
    Write-Host '[3/7] Confirm VeCI HTTP works BEFORE applying any changes'
    Check-Http
  }

  Write-Host '[4/7] Stage files into router RAM (no flash)'
  Run-Ssh ('mkdir -p ' + $Job) | Out-Null
  Run-Scp $Installer (('root@' + $RouterHost + ':' + $Job + '/apply.sh'))
  Run-Scp $Archive (('root@' + $RouterHost + ':' + $Job + '/veci-core-r4.tar.gz'))

  if ($Rollback) {
    if (-not $BackupFile) {
      $latest = Get-ChildItem -LiteralPath $BackupDir -Filter ($RouterHost + '-*-core-backup.tar.gz') -File |
        Sort-Object LastWriteTime -Descending | Select-Object -First 1
      if (-not $latest) { throw 'No matching VeCI backup found; use -BackupFile.' }
      $BackupFile = $latest.FullName
    }
    if (-not (Test-Path -LiteralPath $BackupFile -PathType Leaf)) { throw 'Rollback backup not found.' }
    Write-Host ('Restoring saved backup ' + $BackupFile)
    Run-Scp $BackupFile ('root@' + $RouterHost + ':' + $Job + '/backup.tar.gz')
    Run-Ssh ('sh ' + $Job + '/apply.sh rollback ' + $Job + ' ' + $ExpectedSha256) | Write-Host
    Write-Host 'Rollback files restored; verify VeCI and LuCI manually.'
    return
  }

  Write-Host '[5/7] Read-only checks and backup of current VeCI Core'
  Run-Ssh ('sh ' + $Job + '/apply.sh prepare ' + $Job + ' ' + $ExpectedSha256) | Write-Host
  $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
  $backupLocal = Join-Path $BackupDir ($RouterHost + '-' + $stamp + '-core-backup.tar.gz')
  Run-Scp ('root@' + $RouterHost + ':' + $Job + '/backup.tar.gz') $backupLocal
  if (-not (Test-Path -LiteralPath $backupLocal) -or (Get-Item -LiteralPath $backupLocal).Length -lt 200) {
    throw 'STOP: router backup could not be saved on the office laptop.'
  }
  Write-Host ('Saved rollback backup: ' + $backupLocal)
  Write-Host '[6/7] Confirm the manual update'
  Write-Host 'This updates ONLY the VeCI web interface, rpcd backend and ACL. It does NOT flash firmware or install optional apps.'
  $approval = Read-Host 'Type UPDATE to apply Core r4, or Enter to cancel'
  if ($approval -cne 'UPDATE') { throw 'Update cancelled. Router configuration unchanged.' }
  try {
    Run-Ssh ('sh ' + $Job + '/apply.sh apply ' + $Job + ' ' + $ExpectedSha256) | Write-Host
  } catch {
    Write-Warning ('Apply failed: ' + $_.Exception.Message)
    try {
      Run-Ssh ('sh ' + $Job + '/apply.sh rollback ' + $Job + ' ' + $ExpectedSha256) | Write-Host
    } catch {
      Write-Warning ('Automatic rollback could not be confirmed. Backup is on laptop: ' + $backupLocal)
    }
    throw 'Core r4 update failed. Previous files restored where possible.'
  }

  Write-Host '[7/7] Verify HTTP after updating the files'
  try {
    Check-Http
    $marker = Invoke-WebRequest -Uri ('http://' + $RouterHost + '/veci/veci-core-commit.txt') -UseBasicParsing -TimeoutSec 15 -MaximumRedirection 0
    if ($marker.Content.Trim() -ne '81853a6b8b710a26a2427d1176751bf781bc7243') {
      throw 'Core r4 marker mismatch after update.'
    }
  } catch {
    Write-Warning 'Post-update HTTP check failed: automatically attempting file rollback.'
    Run-Ssh ('sh ' + $Job + '/apply.sh rollback ' + $Job + ' ' + $ExpectedSha256) | Write-Host
    throw 'HTTP check failed. Rolled back previous VeCI Core files.'
  }
  Write-Host 'SUCCESS: VeCI Core r4 hot-update verified on HTTP. No firmware flash performed.'
  Write-Host ('Backup retained at: ' + $backupLocal)
} finally {
  if (Test-Path -LiteralPath $Tmp) { Remove-Item -LiteralPath $Tmp -Recurse -Force -ErrorAction SilentlyContinue }
}
