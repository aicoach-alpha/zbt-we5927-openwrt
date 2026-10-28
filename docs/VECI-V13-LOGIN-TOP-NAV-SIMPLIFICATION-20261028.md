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

## Focused login timeout isolation (2026-10-28)

Owner reports that VeCI still displays `session.login timed out`. Previous audit already established `rpcd`, `uhttpd`, `ubusd` process presence and HTTP 200 from an **unauthenticated session.access request**, but **did not** test a real `session.login` method. Do not confuse reachability of `/ubus` with auth success.

One read-only office helper is committed: `scripts/veci-v13-login-timeout-triage-office-20261028.ps1` (commit `47d65ddc626b1cd5154223ca7b13f32d2c6df32d`). It reads only the previously captured static frontend tar.gz (SHA-256 `1813a12623758fe662eda06eb7c90a4dbbfb85572304ec4b4551381d928b3e15`) and prints bounded source windows for `veci/js/lib/api.js`, `veci/js/app.js`, `veci/index.html`. It runs **one** synthetic `session.login` request over router-local HTTPS using an intentionally nonexistent username and invalid dummy password, reporting only HTTP timing and JSON-RPC status code. This does not use or print the user's password, cannot create a valid login session, and never restarts services or changes router files. A synthetic denial is diagnostic of RPC responsiveness only, not a successful authentication path for a genuine account.

No login patch has been applied or verified yet. The subsequent patch must be grounded in the exact login controller source and probe receipt, should preserve login security, and should be deployed with a rollback and one focused integrity check. Do not reset router passwords or restart `rpcd` speculatively.

## 2026-10-28 — Login timeout confirmed at RPC method, conditional repair source prepared

User's actual office capture of frontend source:

- `veci/js/lib/api.js` uses `fetch('/ubus')` with `AbortController` default 10,000 ms; a client-side abort becomes `session.login timed out`.
- `veci/js/app.js` directly awaits `this.api.login(username,password)` and displays the error.
- A synthetic **nonexistent username + invalid password** sent directly to `https://192.168.1.1/ubus` received **HTTP 200 response headers but no JSON body within 12.003 seconds** (`curl exit=28`). Thus blindly increasing JS timeout is not the appropriate first fix; the auth method/HTTP bridge is unresponsive.
- OpenWrt `ubus -t <seconds>` is a built-in bounded CLI probe, unlike the absent standalone `timeout` executable. OpenWrt rpcd's session login should promptly return status 6/Permission denied for an unknown user, without a costly root password hash operation.

Corrective implementation:

- Router: `scripts/veci-v13-conditional-login-recovery-20261028.sh`. One `ubus -t 4` synthetic invalid login distinguishes local RPC denied_fast vs timeout. When local RPC truly times out, it permits **one `rpcd` restart**, then a single post-check. If local RPC is already responsive, preserve rpcd and existing sessions. It refuses auto-restart for unknown local outcomes. The HTTP bridge may be restarted separately only when RPC is confirmed responsive.
- Office: `scripts/veci-v13-conditional-login-recovery-office-20261028.ps1` pinned to router script at `81587bebec2d8af410ef1f7f41dac6222dd71997`. Makes one HTTPS synthetic login check, conditionally restarts only `uhttpd` when the RPC is good but HTTP call times out, then one post-check. No password entry, no account changes, no service-wide reboot, no LTE or modem changes, no firmware or package writes. A `rpcd` restart will invalidate prior ubus sessions; a `uhttpd` restart will briefly interrupt web requests.
- Offline shell syntax test and one focused source-integrity check passed. **Not yet executed against production**; do not claim successful login before the owner applies it and tests the real user login once.

Owner PowerShell command:

```powershell
$p="$env:TEMP\veci-v13-auth-recover.ps1"; curl.exe -fLsS https://raw.githubusercontent.com/aicoach-alpha/zbt-we5927-openwrt/d0e1a5d7eef8176b0eca61884aac4143d7794f4f/scripts/veci-v13-conditional-login-recovery-office-20261028.ps1 -o $p; if ($LASTEXITCODE -eq 0) { & $p }
```

Receipt `VECI_AUTH_OFFICE=rpc_path_pass` means only that the dummy account is rejected quickly through the end-to-end RPC route. It does **not** prove real login credentials or the full frontend work. If real login still fails, inspect that specific case and the captured frontend source without repeated router restarts. The top-nav and XL quota/USSD retirement remain pending after authentication recovery.

## v13u — Owner-requested LAN HTTP return and isolated login test (2026-10-28)

The user explicitly requested that VeCI switch back from enforced HTTPS to **HTTP on the trusted local network**, while continuing to address the original \`session.login timed out\` failure. The preceding targeted \`rpcd\` restart was verified **ineffective**: the dummy HTTPS \`session.login\` request still timed out after 12 seconds and 0 body bytes. Do not repeat that restart or merely extend the 10-second browser timeout.

Implementation:
- \`scripts/veci-v13u-lan-http-login-20261028.sh\` changes only \`uhttpd.main.listen_http=192.168.1.1:80\` and \`uhttpd.main.redirect_https=0\`, preserving the HTTPS listener and uhttpd's existing other settings. The script first executes one bounded *direct local ubus* dummy login (\`ubus -S -t 6 call session login\`) to classify internal auth responsiveness.
- LAN IP \`192.168.1.1\`, OpenWrt board/version and actual local IP assignment are enforced before changing config. The previous \`/etc/config/uhttpd\` is backed up, the \`uhttpd\` service is restarted once (not \`rpcd\`, router, modem or LTE), and a single config/process integrity gate checks the new state. Rollback via \`--rollback\` is available.
- \`scripts/veci-v13u-lan-http-office-20261028.ps1\` stages the pinned script from Windows, runs it via SSH, then sends exactly one synthetic invalid-credentials login to \`http://192.168.1.1/ubus\`. The printed result distinguishes responsive rejection from timeout without revealing session IDs or user passwords.
- HTTP is plaintext: router passwords could be captured by users/devices on the same network. It is explicitly restricted to the LAN IP, never exposed on all interfaces; HTTPS stays available for secure fallback. Users should prefer HTTPS again once login is repaired, and avoid sending passwords over public or untrusted Wi-Fi.
- Browser HTTPS-Only/HSTS policies may still upgrade \`http://\` locally. Test with the literal \`http://192.168.1.1/veci/\` URL on a trusted LAN. If direct internal ubus still stalls, the problem is **not solely HTTPS**; examine the auth backend rather than rewriting frontend fetch code.

This is a source-ready office cutover script, **not evidence of live HTTP configuration or successful VeCI login**. Owner receipt required. No package upgrade, firmware flash or repeat of prior LTE/UI UAT.
