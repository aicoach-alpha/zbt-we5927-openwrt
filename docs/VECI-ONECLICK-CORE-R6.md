# VeCI General Core r6 — one-command upgrade from office laptop

This update improves Router Apps signed-feed reporting. It does **not** install missing Guest/Voucher packages: those require exact-ABI signed APKs with uspot dependencies. Do not confuse Core hot-update with firmware flash.

## Core r6 update — paste complete PowerShell command

    $ErrorActionPreference='Stop'; $u='https://raw.githubusercontent.com/aicoach-alpha/zbt-we5927-openwrt/feat/veci-default-ui/scripts/veci-oneclick-r6-update.ps1'; $p=Join-Path $env:TEMP ('veci-r6-'+[guid]::NewGuid().ToString('N')+'.ps1'); Invoke-WebRequest -UseBasicParsing -Uri $u -OutFile $p; powershell.exe -NoProfile -ExecutionPolicy Bypass -File $p

## Core r6 manual rollback — paste complete PowerShell command

    $ErrorActionPreference='Stop'; $u='https://raw.githubusercontent.com/aicoach-alpha/zbt-we5927-openwrt/feat/veci-default-ui/scripts/veci-oneclick-r6-update.ps1'; $p=Join-Path $env:TEMP ('veci-r6-rollback-'+[guid]::NewGuid().ToString('N')+'.ps1'); Invoke-WebRequest -UseBasicParsing -Uri $u -OutFile $p; powershell.exe -NoProfile -ExecutionPolicy Bypass -File $p -Rollback

## App dependency and signed-feed inventory — paste complete PowerShell command

    $ErrorActionPreference='Stop'; $u='https://raw.githubusercontent.com/aicoach-alpha/zbt-we5927-openwrt/feat/veci-default-ui/scripts/veci-apps-readiness.ps1'; $p=Join-Path $env:TEMP ('veci-apps-'+[guid]::NewGuid().ToString('N')+'.ps1'); Invoke-WebRequest -UseBasicParsing -Uri $u -OutFile $p; powershell.exe -NoProfile -ExecutionPolicy Bypass -File $p

Core r6 pinned VeCI source: 72ffc33a2bd30d143692909bd387af5742277d93.
Core archive SHA256: 6d8c8978a7d57ade483440c3813eeea47080b1e95ace898c8ae980cb0fc7742f.
Installer shell SHA256: 908014cc9017f509398dac25c8a50b5f26eadd02f96c811e7309d5a31a5fc7df.
The PowerShell updater verifies both checksums before copying to router RAM.

Source and offline simulations PASS are not evidence of hardware install. Never use the Oct 6 image or J8c APKs on unverified kernel/firmware. No auto-flashing. GitHub source push and physical device deployment are separate stages.
