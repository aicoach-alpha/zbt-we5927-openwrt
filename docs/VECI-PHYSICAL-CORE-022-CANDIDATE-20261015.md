# VeCI Core 0.2.2 physical SMS/USSD + Operator Quota — signed prerelease

**Date:** 15 October 2026
**Status:** RELEASE CANDIDATE BUILD / CI PASS. Physical `0.2.2` upgrade NOT performed. Router remains on working `veci 0.2.0` + separately installed native quota overlay.

## Scope and immutable evidence

The office-laptop-sourced WE5927 frontend snapshot contains 19 files, including a 58,588-byte production Cellular page (SHA256 `8f9219c21ca49b44ea5d5a2705fccdde77315249c53c21715974df384d4adef6`). Its exact Git blob is already tracked as `scripts/veci-xl-ussd-v17-staged/cellular-v160.js`; its SMS CSS matches `scripts/veci-sms-mifi-v159-staged/sms-center.css`. A historical VeCI revision supplies the exact physical Home page, and pinned VeCI upstream commits supply the other unchanged assets.

`scripts/veci-physical-core-stage-20261015.py` rebuilds a **byte-for-byte matching physical frontend baseline** before making exactly two source insertions to enable the already-LIVE panel. It asserts all 19 full SHA256 fingerprints, not only filenames or version numbers. The patched Cellular SHA256 is `b075a4852d3eeb5f717e4db568a0929fc732b225f025a154beb24961a3f85379`, which matches the owner's final physical installed status. The native module SHA256 is `5c1f66b5a5aa292be202897ef538f67ed7933e857ff3e11bcaabb075b75c692d`.

## Actual signed APK assets

[GitHub immutable prerelease](https://github.com/aicoach-alpha/zbt-we5927-openwrt/releases/tag/veci-physical-core-022-b9f91e84899c).

| Artifact | Bytes | SHA256 |
|---|---:|---|
| `veci-0.2.2-r1.apk` | 61,691 | `57e1c66473e9ce4d7fb920beaeb82dadabfbf7d6984f52837b826d11cb1f1793` |
| `veci-0.2.0-r1.apk` | 60,424 | `b30d66c259d3a90ffafabecbe0a36baa9377af76e9f51341c1b0c13078c8f1c7` |
| `veci-physical-022.pem` | 178 | `2d27345b4b48c70131ea03799af96699625378a571dfa1d67c2f18f40ded4147` |

Build CI: [38686919678 — PASS](https://github.com/aicoach-alpha/zbt-we5927-openwrt/actions/runs/38686919678). Proven: exact 19-file physical parity, node syntax and quota behavioral tests, unchanged core RPCD/ACL/config between update and rollback candidates, SDK compile for ramips/mt76x8 OpenWrt 25.12.5, P-256 signatures, signature rejection without key, package content inspection, paired release publishing.

Signed-release preflight guard CI: [38687372882 — PASS](https://github.com/aicoach-alpha/zbt-we5927-openwrt/actions/runs/38687372882). VeCI-only UI policy gate: [38687372870 — PASS](https://github.com/aicoach-alpha/zbt-we5927-openwrt/actions/runs/38687372870).

## Mandatory physical go/no-go before ANY APK installation

The **actual router's runtime and ACL must be independently checked** before replacing its core package. Expected core RPCD SHA256 `2b83fac1da487188617888757a2b769d6ed9bf94d32aeaa9a87139b008f913da`; core ACL SHA256 `1c59a295448483147507d58336a554db96803aebf4eff8263bc73e89ace6eb5b`. If either differs, STOP and reconcile to the original before packaging: never bypass the gate.

1. From **office Windows laptop `25NBCABA13CF`** only, run `scripts/veci-physical-core-runtime-identity-20261015.sh --status` against physical `root@192.168.1.1` to inventory board, core backend runtime/ACL hashes, CSS, quota overlay and backend status. Read-only, no secrets.
2. Run `scripts/veci-physical-core-022-preflight-20261015.sh --verify`. It checks physical state, PHP-free BusyBox tools, exact live page/module/CSS hashes, core RPCD/ACL, both quota and cellular backend statuses, available overlay, immutable APK SHA/size, isolated temporary P-256 keys, `apk verify` for signed update and rollback, and offline `apk --simulate add` without other package changes.
3. Physical package installation is not authorized until both pass, a rollback installer has been reviewed and audited with persistent backup of the **currently LIVE patched page/module/config**, and expected rpcd/uhttpd restart behavior is approved. Do not mistake signed APK build CI for physical UAT.
4. Browser UAT after eventual controlled install must recheck Cellular quota panel, all SMS Inbox/Sent/Drafts controls, read-only XL USSD controls, LTE data Internet status, and package version; avoid sending real SMS or requesting an unsolicited USSD session merely to claim a test PASS.
5. XL account authentication and a real operator-verified quota response remain NOT implemented or proven. The only valid display currently is `Not connected`; no synthetic or router-traffic quota can be shown as carrier quota.

## Current LIVE milestone

Owner supplied screenshot and router output confirming the **VeCI native Operator Data Quota status panel** LIVE/PASS, backend `veci.quota` PASS, local operator label XL with `Not connected`, LTE Internet Reachable, and visible existing SMS/USSD UI. On-router Core version is STILL `0.2.0`, plus reversible overlay. No LuCI UI development or change has been performed for this release. Never route to `andre-nas`, whose `192.168.1.1` is unrelated hardware.
