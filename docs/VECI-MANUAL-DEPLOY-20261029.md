# VeCI General — operator handover (Windows office laptop)

Status: SOURCE TESTED, PHYSICAL ROUTER NOT DEPLOYED; FLASH NO_GO.

The ZBT WE5927 router is connected to the Windows office laptop, NOT to andre-nas. All flashing, package installation and tests on the router are MANUAL. No automated flash.

## Exact source identity
- VeCI Core r4 SHA: 81853a6b8b710a26a2427d1176751bf781bc7243 (aicoach-alpha/veci branch dev).
- Firmware source SHA: f1dc4d88904bb638bb1ca24806e118762316ef89 (aicoach-alpha/zbt-we5927-openwrt branch feat/veci-default-ui).
- No new compiled r4 sysupgrade binary or paired r4 signed APK feed is included in this repository. The tracked 2026-10-06 .bin image is OLD, and must never be mislabeled as r4. Do not flash this as an r4 release.

## Operator preflight — no changes

Obtain this repository on the office Windows laptop. Review scripts/veci-router-preflight.ps1. Run in PowerShell as an explicit LOCAL file:

    powershell.exe -NoProfile -File .\scripts\veci-router-preflight.ps1 -RouterHost ROUTER_IP_VISIBLE_FROM_OFFICE_LAPTOP

Replace the placeholder with the router IP on the laptop's network, not the IP seen from andre-nas. Requires Windows OpenSSH. Interactive SSH password login is allowed when the operator runs it locally, and the first host-key confirmation must be checked against a trusted fingerprint; never automatically accept an unknown key. If SSH is unavailable and only HTTP UI is used, collect equivalent read-only identity through the router UI. Never disable HTTP or force HTTPS to complete this preflight.

When a newly built r4 image and independent checksum exist, optionally check the local binary:

    powershell.exe -NoProfile -File .\scripts\veci-router-preflight.ps1 -RouterHost ROUTER_IP -FirmwareFile C:\path\new-r4-sysupgrade.bin -ExpectedSha256 PUBLISHED_64_DIGIT_SHA256

This verifies only board identity, image size/hash and basic storage inventory. It does not verify image signature, package ABI or sysupgrade compatibility.

## Manual deployment gates

1. Build the exact pinned Core and firmware together with matching signed feed using a controlled build environment (or owner-triggered GitHub workflow if quota permits). Check kernel ABI, package index signatures, firmware SHA256 and board metadata. Old J8c app packages must not be used on another kernel.
2. Test on owner-approved recoverable hardware. Back up settings and verify physical UART/U-Boot or recovery procedure; keep wired network access and known-good firmware.
3. After independently verifying file identity and approval, manually upload the candidate on the approved router and run a compatibility check (sysupgrade -T) without force flags. Do not run sysupgrade -F.
4. Run U01–U16 in docs/J9C-HARDWARE-UAT.md and record results, rollback, and HTTP/LuCI, LTE/USB, cellular, Wi-Fi, DHCP/DNS, Guest/Voucher, SQM and app installation. Mask all private identifiers, credentials, codes and keys in exported evidence.
5. Flash only after the owner approves the exact image, device and maintenance window and hardware recovery is proven. Use the established manual upgrade procedure; this kit contains no flash command.

Stop immediately if device ID, image hash, signed feed, recovery path, or any preflight condition disagrees. GitHub push is not firmware deployment.

## Status vocabulary
- SOURCE_PASS: tests/build of source successful, no binary release implied.
- BUILT_PAIR_VERIFIED: exact-ABI firmware and signed APK feed built and verified together.
- HARDWARE_UAT_PASS: all applicable physical test cases passed.
- OPERATOR_APPROVED: the exact image/device/maintenance window approved.
- DEPLOYED_VERIFIED: the operator manually flashed and confirmed service recovery.

The source is SOURCE_PASS only; all later gates are pending.
