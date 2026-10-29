# VeCI General Core r5 + optional installed Guest/Voucher hotfix

**Operator action only.** Paste one complete command into PowerShell on the Windows office laptop connected to the WE5927. No access or deployment from andre-nas.

## Install/update with one command

    $ErrorActionPreference='Stop'; $u='https://raw.githubusercontent.com/aicoach-alpha/zbt-we5927-openwrt/feat/veci-default-ui/scripts/veci-oneclick-r5-update.ps1'; $p=Join-Path $env:TEMP ('veci-r5-'+[guid]::NewGuid().ToString('N')+'.ps1'); Invoke-WebRequest -UseBasicParsing -Uri $u -OutFile $p; powershell.exe -NoProfile -ExecutionPolicy Bypass -File $p

The script detects the router gateway or asks for the IP; validates ZBT WE5927 and OpenWrt target; downloads/checks the archive SHA256; checks that VeCI HTTP is reachable; stages files in router RAM; backs up the old frontend/RPC and installed Guest/Voucher files to Documents/VeCI-backups on the **laptop**; then requests confirmation (type UPDATE). After copying, it restarts rpcd, verifies uBus and HTTP/commit marker, and attempts rollback on failure.

**Updated components:** VeCI Core r5, frontend, rpcd provider and ACL. The already-installed Guest and Voucher app JS/RPC files are updated conditionally. Neither package nor kernel is installed if missing. The official signed package feed still requires its exact kernel ABI and is not replaced here. No firmware image flashing, Linux kernel, modem, IP, WLAN, DNS, DHCP, uHTTPd listeners, or HTTPS redirect changes.

## Manual rollback (complete one-line command)

    $ErrorActionPreference='Stop'; $u='https://raw.githubusercontent.com/aicoach-alpha/zbt-we5927-openwrt/feat/veci-default-ui/scripts/veci-oneclick-r5-update.ps1'; $p=Join-Path $env:TEMP ('veci-r5-rollback-'+[guid]::NewGuid().ToString('N')+'.ps1'); Invoke-WebRequest -UseBasicParsing -Uri $u -OutFile $p; powershell.exe -NoProfile -ExecutionPolicy Bypass -File $p -Rollback

Rollback restores the latest backup for the router IP from the laptop. The last known good Core r4 backup remains separate if available. Verify Internet, HTTP, LuCI and cellular after update/rollback.

## Source/validation

- Core r5 SHA: e2d450a32bdf5d968511da7f9703e5086a76720c.
- Firmware source pin: source/veci.commit.
- Tarball: releases/veci-core-r5-hotfix/veci-core-r5.tar.gz.
- Expected archive SHA256: a5c16d2607a86c2ed51f1e14c221f4135d3218cd6e679b307ff5cb7241a41ef5.
- The tarball is a **hotfix for files on an existing compatible router**, not an OpenWrt firmware image or an APK signed release.

Uninstalled Guest/Voucher apps are intentionally skipped. The batch voucher feature appears only when Voucher returns batch_supported=true. Any missing provider, SSH failure, board mismatch, checksum mismatch or router storage shortage aborts without flashing.

**Hardware validation is still required** for Guest portal behavior, uspot authentication, client isolation, live vouchers, LTE, and recovery. Source PASS does not imply firmware UAT PASS. OpenWrt sysupgrade and new optional-app package installation remain separate owner-authorized manual operations.
