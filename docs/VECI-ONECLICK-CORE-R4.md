# VeCI Core r4 — download and update from the office laptop in one PowerShell command

Use from the OFFICE Windows 11 laptop connected to WE5927. No connection from andre-nas is involved.

## One-line download and run

Paste this single line into PowerShell:

    $ErrorActionPreference='Stop'; $u='https://raw.githubusercontent.com/aicoach-alpha/zbt-we5927-openwrt/feat/veci-default-ui/scripts/veci-oneclick-update.ps1'; $p=Join-Path $env:TEMP ('veci-'+[guid]::NewGuid().ToString('N')+'.ps1'); Invoke-WebRequest -UseBasicParsing -Uri $u -OutFile $p; powershell.exe -NoProfile -ExecutionPolicy Bypass -File $p

The script will detect the laptop's default gateway and let you confirm or enter the real router IP. It downloads the Core r4 bundle and installer over HTTPS; verifies the archive against a hard-coded SHA256; verifies zbtlink,zbt-we5927 and ramips/mt76x8 via router SSH; confirms HTTP access; stages in RAM; checks available space; saves a router backup onto the laptop; and asks you to type UPDATE before applying.

This DOES update the running VeCI web frontend + rpcd backend + ACL on the router. It does NOT flash OpenWrt, install Guest/Voucher/SQM APKs, replace the kernel, alter modem or LTE settings, or force HTTPS. Updating optional apps and firmware still requires a separately built and verified signed exact-ABI image/feed.

Expected Core SHA: 81853a6b8b710a26a2427d1176751bf781bc7243

Expected archive SHA256 (checked by PowerShell and the router): 425b22c09d5ba4d41077f3664c84f314d223d46eefa64c82f77a79c64e0c308c

The archive is releases/veci-core-r4-hotfix/veci-core-r4.tar.gz and contains only web files, rpcd shell backend and RPC ACL. It preserves installed configuration, package database, HTTP listeners, Wi-Fi, LAN, LTE, DNS and router firmware. The boot image remains unchanged. This is a hotfix on the currently running core, not a flash/release-grade APK upgrade; a later official firmware upgrade may supersede it.

## Requirements

- Windows 11 PowerShell with ssh.exe and scp.exe; root SSH access from the office laptop to the router. Interactive SSH password is supported. Verify any first-time host fingerprint. SCP uses -O for Dropbear-compatible legacy SCP.
- An existing VeCI installation on a genuine WE5927 OpenWrt router; HTTP http://ROUTER/veci/ must work.
- At least 1 MiB free overlay and 4 MiB free temporary RAM space on the router. The script refuses to update if these checks fail.
- If the router is HTTP-only with no SSH access, this installer will safely stop before updating. It does not try guessing passwords or bypassing SSH access.

## Automatic backup and rollback

Every update saves VeCI-backups/ROUTER-IP-YYYYMMDD-HHMMSS-core-backup.tar.gz inside the laptop's Documents folder. The script attempts rollback if installation or post-install HTTP verification fails.

To manually restore the newest saved backup, paste the same one-line download command with -Rollback after the script path:

    $ErrorActionPreference='Stop'; $u='https://raw.githubusercontent.com/aicoach-alpha/zbt-we5927-openwrt/feat/veci-default-ui/scripts/veci-oneclick-update.ps1'; $p=Join-Path $env:TEMP ('veci-'+[guid]::NewGuid().ToString('N')+'.ps1'); Invoke-WebRequest -UseBasicParsing -Uri $u -OutFile $p; powershell.exe -NoProfile -ExecutionPolicy Bypass -File $p -Rollback

Both operations are initiated manually from the laptop. The scripts do not run on schedules and do not update the actual firmware. No physical router deployment can be claimed until this script completes successfully on the laptop.
