# VeCI Native XL v12n — local signed APK repository LIVE/PASS (2026-10-20)

## Production execution receipt (office laptop → OpenWrt WE5927)

Owner ran `veci-xl-v12n-local-feed-office.ps1 -Apply` on office PC and supplied terminal output:

```text
XL_V12N_OFFICE_HASHES=pass
XL_V12N_SIGNATURE=pass
XL_V12N_SIMULATION=no_package_changes
XL_V12N_RELEASE=installed
XL_V12N_REPO=local_signed_ndx
XL_V12N_INTEGRITY=pass
XL_V12N_WORLD=name_constraints
XL_V12N_PACKAGES=unchanged
XL_V12N_CARRIER_QUOTA=operator_config_required
XL_V12N_OFFICE=live_pass
```

The offline resolver reported `OK: 11.0 MiB in 157 packages` before and after repository registration, with no installation, removal, or native APK upgrade proposed.

## What was deployed

- Existing signed package `veci-telco-xl-native 0.3.8-r2` remains installed unchanged; prior release SHA-256 `801b421569f6cd18ade2bfc3a86c7e61e333e680dfc41e29edffd3cdd0793f37`.
- Existing signed package `veci-telco-indonesia 0.2.2-r2` remains installed unchanged; prior release SHA-256 `da3d5d9da1bdc684170d75773a03562f7dcca672a3d3d8dd1575969ad4d65866`.
- Signed, offline index `Packages.adb` includes precisely two packages; SHA-256 `d4dfe6c213c6fd7ebb92e50189511b1e941105e0a43fd5ef47aae054a43525ea`.
- Local feed at `/etc/apk/veci-xl-feed` with `ndx file://...` repository; `/etc/apk/world` now uses two package-name constraints instead of archive checksum pins.
- No remote feed/service dependency, no router firmware change, no LTE/SMS/USSD changes. Private signing key remained on the office laptop.

## Completion and residual limitations

**Package ownership upgrade and offline repository migration: COMPLETE (LIVE/PASS).** Do not re-run v12k–v12n installers, rebuild existing APKs, or re-test previously accepted gates.

Carrier API: **NOT LIVE**. Native UI/API remains `operator_config_required`. The device-local authorized-config importer can validate a provider-approved configuration bundle but no credentials or operator entitlement were supplied. The myXL link is a fallback to the official service and is not an API integration or quota import.

Next implementation workstream: pursue a currently supported, user-authorized XL integration method or formally supported carrier/provider API for consent and account data. Until authorization is available, keep `authentication_required`/`unavailable` and don't fabricate quota. Separately scope a future feed refresh/update lifecycle (not needed to close v12n) when a newer signed package exists.

No claim of a tested post-reboot feed state or full reconstructed rollback: not established in supplied output.
