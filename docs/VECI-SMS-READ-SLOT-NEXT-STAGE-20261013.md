# VeCI WE5927 — next stage: consent-gated single SMS read (NOT LIVE)

Date 2026-10-13. Physical device already has metadata-only Inbox v1.3.1 LIVE/PASS, including five SMS slots 0..4, no sender/content exposed. LTE remains online.

## Release gates before reading content

1. **Effective authorization negative test:** `veci.sms.listIndex` is a method protected by write ACL, not automatically an admin-only method. `id -u=0` in rpcd merely describes rpcd privilege; it is not the authenticated user's identity. Review actual rpcd login/ACL assignment without copying password hashes or session tokens to logs/chat. Demonstrate a least-privileged session is rejected with ubus access denied and a valid privileged session permitted, without issuing another real SMS list.
2. **No privilege escalation via UI:** A checkbox/modal alone is UX, not authorization. The server must enforce a separate restricted `readSlot` permission and an exact per-action consent token tied to a current session / request; do not rely on client-supplied flags alone as an access policy.
3. **Transport:** Keep shared full-session AT lock; prevent ttyUSB3, verify USB interface 1.4 05c6:902e using opened descriptor rather than only sysfs precheck; quarantine stale responses/hotplug changes. No silent fallback to another modem or port.
4. **Sensitive payload:** `AT+CMGR=<index>` may mark unread SMS as read, and returned PDU can contain OTP, financial messages, passwords and identifiable sender numbers. Treat all as sensitive. Show only after fresh foreground consent, never poll/auto-preview, don't include sender/body in `smsStorage`/`status`/`listIndex` or unsolicited notifications.
5. **Bounded decoding:** exact selected index 0..65535, PDU length and stream size caps, final OK required; text-only support for validated SMS-DELIVER GSM7/UCS2 with safe handling of multipart; unsupported binary/8bit/compressed DCS should return `unsupported_encoding`, not raw hex. No unbounded JSON/HTML.
6. **No persistence or leakage:** no message text, sender, OTP or PDU in syslog, shell tracing, querystring, localStorage/sessionStorage, CSV, cache or server-side files. Display selected message only with DOM `textContent` and clear on navigation, logout or new selection. Avoid putting sensitive content into analytics.
7. **Side effects:** show the explicit warning that reading selected SMS may change unread to read, with two-step confirmation per slot and no retry that may repeat state change. Rate-limit calls and reject busy modem rather than queueing unapproved operations.
8. **Rollback:** preserve all backups v1/v2/v1.2/v1.3/v1.3.1, and current v1.3.1 UI and `veci.sms.listIndex` ABI. New read capability must be a separate source-only development until sanitizer fuzz/PTY/rpcd ACL tests pass; no firmware flashing or LTE restart.

## Useful UAT without reading any real SMS

- Confirm `ubus -v list veci.sms` advertises `listIndex` and no `readSlot` yet. Do NOT call `listIndex` again just for registration checks.
- Confirm root admin session is privileged with `session access` checks, and a temporary least-privileged account session has `access:false` to `veci.sms.listIndex`. Never paste a live ubus session ID or credentials in a chat/report.
- Verify SMS storage count button remains independent and LTE Internet reachable. Clicking storage reads CPMS only; it does not read any SMS bodies.

## Release states

- SMS Storage v1.2 and metadata-only Inbox v1.3.1: **LIVE/PASS on real WE5927**.
- Privileged negative ACL check: **NOT VERIFIED**.
- Body/sender/OTP reading: **NOT IMPLEMENTED/LIVE**.
- SMS send/delete and XL USSD interaction: **NOT IMPLEMENTED/LIVE**.

Evidence: `docs/VECI-SMS-INBOX-INDEX-V13-UAT-20261013.md` and PR #4.
