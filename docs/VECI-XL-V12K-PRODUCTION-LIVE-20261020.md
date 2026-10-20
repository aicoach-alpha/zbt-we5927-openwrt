# VeCI Native XL v12k — production LIVE/PASS

Date: 2026-10-20. Device: office-connected OpenWrt 25.12.5 ZBT WE5927. Scope: two original package owners, no firmware replacement.

## Confirmed production receipt from authorized office deployment

```text
XL_V12K_SIGNATURE=pass
XL_V12K_PREFLIGHT=pass
XL_V12K_ACTION=upgrading_two_existing_packages
(1/2) Upgrading veci-telco-indonesia (0.2.1-r1 -> 0.2.2-r2)
  Executing veci-telco-indonesia-0.2.2-r2.post-upgrade
(2/2) Upgrading veci-telco-xl-native (0.3.7-r1 -> 0.3.8-r2)
OK: 11.0 MiB in 157 packages
XL_V12K_RELEASE=installed
XL_V12K_INTEGRITY=pass
XL_V12K_CHANGED_PACKAGES=two
XL_V12K_ROLLBACK=staged_reconstructed_apks
XL_V12K_QUOTA=operator_config_required
XL_V12K_PACKAGE_WORLD=local_apk_pins_possible
XL_V12K_OFFICE=live_pass
XL_V12K_ROUTER_STAGING=/tmp/veci-xl-v12k-20261020
```

## Exact signed APKs installed

- veci-telco-xl-native-0.3.8-r2-mipsel_24kc.apk: `801b421569f6cd18ade2bfc3a86c7e61e333e680dfc41e29edffd3cdd0793f37`
- veci-telco-indonesia-0.2.2-r2-mipsel_24kc.apk: `da3d5d9da1bdc684170d75773a03562f7dcca672a3d3d8dd1575969ad4d65866`

## Rollback

- Office laptop holds reconstructed APK versions `veci-telco-xl-native-0.3.7-r1` and `veci-telco-indonesia-0.2.1-r1`; these are NOT the original signed vendor APKs.
- Router staged copies and `world.before` snapshot currently reside under `/tmp/veci-xl-v12k-20261020` and may be lost after reboot. No rollback has been performed.

## Explicitly not proven

- XL carrier-authenticated quota is not LIVE: `operator_config_required`; no subscriber/operator secrets have been supplied.
- The installer's `PACKAGE_WORLD=local_apk_pins_possible` is a warning, not evidence that a pin actually changed. Next narrow action is compare `/etc/apk/world` with the v12k `world.before` snapshot, avoiding any repeat of signed APK builds or broad UAT.
- Do not claim post-reboot persistence or a tested rollback until observed.

## Next engineering priority

1. Resolve only any changed local APK world constraints (if shown by the targeted comparison) without touching unrelated package constraints.
2. For actual XL official quota, require a carrier-authorized device-local authentication/configuration source; don't invent secrets or use local usage as remaining quota.
3. Continue feature implementation; no more v12k blanket retests.
