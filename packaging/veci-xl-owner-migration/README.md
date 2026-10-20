# VeCI XL — Two-owner Core Migration (2026-10-20)

The LIVE router reports that core paths have two **different APK owners**:
- `veci-telco-xl-native-0.3.7-r1` owns `usr/libexec/rpcd/veci.xl` and `usr/share/rpcd/acl.d/veci-xl-owner.json`.
- `veci-telco-indonesia-0.2.1-r1` owns `usr/libexec/rpcd/veci.quota`.
- `usr/libexec/veci-xl-session-clear` is presently unowned.

**Do not install `veci-xl-core-policy-0.1.0-r1`**. Its signed build is a verified source snapshot, NOT an admissible on-router package. It would conflict with three owned file paths. Never use `--force-overwrite`, `--force-broken-world`, removal of installed owners, or blanket `apk upgrade`.

## Required build release train
To graduate the policies into APK ownership correctly:

1. Retrieve **complete original APKv3 archives** (not merely current versions of the four policy files) for both owning packages. They may include native binaries, helper scripts, post-install hooks, triggers and dependencies that must be preserved. Work only with APKs sourced from an authorized build; preserve their SHA-256.
2. Analyze package metadata and file manifests. Prove original binary/runtime contents are retained, including `veci-xl-ciam`, `veci-xl-crypto`, `veci-xl-profile-chain` and others. Preserve `veci.quota` non-XL provider handlers.
3. Build signed *upgraded versions of the same two package names*, updating only `veci.xl`, its owner ACL, `veci.quota`, and bundling `veci-xl-session-clear` under XL native. Do not promote separate Core Policy package as owner.
4. Stage both owner upgrades **together**, verify local APKv3 signature and dependencies, and perform one bounded simulator/solver check. Install only if rollback APKs and matching private backup are available. No firmware switch.
5. One registration/integrity check; rollback both packages together if necessary.

Current signed overlay `veci-xl-native-overlay-1.0.0-r1` remains installed. Do not rebuild it. Native carrier quota is still blocked pending authorized XL API credentials/consent.

## Evidence to acquire next
Run only `scripts/veci-xl-two-owner-package-inventory-20261020.sh` on the office-connected router. This script reports installed file manifests and local APK archive availability **without exposing package contents, subscriber data, credentials or tokens**.

No source replacement is performed by the inventory. If original APKv3 archives cannot be located, stop the ownership migration and retain the stable working router. Creating owner upgrades by guessing package payload is not an acceptable implementation shortcut.
