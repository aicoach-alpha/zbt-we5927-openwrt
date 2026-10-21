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
