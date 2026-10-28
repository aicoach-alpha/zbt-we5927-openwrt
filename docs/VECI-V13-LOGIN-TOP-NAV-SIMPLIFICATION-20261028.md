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

## v13u SSH stall and v13v nonblocking replacement — 2026-10-28

The owner attempted the v13u office `-Action Apply`, got SSH root password prompt after successful SCP and then reported **stuck before any installer receipt**. No `VECI_LOGIN_DIRECT_UBUS_CHECK`, `VECI_V13U_HTTP_LISTEN` or `VECI_V13U_RELEASE` was observed. **Production HTTP state is unknown**, not accepted.

The v13u router script attempted direct `ubus session.login` before applying HTTP configuration, despite that same authentication method already having timed out over HTTPS after a targeted `rpcd` restart. That call was not an appropriate deployment prerequisite. It was not proven to be the precise stall location because the router script did not output any early progress marker. Avoid making that claim.

**Stop/abandon the old v13u SSH run with Ctrl+C; do not replay it.** Corrected candidate v13v:
- `scripts/veci-v13v-http-no-auth-blocker-20261028.sh`: emits an immediate start marker, never calls `ubus` or tests login during HTTP reconfiguration. Before changes, detects old v13u backup and current config. If already correctly configured and uhttpd running, returns without a restart. If prior backup exists but current HTTP configuration is incomplete, **fails closed** to avoid overriding a partial old transaction. Otherwise stores original uhttpd config, binds HTTP on LAN `192.168.1.1:80`, disables forced HTTPS redirect, preserves HTTPS listener, restarts only uhttpd once, checks configuration and process, and provides `--rollback`.
- `scripts/veci-v13v-http-office-20261028.ps1`: stages the exact new script, runs `sh -n` before execution, then performs **one anonymous GET** of `http://192.168.1.1/veci/` with bounded timeout. This proves only local HTTP page delivery, not actual login.
- Source readback/contract checks passed for scope, staging pin, backup order, no `ubus session.login` calls, no `rpcd` or LTE restart, HTTPS retention and status-first handling. **No successful deployment or router integrity receipt has yet been observed.**

If the new script remains stuck before `VECI_V13V_STAGE=started_no_ubus`, focus on SSH command launch/authentication, not `ubus`. If it reaches an error/backup guard, stop and inspect that single state rather than running a second blind apply. The original login timeout may remain even when HTTP is reachable; fix the real auth backend separately. Restore HTTPS as the preferred transport after the authenticated login path is repaired because HTTP sends passwords without encryption.

## v13v preflight hang and v13w focused fix — 2026-10-28

User ran v13v and the last printed lines were:

```text
VECI_V13V_STAGE=started_no_ubus
VECI_V13V_STAGE=preflight_ok
VECI_V13V_OLD_BACKUP=absent
VECI_V13V_NEW_BACKUP=absent
VECI_V13V_HTTP_CURRENT=unavailable
VECI_V13V_REDIRECT_CURRENT=0
```

The v13v source places `uci get network.lan.ipaddr` and `ip -4 addr show` after the last line and before the `VECI_V13V_STAGE=backing_up` marker. This narrows the **likely** stall to one of those LAN preflight operations, not proven individually. No evidence of an HTTP configuration write or service restart was returned. Old script must be interrupted with Ctrl+C and never replayed.

**Corrected implementation:** v13w `scripts/veci-v13w-http-without-lan-probe-20261028.sh` (commit `00590af2c5156d8b8e5c1765d298d82ea2f1564b`), office wrapper `scripts/veci-v13w-http-office-20261028.ps1` (commit `293935b2320ac05a31711f783726a3b7fd15ca54`). Removes *all* direct ubus auth calls, `uci get network.lan.ipaddr` and `ip addr` checks from the HTTP path. The router is already reached via `root@192.168.1.1`. It guards against a prior v13u/v13v process still running and stale v13u/v13v backup files; it stages the original uhttpd config in a new private backup before changing only LAN HTTP listener and redirect. The HTTPS listener, `rpcd`, modem and LTE are untouched. It reports numbered progress stages, performs one uhttpd restart, one uhttpd config/process integrity gate, and one bounded anonymous HTTP GET expecting exactly 200 without redirect. Its static focused source contract passed.

