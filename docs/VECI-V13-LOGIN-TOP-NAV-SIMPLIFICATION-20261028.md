# VeCI v13 — Restore login, top navigation, retire USSD and XL carrier quota

Date: 2026-10-28 (WIB).

## Authoritative current position

- Last **confirmed live** XL overlay: `veci-xl-native-overlay 1.0.2-r1` (v12r, installed and integrity PASS).
- The v12s `1.0.3-r1` source was prepared, but its deployment was **not confirmed**. Do **not** call v12s live or try the stale v12s installer.
- User screenshot shows VeCI login with text `session.login timed out`; no proof yet that the stored password is invalid. SSH access and an existing Lua/LuCI login may remain intact, so avoid password changes/resets, firmware flashes, firewall modifications or whole-router reboots.
- User explicitly cancelled XL/XLSMART **carrier-quota integration** and wants obsolete **USSD** and quota UI removed; retain **Data Meter local traffic counting**, which is a separate feature and must not be presented as actual carrier remaining quota.
- Preserve LTE/modem, SMS/OTP transport that supports other router operations if still used, and LuCI, as well as existing Wi-Fi/network settings.

## Implementation target

1. Investigate VeCI `session.login` timeout by correlating browser frontend request timeout, `rpcd` ubus `session` registration, `uhttpd` process, and anonymous HTTPS `/ubus` JSON-RPC transport. Read front-end source to pinpoint actual call path and timeout handling. Make the narrowest verified fix; no blanket service restarts.
2. Replace side navigation (once actual VeCI app templates are captured) with a responsive horizontal top menu using the **existing verified routes**. Requested categories: Dashboard, Internet/Cellular, Wi-Fi, Network, Data Meter, System, Administration. No fabricated URLs, no unrelated LuCI edits.
3. Remove failed XL quota and USSD controls, handlers, menu entries and client-side modules from the active VeCI UI. Audit `apk` owner/dependencies before deleting package-owned files. Retain signed previous APKs needed for rollback until the replacement has completed one integrity gate. No blind `rm` or forced APK overwrite.
4. Single narrow test (login + navigation + removed-menu absence), then production apply with rollback, followed by one integrity check. Do not re-run prior v12k–v12r UAT.

## Why first capture is necessary

This repository contains the v12r overlay JS, meter module and historical injection scripts, but **does not contain the actual current complete** `/www/veci` login controller / top-level navigation sources. Editing guessed routes/selectors could break login and access further. Before modifying production, one read-only office audit captures public, browser-delivered `/www/veci` source and non-secret `rpcd/uhttpd` health. It neither reads router passwords nor calls carrier APIs.

Pinned scripts:

- Router-side read-only audit: `scripts/veci-v13-source-login-audit-20261028.sh`
- Office PowerShell wrapper: `scripts/veci-v13-source-login-audit-office-20261028.ps1`

The office script stores a `*.tar.gz` of static UI source at `C:\veci-build\veci-v13-readonly-20261028\veci-v13-ui-source-20261028.tar.gz` and prints the anonymous HTTPS `/ubus` transport status. The operator should **upload that archive privately to this conversation**, plus the short terminal status; never commit the capture archive or router data publicly. It deliberately stops without mutating services, packages or credentials.

## Production acceptance gate

Do not mark v13 login repaired, top navigation deployed, or quota/USSD deinstalled until the actual new sources/patch are staged, installed, and produce a one-time scoped integrity receipt. At this stage the read-only capture tooling is implemented and GitHub committed; production is **unchanged**.

## Repository implementation completed (source-only)

- `web/v13/top-navigation.js`: reusable horizontal main navigation component that accepts actual verified routes from current VeCI menus, filters retired entries, keeps current-page semantics, and blocks invalid/external URL values.
- `web/v13/top-navigation.css`: compact desktop and mobile horizontal top menu with keyboard focus and active selection.
- One focused in-memory navigation unit check PASS: excludes retired USSD entries, preserves actual source-supplied routes, sets aria-current and rejects external link injection.
- Automatic quota contract workflow `.github/workflows/veci-quota-contract.yml` now manual-only; no further push/PR CI consumption for a cancelled feature.
- Historic `v12s` script marked **DO NOT DEPLOY**; current production package must not be mistaken for it.

**Not yet installed:** The navigation module needs wiring into the actual VeCI login, routing, and page template extracted from router. Historical XL/USSD package-owned files are not yet removed from router; uninstall decisions depend on a targeted package-ownership audit. Static component source is not a production UI fix.

Next required owner action: run the read-only v13 office capture wrapper and provide the resulting UI source tarball. That is the minimum source needed to repair the screenshot's login timeout, connect the horizontal navigation without fabricating routes, and safely retire all old UI and backend package components in one scoped v13 deployment.

## Real office read-only audit acceptance — 2026-10-28

User ran v13 source capture and returned:

```text
VECI_V13_BOARD=zbtlink,zbt-we5927
VECI_V13_VERSION=25.12.5
VECI_V13_PROCESS_rpcd=running
VECI_V13_PROCESS_uhttpd=running
VECI_V13_PROCESS_ubusd=running
VECI_V13_SESSION_RPC=timeout_command_unavailable
VECI_V13_HTTPS_UBUS=http=200;duration=0.198189
VECI_V13_HTTP_JSONRPC=responding
VECI_V13_AUDIT=pass
VECI_V13_SOURCE_ARCHIVE_BYTES=45377
VECI_V13_LOCAL_SOURCE_SHA256=1813a12623758fe662eda06eb7c90a4dbbfb85572304ec4b4551381d928b3e15
VECI_V13_PRODUCTION=unchanged
```

`timeout` is not installed on the router, so the many `VECI_V13_RPC_*=not_confirmed` records and `SESSION_RPC=timeout_command_unavailable` **cannot** be interpreted as the RPCs absent or malfunctioning. The public HTTPS /ubus transport responded quickly, but the authenticated `session.login` transaction is still unverified. Retain all credentials and avoid broad service restart. The source archive `C:\veci-build\veci-v13-readonly-20261028\veci-v13-ui-source-20261028.tar.gz` resides on the **user's office PC** and has **not** been uploaded to this chat. Its actual frontend files have not been examined here; request the tar.gz attachment before designing an auth/controller or live nav patch.

## Additional priority: automatic LTE reconnect

As requested after this audit, faster LTE reconnect is handled separately from VeCI frontend and does not require the frontend archive. Existing source confirms `ping_interval=30`, `fail_threshold=6`, checking 1.1.1.1 and 8.8.8.8 and recovering by LTE interface before CFUN. Signed/owned firmware binary need not be overwritten to adjust the two UCI configuration keys. The scoped scripts `scripts/veci-v13-lte-fast-reconnect-20261028.sh` and `scripts/veci-v13-lte-fast-reconnect-office-20261028.ps1` target `10s x 3` checks, preserve SIM/APN/failover, back up the original UCI file, restart only the existing watchdog service once, and check runtime integrity once. Repository defaults and `docs/RECOVERY.md` were changed. **Live application still requires owner execution/receipt**; no controlled outage test has been claimed.
