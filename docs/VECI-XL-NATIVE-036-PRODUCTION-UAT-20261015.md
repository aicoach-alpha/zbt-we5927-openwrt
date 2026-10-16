# VeCI XL Native 0.3.6 — production UAT readiness gate

Date: 2026-10-15.

**Scope:** Native VeCI only; no new LuCI UI, no modem/SMS/USSD action, no Core 0.2.2 file changes.

## Finished source and signed artifacts

- Exact signed MIPS OpenWrt 25.12.5 APK: [veci-xl-native-036-5cfa0e0d3860](https://github.com/aicoach-alpha/zbt-we5927-openwrt/releases/tag/veci-xl-native-036-5cfa0e0d3860).
- APK `veci-telco-xl-native-0.3.6-r1.apk`: 34,460 bytes, SHA-256 `ca670e83b5dc454b8d0afd736846e55e578d8c0aad67ada5112b3273f2eee82c`.
- Public signing key `veci-xl-036.pem`: SHA-256 `2301eb6954b58d29bd9f76a1616a9182fc5efb04d70c29b7b6e2d4db83cfb48e`.
- Native XL RPC plugin: `/usr/libexec/rpcd/veci.xl` with `status`, `requestOtp`, `submitOtp`, `refreshQuota`. No credentials or OTP are logged or output; OTP cooldown 180 seconds.
- VeCI-only page: `/www/veci/xl-account.html` and `xl-account.js`, using existing authenticated `VeciApi` to request OTP and display only safe status. Must access it over **HTTPS** in the **same authenticated browser tab**. No local storage of number or OTP, no third-party Javascript or iframe; strict CSP. The existing Cellular page is unchanged, so this is a separately-addressable VeCI page, **not yet a Cellular inline card/link**.
- Scoped ACL: `/usr/share/rpcd/acl.d/veci-xl-owner.json` separates read-only status from account-mutating actions.
- Install script: `scripts/veci-xl-native-036-signed-deploy-20261015.sh`, supporting `--status`, `--verify`, `--install`, `--rollback`. Uses immutable SHA/signature checks and offline APK transaction simulation. Validates physical board, OpenWrt and exact installed Core 0.2.2 source hashes, including PRIVATE config hash without publishing config. It does not touch modem/SMS, upgrade the firmware, change LuCI, or silently change HTTPS listener configuration.
- Focused RPC/UI CI [38712040285 PASS](https://github.com/aicoach-alpha/zbt-we5927-openwrt/actions/runs/38712040285); signed APK CI [38712152508 PASS](https://github.com/aicoach-alpha/zbt-we5927-openwrt/actions/runs/38712152508); installer CI [38712971437 PASS](https://github.com/aicoach-alpha/zbt-we5927-openwrt/actions/runs/38712971437); VeCI-only policy gate [38712971653 PASS](https://github.com/aicoach-alpha/zbt-we5927-openwrt/actions/runs/38712971653).

## Production test admission

Before installing, run **read-only** `--status` and `--verify` on the physical WE5927 from the authorized office laptop. The package installer is **intentionally blocked** unless:

1. Router administration is explicitly configured **HTTPS-only** (no `uhttpd.main.listen_http`, non-empty `listen_https`, valid local cert/key paths). It does not automatically close port 80 or change the active router network.
2. A locally authorized operator app integration exists in root-owned 0700 RAM directories `/tmp/veci-xl-ciam`, `/tmp/veci-telco-private`, with required per-file mode 0600. Raw app secrets / proprietary mobile app keys must not be published in GitHub. The code never populates fake credentials.
3. The SDK-signed APK has valid signature and exact hash; offline dependency/transaction simulation alters **only** the optional XL package; Core 0.2.2 hashes match the physical snapshot.
4. The named physical router has sufficient overlay storage and successful existing `veci.quota` and `veci.cellular` health.

If any prerequisite fails, **NO package install happens**, and the existing Core/UI/LTE/SMS/USSD remain unchanged. This is preferable to installing an inert login page and asking the owner to debug it manually.

Even after all prerequisites, the first real OTP/profile/quota account owner test might fail because myXL reverse-engineered API request shapes, app version and response format are **not yet confirmed against the live operator**. Never claim carrier quota LIVE based on GitHub tests alone.

## Next bounded production interaction

Only if the owner requests it, supply one office-laptop PowerShell SSH command to fetch this pinned installer and run its **read-only `--status`**. Ask the owner to share only its safe output (no private files, phone numbers or OTP). If HTTPS/account prerequisites are not ready, fix those prerequisites **before** suggesting an APK installation.

No need for another broad modem, SMS, USSD, kernel, firmware or Core 0.2.2 regression suite.
