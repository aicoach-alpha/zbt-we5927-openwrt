# VeCI WE5927 Cellular UI hotfix v1.2 — exact captured live asset

Date: 2026-10-12. Source of truth: owner-provided physical router file, exported by SCP from office Windows PC.

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
- On-router v1.2 deployment is **NOT YET PERFORMED**; true browser rendering and RPC call remain hardware UI acceptance checks.

## Recommended physical operator check

1. Use SSH on physical WE5927, never NAS ZTE IP.
2. Download immutable v1.2 script to `/tmp` and run `sh -n` + `status`. Expected actual SHA `0a4e78d5...d8ee18`.
3. `apply` only if exact SHA matches; success marker `V12_UI_ASSETS_LIVE_PASS`.
4. Browser hard refresh Cellular page; click `Check stored SMS count`. Expect output similar to `5 / 255 (ME)` if storage remains unchanged. Do not assume count never changes.
5. If UI fails or needs reversal, invoke only v1.2 `rollback` from `/tmp`, marker `V12_UI_ROLLBACK_PASS`.

Never execute v1/v1.1 installers again and never run actual `AT+CMGL=4` merely for this storage-count UI.
