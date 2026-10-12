# On-demand SMS storage counters — device UAT pending

Date: 2026-10-12. **Source and offline mocked tests PASS**; this
SMS count feature has **NOT yet been run on physical W907-EC**.
Existing installed capability-only hotfix remains LIVE/PASS and unchanged.

## What it does

The source helper `veci-modem-capabilities` now has an *additional*
`storage` command (the installed immutable helper does NOT).
It issues precisely `AT+CPMS?` on the verified 05c6:902e USB 1.4 AT
port, under the existing nonblocking `/var/lock/we5927-at.lock`
whole-request lock, only after an explicit operator command.

A strict BusyBox awk parser reports only the first selected SMS memory
store, used count and capacity. It requires a valid 9-field response and
an `OK` terminal and rejects unsolicited lines, duplicated responses,
malformed bounds, inconsistent counts or partial output. It returns
no sender, message body, OTP, SMS PDU or raw serial output; no data are
saved persistently. No `AT+CMGL`, `AT+CMGR`, `AT+CMGS`, `AT+CMGD`
or `AT+CUSD=1` commands are issued.

CI: https://github.com/aicoach-alpha/zbt-we5927-openwrt/actions/runs/38220020943
=> 253/253 host regression tests PASS, including 15 SMS storage cases.
The earlier LIVE/PASS capability-only snapshot was frozen under
`scripts/veci-live-minimal/veci-modem-capabilities` and retains its
original SHA256, independent of the new helper source.

## Operator-only nonpersistent UAT

On **office Windows laptop SSH session** already connected to
WE5927 at 192.168.1.1, not on andre-nas:

1. Download a specific reviewed immutable repository commit of the
   new helper to **/tmp**. Do not overwrite /usr/libexec,
   /usr/libexec/rpcd or any ACL. Check shell syntax first.
2. Explicitly run `sh /tmp/veci-modem-capabilities storage`.
3. Record only sanitized JSON numeric output, with no raw AT bytes.
4. If read fails or `modem_busy`, do not retry automatically; check
   link health and report error. No SMS data was deliberately accessed.

The helper is not yet included in an on-device RPC upgrade. The new
source RPC's `messagingStorage` and ACL are staged for the next
separately reversible package; they have not been installed.
Full inbox reading, carrier USSD sessions and XL quota stay blocked
until their own explicit-consent, privacy and hardware UAT gates PASS.

Do NOT run sysupgrade or make any modem config changes as part of this
test. The old `/root/veci-capability-hotfix-rollback` must be preserved.
