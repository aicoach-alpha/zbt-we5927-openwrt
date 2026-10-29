# VeCI General v15 — Cafe Router / Voucher Apps Catalog

Date: 2026-10-29 WIB. Status: **SOURCE-READY; NOT YET DEPLOYED**.
Parent: `aicoach-alpha/zbt-we5927-openwrt`, owner router ZBT WE5927 OpenWrt 25.12.5 (mipsel_24kc / APKv3).

## Purpose

Transition VeCI from Indonesia-provider-specific functions to a general router with a
responsive top navigation and a cafe-friendly Apps page. Keep existing internet,
Wi-Fi, LTE, Fast Reconnect, Data Meter, SMS and network controls. Remove only
cancelled `XL Account / Koneksi myXL` and `Indonesia · Operator / Operator Data Quota`
from Cellular. Do not uninstall essential modem, SMS or meter services.

## 14 Apps cards, 4 groups

| Card | Mode | Package / route | Priority |
|---|---|---|---|
| Hotspot Portal | conditional APK | opennds | P0 |
| Voucher Manager | not ready / backend required | official openNDS ThemeSpec voucher + persistent external storage | P0 |
| Guest Wi-Fi | built-in | #/wi-fi | P0 |
| Connected Clients | built-in | #/devices | P0 |
| Smart Queue (SQM) | conditional APK | sqm-scripts | P1 |
| Speed Profiles | not ready / backend required | client shaping integration | P1 |
| Data & Time Limits | not ready / backend required | voucher session/accounting | P1 |
| Firewall & Guest Isolation | built-in | #/security | P0 |
| DNS Filtering Lite | conditional APK | adblock-fast | P2 |
| Dynamic DNS | conditional APK | ddns-scripts | P2 |
| WireGuard | conditional APK | luci-proto-wireguard | P2 |
| Data Meter | built-in | /veci/data-meter.html | P0 |
| Fast LTE Reconnect | built-in | #/cellular | P0 |
| Backup & Restore | built-in | #/system | P0 |

Source: `web/v15/veci-cafe-app-catalog.js`.
Card renderer: `web/v15/veci-cafe-app-cards.js` and CSS.
Authenticated API bridge: `web/v15/veci-apps-rpc-adapter.js`.
Allowlisted RPC + worker + ACL Buildroot package:
`packaging/veci-general-apps/` (`veci.apps`, worker, ACL and Makefile).

One source-only gate PASS: 14 unique valid cards; 6 built-ins, 5 optional APK,
3 deferred; exact matching package whitelist across catalog, adapter, RPC,
worker; voucher cannot falsely show Install; authenticated requests only.

## Resource/safety decisions

Latest verified router overlay free space ~1120 KiB and RAM ~57.2 MiB total.
This is **not enough to claim any new package with its dependencies fits**.
The prototype manager explicitly requires >=8192 KiB free before install;
on the existing router, all optional Install buttons should be disabled with
the real flash-space reason. It is intentionally conservative: a source-ready
button is **not** permission to risk a full JFFS2 overlay.

Production choices:
1. For immediate value, enable built-in Guest Wi-Fi, client list, firewall
   separation, Data Meter, LTE watchdog and configuration backup.
2. For cafe voucher access, prefer openNDS with official Voucher ThemeSpec,
   **but only after confirming exact package+dependencies and spare storage**.
   Voucher file needs persistent storage **away from flash**; frequent writes
   to router flash will wear it out. A remote controller or appropriate
   mounted storage is needed for reliable paid vouchers.
3. A firmware-baked/squashfs image or verified extroot could fit additional
   packages; neither is authorized to flash or modify by this code.
4. SQM may lower throughput on low-end MIPS, so measure CPU before making
   promises about per-client bandwidth caps.
5. Do not imply RouterOS/MikroTik license or feature parity. OpenWrt can
   implement comparable selected hotspot, queue and firewall workflows.

