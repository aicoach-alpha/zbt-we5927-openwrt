# VeCI XL native v12i — exact hooks and reconstructed rollback

## Authoritative source evidence

Uploaded archive `veci-xl-v12h-original-hooks-20261020.tar.gz` was inspected and has SHA-256 `b10ee80013608f6f1f66d234588f3cd708c79e5d8cfc3ffbdf960b07e2a33ca7`.

Original installed `veci-telco-indonesia-0.2.1-r1` APK hooks:

| Hook | SHA-256 | Behavior |
| --- | --- | --- |
| post-install | `10aaaceb1f28a6d7c94833275b7bff3b4f244aa46adb38f335a6234aa07ddad4` | sources OpenWrt `/lib/functions.sh`, sets package name, calls `add_group_and_user`, `default_postinst` |
| post-upgrade | `e6cc1bb6d32da1d183ad458231919e55fbab2692a7c5fbd15295ebcab1f6b570` | exports `PKG_UPGRADE=1`, performs same OpenWrt post-install functions |
| pre-deinstall | `5a46723558bc474f6f4e695d0ec30dcbd8a414c701d82d2d480c05dd852d9c62` | calls OpenWrt `default_prerm` |

Installed script database list contained no entries for `veci-telco-xl-native`. The scripts were inspected as text only; **never run on the host**.

## v12i build

Run `packaging/veci-xl-owner-migration/build-candidates-office-v12i.ps1` on the authorized office laptop. The source files, original `veci-telco-indonesia.list`, and original hooks remain locally on the office laptop, never uploaded to GitHub.

Builds two candidate signed APKv3 archives:

- `veci-telco-xl-native-0.3.8-r2-mipsel_24kc.apk` — 15 original package-owned application files; no unverified maintainer hooks.
- `veci-telco-indonesia-0.2.2-r2-mipsel_24kc.apk` — 6 original application files **plus** original `lib/apk/packages/veci-telco-indonesia.list`, with the three installed OpenWrt hooks included via `apk mkpkg --script TYPE:FILE`.

Builder also generates signed **reconstructed rollback archives** from the captured original payload:

- `dist/rollback/veci-telco-xl-native-0.3.7-r1-mipsel_24kc.apk`
- `dist/rollback/veci-telco-indonesia-0.2.1-r1-mipsel_24kc.apk`

These reconstruct files and scripts but are **not byte-identical original vendor APKs** (original signed packages were not found, and not all original metadata is available). Treat them as provisional rollback candidates, not a verified rollback path.

## Production gate

**Do not install yet**. Signed archives and matching captured files are necessary but not sufficient. Next perform a **single targeted offline transaction simulation against installed package versions, owner conflicts and reverse dependencies**; validate executable modes and restoration sequence. Only then plan a controlled router upgrade with tested rollback and one post-upgrade integrity check.

No firmware flash, LTE/SMS/USSD restart, customer-secret export, external server, or OTP operations are part of v12i. Carrier quota remains unconnected without authorized XL configuration.
