# VeCI XL v12s — On-demand Local Data Meter Diagnostics (2026-10-21)

> **CANCELLED BEFORE DEPLOYMENT — 2026-10-28.** Do not run the v12s `-Apply` command below. The user retired XL carrier quota and USSD. Migrate any useful read-only local Data Meter diagnostics into the new non-XL navigation after retrieving actual VeCI frontend source. Current confirmed live overlay baseline remains v12r `1.0.2-r1` until verified otherwise.


## Release scope and current authority

**SOURCE READY / FOCUSED TEST PASS / PRODUCTION NOT DEPLOYED.** The last observed production baseline is v12r, `veci-xl-native-overlay 1.0.2-r1` LIVE/PASS. Do not call v12s LIVE until the office router prints `XL_V12S_RELEASE=installed`, `XL_V12S_INTEGRITY=pass` and `XL_V12S_OFFICE=live_pass`.

The same-owner overlay upgrade `1.0.2-r1 → 1.0.3-r1` ships a UI-only feature: a diagnostician may choose **Lihat Diagnostik XL → Periksa Data Meter Lokal** and optionally **Salin Laporan Aman**. Data Meter lookup calls only `veci.meter status` using the existing logged-in VeCI RPC session **when clicked**, and explicitly says that the counter or estimate is **not remaining quota from XL**. The report contains only whitelisted local state labels and preset advice; it excludes raw RPC payload, subscriber numbers, credential fields, OTPs, tokens, exception messages, and raw usage-counter values. A failed/unregistered meter RPC reports `rpc_tidak_tersedia` rather than simulating a reading. The official myXL fallback and XL authentication paths are unchanged.

## One focused test

A small simulated-DOM source harness was executed with PASS checks: diagnostic controls initially hidden; no meter call until clicked; exactly one meter status call on demand; no OTP; correct local-counter vs remaining-quota label; valid official operator-source quota still displayed; a malformed authenticated meter response and an RPC exception were safely redacted; and safe clipboard text excluded sensitive fields. The fixture is committed at `packaging/veci-xl-native-overlay/v12s/tests/local-meter-diagnostics.test.cjs`.

## Build and install contract

- Source: `packaging/veci-xl-native-overlay/v12s/files/veci-xl-connection-status.js`.
- Offline signed APKv3 builder (apk-tools 3): `packaging/veci-xl-native-overlay/v12s/build-in-docker.sh`.
- Single-overlay guarded router installer: `packaging/veci-xl-native-overlay/v12s/guarded-overlay-install.sh`.
- Resumable office wrapper: `packaging/veci-xl-native-overlay/v12s/build-and-apply-office.ps1`.
- Source package version `1.0.3-r1`, architecture `mipsel_24kc`. The two helper scripts remain byte-for-byte unchanged. Web directory mode 0755, UI JS 0644, private helpers 0700.
- The **exact signed v12r 1.0.2-r1 APK** is required for rollback at `C:\veci-build\xl-native-overlay-v12r\dist\veci-xl-native-overlay-1.0.2-r1-mipsel_24kc.apk`, SHA-256 `e823c14e57b191bc770e59213abfb80c883fdbcf2413bae4982481b5d6467ed8`. No reconstructed rollback archive.
- Office and router staging path are identically `/tmp/veci-xl-v12s-20261021`, preventing the previous release's date mismatch.
- One offline solver simulation must show **exactly one** upgrade `veci-xl-native-overlay (1.0.2-r1 -> 1.0.3-r1)`. Only then can the installer upgrade and run one package/version/file-hash/world/non-target inventory integrity gate. On failure, revert using the original signed archive where possible and report any unresolved rollback errors.
- No modifications to LTE, modem, SMS, USSD, core XL native binaries, telco owner package, signed two-owner local feed or firmware.

## Office execution — owner-gated

```powershell
$p="$env:TEMP\veci-xl-v12s.ps1"; curl.exe -fLsS https://raw.githubusercontent.com/aicoach-alpha/zbt-we5927-openwrt/013059c8020fc0be7d08cad0441cb3cae2922b23/packaging/veci-xl-native-overlay/v12s/build-and-apply-office.ps1 -o $p; if ($LASTEXITCODE -eq 0) { & $p -Apply }
```

Required production receipt: `XL_V12S_BUILD=pass`, `XL_V12S_SIGNATURE=pass`, `XL_V12S_SIMULATION=one_overlay_upgrade`, `XL_V12S_RELEASE=installed`, `XL_V12S_INTEGRITY=pass`, `XL_V12S_OFFICE=live_pass`. Stop rather than retry if any prerequisite fails. Do not rerun previous v12k–v12r builders or SIT/UAT.

## Unchanged operator dependency

Actual carrier-authenticated XL quota remains unavailable without operator-authorized session/API configuration. The new local Data Meter probe **does not** fix or fake this dependence and must never be described as real remaining quota.
