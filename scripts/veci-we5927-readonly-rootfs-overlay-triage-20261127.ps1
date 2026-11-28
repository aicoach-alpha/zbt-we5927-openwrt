# Exact ZBT WE5927 MTD3 immutable-prefix/overlay triage.
# READ ONLY: sends SHA calculations, never writes flash, reloads, reboots, flashes or changes UCI.
# Not a recovery demonstration; live MTD reads may temporarily consume CPU/I/O.
[CmdletBinding()]
param([string]$AuditJson='D:\Report_CCB\WE5927-RECOVERY-AUDIT-20261127_115107.json')
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'

function Get-SegmentSha256([string]$Path, [long]$Offset, [long]$Count) {
  $stream=[System.IO.File]::Open($Path,[System.IO.FileMode]::Open,[System.IO.FileAccess]::Read,[System.IO.FileShare]::ReadWrite)
  $hash=[System.Security.Cryptography.SHA256]::Create()
  try {
    if($Offset -lt 0 -or $Count -le 0 -or ($Offset+$Count) -gt $stream.Length) {throw 'STOP=SEGMENT_OUT_OF_RANGE'}
    $stream.Position=$Offset
    $buffer=New-Object 'byte[]' 65536
    $remaining=$Count
    while($remaining -gt 0) {
      $request=[int][Math]::Min([long]$buffer.Length,$remaining)
      $got=$stream.Read($buffer,0,$request)
      if($got -le 0) {throw 'STOP=UNEXPECTED_EOF'}
      [void]$hash.TransformBlock($buffer,0,$got,$buffer,0)
      $remaining-=$got
    }
    [void]$hash.TransformFinalBlock([byte[]]@(),0,0)
    return (-join @($hash.Hash | ForEach-Object { $_.ToString('x2') }))
  } finally {
    $hash.Dispose()
    $stream.Dispose()
  }
}

if(!(Test-Path -LiteralPath $AuditJson -PathType Leaf)) {throw 'STOP=AUDIT_JSON_MISSING'}
$audit=Get-Content -LiteralPath $AuditJson -Raw | ConvertFrom-Json
if($audit.schema -ne 'we5927-local-recovery-audit.v1' -or $audit.flash_authorized -ne $false) {throw 'STOP=AUDIT_SCHEMA_OR_PERMISSION'}
$archives=@{}
foreach($date in @('NOV23','NOV25')) {
  $entry=@($audit.partition_results | Where-Object {$_.Backup -eq $date -and $_.Partition -eq 'mtd3'})
  $folder=@($audit.backups | Where-Object {$_.Label -eq $date})
  if($entry.Count -ne 1 -or $folder.Count -ne 1) {throw "STOP=REFERENCE_AMBIGUOUS_$date"}
  $e=$entry[0]
  if($e.Sha256 -notmatch '^[a-fA-F0-9]{64}$' -or [long]$e.Bytes -ne 7995392 -or $e.ExpectedBytes -ne 7995392) {throw "STOP=UNSAFE_ARCHIVE_$date"}
  $files=@(Get-ChildItem -LiteralPath $folder[0].Folder -Recurse -File -ErrorAction Stop | Where-Object {$_.Name -eq $e.File})
  if($files.Count -ne 1 -or $files[0].Length -ne 7995392) {throw "STOP=ARCHIVE_FILE_MISSING_OR_AMBIGUOUS_$date"}
  $f=$files[0].FullName
  if((Get-FileHash -LiteralPath $f -Algorithm SHA256).Hash.ToLowerInvariant() -ne $e.Sha256.ToLowerInvariant()) {throw "STOP=ARCHIVE_SHA256_CHANGED_$date"}
  $archives[$date]=$f
}
if(!(Get-Command ssh.exe -ErrorAction SilentlyContinue)) {throw 'STOP=NO_SSH_EXE'}
$sshArgs=@('-o','HostKeyAlgorithms=+ssh-rsa','-o','StrictHostKeyChecking=yes',
  '-o','ConnectTimeout=8','-o','ConnectionAttempts=1','-T','root@192.168.1.1','/bin/sh -s')
$script = @'
set -eu
[ "$(cat /tmp/sysinfo/board_name 2>/dev/null)" = "zbtlink,zbt-we5927" ] || { echo STOP=BOARD_MISMATCH >&2; exit 3; }
for cmd in awk dd sha256sum; do command -v "$cmd" >/dev/null || { echo "STOP=MISSING_TOOL_$cmd" >&2; exit 3; }; done
h3="$(awk '$1=="mtd3:" && $4=="\"firmware\"" {print $2}' /proc/mtd)"
h4="$(awk '$1=="mtd4:" && $4=="\"kernel\"" {print $2}' /proc/mtd)"
h5="$(awk '$1=="mtd5:" && $4=="\"rootfs\"" {print $2}' /proc/mtd)"
h6="$(awk '$1=="mtd6:" && $4=="\"rootfs_data\"" {print $2}' /proc/mtd)"
for hex in "$h3" "$h4" "$h5" "$h6"; do
  case "$hex" in ""|*[!0123456789abcdefABCDEF]*) echo STOP=PARTITION_LAYOUT_NOT_SUPPORTED >&2; exit 3;; esac
