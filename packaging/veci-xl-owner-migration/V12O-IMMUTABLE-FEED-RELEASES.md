# VeCI v12o: immutable signed local APK release publisher

## Status

Source committed and one targeted syntax/static check passed. **Office Docker execution not yet observed; router production remains v12n LIVE/PASS.**

## Motivation

The v12n signed local APK feed is LIVE and registered. Subsequent VeCI updates need a reproducible versioned feed built from already-signed APKs, without repeating v12k owner reconstruction, changing firmware, or rebuilding existing packages.

## Build (office laptop only)

Use `packaging/veci-xl-owner-migration/build-versioned-feed-office-v12o.ps1`. With no parameters, it captures a signed, immutable snapshot of the deployed v12n APK versions (XL Native 0.3.8-r2, Telco Indonesia 0.2.2-r2).

With `-NativeApk PATH -IndonesiaApk PATH`, it accepts two **already signed** future release files, validates source names and signatures using the local signing public key, copies them into a new immutable directory, and creates a signed APKv3 `Packages.adb` in Alpine Docker with `--network none`.

Output lives in `C:\veci-build\xl-native-feed-releases\native-<version>__indonesia-<version>` and includes `release-files.txt`, two canonical APK archives, `Packages.adb`, and `release-receipt.txt` with the three SHA-256 values. An already-existing release directory stops the build rather than overwriting it.

**The v12o publisher does not SSH, deploy, upgrade production, change `/etc/apk/world`, touch LTE/SMS/USSD, or access any XL subscriber credentials.**

## Separate source hardening

`source/veci-quota/quota-view.js` is now fail-closed for invalid/stale/empty operator-source data. One targeted Node test passed. This source-only change is **not** bundled or deployed to the live VeCI UI at v12o.

## Next

1. Run the default office publisher once to confirm the new immutable release snapshot.
2. When a new signed release actually exists, add a guarded repo roll-forward/rollback transaction, with one package solver simulation and one integrity gate, instead of rerunning old v12k/v12n scripts.
3. Obtaining a carrier-authorized XL quota API/consent flow remains a separate external dependency. Existing status `operator_config_required` is correct until such authorization exists.
