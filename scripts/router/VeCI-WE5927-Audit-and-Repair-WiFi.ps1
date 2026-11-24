#Requires -Version 5.1
<#
  VeCI WE5927, signed OpenWrt 25.12.6, one-router physical UAT:
  1. Verify path and previously accepted SSH host key
  2. Download and SHA256-verify pinned, inspectable audit/repair scripts
  3. Run safe read-only router audit, write sanitized report locally
  4. Apply guarded secure Wi-Fi repair on router if eligible (unless -AuditOnly)
  5. Audit again; redact any newly generated Wi-Fi password from saved reports
  SSH / LAN / LTE remain untouched by the repair script.
#>
[CmdletBinding()]
param([switch]$AuditOnly)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$Router = '192.168.1.1'
$ExpectedHostKey = 'SHA256:vTuQFuvd+br7jrfmqqNDN2FZxLtNNRYvOo3bDQ2Zlic'
$GitHubRaw = 'https://raw.githubusercontent.com/aicoach-alpha/zbt-we5927-openwrt/41d14321e6bb1573f3d10ae376c1b3b05da0292f/scripts/router'
$Scripts = @(
    @{
      Name='veci-live-router-audit.sh';
      Sha256='b2ea348a9f2ef4517a06aeeafc3a1e277cc0a9a5b5a7b631b3dd22198c1daa02'
    },
    @{
      Name='veci-live-wifi-guarded-repair.sh';
      Sha256='b6d7b8d302693766b3cc1c983951fe0e0f3fa0303a7ea4446641b8ea238ffb45'
    }
)
$TimeTag = Get-Date -Format 'yyyyMMdd-HHmmss'
$WorkDir = Join-Path $env:TEMP "VeCI-router-WiFi-$TimeTag"
$ReportDir = Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'VeCI-Router-Audits'
New-Item -Path $WorkDir,$ReportDir -ItemType Directory -Force | Out-Null
$Report = Join-Path $ReportDir "WE5927-physical-audit-$TimeTag.txt"
Write-Host 'VeCI WE5927 - audit total router, Wi-Fi guard, no flash/reboot'
Write-Host "File hasil: $Report"
Write-Host 'Memastikan koneksi SSH melalui kabel Ethernet dan identitas host...'
$Link = Test-NetConnection $Router -Port 22 -WarningAction SilentlyContinue
if (-not $Link.TcpTestSucceeded) {
  throw "Router $Router tidak menerima SSH di port 22. Tidak ada perubahan."
}
if ($Link.InterfaceAlias -notmatch '^Ethernet') {
  throw "Akses router bukan melalui adapter Ethernet ($($Link.InterfaceAlias)). Tidak ada perubahan."
}
$KnownHost = (& ssh-keygen.exe -F $Router -l -E sha256 2>$null | Out-String)
if ($KnownHost -notlike "*$ExpectedHostKey*") {
  throw 'Fingerprint SSH router tidak cocok dengan yang sebelumnya diterima. Jangan menerima host key baru tanpa verifikasi. Tidak ada perubahan.'
}
foreach ($Item in $Scripts) {
  $Dst = Join-Path $WorkDir $Item.Name
  Write-Host "Mengambil kode pemeriksaan terverifikasi: $($Item.Name)"
  Invoke-WebRequest -Uri "$GitHubRaw/$($Item.Name)" -UseBasicParsing -OutFile $Dst
  $Actual = (Get-FileHash -Path $Dst -Algorithm SHA256).Hash.ToLowerInvariant()
  if ($Actual -ne $Item.Sha256) {
    throw "Checksum tidak sesuai untuk $($Item.Name). File tidak dijalankan."
  }
}
function Invoke-OnRouter {
  param([Parameter(Mandatory)][string]$Source, [Parameter(Mandatory)][string]$Label)
  Write-Host ''
  Write-Host "===== $Label ====="
  Add-Content -LiteralPath $Report -Value "===== $Label =====" -Encoding UTF8
  $Text = [System.IO.File]::ReadAllText($Source, [System.Text.Encoding]::UTF8)
  # Windows PowerShell 5.1 turns OpenSSH native stderr into ErrorRecord
  # objects. With ErrorActionPreference=Stop it aborts at the first warning
  # even when the remote script has already completed (AUDIT_END=OK).
  # Capture BOTH output streams, then evaluate the actual ssh.exe exit code.
  $SavedPreference = $ErrorActionPreference
  $RemoteLines = @()
  try {
    $ErrorActionPreference = 'Continue'
    # Windows PowerShell 5.1 adds a final CRLF record when a string is piped
    # to a native executable. OpenWrt ash may interpret the trailing CR as
    # a separate command, yielding exit 127 after AUDIT_END=OK.
    # A literal exit statement BEFORE that terminal CR preserves the true
    # previous command status and prevents execution of the stray CR.
    $SafePayload = $Text.TrimEnd([char[]]@([char]10,[char]13)) + [char]10 + 'exit $?' + [char]10
    $RemoteLines = @($SafePayload | & ssh.exe -o 'HostKeyAlgorithms=+ssh-rsa' -o 'StrictHostKeyChecking=yes' -o 'ConnectTimeout=8' -T "root@$Router" '/bin/sh -s' 2>&1)
    $ExitCode = $LASTEXITCODE
  } finally {
    $ErrorActionPreference = $SavedPreference
  }
  $AuditCompleted = $false
  $RepairCompleted = $false
  foreach ($Record in $RemoteLines) {
    if ($Record -is [System.Management.Automation.ErrorRecord]) {
      $Line = [string]$Record.Exception.Message
    } else {
      $Line = [string]$Record
    }
    if ($Line -match '^AUDIT_END=OK\s*$') { $AuditCompleted = $true }
    if ($Line -match '^WIFI_REPAIR_STATUS=AP_STARTED_CONFIGURATION_SAVED\s*$') { $RepairCompleted = $true }
    if ($Line.StartsWith('NEW_WIFI_PASSWORD_PRIVATE_DO_NOT_SHARE=')) {
      Write-Host $Line -ForegroundColor Yellow
      Add-Content -LiteralPath $Report -Value 'NEW_WIFI_PASSWORD_PRIVATE_DO_NOT_SHARE=[REDACTED]' -Encoding UTF8
    } else {
      Write-Host $Line
      Add-Content -LiteralPath $Report -Value $Line -Encoding UTF8
    }
  }
  if ($ExitCode -ne 0) {
    throw "$Label gagal (SSH exit $ExitCode). Laporan menunjukkan pesan error lengkap: $Report"
  }
  if ($Label.StartsWith('AUDIT') -and -not $AuditCompleted) {
    throw "$Label tidak menghasilkan tanda selesai AUDIT_END=OK. Tidak akan lanjut: $Report"
  }
  if ($Label -eq 'WIFI GUARDED REPAIR' -and -not $RepairCompleted) {
    throw "Perbaikan Wi-Fi tidak berhasil terverifikasi. Lihat alasan penolakan/rollback: $Report"
  }
}
$AuditPath = Join-Path $WorkDir 'veci-live-router-audit.sh'
$RepairPath = Join-Path $WorkDir 'veci-live-wifi-guarded-repair.sh'
Invoke-OnRouter -Source $AuditPath -Label 'AUDIT SEBELUM'
if (-not $AuditOnly) {
  Write-Host ''
  Write-Host 'Mulai perbaikan Wi-Fi 2.4 GHz hanya bila lolos seluruh pemeriksaan.'
  Write-Host 'Backup wireless dan watchdog rollback 75 detik tersedia; pemulihan bergantung kernel router masih responsif.'
  Write-Host 'Kata sandi WPA2 baru, bila dibuat, hanya terlihat pada layar dan tidak disimpan dalam laporan.'
  Invoke-OnRouter -Source $RepairPath -Label 'WIFI GUARDED REPAIR'
  Invoke-OnRouter -Source $AuditPath -Label 'AUDIT SESUDAH'
} else {
  Write-Host 'AuditOnly: konfigurasi router tidak diubah.'
}
Write-Host ''
Write-Host "Selesai. Laporan yang aman untuk ditinjau: $Report"
Write-Host 'Jika Wi-Fi AP aktif, verifikasi SSID terlihat dari ponsel dan internet klien berfungsi.'