done
s3=$((0x$h3)); s4=$((0x$h4)); s5=$((0x$h5)); s6=$((0x$h6))
[ "$s3" -eq 7995392 ] && [ "$s4" -gt 0 ] && [ "$s5" -gt "$s6" ] && [ "$s6" -gt 0 ] || { echo STOP=PARTITION_SIZE_MISMATCH >&2; exit 3; }
[ $((s4+s5)) -eq "$s3" ] || { echo STOP=PARENT_LAYOUT_MISMATCH >&2; exit 3; }
base=$((s3-s6))
[ "$base" -gt "$s4" ] && [ $((base%65536)) -eq 0 ] && [ $((s6%65536)) -eq 0 ] || { echo STOP=UNALIGNED_ROOTFS_DATA >&2; exit 3; }
[ -r /dev/mtd3 ] && [ -r /dev/mtd4 ] && [ -r /dev/mtd5 ] && [ -r /dev/mtd6 ] || { echo STOP=MTD_NOT_READABLE >&2; exit 3; }
echo "LIVE_MTD3_BYTES=$s3"
echo "LIVE_MTD4_KERNEL_BYTES=$s4"
echo "LIVE_MTD5_ROOTFS_BYTES=$s5"
echo "LIVE_MTD6_OVERLAY_BYTES=$s6"
echo "LIVE_PRE_OVERLAY_PREFIX_BYTES=$base"
hkernel="$(sha256sum /dev/mtd4)" || exit 3
set -- $hkernel
echo "LIVE_MTD4_KERNEL_SHA256=$1"
hoverlay="$(sha256sum /dev/mtd6)" || exit 3
set -- $hoverlay
echo "LIVE_MTD6_OVERLAY_SHA256=$1"
prefix_blocks=$((base/65536))
overlay_blocks=$((s6/65536))
# sha256sum succeeds even if its upstream reader failed or stopped early.
# Send data directly to the hasher, capturing only dd's short status text.
set -o pipefail
read_blocks() {
  skip=$1
  blocks=$2
  stats=$(LC_ALL=C dd if=/dev/mtd3 bs=65536 skip="$skip" count="$blocks" 2>&1 >&3) || return 1
  case "
$stats
" in
    *"
$blocks+0 records out
"*) return 0 ;;
    *) return 1 ;;
  esac
}
prefix="$(read_blocks 0 "$prefix_blocks" 3>&1 | sha256sum)" || { echo STOP=INCOMPLETE_PARENT_PREFIX >&2; exit 3; }
set -- $prefix
echo "LIVE_MTD3_PRE_OVERLAY_SHA256=$1"
tailhash="$(read_blocks "$prefix_blocks" "$overlay_blocks" 3>&1 | sha256sum)" || { echo STOP=INCOMPLETE_PARENT_TAIL >&2; exit 3; }
set -- $tailhash
echo "LIVE_MTD3_TAIL_SHA256=$1"
echo "ROOTFS_OVERLAY_LAYOUT_HASHES_READ_ONLY_DONE=YES"
'@
# Windows native stdin EOF handling: end with explicit POSIX exit status.
$payload=$script + [char]10 + 'exit $?' + [char]10
Write-Output 'TRIAGE_MODE=READ_ONLY; NO_FLASH; NO_REBOOT; NO_NETWORK_RELOAD'
$lines=@($payload | & ssh.exe @sshArgs)
if($LASTEXITCODE -ne 0) {throw "STOP=ROUTER_READ_ONLY_PROBE_EXIT_$LASTEXITCODE"}
$values=@{}
foreach($line in $lines) {
  if(([string]$line) -match '^(LIVE_[A-Z0-9_]+)=([a-fA-F0-9]+)$') {
    if($values.ContainsKey($Matches[1])) {throw 'STOP=DUPLICATE_ROUTER_FIELD'}
    $values[$Matches[1]]=$Matches[2].ToLowerInvariant()
  }
}
$required=@('LIVE_MTD3_BYTES','LIVE_MTD4_KERNEL_BYTES','LIVE_MTD5_ROOTFS_BYTES','LIVE_MTD6_OVERLAY_BYTES',
  'LIVE_PRE_OVERLAY_PREFIX_BYTES','LIVE_MTD4_KERNEL_SHA256','LIVE_MTD6_OVERLAY_SHA256',
  'LIVE_MTD3_PRE_OVERLAY_SHA256','LIVE_MTD3_TAIL_SHA256')
