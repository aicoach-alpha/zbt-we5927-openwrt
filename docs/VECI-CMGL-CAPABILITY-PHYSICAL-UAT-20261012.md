# SMS Inbox Capability Test — WE5927 (operator-only read-only UAT)

Date 2026-10-12. Scope: one 3GPP SMS command **test**, no SMS listing.

## Verified physical baseline

- Operator via office Windows SSH to WE5927 at 192.168.1.1 ran immutable script veci-messaging-readiness-ondevice.sh.
- Actual device response: {"ok":true,"source":"read_only_at","sms_mode":"pdu","charset":"IRA"}.
- This means PDU is already active; avoid changing AT+CMGF or AT+CSCS.
- Previous LIVE/PASS methods: messagingCapabilities and messagingStorage. SMS slots ME 5 used / 255 capacity when last checked.
- Prior overlay backups /root/veci-capability-hotfix-rollback and /root/veci-storage-hotfix-rollback must remain intact.

## Important state mutation

3GPP TS 27.005 clause 4.1 defines **AT+CMGL listing** as returning
entire SMS PDUs and marking received unread SMS as read. It is
therefore NOT an observational-only operation, despite being an AT query.
Authoritative reference: https://www.etsi.org/deliver/etsi_ts/127000_127099/127005/18.00.00_60/ts_127005v180000p.pdf

The completely DIFFERENT command AT+CMGL=? is the documented TEST
command: it returns supported SMS status values and DOES NOT list
messages or change their unread flags. This is the only AT command
allowed for the next physical UAT.

## Reviewed nonpersistent diagnostic

Immutable commit: 479ed78c797962a26395f5184809f57b56a41e01
Path: scripts/veci-sms-list-command-preflight.sh

Run from router SSH (NOT Windows PowerShell, NOT andre-nas):

    cd /tmp
    wget -O veci-sms-list-command-preflight.sh \
      https://raw.githubusercontent.com/aicoach-alpha/zbt-we5927-openwrt/479ed78c797962a26395f5184809f57b56a41e01/scripts/veci-sms-list-command-preflight.sh
    sh -n veci-sms-list-command-preflight.sh && \
      sh veci-sms-list-command-preflight.sh

This script checks board zbtlink,zbt-we5927 and sysfs ttyUSB2 interface 1.4
with USB VID:PID 05c6:902e. It requires the shared nonblocking
/var/lock/we5927-at.lock and issues ONLY 'AT+CMGL=?', no setting changes.
The response grammar parser recognizes only a single supported-status
parenthesized line followed by final OK; it returns only a fixed label.

Possible JSON format: {"ok":true,"source":"read_only_at_test",
 "cmgl_test":"accepted|unknown","sms_messages_accessed":false}

Unknown is conservative: it does NOT prove CMGL unsupported. Fail closed.
No SMS text, OTP, number or raw PDU is ever emitted.

## Verified offline gates

- 314/314 host tests PASS: https://github.com/aicoach-alpha/zbt-we5927-openwrt/actions/runs/38225842229
- This count includes eight tests for the new CMGL test parser, and
  three additional tests enforcing separate user acknowledgment of the
  CMGL unread-to-read side effect and clearing sensitive buffers.
- CI confirms SMS/USSD native sources are NOT linked into production.

## Status

**OPERATOR-OBSERVED PHYSICAL UAT: PASS — 2026-10-12.**
The owner ran the exact source-pinned script from commit
`479ed78c797962a26395f5184809f57b56a41e01` on the WE5927
through office-laptop SSH. The 2,013-byte file was downloaded; shell
syntax validation succeeded; physical read-only command returned:

```json
{"ok":true,"source":"read_only_at_test","cmgl_test":"accepted","sms_messages_accessed":false}
```

This proves the modem accepted the 3GPP CMGL TEST command only.
It **does not** prove SMS listing has been run, any inbox contents were
retrieved, or that the modem would preserve unread flags on actual list.
No authorization to read the actual SMS inbox or conduct a USSD session.
No third hotfix, no new RPC method, no flash or reboot is needed for this test.
After this test, privileged UI consent and whole-session transport must
still be built and physically validated before SMS inbox is LIVE.
