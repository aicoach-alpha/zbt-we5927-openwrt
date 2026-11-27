# WE5927 recovery inventory — LOCAL FILES ONLY. Never connects to router.
# Reviews recorded 2026-11-23 owner evidence and the later 2026-11-25 backup.
[CmdletBinding()]
param(
  [string]$ReportRoot = 'D:\Report_CCB'
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$parts = @(
  [pscustomobject]@{Index=0; Bytes=196608; Name='u-boot'; Sha23='b2acbf1e762e310d467cfcbae853257a9f63ce311511134bc9d0d5953f835330'}
  [pscustomobject]@{Index=1; Bytes=65536; Name='u-boot-env'; Sha23='757def42b82e074ebf0638d7f45fbbc3d0caf406958225685fea8af423745977'}
  [pscustomobject]@{Index=2; Bytes=65536; Name='factory'; Sha23='65442ad13e9e4795004f16ede40718d0fbf7d8eb07d8702ba3b1e410fee951f7'}
  [pscustomobject]@{Index=3; Bytes=7995392; Name='firmware'; Sha23='6a75b2b3e0db3782c3d3b66908395026840033319705c99ee9391637202528bd'}
  [pscustomobject]@{Index=7; Bytes=65536; Name='art'; Sha23='f143aeb1d2fed906e4d0d88268251083cd4326fa05f66b1c2283834cf973dba9'}
)
$folders = @(
  [pscustomobject]@{Label='NOV23'; Path=(Join-Path $env:USERPROFILE 'Documents\VeCI-WE5927-Recovery-20261123-171236'); Historical=$true}
  [pscustomobject]@{Label='NOV25'; Path=(Join-Path $ReportRoot 'WE5927-Recovery-20261125_135411'); Historical=$false}
)
$records = New-Object 'System.Collections.Generic.List[object]'
$summary = New-Object 'System.Collections.Generic.List[object]'
Write-Output '===WE5927_OFFLINE_MTD_RECOVERY_AUDIT==='
Write-Output 'MODE=LOCAL_READ_ONLY; SSH=NONE; ROUTER_ACCESS=NONE; FLASH=NO; REBOOT=NO'
foreach ($folder in $folders) {
  if (-not (Test-Path -LiteralPath $folder.Path -PathType Container)) {
    Write-Output ("BACKUP_FOLDER_{0}=NOT_FOUND" -f $folder.Label)
    $summary.Add([pscustomobject]@{Label=$folder.Label; Folder=$folder.Path; Present=$false; Good=0; Expected=5})
    continue
  }
  $candidates = @(Get-ChildItem -LiteralPath $folder.Path -Recurse -File -ErrorAction Stop |
    Where-Object { $_.Extension -in @('.bin','.img','.dump') })
  $good = 0
  foreach ($part in $parts) {
    $token = '(?i)(?<![a-z0-9])mtd' + $part.Index + '(?![0-9])'
    $matches = @($candidates | Where-Object { $_.BaseName -match $token })
    if ($matches.Count -eq 0) {
      $aliases = switch ($part.Index) {
        0 { @('u-boot','uboot') }
        1 { @('u-boot-env','uboot-env') }
        2 { @('factory') }
        3 { @('firmware') }
        7 { @('art') }
      }
      $matches = @($candidates | Where-Object { $_.BaseName.ToLowerInvariant() -in $aliases })
    }
    $status = 'MISSING'
    $bytes = $null
    $sha = $null
    $filename = $null
    if ($matches.Count -gt 1) {
      $status = 'AMBIGUOUS_FILES'
    } elseif ($matches.Count -eq 1) {
      $f = $matches[0]
      $filename = $f.Name
      $bytes = [long]$f.Length
      if ($bytes -ne [long]$part.Bytes) {
        $status = 'SIZE_MISMATCH'
      } else {
        $sha = (Get-FileHash -LiteralPath $f.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($folder.Historical) {
          if ($sha -eq $part.Sha23) { $status = 'HISTORICAL_SHA_PASS'; $good++ }
          else { $status = 'HISTORICAL_SHA_MISMATCH' }
        } else {
          $status = 'SIZE_PASS_HASH_RECORDED_NOT_ROUTER_MATCHED'
          $good++
        }
      }
    }
    $records.Add([pscustomobject]@{
      Backup=$folder.Label; Partition=('mtd'+$part.Index)
      PartitionName=$part.Name; Status=$status; File=$filename
      Bytes=$bytes; Sha256=$sha; ExpectedBytes=[long]$part.Bytes
    })
    Write-Output ("{0}_MTD{1}={2}; BYTES={3}" -f $folder.Label, $part.Index, $status, $bytes)
  }
  $summary.Add([pscustomobject]@{Label=$folder.Label; Folder=$folder.Path; Present=$true; Good=$good; Expected=5})
}
$old = @($summary | Where-Object { $_.Label -eq 'NOV23' })[0]
$recent = @($summary | Where-Object { $_.Label -eq 'NOV25' })[0]
if ($old.Good -eq 5) { Write-Output 'HISTORICAL_NOV23_FIVE_MTD_SHA256=PASS' }
else { Write-Output 'HISTORICAL_NOV23_FIVE_MTD_SHA256=NOT_VERIFIED' }
if ($recent.Good -eq 5) { Write-Output 'NOV25_FIVE_MTD_FILE_SIZES=PASS_SHA_NOT_ROUTER_MATCHED' }
else { Write-Output 'NOV25_FIVE_MTD_FILE_SIZES=INCOMPLETE_OR_UNVERIFIED' }
Write-Output 'CURRENT_ROUTER_MTD_EQUALS_BACKUP=NOT_TESTED'
Write-Output 'LIVE_BOOTLOADER_RECOVERY=NOT_TESTED'
Write-Output 'CONFIG_BACKUP_IS_NOT_FULL_MTD_BACKUP=YES'
Write-Output 'FIRMWARE_FLASH_AUTHORIZED=NO'
$report = [ordered]@{
  schema='we5927-local-recovery-audit.v1'
  historical_evidence_date='2026-11-23'
  source='local_files_only'
  router_access=$false
  flash_authorized=$false
  current_router_match='NOT_TESTED'
  bootloader_recovery='NOT_TESTED'
  backups=$summary.ToArray()
  partition_results=$records.ToArray()
}
if (-not (Test-Path -LiteralPath $ReportRoot -PathType Container)) {
  Write-Output 'REPORT=NOT_SAVED_ROOT_NOT_FOUND'
} else {
  $output = Join-Path $ReportRoot ('WE5927-RECOVERY-AUDIT-' + (Get-Date -Format 'yyyyMMdd_HHmmss') + '.json')
  if (Test-Path -LiteralPath $output) { throw 'REPORT_FILE_ALREADY_EXISTS' }
  $report | ConvertTo-Json -Depth 7 | Set-Content -LiteralPath $output -Encoding UTF8
  Write-Output ("LOCAL_AUDIT_REPORT={0}" -f $output)
}
Write-Output 'OFFLINE_AUDIT_COMPLETE; NO_ROUTER_CONTACT; NO_FLASH'
