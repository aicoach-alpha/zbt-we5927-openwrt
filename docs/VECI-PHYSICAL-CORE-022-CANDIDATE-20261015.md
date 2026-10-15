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


## 2026-10-15 — Physical runtime/ACL compatibility result: BLOCKED, correctly fail-closed

Operator executed the immutable read-only identity and signed-APK preflight from the authorized Windows office laptop against the actual WE5927. Live facts (read-only):

```text
VECI_RELEASE_INSTALLED_CORE=0.2.0
VECI_RELEASE_CELLULAR_SHA256=b075a4852d3eeb5f717e4db568a0929fc732b225f025a154beb24961a3f85379
VECI_RELEASE_QUOTA_MODULE_SHA256=5c1f66b5a5aa292be202897ef538f67ed7933e857ff3e11bcaabb075b75c692d
VECI_RELEASE_RPCD_SHA256=d08edadd38f0d9b992fc54d879eabf9f797bf54df83fa8c8cf7b59e55b9e99ce
VECI_RELEASE_CORE_ACL_SHA256=d655406fd94214c22cf047bf5fc49e66876365634958be9d25171e6100e6a171
VECI_RELEASE_CONFIG_SHA256=95927da8bad40be6ac0eb14d8c92d13fa82ffc1594a8f608d59a06680275caae
VECI_RELEASE_SMS_CSS_SHA256=fd3b3540109d815d9b3cb5151298af04ef865e55557d8a8a91d9c30f1548fdb2
VECI_RELEASE_CORE_RPCD_PARITY=drift
VECI_RELEASE_CORE_ACL_PARITY=drift
VECI_RELEASE_BACKEND_BASELINE=blocked_pending_reconciliation
VECI_RELEASE_BACKEND_QUOTA=pass
VECI_RELEASE_BACKEND_CELLULAR=pass
VECI_RELEASE_OVERLAY_FREE_KB=1336
VECI_022_PREFLIGHT=blocked
VECI_022_REASON=existing_core_rpcd_drift
```

Interpretation: all **frontend** source fingerprint checks match the operator-verified deployed snapshot, but the *live core backend RPCD* and *live core ACL* differ from the upstream baseline packed in the signed candidate. The difference might come from legitimate prior hotfixes; absence of an exact source match is **not evidence of compromise**. The preflight did not reach the package transaction phase. No APK was installed; the live 0.2.0 + native quota overlay remains intact.

**RELEASE HOLD / NO-GO:** do NOT attempt `apk add` / `apk upgrade`, use `--allow-untrusted`, relax the fingerprint gate, replace core RPCD/ACL with upstream defaults, or install the previously signed 0.2.0 APK as a purported rollback. That signed 0.2.0 APK is only frontend-identical and does **not** reproduce the live backend; rollback fidelity is not yet established.

**Required next evidence:** read-only copies of `/usr/libexec/rpcd/veci` and `/usr/share/rpcd/acl.d/veci.json` from the *office laptop to a private local ZIP*. Verify the SHA-256 fingerprints above on the laptop before sharing them for inspection. Do not export `/etc/config/veci` or arbitrary private secrets. Inspect the captured files for credentials or device-specific data before any public GitHub commit or GitHub Actions artifact.

After inspection, reconstruct a candidate whose packaged core runtime and ACL match the physical files (or a narrowly audited superset), rebuild and re-sign an exact rollback package, and revalidate the package simulation and physical browser UAT. Keep modem/LTE/SMS unchanged throughout. Note signed APK CI PASS alone does not supersede this LIVE NO-GO.

## Current LIVE milestone

Owner supplied screenshot and router output confirming the **VeCI native Operator Data Quota status panel** LIVE/PASS, backend `veci.quota` PASS, local operator label XL with `Not connected`, LTE Internet Reachable, and visible existing SMS/USSD UI. On-router Core version is STILL `0.2.0`, plus reversible overlay. No LuCI UI development or change has been performed for this release. Never route to `andre-nas`, whose `192.168.1.1` is unrelated hardware.
