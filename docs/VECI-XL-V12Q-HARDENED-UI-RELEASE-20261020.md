# VeCI XL v12q — hardened UI overlay 1.0.1-r1

## Current state

Based on previously observed owner receipts, v12n is LIVE/PASS with `veci-telco-xl-native 0.3.8-r2`, `veci-telco-indonesia 0.2.2-r2` and a two-package signed local feed. v12o is a checksum-identical offline snapshot, **not an upgrade**. v12p is a future two-owner feed updater; it is **not** required for this v12q UI-only release.

**v12q is source-ready, focused test PASS, production install pending owner execution.**

## Functional change

The current UI in `www/veci/js/lib/veci-xl-connection-status.js` previously accepted an `operator` quota bucket with no total and no expiry even when the backend did not explicitly authorize a partial remaining-only response. New logic requires both `total_bytes` and `expires_at` for complete balances; when `quality=remaining_only` is explicitly present, it allows verified remaining bytes without synthesizing other values. It also rejects nonnumeric, negative, internally inconsistent, empty, stale and unauthenticated data. The myXL official fallback remains unchanged; the UI never calls the operator directly.

One scoped executable owner-panel test passed: two accepted response variants, seven malformed/stale cases rejected, missing carrier config disables quota call. **No real operator access or OTP attempted.**

## Package and permission integrity

The *same installed package owner*, `veci-xl-native-overlay`, is upgraded from `1.0.0-r1` to `1.0.1-r1`. Payload contains exactly the existing three application paths: new JS, unchanged quota session gate, unchanged authorized config importer. Web directories are explicitly 0755, UI JS 0644, private helper executables 0700. No separate owner package and no `--force-overwrite`.

Builder `packaging/veci-xl-native-overlay/v12q/build-in-docker.sh` runs with Docker networking disabled and signs only the *new* APK. The office script requires the exact **original signed installed v1.0.0-r1 APK** as rollback at `C:\veci-build\xl-overlay\dist\veci-xl-native-overlay-1.0.0-r1-mipsel_24kc.apk`, SHA-256 `5b418533be9ffdfced4b357bef933934496606f769d400c99df3921116dec486`. Missing or altered original archive blocks any router action; no reconstructed rollback version is substituted.

The installer checks existing installed v1.0.0 version, original UI and helper SHA-256 against commit-pinned source, verifies the two APK signatures with a temporary public-key directory, runs one offline solver simulation requiring exactly one named upgrade, saves world and file backups, and upgrades only `veci-xl-native-overlay`. One post-install gate verifies new version, three file hashes, unchanged other-package list, and unchanged other-world constraints. If install or integrity fails, rollback to the original signed archive is attempted and outcome is reported. Does not flash firmware, restart modem, or request carrier API access.

The legacy loose-file release reconciler was updated to return `XL_RELEASE_LEGACY_RECONCILE=skipped` when the signed overlay is already at 1.0.1-r1, avoiding downgrading the UI. Canonical OpenWrt Makefile now targets 1.0.1.

## Owner execution (office Windows PC)

```powershell
$p="$env:TEMP\veci-xl-v12q.ps1"; curl.exe -fLsS https://raw.githubusercontent.com/aicoach-alpha/zbt-we5927-openwrt/45f9c4f39793da99f8f6deab2c5a4fcf885a570a/packaging/veci-xl-native-overlay/v12q/build-and-apply-office.ps1 -o $p; if ($LASTEXITCODE -eq 0) { & $p -Apply }
```

Expected success includes `XL_V12Q_BUILD=pass`, `XL_V12Q_SIGNATURE=pass`, `XL_V12Q_SIMULATION=one_overlay_upgrade`, `XL_V12Q_RELEASE=installed`, `XL_V12Q_INTEGRITY=pass`, `XL_V12Q_OFFICE=live_pass`. Stop and inspect if any other receipt occurs; never repeat `-Apply` indiscriminately.

## External dependency

This is a UI correctness release, not carrier authentication. `operator_config_required` remains the last observed live state; a supported XLSMART/XL operator API enrollment path and authorized configuration are still required for real remaining quota. Do not invent endpoint credentials, scrape app secrets, or show local data-meter bytes as operator quota.
