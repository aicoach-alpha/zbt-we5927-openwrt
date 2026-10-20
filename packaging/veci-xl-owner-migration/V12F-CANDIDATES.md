# XL same-owner upgrade candidates — v12f

The original signed APK archives for `veci-telco-xl-native-0.3.7-r1` and `veci-telco-indonesia-0.2.1-r1` were **not** found by the targeted search on the office laptop (`XL_V12E_ORIGINAL_CANDIDATES=0` for both). The production router remains unchanged.

## Candidate build path

`build-candidates-office-v12f.ps1` assembles two signed APKv3 candidates entirely on the office laptop using the previously captured and SHA-256-verified `C:\veci-build\xl-native-origin\staged-v12b` snapshot:

- `veci-telco-xl-native-0.3.8-r1-mipsel_24kc.apk`, all **15** captured files
- `veci-telco-indonesia-0.2.2-r1-mipsel_24kc.apk`, all **6** captured application files including original, unchanged `quota.js`

The original `lib/apk/packages/veci-telco-indonesia.list` is packaging metadata, **not** bundled as an application file. Dependency lines are read from the captured `apk info --depends` metadata; unrecognized dependency format aborts the build instead of guessing. The builder checks exact file-list equality, the historical `quota.js` digest, existing account/owner-ACL/logout source, RPM-independent OpenWrt APKv3 signing and signature verification. It does not access the router or upload private binary snapshots and keys.

**Important: these are staging-only candidates. DO NOT INSTALL THEM ON PRODUCTION.** The original APK archives and their maintainer scripts/triggers were not recovered; signing and matching file counts do not guarantee upgrade-script parity or dependency correctness. `XL_V12F_INSTALL_GATE=blocked_original_maintainer_scripts_not_recovered` is an intentional safeguard.

The local logout helper `/usr/libexec/veci-xl-session-clear` is currently unowned and is **not** part of the 21 existing package-owned application files. It must be handled in a final owner-aware package migration, not silently dropped or claimed to be owned in v12f.

Next: obtain the original packaging hooks from a build source/artifact or independently design and review an explicit same-owner migration with rollback, then stage a single upgrade and integrity check. No firmware or carrier access claims are made at this stage.
