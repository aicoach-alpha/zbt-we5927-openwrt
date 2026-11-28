# Physical router MTD SHA256 comparison — READ ONLY. No dumping, writing or flashing.
# Running this script actively reads flash partitions (8.6MB total); it changes no settings.
[CmdletBinding()]
param(
  [string]$AuditJson = 'D:\Report_CCB\WE5927-RECOVERY-AUDIT-20261127_115107.json'
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $AuditJson -PathType Leaf)) { throw 'STOP=LOCAL_AUDIT_JSON_NOT_FOUND' }
$audit = Get-Content -LiteralPath $AuditJson -Raw | ConvertFrom-Json
if ($audit.schema -ne 'we5927-local-recovery-audit.v1' -or $audit.flash_authorized -ne $false) {
  throw 'STOP=INVALID_OR_UNSAFE_AUDIT_JSON'
}
$ids = @('mtd0','mtd1','mtd2','mtd3','mtd7')
$ref = @{}
foreach ($id in $ids) {
  foreach ($date in @('NOV23','NOV25')) {
    $matches = @($audit.partition_results | Where-Object { $_.Backup -eq $date -and $_.Partition -eq $id })
    if ($matches.Count -ne 1) { throw ('STOP=REFERENCE_MISSING_OR_AMBIGUOUS_{0}_{1}' -f $date,$id) }
    $entry = $matches[0]
    if ($entry.Sha256 -notmatch '^[a-fA-F0-9]{64}$' -or $entry.Bytes -ne $entry.ExpectedBytes) {
      throw ('STOP=REFERENCE_INTEGRITY_FAILED_{0}_{1}' -f $date,$id)
    }
    if ($date -eq 'NOV23' -and $entry.Status -ne 'HISTORICAL_SHA_PASS') {
      throw ('STOP=NOV23_REFERENCE_NOT_VERIFIED_{0}' -f $id)
    }
    if ($date -eq 'NOV25' -and $entry.Status -ne 'SIZE_PASS_HASH_RECORDED_NOT_ROUTER_MATCHED') {
      throw ('STOP=NOV25_REFERENCE_NOT_VERIFIED_{0}' -f $id)
    }
    $ref[("$date/$id")] = $entry.Sha256.ToLowerInvariant()
  }
}
if (-not (Get-Command ssh.exe -ErrorAction SilentlyContinue)) { throw 'STOP=SSH_EXE_MISSING' }
$sshArgs = @('-o','HostKeyAlgorithms=+ssh-rsa','-o','StrictHostKeyChecking=yes',
             '-o','ConnectTimeout=8','-o','ConnectionAttempts=1','-T',
             'root@192.168.1.1','/bin/sh -s')
$script = @'
set -eu
[ "$(cat /tmp/sysinfo/board_name 2>/dev/null)" = zbtlink,zbt-we5927 ] || { echo STOP=BOARD_MISMATCH >&2; exit 3; }
grep -Eq '^mtd0:[[:space:]]+00030000[[:space:]]+00010000[[:space:]]+"u-boot"$' /proc/mtd || exit 3
grep -Eq '^mtd1:[[:space:]]+00010000[[:space:]]+00010000[[:space:]]+"u-boot-env"$' /proc/mtd || exit 3
grep -Eq '^mtd2:[[:space:]]+00010000[[:space:]]+00010000[[:space:]]+"factory"$' /proc/mtd || exit 3
grep -Eq '^mtd3:[[:space:]]+007a0000[[:space:]]+00010000[[:space:]]+"firmware"$' /proc/mtd || exit 3
grep -Eq '^mtd7:[[:space:]]+00010000[[:space:]]+00010000[[:space:]]+"art"$' /proc/mtd || exit 3
for n in 0 1 2 3 7; do
  [ -r "/dev/mtd$n" ] || { echo "STOP=MTD_NOT_READABLE_$n" >&2; exit 3; }
  result="$(sha256sum "/dev/mtd$n")" || { echo "STOP=MTD_HASH_FAILED_$n" >&2; exit 3; }
  set -- $result
  printf 'LIVE_MTD%s_SHA256=%s\n' "$n" "$1"
done
echo LIVE_MTD_HASHES_READ_ONLY_COMPLETE=YES
'@
# Explicitly terminate native stdin to preserve remote shell exit status.
$payload = $script + [char]10 + 'exit $?' + [char]10
Write-Output 'ROUTER_AUDIT=READ_ONLY; TARGET=192.168.1.1; HASH_PARTITIONS=mtd0,mtd1,mtd2,mtd3,mtd7'
$remote = @($payload | & ssh.exe @sshArgs)
if ($LASTEXITCODE -ne 0) { throw ("STOP=SSH_OR_ROUTER_HASH_FAILED_{0}" -f $LASTEXITCODE) }
$live = @{}
foreach ($line in $remote) {
  $line = [string]$line
  if ($line -match '^LIVE_MTD([01237])_SHA256=([a-fA-F0-9]{64})$') {
    $id = 'mtd' + $Matches[1]
    if ($live.ContainsKey($id)) { throw ("STOP=DUPLICATE_HASH_{0}" -f $id) }
    $live[$id] = $Matches[2].ToLowerInvariant()
  }
}
if ($live.Count -ne 5 -or -not ($remote -contains 'LIVE_MTD_HASHES_READ_ONLY_COMPLETE=YES')) {
  throw 'STOP=INCOMPLETE_ROUTER_HASH_RECEIPT'
}
$rows = New-Object 'System.Collections.Generic.List[object]'
foreach ($id in $ids) {
  $h = $live[$id]
  $same23 = $h -eq $ref[("NOV23/$id")]
  $same25 = $h -eq $ref[("NOV25/$id")]
  $match = if ($same23 -and $same25) { 'MATCH_BOTH' }
           elseif ($same25) { 'MATCH_NOV25' }
           elseif ($same23) { 'MATCH_NOV23' }
           else { 'MATCH_NEITHER' }
  Write-Output ("{0}_CURRENT_VS_BACKUPS={1}" -f $id.ToUpperInvariant(),$match)
  $rows.Add([pscustomobject]@{
    Partition=$id; Comparison=$match; MatchesNov23=$same23; MatchesNov25=$same25
    LiveSha256=$h
  })
}
$out = Join-Path (Split-Path -Parent $AuditJson) ('WE5927-LIVE-MTD-HASH-COMPARISON-' + (Get-Date -Format 'yyyyMMdd_HHmmss') + '.json')
if (Test-Path -LiteralPath $out) { throw 'STOP=OUTPUT_EXISTS' }
[pscustomobject]@{
  schema='we5927-live-mtd-readonly-hash-compare.v1'
  source_audit_file=$AuditJson
  router='192.168.1.1'
  read_only=$true
  partitions=$rows.ToArray()
  bootloader_recovery_test='NOT_RUN'
  image_restore_format='NOT_VERIFIED'
  firmware_flash_authorized=$false
} | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $out -Encoding UTF8
Write-Output ("COMPARISON_REPORT={0}" -f $out)
Write-Output 'LIVE_HASH_COMPARISON_COMPLETE=YES; ROUTER_NOT_MODIFIED=YES; FLASH_AUTHORIZED=NO'
