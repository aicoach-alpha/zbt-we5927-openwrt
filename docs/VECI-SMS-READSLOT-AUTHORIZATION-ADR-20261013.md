# ADR: safe per-session SMS readSlot authorization on WE5927

Date: 2026-10-13. Status: **DEVELOPMENT DECISION / NOT LIVE**.

## Physical baseline

- Owner's ZBT WE5927 runs VeCI Cellular storage count and metadata-only SMS Inbox v1.3.1; both LIVE/PASS, 5 metadata slots observed. LTE online. No SMS text, sender or OTP is accessible in the existing browser.
- Physical `/etc/config/rpcd` *redacted* ACL audit: one configured rpcd login section with `write '*'`; an all-zero anonymous session is denied to `veci.sms.listIndex`. This does not prove authorization of a nonexistent non-admin account.

## Critical source-level finding: rpcd exec plugin does not know the caller session

- VeCI browser `veci/js/lib/api.js` sends JSON-RPC with an authenticated `ubus_rpc_session` as `params[0]` to `/ubus`.
- uhttpd checks the session's ACL before invoking ubus methods, see https://openwrt.org/docs/techref/ubus . This is the real effective access gate for current `veci.sms.listIndex` over HTTP.
- However `rpcd/plugin.c` (upstream `openwrt/rpcd`), inside `rpc_plugin_call`, uses `blobmsg_format_json(msg, true)` as the child executable's *entire input*, with argv `plugin call <method>`. It does NOT add the originating browser session ID or an authenticated principal to executable stdin or argv. See https://github.com/openwrt/rpcd/blob/master/plugin.c . The exec plugin receives only declared ubus method arguments.
- Therefore **do not treat an arbitrary browser-submitted `ubus_rpc_session`, `is_admin`, `csrf_verified` or consent flag as a trusted identity assertion** in a root shell executable. Calling `ubus session access` on a claimed session ID alone cannot prove it belongs to this invocation.
- Real `/ubus` ACL method permission remains effective, but it does not solve an internal cross-request trusted session-binding requirement by itself.

## Implementation added on development branch, not shipped

- `source/we5927-lte/src/veci-sms-read-capability.[ch]` adds a tiny C-only, RAM-only one-use capability with **16-byte trusted session binding** and **16-byte cryptographic nonce** (random bytes supplied by a trusted server), bound to exact slot number (0..65535), modem generation and a bounded monotonic clock TTL (max 30 seconds).
- It requires caller-supplied *already-verified* ACL, CSRF and fresh explicit per-slot consent. The library does not and cannot establish any of those from untrusted input.
- The single-use token is consumed and its private bytes wiped **before any modem I/O**, including on incorrect token/session/slot, expiry, clock rollback or USB generation mismatch; there is no automatic retry/re-arm.
- This remains one-process in-memory state. Because rpcd *exec* scripts are a new process for each method, the in-memory capability cannot be shared across separate `armRead` and `readSlot` exec invocations. A future trusted persistent service, native process context, or short-lived securely locked tmpfs store is required. No new daemon is approved for the WE5927's constrained RAM without resource review.
- The code itself performs zero modem I/O and is not linked into the OpenWrt firmware.

## Non-negotiable production contract

