# VeCI WE5927 Cellular UI hotfix v1.2 — exact captured live asset

Date: 2026-10-12; physical UI acceptance proof received 2026-10-13 (Asia/Jakarta). Source of truth: owner-provided physical router file, exported by SCP from office Windows PC.

## Actual device source evidence

- Physical path: `/www/veci/js/pages/cellular.js` on actual WE5927 `192.168.1.1` from office Windows, NOT home NAS.
- User copied binary via `scp -O` and independently verified **6357 bytes** and SHA256 `0a4e78d5368806b31441612b8979ab7b2ac8f425890cfd89104f969accd8ee18`.
- This actual file is a **plain unminified custom/older Cellular module**, not the 9829 byte minified VeCI CI build. Earlier attempted v1/v1.1 source/base comparisons therefore rightly refused to overwrite.
- Original code includes Internet reachability status, cellular signal/connection details, operator deduplication, reconnect and switch SIM. Actual file does NOT contain newer diagnostic/IMEI/CELLULAR capability panel from dev source.

## Exact surgical delta

- Patched asset committed to `scripts/veci-sms-ui-live-captured-20261012/cellular.js`, immutable payload commit `9c5be87354cb08b93ef478fdd2dbd1b7e777fc7b`.
- Patched file **8352 bytes**, SHA256 `2deb013e6ccf433b9c3abc3d7f02aafb33739dd1b5b5f222d4de501865314d40`.
- Source delta is **only** two append-only pieces: `<section class=panel>` labeled SMS storage and click-only event handler. Removing those two inserted blocks recreates the entire real original file **byte-for-byte**; this is a CI assertion.
- The button sends only existing LIVE v2 `veci.cellular.messagingStorage`, which invokes `AT+CPMS?` for used/total/memory; does NOT read sender/body/OTP or issue actual SMS listing/USSD.
- Strict response schema: `ok=true`, `state=queried`, `source=read_only_at_cpms`, integer `0 <= used <= total <= 65535`, `total > 0`, memory only two uppercase letters. All response values rendered with `textContent`, no modem-supplied HTML.
- No SMS query at page render or implicit polling. Message warns real inbox can mark unread as read.

## v1.2 safe installer

- Path: `scripts/veci-sms-storage-ui-exact-live-hotfix-v12.sh`. This is a one-shot UI-only change, not new router firmware.
- It requires root on WE5927 and exact SHA256 match of installed live 6357B source before making changes. Any mismatch aborts without altering the file.
- Immutable content source and new payload SHA are verified before installation. Uses `/tmp` RAM staging, separate persistent `/root/veci-sms-ui-exact-live-v12-backup`, atomic page replacement and checksum, automatic restore on failed write.
- `status`, `apply`, `rollback` are supported. Rollback refuses to overwrite any newer local UI edit.
- It does NOT call modem AT, reboot, flash, restart RPC/LTE, install packages, touch SIM or change UCI.

## Tested

- `node --check` on exact patched asset PASS; local mock-browser click test PASS (no SMS request on page render, count after click, malformed data rejected, prior reconnect/SIM still present).
- **350/350 CI tests PASS** https://github.com/aicoach-alpha/zbt-we5927-openwrt/actions/runs/38239395721; includes 6 exact source integrity tests and 5 isolated installer/rollback simulations.
- `INERT_BUILD_GUARD_PASS`: native SMS/USSD sources are still not linked to firmware.
- On-router v1.2 deployment **PHYSICALLY LIVE/PASS**, verified from owner's router SSH output and screenshot. See the acceptance evidence below.

## Physical device deployment and browser UAT — LIVE/PASS

User executed the pinned 4,690-byte v1.2 installer from immutable commit `400ecfaa28d35553c552397d319ab2c6099a52c8` on physical WE5927 (office Windows SSH). Their output shows:

```text
CURRENT_SHA=0a4e78d5368806b31441612b8979ab7b2ac8f425890cfd89104f969accd8ee18
CURRENT_BYTES=6357
BACKUP=none
V12_UI_ASSETS_LIVE_PASS
NO_MODEM_AT_COMMAND_SENT
BACKUP=/root/veci-sms-ui-exact-live-v12-backup
CURRENT_SHA=2deb013e6ccf433b9c3abc3d7f02aafb33739dd1b5b5f222d4de501865314d40
CURRENT_BYTES=8352
```

Owner also supplied a VeCI Cellular screenshot showing **SMS storage: 5 / 255 (ME)** after using the new `Check stored SMS count` button, with `Data link active`, `Internet: Reachable`, `LTE`, `Registered (home)`, `Packet service: Attached`. Screenshot retains both **Reconnect data** and **Switch SIM** buttons. This establishes physical UI rendering, existing storage RPC integration, and observed continued LTE availability. Button availability does not itself test reconnect or SIM switch operations; they were not invoked for this UAT.

Overlay before: `/dev/mtdblock6` 2.1 MiB, used 364 KiB (17%), available 1.7 MiB. After: used 372 KiB (18%), available 1.7 MiB. Roughly +8 KiB flash overhead.

Status by feature:
- `veci.cellular.messagingStorage`: LIVE/PASS.
- `veci.cellular.messagingCapabilities`: LIVE/PASS (prior UAT).
- VeCI `Cellular → Check stored SMS count` panel: LIVE/PASS.
- Privileged SMS Inbox listing RPC/UI: **NOT LIVE**. The one-shot root SSH `AT+CMGL=4` metadata preview previously passed separately, but can mark unread SMS as read.
- SMS contents, OTP display, SMS sending and live XL USSD sessions: **NOT LIVE**.
- v1/v2 SMS diagnostics backups remain retained. This UI v1.2 rollback backup is a separate directory and has not been exercised on the physical router. Isolated mock rollback CI PASS.

**No further hotfix installation needed.** Only advance to actual Inbox after authenticated elevated write ACL, explicit per-action user warning/acknowledgment, serial open-FD identity verification, bounded response handling, and no automatic polling. Avoid re-running `AT+CMGL=4` just to confirm the five-message list.

## Historical operator installation procedure (already completed; do not rerun)

1. Use SSH on physical WE5927, never NAS ZTE IP.
2. Download immutable v1.2 script to `/tmp` and run `sh -n` + `status`. Expected actual SHA `0a4e78d5...d8ee18`.
3. `apply` only if exact SHA matches; success marker `V12_UI_ASSETS_LIVE_PASS`.
4. Browser hard refresh Cellular page; click `Check stored SMS count`. Expect output similar to `5 / 255 (ME)` if storage remains unchanged. Do not assume count never changes.
5. If UI fails or needs reversal, invoke only v1.2 `rollback` from `/tmp`, marker `V12_UI_ROLLBACK_PASS`.

Never execute v1/v1.1 installers again and never run actual `AT+CMGL=4` merely for this storage-count UI.
