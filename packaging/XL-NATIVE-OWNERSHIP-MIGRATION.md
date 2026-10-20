# Native XL ownership-correct upgrade sources

Confirmed from live router on 2026-10-20:
- `veci-telco-xl-native-0.3.7-r1` owns `/usr/libexec/rpcd/veci.xl` and `/usr/share/rpcd/acl.d/veci-xl-owner.json`.
- `veci-telco-indonesia-0.2.1-r1` owns `/usr/libexec/rpcd/veci.quota`.
- `/usr/libexec/veci-xl-session-clear` is unowned.
- `veci-xl-native-overlay-1.0.0-r1` is already installed.

## Source handoff completed
The captured 2026-10-20 exact live sources are now split into `packaging/veci-telco-xl-native-upgrade/files` and `packaging/veci-telco-indonesia-upgrade/files`. This is **not** a replacement package build; it is an ownership-correct overlay for the original package source tree.

## Required to build replacement packages
1. Retrieve **complete original packaging metadata and file manifests** for both installed APK packages from an authorized development artifact or the office laptop. Confirm all native executables, dependencies, scripts and other files will remain intact.
2. Apply only the corresponding two XL Native files to the source for `veci-telco-xl-native`, and the quota RPC file to the source for `veci-telco-indonesia`.
3. Add the local logout helper in a versioned, non-conflicting package or in the XL Native package only after confirming file ownership and migration handling.
4. Rebuild both *same-name* packages at higher versions, using existing local signing infrastructure. Never replace an existing full native APK with a partial APK that omits its executables.
5. Perform a single file-manifest diff for each candidate and one staged installation+integrity check. Do not use `--force-overwrite` or uninstall the existing native XL/Indonesia packages.

## Safety and product limits
Do not deploy the old `veci-xl-core-policy-0.1.0-r1` APK on the live router; it conflicts with installed package ownership. The overlay APK remains installed. Do not flash firmware or modify LTE, SMS, USSD, LuCI, customer data or operator credentials. Native operator quota remains unavailable pending authorized carrier access.
