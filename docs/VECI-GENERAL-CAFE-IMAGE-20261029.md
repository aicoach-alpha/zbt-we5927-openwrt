# VeCI General-Café firmware candidate / 8-MB ZBT WE5927

## Current device facts (operator's 2026-10-29 audit)
Board zbtlink,zbt-we5927, target ramips/mt76x8, OpenWrt 25.12.5, running kernel 6.12.94, apk arch mipsel, overlay free 1116 KiB, memory free 19580 KiB. Core r6 deployed and HTTP verified. Guest, Voucher, uspot, uspot-www, app catalog, signed app provider, build ID absent. The install gate is BLOCKED.

**Decision**: do not attempt APK installation or forcibly delete OpenWrt services. The current overlay is below the minimum 2048 KiB Core preflight, before package sizes are accounted for. The firmware candidate must bundle Guest, Voucher, uspot and uspot-www into the read-only image instead of relying on overlay APK install.

## Reproducible source profile (offline OpenWrt build host only)

The existing source/openwrt-we5927.config has the correct board, protected modem packages and signed-package selection. After the pinned OpenWrt tree and feeds have been checked out and staged with scripts/prepare-veci.sh:

    cp source/openwrt-we5927.config /path/to/openwrt/.config
    scripts/install-veci-feeds.sh /path/to/openwrt
    make -C /path/to/openwrt defconfig
    scripts/prepare-veci-general-cafe-profile.sh /path/to/openwrt
    make -C /path/to/openwrt -j2

IMPORTANT: the above is a BUILD-HOST recipe, NOT a Windows PowerShell command and NOT a router instruction. The OpenWrt tree must be the exact pinned sources from source/openwrt-maintenance-pins.env and source/openwrt-zbt-we5927-current.patch; package feeds must be pinned to the same commits. Do not use a generic Image Builder from another release.

The profile:
- Validates the zbtlink_zbt-we5927 target and SIGNED_PACKAGES=y.
- Preserves Core, HTTPS/HTTP, LTE, WAN, wireless, firewall and DHCP selections.
- Selects uspot, uspot-www, veci-app-guest and veci-app-voucher as built-in y, NOT as m modules.
- Fails if Kconfig does not actually select those dependencies.
- Does not enable or provision the captive portal; Guest requires explicit operator action only after UAT.

Optional SQM, DDNS and WireGuard remain separate and require a matching signed feed / exact ABI for their later installation. Do not force those packages into this minimal 8-MB profile.

## Verify the produced image (offline; mandatory)

    scripts/verify-veci-general-cafe-image.sh /path/to/*sysupgrade.bin /path/to/*.manifest /path/to/staging_dir/host/bin/fwtool

This validates image size between 1 MiB and **7808 KiB**, target-board fwtool metadata, and a manifest including all essential management, LTE, Guest/Voucher and uspot packages. If the actual fwtool executable path differs, pass the real host-built fwtool binary from the matched toolchain. It reports SHA256 and always says FLASH_DECISION=NO_GO_UNTIL_HARDWARE_RECOVERY_AND_UAT: passing metadata/package/size checks never proves bootability, wireless recovery or data connectivity.

## Hardware release gate and rollback

BEFORE owner-authorized manual sysupgrade: obtain a physical backup, known-good recovery firmware, wired LAN and serial/bootloader rescue path, independent power/recovery plan, verified firmware signature/sha256, and size/partition checks from the actual device. Validate /etc/config network/firewall/wireless/LTE and modem persistence. Test LuCI fallback, HTTP VeCI, WAN/LTE, radio, DHCP, DNS, guest isolation, uspot login, voucher expiry/revoke, batch CSV, resource pressure, restore after failure, and reboot. Record results without IMEI/SIM IDs/credentials.

No flashing, apk install, extroot formatting or deletion has been executed. The host currently lacks a full locally built *matched* r7 General-Café image and signed feed. This source profile is completed and tested, but the physical deployment is explicitly PENDING an image build and hardware validation. The 2026-10-06 sysupgrade image does NOT include the missing Guest/Voucher runtime and cannot solve this alone.

## External references

OpenWrt Image Builder and package-management documentation describe bundled packages versus post-flash APK installation; storage limits and package dependency fit must be checked on the actual target. Extroot is another option if the router's physical USB/storage path and boot-time drivers are confirmed, but it would require separately approved hardware and configuration changes.
