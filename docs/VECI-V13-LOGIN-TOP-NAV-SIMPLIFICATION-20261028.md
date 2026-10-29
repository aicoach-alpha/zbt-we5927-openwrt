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

## Post-HTTP login still timed out — 2026-10-28

After v13x produced `HTTP 200` and LAN HTTP was confirmed LIVE/PASS, owner reports the **same** VeCI login error `session.login timed out`. This demonstrates that changing HTTPS to HTTP **did not fix authentication**. Stop treating webserver listener/redirect as the login root cause. No further uhttpd cutover or rpcd restart is justified by this evidence.

Upstream OpenWrt rpcd `session.c`, `rpc_handle_login()` and `rpc_login_test_login()` call `uci_alloc_context()`, `uci_load(uci, "rpcd")` and iterate configured `config login` entries before rejecting even invalid credentials. This is consistent with the observed anonymous dummy login request timing out, independent of the user password. Local `uci` reads, especially the previously implicated `network.lan.ipaddr`, should be isolated next. This does **not** yet prove the UCI subsystem is the root cause.

Committed **one bounded read-only audit** at `scripts/veci-v13y-bounded-auth-uci-diagnose-20261028.sh` (commit `3d7e20a634031ce0cf4999638f9b6de03952d44f`). It counts rpcd login section/option presence without printing usernames, passwords, shadow hashes, tokens or sessions; checks rpcd process presence; then executes exactly three bounded `uci` operations, reporting `completed_rc_*` or `timed_out_terminated`, with exact child-only signal termination, not broad process kills or daemon restarts. This is not a production mutation; final output requires `VECI_V13Y_PRODUCTION=unchanged`.

Only after this receipt should the repair target the observed fault: malformed/missing UCI rpcd config or stalled UCI read, versus another internal rpcd/auth path. Preserve original authentication configuration and credentials; use backup + atomic repair and one final login integrity test. Do not insert a password bypass, create shared/blank credentials or make the router administration accessible from WAN. LAN HTTP is intentionally plaintext and should be limited to a trusted private network.

## v13y complete — UCI reads are healthy, isolate rpcd login branch (2026-10-28)

User's real v13y audit receipt:

```text
VECI_V13Y_RPCD_CONFIG_BYTES=172
VECI_V13Y_RPCD_LOGIN_SECTIONS=1
VECI_V13Y_RPCD_USERNAME_OPTION_COUNT=1
VECI_V13Y_RPCD_PASSWORD_OPTION_COUNT=1
VECI_V13Y_RPCD_PROCESS=running
VECI_V13Y_CHECK_rpcd_uci=completed_rc_0
VECI_V13Y_CHECK_network_uci=completed_rc_0
VECI_V13Y_CHECK_uhttpd_uci=completed_rc_0
VECI_V13Y_PRODUCTION=unchanged
```

This **falsifies** the earlier simplistic claim that plain command-line UCI reads are stalled. The root cause of `session.login timed out` remains open. Do not change credentials, reset ACLs, reinstall packages, restart services, re-apply v13x, or extend the browser timeout based solely on this receipt.

Upstream OpenWrt rpcd `session.c` shows the login handler immediately rejects missing username/password with invalid argument; for a structurally complete request, it runs `rpc_login_test_login`, loads the UCI `rpcd` package and compares username before password/shadow/crypt. One focused diagnostic distinguishes method dispatch from the credential lookup branch:

- New `scripts/veci-v13z-local-login-path-isolation-20261028.sh` (commit `be352afbb3bccd788fa065fa85c36d82e517ab74`).
- Direct local `ubus session login '{}'` (must return quickly as invalid argument, without UCI).
- Only if the empty-argument call completes, one direct local `ubus session login` with an intentionally nonexistent account and invalid dummy password, which cannot authenticate or create a session. No account credentials are read or printed.
- Each call has a ubus `-t 4` timeout and an independent 5-second shell watchdog with TERM of only its own spawned child; stops rather than issuing more calls if the first request stalls. The output is only status and exit code, never response payload, passwords or session tokens.
- If both direct calls return while HTTP/HTTPS login times out, investigate `uhttpd-mod-ubus` bridging. If empty arguments return but nonexistent-user lookup stalls, concentrate on rpcd's credential lookup context. If even empty arguments stall, inspect rpcd event-loop/ubus dispatch rather than the UCI data or crypt hash. A valid-user password/hash path is not tested.

Source is ready but not run on router. No mutation, no successful login claim. Leave HTTP reachable; local HTTP is plaintext. The future fix should have a backup and **one real login verification** without printing credentials.

