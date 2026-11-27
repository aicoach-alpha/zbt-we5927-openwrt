# Exact board WE5927: make a read-only binary MTD3 dump on Windows without router temp files.
# RAW MTD3 is evidence/backup, NOT a validated sysupgrade or U-Boot rescue image.
# Requires user separately to run on office Windows laptop; no automatic router access.
[CmdletBinding()]
param([string]$BackupRoot='D:\Report_CCB')
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'

$router='root@192.168.1.1'
$arguments=@('-o','HostKeyAlgorithms=+ssh-rsa','-o','StrictHostKeyChecking=yes',
  '-o','ConnectTimeout=8','-o','ConnectionAttempts=1','-o','ServerAliveInterval=10',
  '-o','ServerAliveCountMax=2','-T',$router)
$expectedSize=[long]7995392

function Get-Exact-Router-Hash {
  $probe=@(& ssh.exe @arguments 'cat /tmp/sysinfo/board_name; cat /proc/mtd; sha256sum /dev/mtd3')
  if($LASTEXITCODE -ne 0){throw "STOP=ROUTER_PREFLIGHT_SSH_EXIT_$LASTEXITCODE"}
  if($probe.Count -lt 8 -or [string]$probe[0] -ne 'zbtlink,zbt-we5927') {
    throw 'STOP=BOARD_MISMATCH'
  }
  $sizes=@{
    0='00030000'; 1='00010000'; 2='00010000'; 3='007a0000'; 7='00010000'
  }
  $names=@{
    0='u-boot'; 1='u-boot-env'; 2='factory'; 3='firmware'; 7='art'
  }
  foreach($n in @(0,1,2,3,7)){
    $regex=('^mtd{0}:\s+{1}\s+00010000\s+"{2}"$' -f $n,$sizes[$n],$names[$n])
    if(@($probe | Where-Object { ([string]$_) -match $regex }).Count -ne 1){
      throw ('STOP=MTD_LAYOUT_NOT_EXACT_MTD{0}' -f $n)
    }
  }
  $hashLines=@($probe | Where-Object {([string]$_) -match '^[a-fA-F0-9]{64}\s+/dev/mtd3$'})
  if($hashLines.Count -ne 1){throw 'STOP=MTD3_HASH_MISSING_OR_AMBIGUOUS'}
  return ([regex]::Match([string]$hashLines[0],'^[a-fA-F0-9]{64}')).Value.ToLowerInvariant()
}

function Copy-BinaryStdoutToFile([string]$Executable, [string]$Arguments, [string]$Path) {
  $psi=New-Object System.Diagnostics.ProcessStartInfo
  $psi.FileName=$Executable
  $psi.Arguments=$Arguments
  $psi.UseShellExecute=$false
  $psi.RedirectStandardOutput=$true
  $psi.RedirectStandardError=$false
  $psi.CreateNoWindow=$true
  $proc=New-Object System.Diagnostics.Process
  $proc.StartInfo=$psi
  $file=$null
  $started=$false
  try {
    if(-not $proc.Start()){throw 'STOP=PROCESS_NOT_STARTED'}
    $started=$true
    $file=New-Object System.IO.FileStream($Path,[System.IO.FileMode]::CreateNew,
      [System.IO.FileAccess]::Write,[System.IO.FileShare]::None)
    # Native byte stream, not PowerShell pipeline/redirection (PS 5.1 corrupts binary output).
    $proc.StandardOutput.BaseStream.CopyTo($file)
    $file.Flush($true)
    $file.Dispose()
    $file=$null
    if(-not $proc.WaitForExit(15000)){throw 'STOP=SSH_PROCESS_HUNG'}
    if($proc.ExitCode -ne 0){throw ("STOP=BINARY_TRANSFER_EXIT_{0}" -f $proc.ExitCode)}
  } finally {
    if($null -ne $file){$file.Dispose()}
    if($started -and -not $proc.HasExited){$proc.Kill();$proc.WaitForExit()}
    $proc.Dispose()
  }
}

