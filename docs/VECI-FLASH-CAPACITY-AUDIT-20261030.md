# ZBT WE5927 flash partition read-only readiness audit

Firmware must not be flashed until the device flash partition can fit the finished board-specific sysupgrade image and the owner has tested a wired hardware recovery path.

The source General-Café profile's 7808 KiB maximum is not proof of device storage. This audit reads board and target, live kernel, and the firmware partition size from /proc/mtd. It refuses unknown, duplicate, undersized, malformed, or wrong-board partition records. MTD_GATE=PROFILE_LIMIT_FITS_REPORTED_PARTITION means only the profile budget fits the reported partition; it is not proof the finished image will work.

## Office Windows laptop (one complete PowerShell line)

    $ErrorActionPreference='Stop'; $u='https://raw.githubusercontent.com/aicoach-alpha/zbt-we5927-openwrt/feat/veci-default-ui/scripts/veci-flash-capacity-audit.ps1'; $p=Join-Path $env:TEMP ('veci-flash-audit-'+[guid]::NewGuid().ToString('N')+'.ps1'); Invoke-WebRequest -UseBasicParsing -Uri $u -OutFile $p; powershell.exe -NoProfile -ExecutionPolicy Bypass -File $p

The launcher separately validates the checksum-pinned read-only shell script, verifies board/target, copies the script to volatile /tmp, executes it over SSH, saves a report in Documents/VeCI-audits, and deletes only its own temporary shell script. No UCI/network changes, package installation or firmware flash. A blocked audit still saves its report.

After a finished General-Café image exists, verify actual image size, metadata, essential packages, embedded SquashFS and signed indexes; then complete owner-approved recovery and LTE/guest/voucher UAT before any physical upgrade.