## v13z receipt CORRECTION: exit code 7 means TIMEOUT (2026-10-28)

Owner terminal receipt:
```text
VECI_V13Z_EMPTY_ARGUMENTS=returned
VECI_V13Z_EMPTY_ARGUMENTS_CODE=7
VECI_V13Z_UNKNOWN_USER=returned
VECI_V13Z_UNKNOWN_USER_CODE=7
VECI_V13Z_PRODUCTION=unchanged
```

**Critical interpretation:** OpenWrt libubus defines `UBUS_STATUS_TIMEOUT=7`. The v13z script's `returned` label only indicates the *ubus client process exited*; it did **not** indicate that rpcd sent a method response. Both the missing-arguments login and nonexistent-user login timed out. Previous speculation that this proves only the HTTP bridge or frontend was at fault is **invalid**. Since the missing-arguments branch should synchronously reject as `UBUS_STATUS_INVALID_ARGUMENT=2` before any UCI/auth lookup, the evidence points to session-method RPC dispatch/service responsiveness rather than solely password verification. Plain UCI reads completed normally in v13y.

Next single diagnostic **not another login test:** `scripts/veci-v14a-rpcd-session-responsiveness-20261028.sh`, committed `613319cc4754a2153acae9bc0d2f4a9505f5ab91`. It outputs the current rpcd PID/state/wchan/threads, then runs just two bounded, privacy-safe direct RPCs: `session.access` and `session.list` with a 3-second CLI timeout each. All response bodies (including session IDs) are suppressed. Exit code 7 is explicitly reported as timeout; code 0 or expected permission/argument errors show the service replied. No restart, credentials, session destruction, UCI modification or modem action. If both other methods also time out, investigate general rpcd event-loop/plugin blocking; if they return, investigate session.login handler dispatch. Neither scenario is yet proof of the exact root cause. Do not repeat rpcd restart, v13x HTTP install or old dummy login probes. The office owner must execute this narrow check to supply runtime evidence.

## v14a runtime diagnosis — rpcd PID 1017 in D state (2026-10-28)

Real operator terminal receipt:

```text
VECI_V14A_RPCD_PROCESS=pid:1017,state:D,threads:1,rss_kib:1748,wchan:unavailable
VECI_V14A_RPCD_PID_COUNT=1
VECI_V14A_CHECK_SESSION_ACCESS-CODE=7
VECI_V14A_CHECK_SESSION_ACCESS=timed_out
VECI_V14A_CHECK_SESSION_LIST-CODE=7
VECI_V14A_CHECK_SESSION_LIST=timed_out
VECI_V14A_PRODUCTION=unchanged
```

**Strong finding:** rpcd's one observed process is in kernel `TASK_UNINTERRUPTIBLE` (D), and not merely the login method: both unrelated `session.access` and `session.list` time out with ubus code 7. The normal CLI UCI package lookups in v13y were successful. The root cause is therefore **not explained by incorrect password, HTTP redirect, or slow frontend JS**. There is not yet evidence of *which* kernel subsystem or device is blocking rpcd. Do not assert it is USB/ttyUSB3, flash or a specific driver until kernel evidence establishes it. A SIGKILL on a D-state task normally cannot take effect until its kernel wait finishes. Another `rpcd` restart, password reset, reinstall, v13x HTTP cutover or web timeout increase is not justified.

**Next one targeted diagnostic, source committed and readback-gated:**
`scripts/veci-v14b-rpcd-d-state-kernel-snapshot-20261028.sh` (commit `b6cf8f2e7f8258dd55c3deec02a0f7cc79e4990f`). The script:
- Verifies exact board, firmware, PID 1017 identity (`/proc/PID/comm`), and current D state to avoid misattributing an exited/recycled process.
- Reads `/proc/1017/stack` and `/proc/1017/wchan` (may be unavailable depending on kernel options) and numeric `/proc/1017/syscall`; shows only if rpcd has any `/dev/ttyUSB*` or `/dev/ttyACM*` FDs open.
- Reads up to 24 already-existing **kernel** messages matching blocked I/O/USB/MTD/flash/hung task terms. Does not run SysRq, modify procfs, signal processes, restart any service, rebind USB, edit firmware, send auth requests, or change LAN/LTE.
- Explicitly reports `VECI_V14B_PRODUCTION=unchanged`. This does not itself fix login.

If the kernel stack identifies a recoverable device driver wait, plan the smallest device-specific remediation **with internet interruption/rollback risk clearly disclosed**. If rpcd remains D-state and cannot resume, restoring management may require a controlled maintenance reboot; this is an outage decision and not an unannounced automatic action. Do not call login PASS until one real browser session is authenticated.

