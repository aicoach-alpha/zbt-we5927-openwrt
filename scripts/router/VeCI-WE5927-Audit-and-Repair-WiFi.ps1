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
$GitHubRaw = 'https://raw.githubusercontent.com/aicoach-alpha/zbt-we5927-openwrt/d123dc4b30b4650f07e79ced40d888fd55d8aa35/scripts/router'
$Scripts = @(
    @{
      Name='veci-live-router-audit.sh';
      Sha256='98fcb277fc59ca6cc7376499c4b6d19924930e841f8dade48d177f380f54c540'
    },
    @{
      Name='veci-live-wifi-guarded-repair.sh';
      Sha256='9d51c6de7569d18ed9113306f6bbcdb9599de7aeb0d8feb540a8ecc1efc7ca34'
    }
)
$TimeTag = Get-Date -Format 'yyyyMMdd-HHmmss'
$WorkDir = Join-Path $env:TEMP "VeCI-router-WiFi-$TimeTag"
$ReportDir = Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'VeCI-Router-Audits'
New-Item -Path $WorkDir,$ReportDir -ItemType Directory -Force | Out-Null
$Report = Join-Path $ReportDir "WE5927-physical-audit-$TimeTag.txt"
Write-Host 'VeCI WE5927 — audit total router, Wi-Fi guard, no flash/reboot'
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
  $Text | & ssh.exe -o 'HostKeyAlgorithms=+ssh-rsa' -o 'StrictHostKeyChecking=yes' -o 'ConnectTimeout=8' -T "root@$Router" '/bin/sh -s' 2>&1 | ForEach-Object {
    $Line = [string]$_
    if ($Line.StartsWith('NEW_WIFI_PASSWORD_PRIVATE_DO_NOT_SHARE=')) {
      Write-Host $Line -ForegroundColor Yellow
      Add-Content -LiteralPath $Report -Value 'NEW_WIFI_PASSWORD_PRIVATE_DO_NOT_SHARE=[REDACTED]' -Encoding UTF8
    } else {
      Write-Host $Line
      Add-Content -LiteralPath $Report -Value $Line -Encoding UTF8
    }
  }
  $ExitCode = $LASTEXITCODE
  if ($ExitCode -ne 0) {
    throw "$Label gagal (exit $ExitCode). Router tidak dinyatakan PASS. Buka laporan: $Report"
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
