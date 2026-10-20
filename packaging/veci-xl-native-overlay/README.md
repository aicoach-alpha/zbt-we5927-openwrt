# VeCI XL native addon — build source (2026-10-20)

This is a **source-only OpenWrt package definition**, staged for the ZBT WE5927 / ramips/mt76x8 OpenWrt 25.12.5 APK build. It has NOT been compiled into an APK or into a new firmware image. **Do not flash firmware based solely on these files.**

## Contains
- `files/veci-xl-connection-status.js`: native Cellular UI with user-initiated OTP, quota status, logout, and link to official myXL
- `files/veci-xl-quota-session-gate`: read-only session/cache guard
- `files/veci-xl-authorized-config-import`: root-only RAM provisioning tool for authorized app configuration

The package excludes all tokens, credentials, API signatures and user data. The helper scripts are installed with root-only executable permissions.

## Required before packaging a complete firmware
1. The existing **binary** package `veci-telco-xl-native` (0.3.7-r1 on the test router) has to be available in the OpenWrt build package feed or a suitable binary repository. Its sources were not found in this GitHub repository. This addon **does not build its 11 native executable components**.
2. `veci.xl` RPC with owner-only logout, the owner ACL and the `veci.quota` RPC gate dispatcher must be included from their source packages.
3. The Cellular VeCI UI source must include the `mountXlConnection(root, api)` module invocation. This addon does not install or replace `cellular.js`.
4. Check package conflicts for `/www/veci/js/lib/veci-xl-connection-status.js` and the two `/usr/libexec` paths. Only one package should own each path.
5. Build and sign a real `mipsel_24kc` APK on the office development computer, stage it, and perform one installation/integrity check. **Do not switch production firmware while those prerequisites are missing.**

## Staging into an OpenWrt source tree
Copy the folder `packaging/veci-xl-native-overlay` into the `package/` directory of a matching OpenWrt 25.12.5 SDK/full source tree. Use `make menuconfig` or package build to select `veci-xl-native-overlay` only when its native dependency stack is available. This Makefile has no network calls during build, no bundle secrets, and does not modify LuCI/LTE/SMS.

The separately tested router release reconciler `scripts/veci-xl-native-release-reconcile-20261020.sh` remains the operational method for the existing router. Its LIVE result reported `XL_RELEASE_INTEGRITY=pass`, but that does **not** establish successful carrier authentication.

## Actual XL quota
No official, approved provider API credentials or subscriber quota endpoint have been verified for third-party access. Do not simulate carrier balance, extract mobile-app secrets or treat the myXL website link as an automated quota API.
