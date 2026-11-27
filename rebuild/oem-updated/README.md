# OEM Updated — separate WE5927-2SIM development variant

Base: VeCI v2 d8faaeff420bdc44e03fc756a5e0527c886cdc27, OpenWrt 25.12.6 / Linux 6.12.112. Full VeCI remains unchanged.

## Current state
- OEM static asset staging only: 85 files, 3,202,323 uncompressed bytes.
- OEM menu baseline: 20 enabled flags, 158 declared CGI operations.
- Current operation status is derived from the live registry, not a hardcoded initial count. Run `python3 rebuild/oem-updated/progress.py`. Fixture PASS, source-complete, disabled review and functional PASS are separate; none of the first three is release approval.
- No legacy CGI, vendor kernel modules, proprietary executables or user overlay imported. Vendor CGI contains hardware-specific operations including writes to calibration storage; it must not be deployed.
- LTE parity target is verified OEM Enhanced V3 behavior: Qualcomm 05c6:902e, ttyUSB2, RNDIS usb0, DHCP, serialized bounded recovery, no healthy-link redial, watchdog 60/60. Do not run old and new dialers together. Translate behavior into the single existing modern LTE service, not duplicate it.
- Do not publish proprietary OEM assets in Git. Use a locally supplied, verified original OEM file. Do not upload raw router dumps into repository or Actions.

## Stage preview locally
Install squashfs-tools on the development host. Run:
```
python3 rebuild/oem-updated/stage_oem_ui.py /path/to/WE2825-2SIM_V26.03.04_V26.08.09_SSH_ROOT_MOD.bin /path/to/new-preview-dir
```
This produces static assets and an operation inventory, not a bootable image. Do not serve the preview on a live router. For package staging including authenticated adapters use stage_variant.py; staging does not prove runtime functionality.

## Build and release acceptance
1. Map UI requests and response shapes to modern native services; default deny unknown operations; use authenticated sessions, ACLs, CSRF controls, input validation and no arbitrary command dispatch.
2. Reuse pinned VeCI source, custom DTS, Wi-Fi patches, native services and signed image tooling. Keep separate build configuration and variant metadata. Do not select VeCI UI for OEM output.
3. Port LAN/WAN, Wi-Fi main and guest, LTE dual SIM, SMS, DHCP, DNS, firewall, diagnostics, watchdog, upgrade and backup; preserve supported OEM menu and settings. Hidden/unsupported options must be recorded honestly. Local migration allowlist only; no baked-in credentials.
4. Verify firmware image size including sufficient overlay reserve, RAM, root landing, API integration, feature regressions, signature and trust anchor. No writing U-Boot or calibration partitions.
5. Physical boot, LTE DHCP and recovery, Wi-Fi, rollback and 72-hour acceptance are separate from source tests. Existing VeCI hardware evidence cannot be transferred to OEM Updated. Until then: BACKEND_READY=NO, FIRMWARE_BUILT=NO, FLASH_ALLOWED=NO.

## Full-build discipline (owner requirement)
- Do not launch full firmware compilation on individual source changes or on a timer. Run lightweight source and integration tests as often as required.
- First complete the required OEM operation inventory, native backend, security, hardware policy parity, and all feasible offline regressions. Record evidence against the exact candidate commit. Unknown, unimplemented or untested required functionality blocks a full build; do not treat syntax checks as functional acceptance.
- Dispatch the full-image workflow only after the pre-build acceptance review passes. Require actual downloadable BIN, manifest, SHA256, round-trip verification and post-build checks. This lab workflow remains explicitly not flash-approved.
- If post-build inspection fails, aggregate findings, fix all known defects, rerun affected offline tests, then dispatch one new full build. Do not rerun unchanged failing builds.
- Physical boot, modem, actual Wi-Fi and 72-hour stability remain separate hardware gates; never claim these passed based on a source test.

## Owner policy: optional guest Wi-Fi (2026-11-26)

Guest Wi-Fi is optional, absent/disabled on clean firmware, never automatically provisioned or enabled. Reuse native VeCI addon profile controls, require explicit user enable/disable and a separately chosen manual reboot; no global live reload. Existing compatible provisioned profile can be toggled; safe first-time provisioning and physical isolation remain separate acceptance requirements. Do not market an untested guest activation as complete. The base router must work without the addon.
