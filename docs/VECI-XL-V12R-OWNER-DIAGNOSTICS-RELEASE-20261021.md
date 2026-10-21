# VeCI v12r — Owner XL Readiness Diagnostics (2026-10-21)

## Current release boundary

Current observed production: **v12q LIVE/PASS**, `veci-xl-native-overlay 1.0.1-r1`, `veci-telco-xl-native 0.3.8-r2`, `veci-telco-indonesia 0.2.2-r2`. The v12r overlay **1.0.2-r1 has NOT yet been built or deployed on the owner's office workstation**. Do not claim v12r LIVE until the office receipt explicitly confirms `XL_V12R_OFFICE=live_pass`.

## Functional change

A new `Lihat Diagnostik XL` / `Tutup Diagnostik XL` control in the existing native owner panel displays only whitelisted, redacted readiness states derived from the VeCI RPC status **already being fetched**: HTTPS readiness, availability of operator configuration, safe session category, whether operator quota cache is valid, stale or unavailable, and contextual next step. It never prints a subscriber number, OTP, bearer token, secret app configuration, error stack, or raw RPC payload. No additional RPC or operator network request is performed by the diagnostic control. Official myXL fallback is retained.

One focused in-memory UI harness passed: no-configuration status does not request quota/OTP, valid operator-source result is accepted, invalid source is not shown, unknown session and associated private data are redacted, and diagnostics toggle works. A targeted regression test is committed at `packaging/veci-xl-native-overlay/v12r/tests/diagnostics.test.cjs`. Source and package-release contract readback PASS; no repeated v12q UAT.

## Packaging and deployment

Same package owner `veci-xl-native-overlay` upgrades from **1.0.1-r1 to 1.0.2-r1**. Source builder at `packaging/veci-xl-native-overlay/v12r/build-in-docker.sh` runs apk-tools v3 offline, signs only the new overlay APK, and retains unchanged root-only helper payloads. The office wrapper at `packaging/veci-xl-native-overlay/v12r/build-and-apply-office.ps1` reuses verified office workspace files safely, checks the original already installed **1.0.1-r1** rollback APK `C:\veci-build\xl-native-overlay-v12q\dist\veci-xl-native-overlay-1.0.1-r1-mipsel_24kc.apk` with SHA-256 `bc34bcee7996f5ce40e27ac46a9bb40f290c55a3b53857e14d233c5f30c0a34e`, stages the signed new APK, and runs only one offline APK simulation requiring one overlay upgrade. The router installer `packaging/veci-xl-native-overlay/v12r/guarded-overlay-install.sh` checks live file hashes, retains a tmpfs backup, upgrades only the overlay and checks hashes, other package inventory and non-overlay world constraints once; tries original signed APK rollback if the transaction fails. It cannot claim rollback tested.

The package does not change modem, LTE, SMS, USSD, native carrier binaries, firmware or public/private operator secrets. `operator_config_required` remains valid until an authorized operator API integration actually works.

## Single office cutover command (not yet executed)

```powershell
$p="$env:TEMP\veci-xl-v12r.ps1"; curl.exe -fLsS https://raw.githubusercontent.com/aicoach-alpha/zbt-we5927-openwrt/1e0745bcd23d45b8c6d8a8d55d0e2268e064552c/packaging/veci-xl-native-overlay/v12r/build-and-apply-office.ps1 -o $p; if ($LASTEXITCODE -eq 0) { & $p -Apply }
```

Expected success: `XL_V12R_BUILD=pass`, `XL_V12R_SIGNATURE=pass`, `XL_V12R_SIMULATION=one_overlay_upgrade`, `XL_V12R_RELEASE=installed`, `XL_V12R_INTEGRITY=pass`, `XL_V12R_OFFICE=live_pass`. Stop after any failure; do not repeat `-Apply` blindly. Save the office receipt for the next development cycle.

## Office cutover blocker and targeted repair — 2026-10-21

The owner ran the initial v12r `-Apply` and provided:

```text
XL_V12R_DOCKER=linux_engine_ready
XL_V12R_BUILD=pass
XL_V12R_SIGNATURE=pass
XL_V12R_NEW_APK_SHA256=e823c14e57b191bc770e59213abfb80c883fdbcf2413bae4982481b5d6467ed8
XL_V12R_ROLLBACK_APK_SHA256=bc34bcee7996f5ce40e27ac46a9bb40f290c55a3b53857e14d233c5f30c0a34e
XL_V12R_ERROR=staging_unsafe
XL_V12R_OFFICE=upgrade_blocked_review_router_receipt
```

**Root cause:** office wrapper transferred files to `/tmp/veci-xl-v12r-20261021`, whereas the router installer referenced `/tmp/veci-xl-v12r-20261020`. Router stopped at the directory preflight before simulation/upgrade; do not claim production v12r LIVE based on this output.