if(!(Get-Command ssh.exe -ErrorAction SilentlyContinue)){throw 'STOP=SSH_EXE_NOT_FOUND'}
if(!(Test-Path -LiteralPath $BackupRoot -PathType Container)){throw 'STOP=BACKUP_ROOT_NOT_FOUND'}
$drive=New-Object System.IO.DriveInfo -ArgumentList @([System.IO.Path]::GetPathRoot((Resolve-Path -LiteralPath $BackupRoot).Path))
if($drive.AvailableFreeSpace -lt 33554432){throw 'STOP=INSUFFICIENT_LOCAL_DISK_SPACE'}
Write-Output 'MODE=READ_ONLY_ROUTER_MTD3_TO_WINDOWS_BINARY_STREAM'
Write-Output 'FLASH=NO; REBOOT=NO; ROUTER_TMPFS_FILE=NONE'
$before=Get-Exact-Router-Hash
Write-Output 'LIVE_MTD3_HASH_BEFORE=CAPTURED'
$prefix='WE5927-CURRENT-MTD3-RAW-NOT-FLASHABLE-'+(Get-Date -Format 'yyyyMMdd_HHmmss')
$final=Join-Path $BackupRoot ($prefix+'.bin')
$temp=$final+'.partial'
if((Test-Path -LiteralPath $final) -or (Test-Path -LiteralPath $temp)){
  throw 'STOP=OUTPUT_ALREADY_EXISTS'
}
try {
  $ssh=(Get-Command ssh.exe).Source
  # The only remote operation is dd read from /dev/mtd3 to stdout, no remote file.
  $cli='-o HostKeyAlgorithms=+ssh-rsa -o StrictHostKeyChecking=yes -o ConnectTimeout=8 -o ConnectionAttempts=1 -o ServerAliveInterval=10 -o ServerAliveCountMax=2 -T root@192.168.1.1 "dd if=/dev/mtd3 bs=65536 2>/dev/null"'
  Copy-BinaryStdoutToFile -Executable $ssh -Arguments $cli -Path $temp
  $len=(Get-Item -LiteralPath $temp).Length
  if($len -ne $expectedSize){throw ("STOP=RAW_MTD3_SIZE_MISMATCH_{0}" -f $len)}
  $local=(Get-FileHash -LiteralPath $temp -Algorithm SHA256).Hash.ToLowerInvariant()
  if($local -ne $before){throw 'STOP=HASH_BEFORE_DIFFERS_FROM_SAVED_BACKUP'}
  $after=Get-Exact-Router-Hash
  if($local -ne $after){throw 'STOP=HASH_AFTER_DIFFERS_FROM_SAVED_BACKUP'}
  [System.IO.File]::Move($temp,$final)
  $receipt=[pscustomobject]@{
    schema='we5927-readonly-current-mtd3-backup.v1'
    date_local=(Get-Date).ToString('o')
    image_kind='RAW_MTD3_NOT_A_SYSUPGRADE_IMAGE'
    board='zbtlink,zbt-we5927'
    bytes=$expectedSize
    sha256=$local
    remote_hash_before_match=$true
    remote_hash_after_match=$true
    router_tmpfs_file_created=$false
    router_rebooted=$false
    firmware_flash_authorized=$false
    firmware_rollback_format_verified=$false
    restore_procedure_tested=$false
    image_path=$final
  }
  $json=Join-Path $BackupRoot ($prefix+'.json')
  if(Test-Path -LiteralPath $json){throw 'STOP=RECEIPT_ALREADY_EXISTS'}
  $receipt | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $json -Encoding UTF8
  Write-Output 'CURRENT_MTD3_BACKUP_SHA256_BEFORE_AND_AFTER=PASS'
  Write-Output ("CURRENT_MTD3_SIZE_BYTES={0}" -f $expectedSize)
  Write-Output ("CURRENT_MTD3_BACKUP_BIN={0}" -f $final)
  Write-Output ("CURRENT_MTD3_BACKUP_RECEIPT={0}" -f $json)
  Write-Output 'BACKUP_COMPLETE=YES; ROUTER_NOT_MODIFIED=YES; FLASH_AUTHORIZED=NO'
} finally {
  if(Test-Path -LiteralPath $temp){Remove-Item -LiteralPath $temp -Force}
}
