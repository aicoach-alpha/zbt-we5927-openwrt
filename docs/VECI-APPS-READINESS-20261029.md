# WE5927 General Router Apps install-readiness — read-only laptop operator kit

## Run this entire line in Windows PowerShell connected to the actual router

    $ErrorActionPreference='Stop'; $u='https://raw.githubusercontent.com/aicoach-alpha/zbt-we5927-openwrt/feat/veci-default-ui/scripts/veci-apps-readiness.ps1'; $p=Join-Path $env:TEMP ('veci-apps-'+[guid]::NewGuid().ToString('N')+'.ps1'); Invoke-WebRequest -UseBasicParsing -Uri $u -OutFile $p; powershell.exe -NoProfile -ExecutionPolicy Bypass -File $p

The script downloads a SHA256-pinned read-only shell audit, verifies the actual WE5927 via laptop SSH, stages the audit to temporary RAM, prints the result, and saves a sanitized summary to the laptop Documents/VeCI-audits folder. It attempts to remove the temporary shell script after auditing. It NEVER changes router configs or installs APKs, upgrades firmware, enables Guest, restarts Wi-Fi, or writes modem settings.

### Decision matrix

- PKG_uspot=MISSING, PKG_uspot-www=MISSING: must provide them via an exact compatible signed OpenWrt APK feed, not by copying files into the core hot-update.
- PKG_veci-app-guest=MISSING, PKG_veci-app-voucher=MISSING: the existing Core r5 already deployed cannot activate voucher access until the packages and their dependencies are installed.
- BUILD_ID=MISSING or APPS_INSTALL_GATE=BLOCKED: the package repository cannot yet be proven to match the running firmware; DO NOT use old J8c packages with a 6.12.94 kernel just because the architecture is mipsel_24kc.
- APPS_INSTALL_GATE=SIGNED_FEED_READY: reports only prerequisites for an operator-authorized installation, not proof that every specific APK or live Guest/Voucher configuration was tested. Separate exact-package preflight and physical UAT are mandatory.

The report omits Wi-Fi passwords, VPN keys, tokens, SIM IDs, IMEI, router config, voucher codes, and user client data.

The source release channel remains available=false until a newly built, signed, firmware-matched image and APK feed are published and tested. The package installer must never silently use the older October 6 image or the J8c/6.12.112 packages on a potentially different current kernel.