foreach($key in $required) {if(!$values.ContainsKey($key)) {throw "STOP=MISSING_ROUTER_FIELD_$key"}}
if($lines -notcontains 'ROOTFS_OVERLAY_LAYOUT_HASHES_READ_ONLY_DONE=YES') {throw 'STOP=INCOMPLETE_REMOTE_OUTPUT'}
foreach($key in @('LIVE_MTD4_KERNEL_SHA256','LIVE_MTD6_OVERLAY_SHA256','LIVE_MTD3_PRE_OVERLAY_SHA256','LIVE_MTD3_TAIL_SHA256')){
  if($values[$key] -notmatch '^[0-9a-f]{64}$') {throw "STOP=INVALID_ROUTER_HASH_$key"}
}
$s3=[long]$values['LIVE_MTD3_BYTES']; $s4=[long]$values['LIVE_MTD4_KERNEL_BYTES']
$s5=[long]$values['LIVE_MTD5_ROOTFS_BYTES']; $s6=[long]$values['LIVE_MTD6_OVERLAY_BYTES']
$base=[long]$values['LIVE_PRE_OVERLAY_PREFIX_BYTES']
if($s3 -ne 7995392 -or $s4+$s5 -ne $s3 -or $s3-$s6 -ne $base -or $base -le $s4 -or $base%65536 -ne 0) {throw 'STOP=REMOTE_LAYOUT_INCONSISTENT'}
$alias=$values['LIVE_MTD6_OVERLAY_SHA256'] -eq $values['LIVE_MTD3_TAIL_SHA256']
Write-Output ("ROOTFS_DATA_IS_PARENT_TAIL={0}" -f $(if($alias){'HASH_MATCH'}else{'NOT_VERIFIED'}))
$comparisons=New-Object 'System.Collections.Generic.List[object]'
foreach($date in @('NOV23','NOV25')) {
  $f=$archives[$date]
  $hkernel=Get-SegmentSha256 -Path $f -Offset 0 -Count $s4
  $hprefix=Get-SegmentSha256 -Path $f -Offset 0 -Count $base
  $htail=Get-SegmentSha256 -Path $f -Offset $base -Count $s6
  $kernelMatch=$hkernel -eq $values['LIVE_MTD4_KERNEL_SHA256']
  $prefixMatch=$hprefix -eq $values['LIVE_MTD3_PRE_OVERLAY_SHA256']
  $tailMatch=$htail -eq $values['LIVE_MTD3_TAIL_SHA256']
  if($alias) {
    $kernelState=if($kernelMatch){'MATCH'}else{'DIFFERENT'}
    $prefixState=if($prefixMatch){'MATCH'}else{'DIFFERENT'}
  } else {
    $kernelState='NOT_VERIFIED_LAYOUT_ALIAS'
    $prefixState='NOT_VERIFIED_LAYOUT_ALIAS'
  }
  Write-Output ("{0}_KERNEL_VS_CURRENT={1}" -f $date,$kernelState)
  Write-Output ("{0}_PRE_OVERLAY_VS_CURRENT={1}" -f $date,$prefixState)
  Write-Output ("{0}_OVERLAY_TAIL_VS_CURRENT={1}" -f $date,$(if($alias){if($tailMatch){'MATCH'}else{'DIFFERENT'}}else{'NOT_VERIFIED_LAYOUT_ALIAS'}))
  $comparisons.Add([pscustomobject]@{
    Backup=$date; KernelCompare=$kernelState; PreOverlayCompare=$prefixState
    TailCompare=$(if($alias){if($tailMatch){'MATCH'}else{'DIFFERENT'}}else{'NOT_VERIFIED_LAYOUT_ALIAS'})
  })
}
$report=[pscustomobject]@{
  schema='veci-we5927-rootfs-overlay-readonly-triage.v1'
  source_audit_json=$AuditJson; target_router='192.168.1.1'
  parent_firmware_size=$s3; kernel_size=$s4; rootfs_size=$s5
  overlay_size=$s6; pre_overlay_bytes=$base
  overlay_parent_tail_hash_match=$alias
  source_backups=$comparisons.ToArray()
  non_atomic_live_read_warning='Concurrent overlay writes could change hashes during this check'
  bootloader_restore_test='NOT_RUN'
  current_installation_changed=$false
  flash_authorized=$false
}
$out=Join-Path (Split-Path -Parent $AuditJson) ('WE5927-ROOTFS-OVERLAY-TRIAGE-'+(Get-Date -Format 'yyyyMMdd_HHmmss')+'.json')
if(Test-Path -LiteralPath $out) {throw 'STOP=OUTPUT_EXISTS'}
$report | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $out -Encoding UTF8
Write-Output ("TRIAGE_REPORT={0}" -f $out)
Write-Output 'ROOTFS_OVERLAY_TRIAGE_COMPLETE=YES; FLASH_AUTHORIZED=NO; ROUTER_NOT_MODIFIED=YES'