Targeted changes only:

- Router installer now expects `/tmp/veci-xl-v12r-20261021`: commit `a217a8f789debb13ec0dfa00d07425abb579410e`.
- Office wrapper pins that exact fixed installer and resumes the existing staging directory only if it has no upgrade backup yet: commit `6f1772465fb9f17f596898e9ec38d16dac5d60ee`.
- One source contract check PASS: matched paths, no stale staging path, correct pinned revision, verified signed-archive reuse, existing-stage resume, signature/rollback safeguards and one-package scope. **No repeated full tests.**

Run the revised office wrapper against the existing working directory; do **not** delete staging or re-sign already-verified APKs:

```powershell
$p="$env:TEMP\veci-xl-v12r-staging-fix.ps1"; curl.exe -fLsS https://raw.githubusercontent.com/aicoach-alpha/zbt-we5927-openwrt/6f1772465fb9f17f596898e9ec38d16dac5d60ee/packaging/veci-xl-native-overlay/v12r/build-and-apply-office.ps1 -o $p; if ($LASTEXITCODE -eq 0) { & $p -Apply }
```

The production baseline remains v12q `veci-xl-native-overlay 1.0.1-r1` until a newer owner terminal receipt shows `XL_V12R_RELEASE=installed`, `XL_V12R_INTEGRITY=pass`, and `XL_V12R_OFFICE=live_pass`. Stop on an unexpected error, do not blindly retry `-Apply`.

## FINAL PRODUCTION ACCEPTANCE — 2026-10-21, LIVE/PASS

This later user-provided office terminal receipt **supersedes all pending or blocked status above**. The owner executed the corrected, pinned office wrapper `6f1772465fb9f17f596898e9ec38d16dac5d60ee` from the office laptop against the WE5927 router at 192.168.1.1.

```text
XL_V12R_DOCKER=linux_engine_ready
XL_V12R_OFFICE_STAGE=resume_safe
XL_V12R_BUILD=already_valid_signed_archive
XL_V12R_BUILD=pass
XL_V12R_SIGNATURE=pass
XL_V12R_HELPERS=unchanged
XL_V12R_NEW_APK_SHA256=e823c14e57b191bc770e59213abfb80c883fdbcf2413bae4982481b5d6467ed8
XL_V12R_ROLLBACK_APK_SHA256=bc34bcee7996f5ce40e27ac46a9bb40f290c55a3b53857e14d233c5f30c0a34e
XL_V12R_BEFORE_UI_SHA256=34ae70b75a6604a1f5b2eabbab7216ba59a3567b2012ed5b73e9a5046bc98ce3
XL_V12R_AFTER_UI_SHA256=695f75b2db3397c1a41c44217e6e739522c8449a157d9c923492d448a58bca1d
XL_V12R_SIMULATION=one_overlay_upgrade
XL_V12R_PREFLIGHT=pass
XL_V12R_ACTION=upgrade_overlay_only
(1/1) Upgrading veci-xl-native-overlay (1.0.1-r1 -> 1.0.2-r1)
OK: 11.0 MiB in 157 packages
XL_V12R_RELEASE=installed
XL_V12R_INTEGRITY=pass
XL_V12R_PACKAGE=veci-xl-native-overlay-1.0.2-r1
XL_V12R_HELPERS=unchanged
XL_V12R_OTHER_PACKAGES=unchanged
XL_V12R_ROLLBACK=original_v12q_signed_apk_and_tmp_backup
XL_V12R_OPERATOR_QUOTA=unchanged_by_this_release
XL_V12R_OFFICE=live_pass
XL_V12R_ROLLBACK_ARCHIVE=retained_on_office
```

**Decision: v12r package installation and focused integrity gate accepted — production LIVE/PASS.** Current accepted package baseline:

- `veci-xl-native-overlay 1.0.2-r1` (new redacted readiness diagnostics UI)
- `veci-telco-xl-native 0.3.8-r2` (unchanged)
- `veci-telco-indonesia 0.2.2-r2` (unchanged)
- v12n signed local APK feed unchanged.

Remote OpenWrt `packages.adb` cache warnings occurred during `--no-network` solver and installation but the exact one-package upgrade succeeded; they are **not** grounds for repeated UAT. Original signed `1.0.1-r1` rollback APK is retained at the office workstation, and tmpfs staging/backup exists only while that router has not rebooted. The rollback was **not executed/tested**. The installer verified package payload hashes and package inventory; no separate post-cutover browser acceptance of the new diagnostic toggle is claimed.

**Close v12r**. No rebuild, reinstall, or repeated SIT/UAT needed. Native subscriber XL quota **remains unconnected** (`operator_config_required` was last observed prior to this UI-only release). Do not claim that carrier balance reads are live; awaiting carrier-authorized integration is a distinct task.
