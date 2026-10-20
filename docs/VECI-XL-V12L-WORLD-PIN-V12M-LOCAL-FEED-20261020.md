# VeCI Native XL v12l → v12m — local APK world pins and private signed feed

## v12l finding (2026-10-20)

The router is LIVE/PASS at:

- `veci-telco-indonesia 0.2.2-r2`
- `veci-telco-xl-native 0.3.8-r2`

The v12l read-only comparison found **two intentional digest pins updated** by the `apk add /tmp/....apk` production transaction. Before and after lines are both `name><Q1...` values; the installed packages match the new binaries. This is expected `apk add FILE.apk` behavior, **not** corrupt world state. Do **not** restore the old content digests or run `apk del`.

## Correct distribution migration

Until a normal signed VeCI APK repository is available, preserve the current valid digest pins. Unpinning only by replacing `world` with two bare names without a corresponding available repository is not a safe fix.

A self-contained local repository can provide name-based installation while preserving independent VeCI packages and avoiding a developer-hosted server. Build on the office laptop using `packaging/veci-xl-owner-migration/build-offline-feed-office-v12m.ps1`. It checks the two LIVE APK SHA-256 values, copies them to canonical `name-version.apk` filenames, creates an APKv3 `Packages.adb` index with `apk mkndx --sign-key`, and verifies the signature. It has no SSH, modifies no router, and keeps the private signing key on the office laptop.

Only after the offline repository is genuinely built and its index signature verified should a separate, guarded operation:

1. Check router overlay capacity and archive current package/world state.
2. Transfer only signed packages, index, and public key.
3. Install an explicit, local `ndx file://...` repository reference and a properly scoped trusted public key.
4. Run **one** offline `apk add --simulate` for the two bare package names; verify it proposes no package installation, removal or unrelated changes.
5. Apply name-based `apk add` only when the plan is safe, then verify versions and world constraints once. On failure, restore the prior repository config and world snapshot; do not uninstall either VeCI package.

Repository format `ndx file://.../Packages.adb` is documented in apk-repositories(5). File-based APK installs pin the identity checksum, as documented by apk-add(8).

## Product scope

Do not touch LTE, SMS, USSD, firmware, Nextcloud, or unrelated packages. Do not claim real XL operator quota is LIVE until a permitted subscriber-authenticated adapter succeeds. Native XL binaries alone cannot supply the missing carrier authorization. No repeated broad UAT.
