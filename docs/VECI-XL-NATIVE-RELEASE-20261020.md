# VeCI XL native module release — 2026-10-20

## What is shipped
The single idempotent module reconciler at `scripts/veci-xl-native-release-reconcile-20261020.sh` installs/reconciles exactly three upstream-controlled assets:

- `/www/veci/js/lib/veci-xl-connection-status.js` — Native VeCI owner-initiated OTP UI and official myXL fallback link.
- `/usr/libexec/veci-xl-quota-session-gate` — v8 session/cache ordering gate.
- `/usr/libexec/veci-xl-authorized-config-import` — v10 offline root-only configuration importer.

All three source URLs are pinned to GitHub commits; the installer checks static guards, saves pre-change copies, and compares installed files. If already current, it makes no changes. It does not restart rpcd and does not request OTP.

## Required existing package and RPC integration
The installer **does not** package `veci-telco-xl-native` or reconstruct missing RPC/ACL setup. It requires the already deployed `veci.xl` v6 logout, `veci.quota` v7 session-gated dispatcher, XL logout helper, and the VeCI Cellular mount. These must first be incorporated in a full firmware or signed APK build before calling this a complete post-sysupgrade recovery mechanism.

## Official myXL fallback
XL's website documents quota checking with the myXL app. When `operator_configured=false`, the native VeCI panel provides a normal link to `https://www.xl.co.id/id/myxl` in a new tab, without passing subscriber numbers, tokens, or session cookies. This **does not** import quota data into VeCI. The external service may require its own login.

## Operator integration is still blocked
None of this enables a real carrier API or supplies the eight application configuration values. Only a carrier-authorized access method and validated actual subscriber response can satisfy the native `source=operator` quota contract. Do not use scraped or invented application secrets.

## Device / rollout
Target: WE5927 OpenWrt 25.12.5, VeCI only, office laptop SSH to router; never andre-nas. No changes to LTE, SMS, USSD or LuCI. Test is one targeted local UI smoke and one post-install file integrity gate. Credentials remain only in private router RAM, outside GitHub.