**Status:** v13w source prepared; no live HTTP or login-fix claim yet. If a backup/process guard blocks, do not rerun installer. If the page is reachable on HTTP but `session.login` still fails, the true backend auth blocker requires its own scoped diagnosis. Never treat HTTP reachability as proof of successful login. HTTP credentials travel unencrypted even on a trusted LAN.

## v13w blocked by old process guard — 2026-10-28

Real owner terminal receipt:

```text
VECI_V13W_STAGE=download
VECI_V13W_STAGE=upload
veci-v13w-http-without-lan-probe-20261028.sh 100%
VECI_V13W_ACTION=Apply
VECI_V13W_STAGE=started
VECI_V13W_ERROR=previous_cutover_process_still_running
VECI_V13W_OFFICE=router_stopped_no_blind_retry
```

The second SSH password prompt authenticated; one failed password entry in the earlier SCP prompt was retried successfully. The v13w guard ran *before its backup and HTTP configuration changes*. Therefore **v13w did not apply** the HTTP change. Do not repeat v13w `Apply`, restart rpcd, or reboot the router.

A **single read-only exact process audit** was added at `scripts/veci-v13-exact-process-audit-20261028.sh`, commit `87fa13745abaa8f99279558939af175934a53ff3`. This inspects exact `/proc/<PID>/cmdline` arguments for v13u/v13v shell scripts, PID/PPID/state/wchan, existence of three transaction backups, and selected public `/etc/config/uhttpd` listener/redirect directives. Unlike the previous `ps | grep` guard, it cannot mistake a grep command line that mentions script names for the script itself. It does not kill or restart a process, change files, call `ubus`, or read account credentials.

The subsequent focused repair must either terminate only a confirmed stale old deployment script safely (after verifying no backup/config transaction in progress) or correct the guard if no exact script process exists. Do not apply another speculative HTTP cutover before this evidence.

Independent login failure: valid HTTPS `/ubus` endpoint answered `session.access` quickly, while dummy `session.login` timed out twice including after `rpcd` restart. Official OpenWrt `rpcd` code invokes UCI-backed login configuration processing. This means backend auth and configuration stalls may share a cause but the evidence **does not establish that**. HTTP listener recovery alone will not prove login is fixed.

## v13w exact process audit and v13x guarded cleanup — 2026-10-28

The owner ran the exact process audit and returned:

```text
VECI_V13_OLD_PROCESS=v13u;pid=6052;ppid=1;state=S
VECI_V13_OLD_PROCESS=v13v;pid=6081;ppid=1;state=S
VECI_V13_OLD_EXACT_PROCESS_COUNT=2
VECI_V13_BACKUP_v13u=absent
VECI_V13_BACKUP_v13v=absent
VECI_V13_BACKUP_v13w=absent
listen_https='0.0.0.0:443'
listen_https='[::]:443'
redirect_https='0'
ubus_prefix='/ubus'
VECI_V13_PROCESS_AUDIT=read_only_complete
```

This establishes that v13w's blocking guard reflected **real orphaned v13u/v13v shell processes**, not merely a grep false positive. It also establishes no HTTP listener and no transaction backups. The earlier v13u/v13v commands were stopped before any observed HTTP configuration write; production HTTP enablement is still **not confirmed**.

To complete the scoped change without rerunning the stale scripts, a one-shot v13x candidate was committed:
- Router: `scripts/veci-v13x-safe-orphan-cleanup-http-20261028.sh` (commit `37a3437ad2ee73a5ac1aa7332ab68370209e8bef`)
- Office: `scripts/veci-v13x-orphan-cleanup-http-office-20261028.ps1` (commit `2238f5178dbca5bf6d74e48800a0346558688e7c`)

