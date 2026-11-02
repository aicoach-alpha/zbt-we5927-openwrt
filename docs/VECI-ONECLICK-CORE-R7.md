# VeCI General Core r7 overlay diagnostics update

The physical WE5927 is currently at r6 with HTTP verified. Overlay free 1116 KiB, running OpenWrt 25.12.5 kernel 6.12.94, signed feed absent. **This update does not install Guest/Voucher or change the router network.**

Core r7 adds bounded overlay/memory diagnostic fields to the *base* RPC catalog so the Router Apps page can explain the storage restriction even when the optional veci.apps provider is absent. The update preserves the r6 safe signed-feed install guard.

## Update — one complete Windows laptop PowerShell line

    $ErrorActionPreference='Stop'; $u='https://raw.githubusercontent.com/aicoach-alpha/zbt-we5927-openwrt/feat/veci-default-ui/scripts/veci-oneclick-r7-update.ps1'; $p=Join-Path $env:TEMP ('veci-r7-'+[guid]::NewGuid().ToString('N')+'.ps1'); Invoke-WebRequest -UseBasicParsing -Uri $u -OutFile $p; powershell.exe -NoProfile -ExecutionPolicy Bypass -File $p

## Rollback — one complete Windows laptop PowerShell line

    $ErrorActionPreference='Stop'; $u='https://raw.githubusercontent.com/aicoach-alpha/zbt-we5927-openwrt/feat/veci-default-ui/scripts/veci-oneclick-r7-update.ps1'; $p=Join-Path $env:TEMP ('veci-r7-rollback-'+[guid]::NewGuid().ToString('N')+'.ps1'); Invoke-WebRequest -UseBasicParsing -Uri $u -OutFile $p; powershell.exe -NoProfile -ExecutionPolicy Bypass -File $p -Rollback

- Core pin: 185249af9ba217f2bedf4f554104e6fe3e321a45.
- Bundle SHA256: 8818022eb6a03e5de03c642c5b079403a830f14cad2f8c9535bedec2221e16af.
- Executable installer SHA256: 8b6036cbcef17ab4d5514de9ccbc8f44237065f915e56c47e80144053c4e876c.
- Both files verified before staging on the WE5927.
- Prior Core r6 backups remain available on the office laptop.

This file-only Core hot-update is not a firmware sysupgrade, does not add APK packages, does not change uhttpd/LTE or overlay layout. If the router free overlay falls below 1024 KiB, installer refuses to proceed. Actual hardware update status remains pending until operator-run logs show SUCCESS.
