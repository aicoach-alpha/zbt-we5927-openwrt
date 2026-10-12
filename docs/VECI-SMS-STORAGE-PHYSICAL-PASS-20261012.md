# WE5927 SMS storage read-only physical UAT — 2026-10-12

Operator-reported hardware test via Windows office laptop SSH,
WE5927 at 192.168.1.1; no assistant access to router and no firmware
flash or LTE/SIM/network mutation.

## Command executed

On 12 Oct 2026, operator downloaded the 6,367-byte source-only helper
`source/veci-cellular-we5927/files/usr/libexec/veci-modem-capabilities`
from immutable commit
`1536d37daca6d634af4bd33462dbcaec96aa9fa8` to
`/tmp/veci-sms-storage-test` and ran the syntax check and explicit
one-time command:

```sh
sh -n veci-sms-storage-test && sh veci-sms-storage-test storage
```

Observed sanitized physical modem response:

```json
{"ok":true,"state":"queried","source":"read_only_at_cpms",
 "memory":"ME","used":5,"total":255}
```

Meaning: modem-selected ME storage had five slots used of 255 at the
time of the query, i.e. 250 available. The source issues only the
read-only SMS storage command `AT+CPMS?` under the shared modem lock.
No SMS contents, sender phone numbers, PDU, or OTP were read or
included in returned data. No USSD session was executed.

## Feature status boundaries

- Original owner-run capability diagnostics via ubus
  (`messagingCapabilities`) remain **LIVE/PASS**.
- Explicit helper CLI count check from `/tmp` is now
  **PHYSICAL-UAT PASS**, not merely CI PASS.
- Persistent `messagingStorage` RPC and ACL are **NOT LIVE** yet.
- The separate v2 overlay installer has a pinned payload commit,
  SHA256 validation, legacy RPC schema/status checks, persistent v1
  backup in `/root/veci-storage-hotfix-rollback` and rollback on
  failed registration/health. The previous capability-v1 backup
  `/root/veci-capability-hotfix-rollback` must not be overwritten.
- Offline v2 installer regression: 263/263 checks PASS at
  https://github.com/aicoach-alpha/zbt-we5927-openwrt/actions/runs/38221235586
  (includes 15 storage tests and 10 v2 rollback/manifest tests).
- Inbox contents, SMS send, interactive USSD, XL quota, firmware
  upgrade and recovery/power-loss UAT remain **NOT LIVE / NOT TESTED**.

Installation of v2 requires an explicit operator invocation on the
known working Windows-office WE5927 SSH session. It may briefly
restart rpcd; it does not reboot, flash or issue a modem command.
Record `V2_LIVE_RPC_PASS`, `V2_STATUS_PASS` and then a separate
explicit `ubus call veci.cellular messagingStorage` response to
promote the persistent read-only RPC to LIVE/PASS.