## v14b accepted: rpcd blocked in MIPS sendmsg(fd=7) — 2026-10-28

Real read-only kernel snapshot from the owner:

```text
VECI_V14B_PROCESS=rpcd_1017_verified
VECI_V14B_RPCD_STATE=D
VECI_V14B_RPCD_PARENT=1
VECI_V14B_RPCD_RSS_KIB=1748
VECI_V14B_RPCD_THREADS=1
VECI_V14B_STACK=not_available
VECI_V14B_WCHAN=not_available
/proc/1017/syscall: 4179 0x7 0x7fbccdd0 0x0 0x0 0x0 0x0 0x7fbccd00 0x77dfab34
VECI_V14B_RPCD_SERIAL_FD_COUNT=0
VECI_V14B_PRODUCTION=unchanged
```

Linux MIPS o32 `__NR_Linux=4000` offset 179 = `sendmsg`, first argument `0x7` = file descriptor **7**. **The kernel was blocking rpcd while sending data on descriptor 7.** The descriptor has not been resolved to a particular socket endpoint; do not claim it is ubus, USB, cellular modem, JFFS2, or filesystem without further evidence. `rpcd` had no open `ttyUSB*`/ `ttyACM*` FDs at snapshot time, and the kernel log excerpts had only normal early-boot USB enumeration/JFFS2 messages, not new blocked-task details. This is consistent with an IPC/socket bottleneck but does not prove the peer.

Direct RPC `session.login`, `session.access`, and `session.list` all timed out with ubus 7 while the RPCD task remained `TASK_UNINTERRUPTIBLE`. Restarting rpcd previously did not recover its operation. **Do not repeat rpcd kill/restart, HTTP cutover, password reset, UCI diagnostics, or synthetic auth probes.**

**Recovery recommendation:** The fastest practical path back to functional administration is a **single owner-initiated controlled router reboot during an approved network maintenance window**, after ensuring the office can tolerate temporary LTE/Wi-Fi downtime. Use the *normal* OpenWrt `reboot` mechanism preceded by `sync`; do not use `reboot -f`, SysRq, raw USB reset, firewall restart or power pull as routine fixes. A reboot might restore rpcd but is **not proven as a permanent kernel/socket bug fix**. The user should check the normal VeCI login once afterward and report whether it works, using the already LIVE `http://192.168.1.1/veci/` only on a trusted LAN. The existing fast LTE watchdog configuration `10s × 3` was already committed to persistent UCI; no change necessary. If reboot fails/hangs, do not chain attempts without observing the state. Keep original uhttpd config backup at `/etc/config/uhttpd.veci-v13x-original-20261028`, preserve HTTPS listener, and do not expose HTTP over WAN.

This state has **not** yet been rebooted or validated by an actual authenticated VeCI session. Remediation/long-term prevention remains OPEN until post-reboot login and recurrence evidence. A later recurrence warrants capturing descriptor 7's socket inode/peer and kernel-blocked stack under appropriate kernel debug support, then investigating rpcd/ubusd socket backpressure and vendor package patches without destabilizing live service.

## 2026-10-29 — HTTPS LOGIN RECOVERED; HTTP login still browser NetworkError

User has now **successfully logged into VeCI through HTTPS**, while `http://192.168.1.1/veci/` opens the login page but Firefox shows `NetworkError when attempting to fetch resource` after sign-in. This **supersedes the earlier general login-down status**: functioning HTTPS session authentication shows `rpcd session.login` has recovered sufficiently to authenticate users. It does not establish why the previous D-state `rpcd` process had hung or whether any kernel bug is permanently repaired.

Prior verified v13x HTTP cutover established LAN GET /veci HTTP 200 no redirect; this does **not** prove HTTP POST /ubus works or Firefox permits that HTTP subrequest. VeCI frontend source excerpt from the owner's original archive confirms `fetch('/ubus', {method:'POST', ...})` and a 10 s AbortController timeout. Firefox may upgrade or block insecure HTTP subrequests due to HTTPS-Only, CSP upgrade-insecure-requests, an extension, or a failed same-origin POST. These are hypotheses, not diagnoses.

**One targeted no-credential office probe committed**: `scripts/veci-v14c-http-ubus-browser-path-office-20261029.ps1`, commit `2c76f8a54970e09cab8072cbba9929ea22a055eb`. It makes one HTTP GET of the static VeCI page and one anonymous `session.access` JSON-RPC POST over HTTP with the all-zero session ID, with explicit 8 s timeout, no redirect-follow, header inspection for Location/CSP/HSTS/CORS and only summarized JSON-RPC code (no raw response, username, password, login or session ID). Reads only; no SSH, service restarts, router changes, credential entry or firmware modification. It deletes temporary request/response files after the check.

