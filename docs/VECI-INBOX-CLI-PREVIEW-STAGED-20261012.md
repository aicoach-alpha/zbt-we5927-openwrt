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
- It confirms board identity, sysfs ttyUSB2 USB interface 1.4 and VID:PID 05c6:902e. It takes the shared nonblocking modem lock.
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
