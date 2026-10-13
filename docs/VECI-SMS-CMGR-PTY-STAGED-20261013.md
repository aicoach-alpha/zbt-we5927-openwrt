# VeCI WE5927 — consent-bound single SMS read: offline PTY integration

Date: 2026-10-13. **Development PASS; NOT ON ROUTER, NOT LIVE.**

## Starting baseline

- Physical WE5927 runs VeCI SMS Storage (CPMS) and manually consented SMS Inbox metadata (`veci.sms.listIndex`), confirmed five slot indexes 0–4.
- Owner's physical ACL audit: one rpcd login section with wildcard write permission; anonymous `veci.sms.listIndex` denied. A real restricted-account negative test was not performed.
- No change to existing router files, LTE, SMS status, USSD, or backups during this development.

## New source-only components

1. `source/we5927-lte/src/veci-sms-read-slot-policy.[ch]` — verified boolean input gate for an **already-authenticated** session, authentic CSRF proof, fresh per-slot consent, held serial lock, opened-FD identity and nonzero trusted generation + nonce. One slot, one issuance, no replay or automatic retry. The gate itself cannot validate credentials, create CSRF proof or derive trusted session IDs.
2. `source/we5927-lte/src/veci-sms-cmgr-frame.[ch]` — bounded incremental parser accepting only optional exact `AT+CMGR=<approved slot>` echo, one `+CMGR: <status>,,<length>` header, one matching PDU, and final `OK`. Rejects extra CMGL/CMGR, USSD/CMTI URCs, invalid status or length, incomplete stream and nonhex payload. Caps total stream at 8192 bytes and TPDU at 240 octets. GSM7/UCS2 PDU decoded in private memory only AFTER the policy completes and framing is final; unsupported 8-bit/binary DCS returns error. Wipes buffered PDU and temporary data after one result.
3. `source/we5927-lte/src/veci-serial-cmgr-pty-guard.c` — explicitly `VECI_ENABLE_OFFLINE_PTY_HARNESS` compiled only. Uses borrowed noncanonical PTY FD, caller-owned *mock* sysfs and test lock path. Acquires lock, validates vendor `05c6` / product `902e`, USB interface `1.4`, driver and opened FD; rejects preexisting input rather than flushing; sends one exact `AT+CMGR=<slot>` command; polls with fixed monotonic deadline; consumes the strict CMGR parser and unlocks on all paths. Never opens a physical modem port itself, runs on the router, touches SMS in production or logs sensitive data. Caller must wipe decoded result immediately after authorized foreground use.

## Host acceptance tests

- `tests/test_veci_sms_read_slot_policy.py` — 11 tests for all five required gates, wrong slot/session/nonce/epoch, replay and state zeroization.
- `tests/test_veci_sms_cmgr_frame.py` — 13 tests including valid GSM7/UCS2 synthetic content, fragmentation, invalid PDU, status, missing `OK`, unsolicited event, mismatched session, stream bounds and post-decode wipe.
- `tests/test_veci_serial_cmgr_pty_guard.py` — 10 tests using isolated pseudo-terminal and fake sysfs: one requested command, held flock, valid synthetic GSM7/UCS2, no command on absent approval/contended lock/incorrect modem identity, no replay after modem error or timeout, reject second record, harness compile disabled by default.
- **428/428 tests PASS** https://github.com/aicoach-alpha/zbt-we5927-openwrt/actions/runs/38340307316.
- Firmware integration CI **SUCCESS** https://github.com/aicoach-alpha/zbt-we5927-openwrt/actions/runs/38340311566; `INERT_BUILD_GUARD_PASS` confirms new modules remain disconnected from firmware.

## Security release blockers (DO NOT deploy readSlot yet)

- **Real rpcd authorization and CSRF:** derive browser user identity and validate actual effective restricted `readSlot` ACL per current session. The boolean flags and opaque nonce in the C guard are *not authentication*. Do not add `readSlot` to the existing `veci.sms.listIndex` method or broad generic write ACL.
- **Persistent one-use permission:** trusted server must generate one-time token and bind it to authenticated session, slot, modem generation and bounded expiry; consume before I/O, never accept token/flags merely because browser supplied them. Need replay/CSRF negative tests from real ubus session context.
- **Real serial trust:** verify live ttyUSB2 interface 1.4 under the actual shared `/var/lock/we5927-at.lock`, account for USB hotplug, SIM change and stale URCs. The PTY uses an explicitly mock sysfs and lock and cannot prove on-device lifecycle safety.
- **Sensitive browser data:** sender/text/OTP are sensitive; never place in logs, telemetry, status APIs, URLs, caches or browser persistence. Avoid storing SMS text in a general `veci.sms.listIndex` response. No automatic polling or message opening. No content is returned to router yet.
- **Physical read side effect:** `AT+CMGR` may turn unread SMS into read. Require fresh warning and deliberate approval of the exact slot before a physical read. No silently repeated reads or fallback to other slots.
- **Resource limit:** overlay RAM/flash is small; no Python/Node/daemon package for router. Release only after code-size/ABI check and hardware-independent rollback.

**Status:** metadata Inbox v1.3.1 LIVE/PASS; single SMS text/OTP decoding only in host test fixture; SMS send/delete/XL USSD still NOT LIVE. No WE5927 shell commands required in this stage.