Official references:
- https://openwrt.org/docs/guide-user/services/captive-portal/opennds
- https://github.com/openNDS/openNDS/blob/master/community/themespec/theme_voucher/README.md
- https://opennds.readthedocs.io/en/stable/config.html
- https://openwrt.org/supported_devices/864_warning
- https://downloads.openwrt.org/releases/packages-25.12/mipsel_24kc/packages/
- https://downloads.openwrt.org/releases/packages-25.12/mipsel_24kc/luci/

## Pending for actual production

The complete `/www/veci/js/pages/apps.js` / `app.js` / `index.html` source
was captured privately on the office PC at
`C:\veci-build\veci-v13-readonly-20261028\veci-v13-ui-source-20261028.tar.gz`
but has **never been attached to this conversation**. It is not stored in
GitHub. Do not guess the current page mount, event-handler, auth adapter or
top navigation selectors. Wire the modules to the actual captured SPA once
that archive is supplied, and preserve original owner files/rollback.

The new `veci-general-apps` Buildroot Makefile is source-only; no signed
APK has yet been built or installed, and no runtime `veci.apps` RPC is
verified. The third-party package feed and package sizes/dependencies must
be verified on the router before enabling Install. No production changes
are claimed for this v15 catalog. Confirm installation status after
future deploy using one targeted integrity gate and one actual App action,
not repeated legacy UAT.

## v15.1 — Curated essential cards and compatibility reality (2026-10-29)

The owner reiterated the requirement that **only apps useful for a café and realistic on the WE5927** should dominate the page. The initial 14-card catalog was too broad for the default view. Source is now updated:

- `VECI_CAFE_ESSENTIAL_IDS` and `cafeEssentials()` choose **11 essential** cards (Hotspot Portal, Voucher Manager, Guest Wi-Fi, Connected Clients, Smart Queue, Speed Profiles, Data & Time Limits, Firewall & Guest Isolation, Data Meter, Fast LTE Reconnect, Backup & Restore).
- The responsive card renderer displays only those 11 by default. Three lower-priority cards (DNS Filtering Lite, Dynamic DNS and WireGuard) remain in the extended `showAdvanced=true` catalog.
- Voucher Manager and per-user limits are **development only**, not installable pretend packages. OpenNDS is a conditional package, not a working voucher implementation. Guest Wi-Fi, client listing, firewall, Data Meter, LTE watchdog and backup link back to existing authenticated VeCI pages.
- The official OpenWrt **25.12.5 mipsel_24kc packages** listing does show `sqm-scripts-1.7.2-r1.apk` 20.0 KB, `adblock-fast-1.2.4-r4.apk` 30.7 KB, and `ddns-scripts-2.8.4-r8.apk` 23.1 KB. Those are download archive sizes only. The same 25.12.5 base/packages indexes did **not** contain an `opennds-` APK on the date checked, while the snapshot repository showed opennds 10.3.1 (~150 KB). **Do not mix SNAPSHOT packages into stable 25.12.5** or claim openNDS is signed and installable from the current firmware's feed. Use a reproducible exact-version custom build if later authorized.
- The prior audit's overlay was ~1120 KiB free; installed dependencies, uncompressed package sizes and build matching require runtime verification. The existing provisional Apps RPC keeps a conservative **8192 KiB free-space gate**, meaning it should never falsely accept new app installs on that observed state.
- A focused catalog test PASS: 14 valid ids, 11 default essential cards, 3 advanced, UI renderer syntax OK, cross-file package mapping consistent, no voucher fake-install and conservative flash/feed checks intact.

Sources:
- https://downloads.openwrt.org/releases/25.12.5/packages/mipsel_24kc/packages/
- https://downloads.openwrt.org/releases/25.12.5/packages/mipsel_24kc/base/
- https://downloads.openwrt.org/releases/25.12.5/packages/mipsel_24kc/luci/

**Production remains unchanged** by these Github source commits. The real runtime VeCI app source has never been available in this chat, so do not install/inject JS blindly or claim cards already appear on the live router. The upstream packager itself remains a non-shipped source prototype; one release hardening pass and authentic backend integration are required before a signed APK build and a guarded deploy. No new firmware or APN/LTE changes.
