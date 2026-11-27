# WE5927 exact-owner U-Boot string-marker audit: WINDOWS LOCAL FILES ONLY.
# This checks preserved Nov23 and Nov25 mtd0 backups, not the running bootloader.
# Never upload firmware to U-Boot web failsafe just to test its form.
[CmdletBinding()]
param(
  [string]$AuditJson='D:\Report_CCB\WE5927-RECOVERY-AUDIT-20261127_115107.json'
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'

function Find-AsciiMarker {
  param(
    [byte[]]$Bytes,
    [string]$Needle
  )
  if($Bytes.Length -eq 0 -or [string]::IsNullOrWhiteSpace($Needle)) {return -1}
  $ascii=[System.Text.Encoding]::ASCII.GetString($Bytes)
  return $ascii.IndexOf($Needle,[System.StringComparison]::OrdinalIgnoreCase)
}

if(!(Test-Path -LiteralPath $AuditJson -PathType Leaf)){throw 'STOP=LOCAL_BACKUP_AUDIT_REPORT_MISSING'}
$audit=Get-Content -LiteralPath $AuditJson -Raw | ConvertFrom-Json
if($audit.schema -ne 'we5927-local-recovery-audit.v1' -or $audit.flash_authorized -ne $false){
  throw 'STOP=INVALID_BACKUP_REPORT'
}
$expectedSha='b2acbf1e762e310d467cfcbae853257a9f63ce311511134bc9d0d5953f835330'
$expectedSize=196608
$backupPaths=@{}
foreach($generation in @('NOV23','NOV25')){
  $r=@($audit.partition_results | Where-Object {$_.Backup -eq $generation -and $_.Partition -eq 'mtd0'})
  $dir=@($audit.backups | Where-Object {$_.Label -eq $generation})
  if($r.Count -ne 1 -or $dir.Count -ne 1){throw ('STOP=MTD0_REPORT_MISSING_OR_AMBIGUOUS_{0}' -f $generation)}
  $record=$r[0]
  if($record.ExpectedBytes -ne $expectedSize -or $record.Bytes -ne $expectedSize -or
     [string]$record.Sha256 -ne $expectedSha){throw ('STOP=MTD0_SOURCE_SHA_OR_SIZE_MISMATCH_{0}' -f $generation)}
  if($generation -eq 'NOV23' -and $record.Status -ne 'HISTORICAL_SHA_PASS'){
    throw 'STOP=NOV23_MTD0_REFERENCE_UNVERIFIED'
  }
  if($generation -eq 'NOV25' -and $record.Status -ne 'SIZE_PASS_HASH_RECORDED_NOT_ROUTER_MATCHED'){
    throw 'STOP=NOV25_MTD0_REFERENCE_UNVERIFIED'
  }
  if([string]::IsNullOrWhiteSpace([string]$record.File)){throw 'STOP=MTD0_FILENAME_MISSING'}
  $candidates=@(Get-ChildItem -LiteralPath $dir[0].Folder -Recurse -File -ErrorAction Stop |
    Where-Object {$_.Name -eq $record.File})
  if($candidates.Count -ne 1 -or $candidates[0].Length -ne $expectedSize){
    throw ('STOP=MTD0_BINARY_MISSING_OR_AMBIGUOUS_{0}' -f $generation)
  }
  $f=$candidates[0].FullName
  if((Get-FileHash -LiteralPath $f -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expectedSha){
    throw ('STOP=MTD0_BINARY_SHA_MISMATCH_{0}' -f $generation)
  }
  $backupPaths[$generation]=$f
}
Write-Output 'EXACT_MTD0_NOV23_AND_NOV25_SHA256=PASS'
Write-Output 'MODE=LOCAL_ONLY; ROUTER_ACCESS=NONE; FLASH=NO; REBOOT=NO'

$markers=@(
  [pscustomobject]@{ID='UBOOT_SIGNATURE';Needle='U-Boot'}
  [pscustomobject]@{ID='HTTP_SERVER_START';Needle='HTTP server is starting for update'}
  [pscustomobject]@{ID='HTTP_SERVER_READY';Needle='HTTP server is ready'}
  [pscustomobject]@{ID='WEB_FAILSAFE_MENU';Needle='Entr Web failsafe mode'}
  [pscustomobject]@{ID='RESET_UPDATE_MODE';Needle='If you press the RESET button will automatically enter the Update mode'}
  [pscustomobject]@{ID='HTTP_FIRMWARE_FORM';Needle='name="firmware"'}
  [pscustomobject]@{ID='MT76X8_UPDATE_PAGE';Needle='Update for MT76x8'}
  [pscustomobject]@{ID='UPLOAD_TRIGGERS_UPGRADE';Needle='HTTP upload is done! Upgrading'}
  [pscustomobject]@{ID='TFTP_COMMAND';Needle='tftpboot'}
)
$reference=$null
$findings=@()
foreach($generation in @('NOV23','NOV25')){
  $data=[System.IO.File]::ReadAllBytes($backupPaths[$generation])
  if($data.Length -ne $expectedSize){throw 'STOP=MTD0_BINARY_LENGTH_CHANGED'}
  $positions=@{}
  foreach($marker in $markers){
    $offset=Find-AsciiMarker -Bytes $data -Needle $marker.Needle
    $positions[$marker.ID]=[int]$offset
    $state=if($offset -ge 0){'FOUND'}else{'NOT_FOUND'}
    Write-Output ('{0}_{1}={2}' -f $generation,$marker.ID,$state)
    $findings+=([pscustomobject]@{Backup=$generation;Marker=$marker.ID;Status=$state;Offset=$offset})
  }
  if($null -eq $reference){$reference=$positions}
  else {
    foreach($marker in $markers){
      if($reference[$marker.ID] -ne $positions[$marker.ID]){
        throw ('STOP=MARKER_OFFSETS_DIFFER_DESPITE_MTD0_IDENTICAL_SHA_{0}' -f $marker.ID)
      }
    }
  }
}
$found=@($findings | Where-Object {$_.Backup -eq 'NOV23' -and $_.Status -eq 'FOUND'}).Count
$total=$markers.Count
Write-Output ('WEB_FAILSAFE_STATIC_MARKERS={0}_OF_{1}_FOUND' -f $found,$total)
if($reference['UPLOAD_TRIGGERS_UPGRADE'] -ge 0){
  Write-Output 'DANGER=HTTP_FIRMWARE_UPLOAD_MAY_TRIGGER_IMMEDIATE_FLASH'
}
Write-Output 'BOOTLOADER_RESCUE_FORMAT=NOT_VERIFIED'
Write-Output 'PHYSICAL_RECOVERY_ENTRY=NOT_TESTED'
Write-Output 'UPLOAD_ACCEPTANCE=NOT_TESTED'
Write-Output 'NO_FIRMWARE_UPLOAD_PERFORMED=YES'

$out=Join-Path (Split-Path -Parent $AuditJson) ('WE5927-UBOOT-WEBFAILSAFE-OFFLINE-AUDIT-'+(Get-Date -Format 'yyyyMMdd_HHmmss')+'.json')
if(Test-Path -LiteralPath $out){throw 'STOP=OUTPUT_ALREADY_EXISTS'}
[pscustomobject]@{
  schema='we5927-uboot-webfailsafe-offline-markers.v1'
  source_backup_json=$AuditJson
  owner_historical_mtd0_sha256=$expectedSha
  both_backups_sha256_verified=$true
  bytes_scanned=$expectedSize
  marker_count=$total
  marker_found=$found
  marker_receipts=$findings
  firmware_upload_warning='HTTP firmware upload may immediately flash; never test by uploading'
  code_strings_are_not_runtime_capability=$true
  image_format_accepted_by_bootloader='NOT_VERIFIED'
  web_failsafe_reached_physically='NOT_TESTED'
  firmware_uploaded=$false
  current_router_modified=$false
  flash_authorized=$false
} | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $out -Encoding UTF8
Write-Output ('OFFLINE_BOOTLOADER_AUDIT_REPORT={0}' -f $out)
Write-Output 'UBOOT_OFFLINE_AUDIT_COMPLETE=YES; FLASH_AUTHORIZED=NO; ROUTER_NOT_CONTACTED=YES'
