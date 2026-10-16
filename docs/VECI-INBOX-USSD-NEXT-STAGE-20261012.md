# VeCI SMS Inbox + XL USSD — next integration gate (12 Oct 2026)

## Existing live baseline — KEEP INTACT

- Operator executed two reversible overlays on the actual WE5927 through office Windows laptop SSH to 192.168.1.1, not andre-nas.
- LIVE PASS: veci.cellular messagingCapabilities (four read-only 3GPP AT test features supported), and messagingStorage (read-only ME used=5, total=255).
- Existing status, reconnect, switchSim(String) functional. Overlay about 1.7 MiB free. No firmware flash or reboot.
- Keep BOTH recovery directories: /root/veci-capability-hotfix-rollback and /root/veci-storage-hotfix-rollback.
- NOT LIVE: SMS inbox, send/delete, interactive USSD, XL remaining quota.

## Development stage A — SMS PDU inbox index (INERT / offline PASS)

- source/we5927-lte/src/veci-sms-inbox-index.c and .h
- 17 new native tests in tests/test_veci_sms_inbox_index.py.
- Bounded 16 records, only SMS slot index, numeric status, TPDU length; NO message text, sender or OTP retained or returned.
- Parses only strictly bounded PDU-mode CMGL response fragments; exact final OK required to reveal any entries. Refuses duplicate indexes, malformed PDU, text-mode records, unknown/unsolicited URC, post-terminal bytes and truncated streams. Clears data on errors and after use.
- Requires approval flag=1 from a future trusted caller; this is NOT in itself authentication. Server-side owner login, elevated ACL, CSRF, per-action consent and physical modem identity checks remain mandatory.
- Important: on some modems CMGL listing can mark unread SMS as read. No real inbox list may run before evaluating this side effect and informing the user. PDU mode must be temporary and reliably restored under the shared modem lock.
- This parser has NO serial I/O, no ubus endpoint, no daemon, no logging and is NOT installed in live firmware.

## Development stage B — XL USSD consent (INERT / offline PASS)

- source/we5927-lte/src/veci-xl-ussd-consent.c and .h.
- 13 new host tests in tests/test_veci_xl_ussd_consent.py.
- XL official post published 16 September 2026 confirms the *808# menu for quota:
  https://www.xl.co.id/blog/cek-kuota-xl-paling-mudah-ada-yang-baru-lewat-dial-number
- Begins only when the SIM is verified to be XL and the authenticated user explicitly consents to exact *808#; no arbitrary USSD commands.
- Interactive menu entries require a fresh action for EACH numeric choice, a matching unique session generation, and at most six steps. Never auto-select a menu option, buy services, retry USSD or store returned content.
- Menu order can change and may include chargeable purchases. Always show the actual modem menu and ask the user to select the exact action; do not hardcode menu numbers.
- The current on-device AT+CUSD=? test is an ability signal only. Actual network USSD responses, async URCs and DCS remain untested.
- This module has NO modem/network I/O, so XL quota is NOT LIVE.

## Required third-rollout gates

1. Preserve the existing v2 live RPC and its independent rollback backups.
2. Build one full-session, native bounded serial transport, opened-FD attested to USB 05c6:902e / interface 1.4 / ttyUSB2 and exclusive we5927-at.lock over setup, request and response. Never ttyUSB3.
3. Validate authentication, CSRF, explicit user action and elevated RPC permission for each inbox/USSD operation; never expose raw modem AT or OTP to ordinary dashboard polling.
4. Ensure no raw SMS/USSD content enters logs, telemetry or external servers. No automatic OTP capture.
5. Mock lock contention, timeout, cancel, late URCs, corrupted frames, SIM change and rollback; then perform operator-approved actual modem UAT before activating either feature.
6. Keep a separate General firmware and Indonesia operator-profile edition sharing the compact base implementation; router must work offline without private companion infrastructure.

## Verified CI

293/293 host unit regressions PASS on workflow run:
https://github.com/aicoach-alpha/zbt-we5927-openwrt/actions/runs/38223303584

The CI also states that optional SMS/USSD native sources are not linked into the firmware. This PASS is development-only, not permission to flash or use the modem for inbox/USSD yet.
