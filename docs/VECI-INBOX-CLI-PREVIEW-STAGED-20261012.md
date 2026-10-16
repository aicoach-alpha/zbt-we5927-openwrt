# VeCI: explicit-only SMS inbox index preview — STAGED / NO LIVE

Date 2026-10-12, Asia/Jakarta. This is a technical CLI prototype for root SSH, NOT an RPC/UI method, not an unattended service, and not installed in firmware.

## Physical modem evidence — PASS

- Owner verified physical WE5927 via **office Windows SSH**, not andre-nas, with board zbtlink,zbt-we5927 and USB modem 05c6:902e AT ttyUSB2 interface 1.4.
- Original read-only diagnostic methods `messagingCapabilities` and `messagingStorage` remain LIVE/PASS; reported ME SMS used=5, total=255.
- `AT+CMGF?` returned `sms_mode:pdu`; `AT+CSCS?` returned `charset:IRA`; no SMS or modem setting was changed.
- An explicit read-only **test** of `AT+CMGL=?` returned `cmgl_test:accepted` and `sms_messages_accessed:false`. This confirms that modem accepted the test command, NOT that SMS listing works.
- The owner ran the pinned script from 479ed78c797962a26395f5184809f57b56a41e01 and received the exact output recorded in docs/VECI-CMGL-CAPABILITY-PHYSICAL-UAT-20261012.md.

## Prototype implementation

- File `scripts/veci-sms-inbox-index-preview.sh` (pure BusyBox POSIX shell and awk; staged, not deployed).
- It requires root and two exact CLI flags: `--show-indices-only --ack-unread-may-be-marked-read`.
- It confirms board identity, then takes the shared nonblocking modem lock **before** checking sysfs ttyUSB2 USB interface 1.4 and VID:PID 05c6:902e. This is NOT equivalent to a production-grade opened-FD device identity check.
- Within that lock, it reads the already-active PDU mode with `AT+CMGF?` and, if PDU, requests a single `AT+CMGL=4` (up to 5 sec) with no automatic retry.
- Its output is only count + message slot indices, numeric delivery status and TPDU length. The raw SMS PDU, sender, message contents, and OTP are never printed, stored persistently or sent to a server.
- The strict parser rejects missing final OK, invalid lines, malformed PDU/TPDU lengths, unsolicited CUSD/CMTI, duplicate indices, more than 16 entries and post-OK content. It prints zero metadata on incomplete/invalid response.
- It does NOT open individual SMS, send/delete SMS, start USSD, change CMGF/CSCS settings, restart services, modify LTE routing, flash firmware or persist logs.
- **Important:** `AT+CMGL=4` lists real messages and according to 3GPP TS 27.005 CAN CHANGE UNREAD SMS TO READ. This is NOT a read-only modem operation and the explicit ack must be understood by the operator.
- Full-session USB opened-FD identity attestation, serial lifecycle/URC correlation and authenticated UI/CSRF are still incomplete. Thus this script remains an isolated root-only staged prototype, NOT a general user-facing LIVE feature.

## CI

- `327/327` host unit tests PASS at https://github.com/aicoach-alpha/zbt-we5927-openwrt/actions/runs/38227130118.
- The new `tests/test_veci_sms_inbox_cli_preview.py` covers 13 scenarios including privacy, strict parser, consent flags, malformed data, SMSC offset and no auto-polling.
- `INERT_BUILD_GUARD_PASS`: optional native SMS and USSD source is still not built into the firmware image.

## Operating gates / no silent deployment

- Existing v2 RPC and its two rollback directories must not be modified for this prototype.
- No real `AT+CMGL=4` has been run on owner modem yet, and SMS inbox is NOT LIVE.
- Prior to physical test, the operator must acknowledge the unread-state side effect and understand the possibility of exposing SMS/OTP to process memory, even though metadata-only CLI output masks content.
- Do NOT expose this CLI through general read-only ubus ACL or dashboard polling. Implement authenticated per-action consent, CSRF, session lock + identity re-attestation before production.
- The script can be downloaded to /tmp and shell syntax tested without triggering any modem call. Only invoking it with BOTH flags actually lists messages and could mark SMS read.


## Operator-observed actual Inbox index UAT — 2026-10-12

**PHYSICAL DEVICE UAT PASS for one explicit CLI metadata listing** on real WE5927 via Windows-office SSH (NOT NAS). User downloaded the pinned 5,349-byte script from commit `14da3bd48a914a6fba0939e6ebc96bb5ab20ac7b` into `/tmp`, verified with `sh -n`, and **voluntarily invoked both explicit consent flags**, including acknowledgment of possible unread-to-read mutation. Output:

```json
{"ok":true,"source":"on_demand_cmgl","side_effect_acknowledged":true,"count":5,"messages":[{"index":0,"status":0,"tpdu_octets":163},{"index":1,"status":0,"tpdu_octets":48},{"index":2,"status":0,"tpdu_octets":153},{"index":3,"status":0,"tpdu_octets":163},{"index":4,"status":0,"tpdu_octets":52}]}
```

Modem returned **five records** indexed 0–4, with PDU status code 0 (REC UNREAD at time of listing) and TPDU sizes 163,48,153,163,52 octets. **Do not assume they remain unread**: 3GPP states that CMGL listing can transition unread to read. Metadata-only stdout contained no sender numbers, body text, OTP or PDU bytes. The operation internally processes PDU in RAM. This result confirms a working one-time *CLI metadata* listing, **NOT** an authenticated dashboard Inbox or message body reading.

Existing LIVE/PASS v2 RPC `messagingStorage`, `messagingCapabilities` and LTE status unchanged. The CLI lives in `/tmp`, not installed into firmware. No reboot, sysupgrade, SIM/network change or USSD session. Do NOT silently rerun this state-mutating list to retest. `count=5` is a point-in-time observation, not continuously synchronized Inbox state.

Next feature delivery: user-click-only metadata on Cellular page, using the already-approved v2 diagnostic RPCs for safe capacity/capability display; full Inbox requires elevated ACL, per-action UI permission and trusted opened-FD session transport. Generic VeCI UI draft PR: https://github.com/aicoach-alpha/veci/pull/6 (metadata diagnostics UI, **does not list SMS**).