- If HTTP POST responds with valid JSON-RPC and no redirect while the actual Firefox login fails, focus on browser HTTP-only exception / security policy or actual POST request in Firefox Network panel, not on rpcd or uhttpd restarts.
- If HTTP POST fails or redirects while HTTP GET succeeds, inspect the HTTP uhttpd-mod-ubus route and request headers.
- Avoid enabling `ubus_noauth`, or blanket CORS to work around login: those could expose administration unauthenticated or cross-origin. Always retain HTTPS admin access. HTTP sends credentials without encryption, even on LAN; returning to HTTPS should remain the preferred secure configuration.

Owner requests for native top menu and removal of failed USSD/carrier quota still open; local Data Meter and fast reconnect remain retained.

## 2026-10-29 — HTTP TCP/80 unreachable after reboot; HTTPS login healthy

Observed after the earlier recovery reboot: the user confirms VeCI admin **logs in successfully via HTTPS**, while HTTP cannot log in. A focused Windows curl check provides the decisive transport failure:

```text
VECI_V14C_PAGE_TRANSPORT_EXIT=7
VECI_V14C_PAGE_HTTP=http=000;seconds=2.063857
VECI_V14C_UBUS_POST_TRANSPORT_EXIT=7
VECI_V14C_UBUS_POST_HTTP=http=000;seconds=2.058764
VECI_V14C_UBUS_JSON=no_json_response
VECI_V14C_ROUTER=unchanged
```

**Interpretation corrected:** This is not a Firefox HTTPS-Only/CORS/credential failure. The office computer cannot establish TCP to `192.168.1.1:80`, so HTTP login never reaches ubus. HTTPS remains healthy; rpcd/auth is now functional. Earlier v13x proof of HTTP 200 was **before reboot** and did not establish reliable boot-time binding.

**Upstream evidence:** OpenWrt issue `openwrt/openwrt#18551` (https://github.com/openwrt/openwrt/issues/18551) documents exactly this boot ordering defect: uhttpd bound to a specific LAN IPv4 can attempt bind before LAN IP assignment, fail with EADDRNOTAVAIL, and leave no IPv4 listener after boot. A later version of `openwrt/uhttpd` `listen.c` uses IP_FREEBIND to address the startup race, but we have not verified whether the router's installed uhttpd binary includes that code. We must not claim that this is proven without a live bind/error log.

**Source-ready v14d durable correction:**
- Router installer `scripts/veci-v14d-lan-http-boot-rebind-20261029.sh` commit `4a3871e0af47e28cf5cafe2b8161602697d1337d`.
- Office wrapper `scripts/veci-v14d-http-rebind-office-20261029.ps1` commit `fd55ec31e810572d06d9c2c14836d724ec0d7bdc`.
- Reads only actual `/etc/config/uhttpd` to gate on one `uhttpd.main`, working HTTPS configuration, and `redirect_https=0`. Refuses unknown/wildcard listener or prior transaction; creates a new backup and only restores/adds `192.168.1.1:80` to the existing main webserver config if missing. No `0.0.0.0:80` exposure and no firewall modification. Preserves all HTTPS, authentication and LTE configuration.
- Installs `/etc/hotplug.d/iface/95-veci-http-lan-rebind` for LAN `ifup|ifupdate` only, with /proc/net/tcp socket check and one tmp lock; webserver restart is attempted only when the specific TCP/80 listener is absent. The deployment itself restarts **uhttpd once** to bring HTTP back immediately; if the new listener remains absent, it automatically removes the LAN hook, restores the original uhttpd config and attempts one rollback restart. Explicit rollback is also supported.
- The wrapper checks one HTTP page, HTTPS page, and credential-free HTTP `/ubus` JSON-RPC transport after apply. It never sends a real password or user session. Repo source/contract readback PASS, but **router production has not yet received v14d**.
- **Do not mark HTTP after-reboot reliable** based on the post-apply check alone. The hook is a persistence mechanism; verification of survival through a later natural/authorized reboot is still outstanding. Do not force a repeat reboot solely for UAT.

The user requested that HTTP be restored; HTTP is plaintext on LAN and should not be exposed beyond trusted access. Retain HTTPS as secure administrative fallback. Other open work remains horizontal top nav and retiring the abandoned USSD/operator quota features, retaining local Data Meter.
