# ZBT-WE5927 VeCI-only firmware: source release checklist

- Hardware ZBT-WE5927 OpenWrt 25.12.5, ramips/mt76x8, firmware partition 7,995,392 bytes.
- No LuCI packages, root landing is VeCI, source branch integration/veci-feature-complete-20261114.
- Board patch previously forced LuCI via DEVICE_PACKAGES; LTE package depended on luci-base and installed luci-static view, LuCI menu/ACL even when general LuCI selection was disabled.
- Corrected device profile and latest source/we5927-lte/Makefile, removed unused LuCI view, menu and ACL files from native LTE source. Native LTE, AT, RNDIS, dual SIM and SMS retained.
- Failure run 43559170035: image built within size and verified build ID, post-build native-only rootfs gate failed; silent shell test prevented pinpointing the exact file. New workflow names the legacy LuCI file on failure, retains DEBUG-NOT-FLASH image for offline inspection on failure, and preserves hard static gate.
- Native VeCI system, network, Wi-Fi, firewall, DHCP, devices, SMS, Data Meter, App Catalog, firmware update and backup remain in native source. Guest/Voucher hardware testing optional, operator-authenticated quota removed.
- Offline tests are not physical-router UAT. Do not flash until actual new downloaded sysupgrade image and router-side sysupgrade -T pass, plus verified backup and wired recovery.
- Advanced native parity still incomplete for LuCI specialized extensions (e.g. advanced firewall rules and backup restore); no unsupported claim that every historical LuCI feature has been implemented.
