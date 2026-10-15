# VeCI Core 0.2.2 physical SMS/USSD + Operator Quota — LIVE release acceptance

**CURRENT STATUS (15 Oct 2026): Core 0.2.2 physical LIVE/PASS; UI visual UAT PASS; authenticated XL quota NOT CONNECTED.** Earlier candidate-build, NO-GO and rollback descriptions below are chronological records and are superseded by the final acceptance section at the end.

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

## 2026-10-15 — superseding exact-backend signed release READY FOR PHYSICAL INSTALL

After the previous release gate failed due to source runtime drift, the owner copied **exactly** two root-owned existing backend files from the office laptop using `scp -O`, then supplied `veci-core-runtime-20261015.zip` in the conversation. Checksums were independently verified both on Windows and from the ZIP:

- Original core RPCD `/usr/libexec/rpcd/veci`: 7,935 bytes, SHA256 `d08edadd38f0d9b992fc54d879eabf9f797bf54df83fa8c8cf7b59e55b9e99ce`.
- Original core ACL `/usr/share/rpcd/acl.d/veci.json`: 834 bytes, SHA256 `d655406fd94214c22cf047bf5fc49e66876365634958be9d25171e6100e6a171`.

The files contain code and ACL rules, with no embedded account password, API key or bearer token found on inspection. They are included with exact hash checks at `scripts/veci-physical-core-runtime-20261015/`. All 19 verified frontend files, the installed native quota module, SMS Center UI, RPCD script, and ACL are preserved identically in the **new** target package **and** its rollback partner. Rollback target core version remains `0.2.0`, but with the **current patched LIVE frontend**; never use the superseded earlier rollback APK that lacked native quota or the correct core backend.

