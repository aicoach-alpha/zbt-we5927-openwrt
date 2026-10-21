# VeCI XL Native Overlay — Production release baseline

## Next candidate v12s (2026-10-21): source ready, production pending

The package Makefile and canonical owner-panel source now target `1.0.3-r1` (on-demand Data Meter diagnostics plus sanitized copyable report), but **the last verified router installation is still `1.0.2-r1` from v12r**. Do not mistake this source update for a live cutover. Build and gated deployment instructions: `docs/VECI-XL-V12S-LOCAL-METER-DIAGNOSTICS-20261021.md`. The signed `1.0.2-r1` APK from v12r is the only approved rollback archive; the 1.0.2 production release must not be rebuilt. Carrier-authenticated XL quota remains unavailable without permitted operator access.


**Latest verified production (2026-10-21): `veci-xl-native-overlay 1.0.2-r1` LIVE/PASS** on the office-connected ZBT WE5927 running OpenWrt 25.12.5 (APK v3 / mipsel_24kc). In-place upgrade `1.0.1-r1 → 1.0.2-r1` succeeded as one signed APK transaction, post-install integrity PASS, other packages and helpers unchanged.

Signed new APK SHA-256: `e823c14e57b191bc770e59213abfb80c883fdbcf2413bae4982481b5d6467ed8`. Exact original signed rollback APK `1.0.1-r1` SHA-256: `bc34bcee7996f5ce40e27ac46a9bb40f290c55a3b53857e14d233c5f30c0a34e`, retained on the office PC (rollback **not** exercised). The production baseline is `1.0.2-r1`, while source Makefile has advanced to the not-yet-deployed v12s `1.0.3-r1`. Release evidence: `docs/VECI-XL-V12R-OWNER-DIAGNOSTICS-RELEASE-20261021.md`.

The package owns only the VeCI XL owner-panel JS and two previously installed local helpers. It does **not** contain carrier credentials, change LTE/SMS/USSD, or authenticate to the operator. The new diagnostics UI reports redacted local status; actual operator quota retrieval remains dependent on authorized XL/XLSMART access.

**Release policy:** v12n/v12q/v12r installation and integrity gates are closed. Do not rerun completed builders or office cutovers. Legacy 1.0.0 build instructions below are historical; use the versioned `v12r/` release files for v12r traceability and create a separately versioned owner APK for the next change.

---

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

## Signed APKv3 build on the office laptop

The repository includes `build-office-windows.ps1` and `build-in-docker.sh`. The PowerShell script downloads the three source assets from a **pinned GitHub commit** into `C:\\veci-build\\xl-overlay`, uses Docker Desktop's Alpine edge apk-tools v3 to assemble a package for `mipsel_24kc`, and verifies its signature. It uses the **existing local** meter build signing key at `C:\\veci-build\\keys\\veci-meter-r2-rsa.key` and the associated `.pem` public key **via a read-only Docker mount**. Neither key is uploaded, echoed, embedded in the APK, or included in GitHub.

Run the PowerShell builder from the office computer. Its output is:
- `C:\\veci-build\\xl-overlay\\dist\\veci-xl-native-overlay-1.0.0-r1-mipsel_24kc.apk`
- a SHA-256 digest and signature verification receipt.

The separate Makefile defines a platform-independent OpenWrt source recipe; the office build intentionally targets only the tested `mipsel_24kc` router. Both routes package the same three files. A signed package does **not** establish that its native CIAM backend works with XL.

**Safety release gate:** building is permitted without changing router production. Before installing this newly built APK, inspect existing file ownership and live disk space, ensure its signing key is trusted on the router, ensure the native binary prerequisites are already installed, and provide an explicit rollback path. The build script intentionally does not run `apk add` or `sysupgrade`.

The generated local artifact and its signing key must not be committed to GitHub.