The router script fails closed if old backup/staged files are present or the current `uhttpd` main configuration differs from the observed HTTPS-only/redirect=0 baseline. It validates the **exact PID, script argv, PPID=1, and state=S** for 6052 and 6081, revalidates argv immediately before sending **SIGTERM only to those PIDs**, and confirms they are gone. It performs no `killall`, router reboot or `rpcd` restart. Only then does it back up `/etc/config/uhttpd`, insert one `192.168.1.1:80` HTTP listener into the existing `uhttpd.main` UCI text configuration with a minimal AWK edit and atomic rename, preserve the existing HTTPS listeners, restart `uhttpd` once, and perform one integrity gate. It deliberately does not perform a UCI read, netlink probe or ubus login, which were the previously observed stall candidates. Office wrapper requires one HTTP 200 static page response with no redirect and does not send user credentials.

The exact AWK transformation was tested once on a fixture matching the audit's `uhttpd` listener and redirect directives, preserving the two HTTPS listeners and adding one LAN HTTP listener. The release source contract includes exact-PID kill scope, backup order, no UCI/network RPC calls, one restart and one final HTTP GET. This is **source-ready only**, not proven deployed until the owner returns `VECI_V13X_INTEGRITY=pass` and `VECI_V13X_HTTP=reachable`.

Separate outstanding root cause: `session.login` has timed out despite an `rpcd` restart. HTTP listener delivery does **not** fix or prove a real authenticated session. Keep actual account credentials out of scripts and diagnostics; investigate authenticated rpcd configuration separately after clearing orphan processes. HTTP sends credentials in plaintext on LAN.

## Owner-verified v13x production success — 2026-10-28 17:14 WIB

The owner's office PowerShell output **confirmed actual live HTTP cutover**:

```text
VECI_V13X_OLD_v13u=verified_orphan_pid_6052
VECI_V13X_OLD_v13v=verified_orphan_pid_6081
VECI_V13X_OLD_PROCESSES=cleared
VECI_V13X_STAGE=backup_original
VECI_V13X_STAGE=commit_http_config
VECI_V13X_STAGE=restart_uhttpd_only
VECI_V13X_HTTP_LISTEN=192.168.1.1:80
VECI_V13X_TLS_LISTENER=retained
VECI_V13X_LTE=unchanged
VECI_V13X_INTEGRITY=pass
VECI_V13X_HTTP_CONFIG=applied
VECI_V13X_HTTP_PAGE=http=200;seconds=0.727348;redirect=
VECI_V13X_HTTP=reachable
VECI_V13X_LOGIN=not_yet_verified
VECI_V13X_OFFICE=http_cutover_integrity_pass
```

**Status: HTTP access LIVE/PASS**, no redirect; old orphan processes cleared; HTTPS listener retained; LTE untouched. The original uhttpd configuration is backed up at `/etc/config/uhttpd.veci-v13x-original-20261028`. **Do not repeat any HTTP installer or kill the same PIDs again.** Separately, login status is **not yet verified**. Earlier HTTPS dummy `session.login` timed out even after rpcd restart. No actual VeCI credential has been tested successfully, and HTTP availability is not proof of authentication.

### Root-cause priority

OpenWrt `rpcd/session.c` uses `uci_alloc_context()` and `rpc_login_test_login()` followed by `uci_load(uci, "rpcd", ...)` before responding even to an invalid username. Both the frontend 10 s and curl HTTPS 12 s timeouts are therefore consistent with (though do not prove) a blocked UCI authentication configuration read. Earlier v13v stopped after printing HTTP UCI state and before `VECI_V13V_STAGE=backing_up`, at source lines that perform more `uci -q get` calls. The observed pair suggests investigating the UCI/rpcd configuration and any hung `uci` processes using one bounded read-only diagnostic, not repeating service restarts, HTTP cutovers or false frontend timeouts. Restrict diagnostics to counts/modes/process states; never expose auth hashes, tokens or actual user credentials.