**Superseding immutable prerelease**: [veci-physical-core-022-c76cb7f13f06](https://github.com/aicoach-alpha/zbt-we5927-openwrt/releases/tag/veci-physical-core-022-c76cb7f13f06)

| Artifact | Bytes | SHA256 |
|---|---:|---|
| `veci-0.2.2-r1.apk` | 55,594 | `e06ad0b5f57f29630f20ff4bdaa06665261c09cbaef21a17a5a5504c092ff168` |
| `veci-0.2.0-r1.apk` | 55,595 | `2b18a8c1e230314837068649023c097e1c354b9b8bdd77a4a148692fb7f3fd9a` |
| `veci-physical-022.pem` | 178 | `c9915940535bdc8f9f388af8a924f329e77cc20217cb3b3d8fbc495f80628fcc` |

Successful build and signing CI: [38690603865 PASS](https://github.com/aicoach-alpha/zbt-we5927-openwrt/actions/runs/38690603865).
Focused signed deployment/rollback protection CI: [38691024960 PASS](https://github.com/aicoach-alpha/zbt-we5927-openwrt/actions/runs/38691024960).

**Audited installer:** `scripts/veci-physical-core-022-signed-deploy-20261015.sh`, supporting `--status`, `--verify`, `--install`, `--rollback`. Signed release SHA and sizes are immutable, verified in RAM. Preserves `/etc/config/veci` by comparing its observed physical SHA-256 `95927da8bad40be6ac0eb14d8c92d13fa82ffc1594a8f608d59a06680275caae` before and after upgrade, never exporting the config publicly. Creates an owner-only persistent backup under `/root/veci-core-022-live-backup`, confirms backend status, runs an offline APK dependency plan, prevents unrelated package changes, and invokes rollback on postinstall failure. The update will restart rpcd/uhttpd as part of the VeCI package postinst but does not restart LTE modem/SMS services or flash firmware.

**Current status:** Physical installation of VeCI Core `0.2.2` is **PENDING**. The old signed APK release/tag `veci-physical-core-022-b9f91e84899c` is superseded and **MUST NOT be used**. Run only the new pinned installer from the authorized Windows office laptop against actual WE5927 `192.168.1.1`; do not involve andre-nas. A returned CLI `VECI_022_DEPLOY=pass` would prove the package installed but browser UAT of the native quota panel and existing SMS/USSD visible controls is still required. XL carrier-authenticated balances remain unimplemented/not verified.

### Final signed deployment guard

Snapshot installer now verifies all **19** original frontend files (17 unchanged asset hashes, patched Cellular hash and the SMS CSS hash), plus the exact native quota helper, core RPCD, ACL and router-local UCI config hash. This prevents later UI hotfixes being overwritten by an older signed candidate. It keeps the signed downgrade and persistent owner-only configuration backup.

Final installer source commit: `948e376940b093b7381414c633f437e66d369d55`.
Focused final deployment gate CI: [38691242938 — PASS](https://github.com/aicoach-alpha/zbt-we5927-openwrt/actions/runs/38691242938). VeCI-only UI policy CI: [38691243242 — PASS](https://github.com/aicoach-alpha/zbt-we5927-openwrt/actions/runs/38691243242).

The installer is ready for a single controlled physical deployment through the Windows office laptop. It internally performs the signed-asset/dependency preflight, persistent backup and package install, then verifies sources, config, existing backends and unrelated package inventory. `VECI_022_DEPLOY=pass` is required to claim the physical update. The browser quota/SMS UI must still be visually verified afterwards. The earlier blocked signed release is not eligible for deployment.

## 2026-10-15 — First physical signed install failed on UCI config; automatic rollback PASS

Owner executed the pinned 0.2.2 installer from the **office Windows laptop** against the actual WE5927. The installer output was:

```text
VECI_022_PAIRED_SIGNATURES=pass
VECI_022_TRANSACTION_SIMULATION=pass
VECI_022_PERSISTENT_BACKUP=pass
VECI_022_DEPLOY=blocked
VECI_022_REASON=live_uci_config_drift
VECI_022_ROLLBACK=pass
```

Interpretation: both signed APKs and transaction planning passed; the installed 0.2.2 package changed `/etc/config/veci` (or another concurrent process did) before the post-install immutable-config check. The existing script **correctly rejected the mismatch and invoked a successful signed rollback** to the 0.2.0 package plus LIVE source/backup. Because the original owner command used shell `&&`, its trailing `--status` step did not execute after install failure. A fresh physical `--status` and browser check remain needed before asserting complete UI recovery.

**Old installer source commit `c59f3d512d9e87acf7473b2e8cc86c759ccfa70b` must not be re-executed** for this upgrade.

### Narrow config-preservation correction (no APK rebuild required)

The new signed installer recognizes **only two** acceptable post-install `/etc/config/veci` states:

1. Original owner-verified active config SHA-256: `95927da8bad40be6ac0eb14d8c92d13fa82ffc1594a8f608d59a06680275caae` — no restore needed.
2. Exactly the static default configuration bundled with the pinned source package: SHA-256 `63518b50a5cc75eafceea120424e8125194310ac8829f0a5a3e16ab6a172ae54` — atomically replace it with the **private, SHA-verified root-owned backup** at `/root/veci-core-022-live-backup/veci.config`, with mode 0600.

Missing/symlinked config, a missing or modified rollback backup, or **any other config hash** remains a hard failure and triggers the same automatic signed rollback. The installer prints only the post-install hash, never the private config contents. Signed APK hash pins, frontend/source guards, backend checks and unrelated package inventory checks remain unchanged.

GitHub source fix: [`ffa35f7`](https://github.com/aicoach-alpha/zbt-we5927-openwrt/commit/ffa35f7847d395d207580ebc9de27bc92fb37d56). Regression test file: `tests/test_veci_022_config_reconcile.py`.

[CI 38694058037 PASS](https://github.com/aicoach-alpha/zbt-we5927-openwrt/actions/runs/38694058037) proved actual shell-function behaviors for five scenarios (untouched config, signed default restored, unexpected changes refused, corrupted backup refused, symlink refused) and verified the immutable signed release pair. [VeCI-only UI policy 38694058052 PASS](https://github.com/aicoach-alpha/zbt-we5927-openwrt/actions/runs/38694058052).

**Physical status:** 0.2.2 installation is **NOT yet PASS**. Only a new run from the authorized office laptop and fresh `--status` can establish installation success. Existing XL carrier quota authentication is still not configured.

## 2026-10-15 — PHYSICAL VeCI Core 0.2.2 LIVE / PASS (supersedes all earlier pending/NO-GO statuses)

**Final operator evidence:** The owner ran the patched, SHA-pinned signed installer from the authorized Windows office laptop to the physical ZBT-WE5927 at `root@192.168.1.1`, then supplied the full PowerShell output and screenshot of the live VeCI Cellular page. Initial `--status` confirmed version 0.2.0, the exact prior source hashes, both backends PASS and persistent live backup AVAILABLE.

```text
VECI_022_PAIRED_SIGNATURES=pass
VECI_022_TRANSACTION_SIMULATION=pass
VECI_022_CONFIG_PRESERVATION=unchanged
VECI_022_DEPLOY=pass
VECI_022_INSTALLED_VERSION=0.2.2
VECI_022_SMS_USSD_SOURCE_PRESERVED=pass
VECI_022_LIVE_CORE_RPCD_ACL_PRESERVED=pass
VECI_022_CONFIG_PRESERVED=pass
VECI_022_BACKENDS=pass
VECI_022_ROLLBACK_AVAILABLE=true
VECI_022_BROWSER_UAT=pending
VECI_CARRIER_QUOTA=not_verified
VECI_LUCI_UI_MODIFIED=false
VECI_MODEM_SMS_UNCHANGED=true
```

**Independent final `--status` after installation:**

| Artifact | Live SHA-256 |
|---|---|
| VeCI package version | `0.2.2` |
| `/www/veci/js/pages/cellular.js` | `b075a4852d3eeb5f717e4db568a0929fc732b225f025a154beb24961a3f85379` |
| `/www/veci/js/lib/native-quota.js` | `5c1f66b5a5aa292be202897ef538f67ed7933e857ff3e11bcaabb075b75c692d` |
| `/usr/libexec/rpcd/veci` | `d08edadd38f0d9b992fc54d879eabf9f797bf54df83fa8c8cf7b59e55b9e99ce` |
| `/usr/share/rpcd/acl.d/veci.json` | `d655406fd94214c22cf047bf5fc49e66876365634958be9d25171e6100e6a171` |
| `/www/veci/sms-center.css` | `fd3b3540109d815d9b3cb5151298af04ef865e55557d8a8a91d9c30f1548fdb2` |
| `/etc/config/veci` | `95927da8bad40be6ac0eb14d8c92d13fa82ffc1594a8f608d59a06680275caae` |

Final status also reported `VECI_022_BACKENDS=pass`, `VECI_022_LIVE_BACKUP=available`, `VECI_022_STATUS=read_only`.

**Visual browser acceptance:** The screenshot supplied with this final CLI shows VeCI (not LuCI) on the Cellular page; LTE on SIM 1, `Internet: Reachable`, and the native Operator Data Quota panel for XL with `Not connected`. SMS Inbox and XL USSD control groups remain visibly present. This establishes **UI visual UAT PASS**, not functional SMS send/receive testing or a fresh USSD transaction. The script's `VECI_022_BROWSER_UAT=pending` label is a pre-browser CLI status, now satisfied by subsequent operator screenshot.

**Milestone disposition:** `VECI_CORE_022_PHYSICAL_DEPLOY=LIVE_PASS`, `VECI_CELLULAR_QUOTA_STATUS_UI=LIVE_PASS`, `SIGNED_ROLLBACK=AVAILABLE`, `OPERATOR_AUTHENTICATED_QUOTA=NOT_CONNECTED`. Signed target: [physical-core-022-c76cb7f13f06](https://github.com/aicoach-alpha/zbt-we5927-openwrt/releases/tag/veci-physical-core-022-c76cb7f13f06). Do not reinstall or rerun the failed original installer. Any future changes should have a fresh snapshot-bound build and explicit release gate.

**Remaining separate scope:** Authenticated XL/operator-side data quota retrieval is not implemented, and the numerical remaining quota must not be inferred from router traffic statistics. The current signed core is installed and does not require another migration test. The development branch has this evidence; a separately open draft PR may still require review/merge before the wider firmware integration branch adopts it.
