# VeCI native quota overlay — physical router snapshot (15 October 2026)

## Authoritative physical evidence
- Owner copied `/www/veci` from office-laptop SSH to `veci-router-20261015.zip`, via `scp -O -r`.
- Original `/www/veci/js/pages/cellular.js`: **58,588 bytes**; SHA-256 `8f9219c21ca49b44ea5d5a2705fccdde77315249c53c21715974df384d4adef6`.
- Original helper `/www/veci/js/lib/quota.js`: absent.
- Installed package: `veci-0.2.0-r1`. Existing `veci.quota status` backend: PASS.
- Earlier signed VeCI 0.2.1 APK candidate expects a different cellular.js baseline `e5697945...`; installer correctly blocked with `existing_core_source_drift`. Do not bypass it.

## Why preserving source is mandatory
The *actual* physical Cellular page includes existing SMS Inbox, sending, multi-part GSM7/UCS2 PDU, Sent Messages, Drafts, search/filter, and on-demand XL USSD functionality. It must not be overwritten by the smaller generic 0.2.1 source that lacks these on-router modifications. No SMS, USSD, LTE, modem or APN changes are required for a quota status panel.

## Scoped fix
- Isolated read-only VeCI module: `scripts/veci-native-quota-overlay/native-quota.js`, SHA-256 `5c1f66b5a5aa292be202897ef538f67ed7933e857ff3e11bcaabb075b75c692d`. Downloads only from immutable commit `e2f8bc86ef6c214d813a1b3fc021acb8955577bc`.
- Reversible deployment: `scripts/veci-native-quota-overlay-20261015.sh`. Requires exact 58,588-byte physical source hash and `veci 0.2.0-r1`; stages an import plus mount call without altering other existing Cellular source statements. The patched `cellular.js` golden SHA-256 is `b075a4852d3eeb5f717e4db568a0929fc732b225f025a154beb24961a3f85379`.
- Persistent rollback copy: `/root/veci-native-quota-rollback-20261015/cellular.js`, protected 0600. Restore with the same installer using `--rollback`.
- The package database/version stays **0.2.0** because this is a targeted file overlay, **not** an APK upgrade. Any future signed package release must adopt the actual SMS/USSD source plus this addon, then migrate the overlay cleanly.
- UI: `VeCI > Cellular > Operator Data Quota`. Read-only `veci.quota status` only. Unknown/not-connected/stale/unauthorized statuses do not show numeric quota. A number is only shown for a finite, coherent `ready` result with `source=carrier_authenticated`.
- Does not touch LuCI UI, change package manager DB, restart services, read SMS/OTP, dial USSD, or request carrier HTTPS.

## Verification
- Offline extracted snapshot transformation confirmed only **two** source insertions and no removed existing code; the actual BusyBox-compatible awk expression was replayed locally and the resulting file's SHA-256 checked.
- `node --check` of the transformed page PASS.
- GitHub CI: [Native overlay regression](https://github.com/aicoach-alpha/zbt-we5927-openwrt/actions/runs/38685447315) PASS; [VeCI-only UI policy](https://github.com/aicoach-alpha/zbt-we5927-openwrt/actions/runs/38685447298) PASS.
- **Physical deployment and browser UAT: PASS on 2026-10-15.** Owner ran the SHA-pinned installer from Windows office laptop to the intended physical ZBT-WE5927 at `root@192.168.1.1`. The first `--status` reported `VECI_QUOTA_OVERLAY=original`, `CELLULAR_SHA256=8f9219c2...`, `VECI_QUOTA_BACKEND=pass`. The `--install` then reported `VECI_QUOTA_OVERLAY=installed`, `VECI_QUOTA_PATCHED_SOURCE=pass`, `VECI_QUOTA_READONLY_BACKEND=pass`, `VECI_QUOTA_ROLLBACK=available`, `VECI_QUOTA_BROWSER_UAT=pending`, `VECI_OPERATOR_AUTHENTICATED_QUOTA=not_verified`, `VECI_SMS_LTE_MODIFIED=false`, `VECI_LUCI_UI_MODIFIED=false`. Final `--status` confirmed `VECI_QUOTA_OVERLAY=installed`, `VECI_QUOTA_CELLULAR_SHA256=b075a4852d3eeb5f717e4db568a0929fc732b225f025a154beb24961a3f85379`, `VECI_QUOTA_ROLLBACK=available`, `VECI_QUOTA_BACKEND=pass`.
- Owner-provided screenshot from live VeCI Cellular page visually confirms native **Operator Data Quota** panel shows `XL`, `Not connected`, and `Operator account authentication is not configured.` with a local read-only refresh control. The same page still displays an active LTE data link, `Internet Reachable`, SMS Inbox controls and XL USSD panel; this establishes rendered UI coexistence only, not that sending/receiving SMS or USSD transaction tests were rerun.
- **Acceptance status:** native VeCI quota *status UI* physical LIVE/PASS and snapshot-specific rollback AVAILABLE. The browser screenshot closes the previously-pending visual UAT criterion. This targeted overlay has **not** updated the APK package version; installed core remains 0.2.0, which requires future signed package consolidation. Carrier-authenticated XL quota retrieval is **NOT LIVE**, and must not be represented as verified data.
- Real XL provider authentication/verified carrier quota remain not implemented. Do not display guessed or traffic-based quota as genuine.

## Physical path rules
The authorized router is `root@192.168.1.1` **only from office laptop 25NBCABA13CF**. This address via `andre-nas` resolves to unrelated hardware. Desktop Commander monthly call allowance was exhausted. Never use `andre-nas` for this router.