1. **Trusted authentication boundary**: use a component that can verifiably bind an authenticated `/ubus` session to the actual request (e.g. a verified front-controller passing cryptographically attested context, or a native integration with documented session provenance). Do not simply pass the browser's claimed session ID to a root exec handler.
2. **Separate ACL**: create a restricted method `veci.sms.private.readSlot` instead of adding sensitive reads to the existing `veci.sms.listIndex` API or a general read/public ACL. Ensure anonymous or restricted accounts have no access, and test access with real least-privilege account when supported.
3. **Consent**: exact slot selected and two-step human confirmation in UI. The server maintains a one-use nonce with expiry and consumes it before the AT command; no invisible list refresh, no retry, no auto-open.
4. **Modem**: keep exclusive `/var/lock/we5927-at.lock` for full transaction, verify opened ttyUSB2 FD physical VID `05c6`, PID `902e`, interface `1.4`, and reject stale URCs/hotplug/SIM changes.
5. **Privacy**: do not surface SMS sender, body, OTP or PDU in metadata API, syslog, URL, browser storage, generic support bundle or history. Render selected text only after its own approval using `textContent`; wipe buffers immediately upon navigation/logout.
6. **Minimal platform changes**: independent backup/rollback, no LTE restart, no new daemon or data connection to owner NAS. Prefer firmware-safe small C and BusyBox.

## Evidence

- Source-only capability unit tests, **12 new tests PASS**, cumulative **440/440 offline PASS**: https://github.com/aicoach-alpha/zbt-we5927-openwrt/actions/runs/38342460013
- Previous complete mock PTY SMS read + PDU decoder tests, **428/428 PASS**: https://github.com/aicoach-alpha/zbt-we5927-openwrt/actions/runs/38340307316
- Firmware inert-build check PASS: no `readSlot` module linked or callable on physical router.

## Release decision

**GO** for source-only security and modem-PTY development. **NO GO** for production activation of SMS body/sender/OTP read until verified user principal/session propagation across rpcd security boundary and cross-request token persistence are implemented. Current v1.3.1 production metadata UI remains LIVE/PASS with no changes. This is a real release blocker, not something that more unit tests alone can resolve.

## 2026-10-13 follow-up: cross-process single-use tmpfs store (SOURCE-ONLY)

The isolated C library `veci-sms-read-cap-store.[ch]` stages one pending
capability in a caller-created private 0700 tmpfs directory. Each independent
rpcd process opens the directory itself. An exclusive nonblocking `flock`
on the directory serializes create/consume; `openat` uses
`O_CREAT|O_EXCL|O_NOFOLLOW` for create and `O_NOFOLLOW` for consume.
Owner, mode, tmpfs filesystem and file type are validated. The entire
record is removed before validating the session/nonce/slot/generation/TTL:
failed attempts burn the token. No auto retry or SMS body is persisted.
Only one armed request per device; a failed/unconsumed one does not silently
re-arm. RAM-backed file storage is not a permanent daemon or flash write.

**Security limitation NOT FIXED by this stage:** No caller with verified
session provenance exists yet; the store deliberately does NOT trust or
derive a browser principal. The existing exec-plugin `rpcd` cannot infer
the session from method args. Frontend consent flags are not proof of
authorization. This source must NOT be linked into deployed firmware or
a new private ubus RPC until a trusted per-request authentication boundary
and least-privileged negative ACL test have been established.

UAT: host-only tests for tampering, competing processes, symlink,
non-tmpfs rejection, expiry and one-use behavior; firmware inert-build CI.
No actual WE5927 modem command, router deployment, reboot or flash.

Expired pending capability is reclaimed ONLY on a newly validated, fresh `store_arm` consent request under the same flock; active tokens cannot be overwritten. Malformed/corrupt records do not permit automatic replacement. This prevents expired tokens from permanently blocking future approved reads without allowing silent re-arm.

## Additional ucode boundary research

See [VECI-SMS-UCODE-SESSION-BOUNDARY-20261013.md](VECI-SMS-UCODE-SESSION-BOUNDARY-20261013.md). An upstream `rpcd` ucode plugin can inspect the **ubusd Unix peer** (`request.info.acl.user`), and OpenWrt `uhttpd` adds `ubus_rpc_session` to a forwarded /ubus call after its ACL check. A source-only, no-modem ucode audit prototype now checks the tuple with an additional `session.access` lookup. Native root ubus calls can provide their own SID, so this is not yet a trusted per-browser identity bridge, and physical proof with restricted HTTP sessions is still required before any readSlot release.
