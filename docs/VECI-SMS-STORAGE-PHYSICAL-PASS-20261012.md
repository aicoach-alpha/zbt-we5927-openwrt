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
- Persistent `messagingStorage` RPC and ACL are **LIVE/PASS** following the owner-executed v2 hotfix.
- The installed v2 overlay installer has a pinned payload commit,
  SHA256 validation, legacy RPC schema/status checks, persistent v1
  backup in `/root/veci-storage-hotfix-rollback` and rollback on
  failed registration/health. The previous capability-v1 backup
  `/root/veci-capability-hotfix-rollback` must not be overwritten.
- Offline v2 installer regression: 263/263 checks PASS at
  https://github.com/aicoach-alpha/zbt-we5927-openwrt/actions/runs/38221235586
  (includes 15 storage tests and 10 v2 rollback/manifest tests).
- Inbox contents, SMS send, interactive USSD, XL quota, firmware
  upgrade and recovery/power-loss UAT remain **NOT LIVE / NOT TESTED**.

## Operator-observed v2 production rollout — PASS

The owner executed `scripts/veci-live-storage-hotfix-v2.sh` from immutable
GitHub commit `070d271776e5696d48e484273708ee2adb459a76` on the actual
WE5927 via Windows-office SSH. The 7,598-byte installer returned:

```
V2_LIVE_RPC_PASS: messagingStorage registered
V2_STATUS_PASS: LTE status healthy
NO_AT_COMMAND_SENT_BY_INSTALLER
V2_ROLLBACK_BACKUP=/root/veci-storage-hotfix-rollback
```

`ubus -v list veci.cellular` displayed five methods:
`status`, `messagingCapabilities`, `messagingStorage`, `reconnect`,
`switchSim` with the unchanged `sim:String` argument. Subsequent *explicit*
`ubus call veci.cellular messagingStorage` returned:

```
{"ok":true,"state":"queried","source":"read_only_at_cpms",
 "memory":"ME","used":5,"total":255}
```

The owner also explicitly rechecked `messagingCapabilities` and got
`ok:true`, `state:probed`, with SMS mode/storage/notifications and USSD
all reporting `supported`. Overlay remained ~1.7 MiB free (2.1 MiB total,
364 KiB used / 17%). No firmware flash/reboot or LTE/SIM/network change.

**PASS scope:** persistent read-only SMS *storage counts* and read-only
capability diagnostic methods. **NOT PASS:** inbox reading, SMS sending,
USSD network session, live operator balance/XL quota, full firmware
upgrade or recovery tests. Preserve BOTH distinct rollback directories:
`/root/veci-capability-hotfix-rollback` (v1 original)
and `/root/veci-storage-hotfix-rollback` (working v1 backup).

These are owner-provided device observations, not direct remote execution
by this assistant.
