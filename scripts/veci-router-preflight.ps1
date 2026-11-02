# Windows PowerShell 5.1+; deliberately READ ONLY.
[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)]
  [ValidatePattern('^[A-Za-z0-9._-]+$')]
  [string]$RouterHost,
  [string]$FirmwareFile,
  [string]$ExpectedSha256
)
$ErrorActionPreference = 'Stop'
function Read-Router([string]$Command) {
  $ssh = Get-Command ssh.exe -ErrorAction SilentlyContinue
  if (-not $ssh) { throw 'Windows OpenSSH client is missing.' }
  $output = & $ssh.Source '-o' 'ConnectTimeout=7' '-o' 'BatchMode=no' '-o' 'NumberOfPasswordPrompts=1' '-o' 'StrictHostKeyChecking=ask' ('root@' + $RouterHost) $Command 2>&1
  if ($LASTEXITCODE -ne 0) { throw ('STOP: SSH read failed: ' + ($output | Out-String).Trim()) }
  return ($output | Out-String).Trim()
}
Write-Host '[1/4] Device identity (from office laptop, NOT from andre-nas)'
$board = (Read-Router 'ubus call system board') | ConvertFrom-Json
if ($board.board_name -ne 'zbtlink,zbt-we5927') { throw 'STOP: wrong board identity.' }
if ($board.release.target -ne 'ramips/mt76x8') { throw 'STOP: wrong OpenWrt target.' }
Write-Host ('PASS: ' + $board.board_name + ' / ' + $board.release.target)
Write-Host '[2/4] Read-only release, flash and overlay inventory'
Write-Host (Read-Router 'cat /etc/openwrt_release')
Write-Host (Read-Router 'df -Pk /overlay')
Write-Host (Read-Router 'cat /proc/mtd')
Write-Host '[3/4] Optional local firmware check'
if ($FirmwareFile) {
  if ($ExpectedSha256 -notmatch '^[0-9a-fA-F]{64}$') { throw 'STOP: independently published SHA256 is required.' }
  if (-not (Test-Path -LiteralPath $FirmwareFile -PathType Leaf)) { throw 'STOP: image not found.' }
  $size = (Get-Item -LiteralPath $FirmwareFile).Length
  if ($size -lt 1048576 -or $size -gt (7808 * 1024)) { throw 'STOP: firmware image outside expected size.' }
  $actual = (Get-FileHash -LiteralPath $FirmwareFile -Algorithm SHA256).Hash
  if ($actual -ine $ExpectedSha256) { throw 'STOP: image hash mismatch.' }
  Write-Host ('PASS: SHA256 = ' + $actual)
} elseif ($ExpectedSha256) {
  throw 'STOP: ExpectedSha256 without FirmwareFile.'
} else {
  Write-Host 'No image supplied. Firmware verification NOT performed.'
}
Write-Host '[4/4] READ-ONLY PRECHECK PASS. NO ROUTER CHANGES OR FLASH.'
Write-Host 'STOP before installation until exact-ABI signed firmware/feed, backup, sysupgrade -T and UAT approval are confirmed.'
