# VeCI v16: minimal navigation and IPv6 opt-in / low-downtime contract

Date: 2026-11-12. **SOURCE STAGED ONLY. NOT DEPLOYED. NO ROUTER FILES MODIFIED.**

## Navigation: one place per function
Six primary groups: **Home**, **Internet**, **Wi-Fi**, **Devices**, **Settings**, **Apps**.
Canonical inventory uses *existing verified hash routes*; no invented URLs:
- Home: `#/home`
- Internet: `#/internet` (status) and `#/cellular` (LTE/SMS)
- Wi-Fi: `#/wi-fi`
- Devices: `#/devices`
- Settings: `#/network` (Network & IPv6), `#/security` (Firewall), `#/system` (backup, users and system), **one** Firmware & OTA link selected only from an existing `#/update` or `#/firmware` route
- Apps: `#/apps`

Exactly one feature owner. OTA is owned **only** by Settings. Do not also render an OTA card in System when the native VeCI SPA controller is updated. Old URLs may redirect internally, but must not render a second public menu or duplicate the upload/flash controls. The adapter preserves existing anchor listeners and fails closed if a required route is missing. `web/v16/veci-lean-navigation.css` styles a small responsive menu. Grouped Settings links remain accessible for deep links; moving an anchor is not sufficient to migrate its page logic.

## IPv6 default: OFF only on new factory images
IPv4 connectivity has priority. Keep the kernel IPv6 stack and necessary client functionality in the image so the option can later be enabled. The opt-in UI is **Settings → Network → IPv6** (not another top-level menu). `web/v16/veci-ipv6-settings.mjs` exposes a minimal button if and only if a native authenticated backend implements `status()`, `preflight(enabled)`, `setEnabled(enabled)` and verifies an effective post-apply state. A missing backend yields a disabled, transparent control. No fabricated success.

`scripts/veci-ipv6-factory-image-only.sh` uses **host UCI** against a separately extracted/staged factory rootfs and requires explicit `.veci-factory-image-root` marker. It sets `wan6.disabled=1` (if wan6 exists), `wan/ lte.ipv6=0`, removes LAN `ip6assign`, and disables LAN RA/DHCPv6/NDP. It never changes live `/etc/config`, runs network reload, restarts odhcpd, modifies Wi-Fi/LTE, or reboots. Build integration must be reviewed: do **not** package this as an unconditional `uci-defaults` boot hook because it would overwrite users' preserved IPv6 choice during an upgrade.

The real backend for enabling or disabling IPv6 has not been implemented yet. It must preserve prior UCI settings, check WAN protocol and LTE transport, block DS-Lite/MAP/464XLAT, provide safe-apply + automatic rollback, update only relevant IPv6 interfaces, never restart primary Wi-Fi or LTE because of IPv6 settings, and validate IPv4 reachability after every change. Dynamic runtime `wan6`, `wan_6`, `lte_6`, native IPv6 carrier support and DNS must be discovered from physical router observations rather than assumed. If the carrier depends on IPv6 for IPv4, show a clear incompatibility warning and keep current settings.

## UAT + production gates
1. Compare 25.12.5 production SPA `/www/veci` authenticated source and canonical route inventory. The checked-in repo contains UI fragments **not the full production SPA**. Inspect actual duplicated OTA content in System and Update; remove the redundant UI only once source ownership is confirmed.
2. Native IPv6 RPC implemented and ACL-reviewed; authenticated toggle and off-by-default provisioning on newly built image verified.
3. Router wired test: Wi-Fi beacon independent scanning, LTE public & gateway connectivity, SMS, login; no network-wide reload on browsing, toggle or update checks.
4. Preserve configuration across OTA; check IPv6 choice persists. Measure median/p95 UI CPU/RAM/flash use and duration of any actual link interruption; no unverified zero-downtime claims.
5. 72-hour Wi-Fi/LTE UAT and signed board-matched sysupgrade preflight. Production firmware remains unchanged until qualified.

Related: PR #7 MT7603 deadlock, PR #8 LTE recovery, PR #9 guest isolation, PR #10 observe-only guardian, PR #11 external beacon UAT, PR #13 LuCI independence and issue #12 overall release.
