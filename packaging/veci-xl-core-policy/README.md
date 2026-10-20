# VeCI XL Core Policy — captured from live router 2026-10-20

## Evidence
- Office-captured archive SHA-256: `4d6831523d92fd0e674f0406c6b758100c11f62d6cd54267f3a623946b31a795`.
- Captured from **office laptop connected to** `root@192.168.1.1`; not from `andre-nas`.
- Four source files are versioned in `files/`: native account dispatcher `veci.xl`, read-only quota dispatcher `veci.quota`, owner ACL, and local logout helper.
- The source archive was examined; no subscriber caches, OTP, passwords or provider API keys were present.
- This package is a **policy extension**, not a rewrite of the separately installed native CIAM binary or its provider integrations.

## Signed APKv3 build
Use `build-office-windows.ps1` on laptop `2024NB`. It reads the previously captured archive and extracted files under `C:\veci-build\xl-core-source`, checks the original archive hash and each individual file SHA-256, then mounts source into an Alpine apk-tools v3 Docker image. It signs the output with existing local RSA key via a **read-only key mount**. This build step makes no SSH connection and does not modify the router.

Expected output:
`C:\veci-build\xl-core-policy\dist\veci-xl-core-policy-0.1.0-r1-mipsel_24kc.apk`.

## Installation is a separate gated step
The original file ownership of all four core files **must** be checked on the target router using `apk info -W` before installation. If any file is owned by `veci-telco-xl-native` or another package, do NOT install `veci-xl-core-policy` on top of it. Instead coordinate file ownership in a versioned rebuild of the owning package, or use a non-conflicting staging prefix.

Also check that `veci-telco-xl-native`, `veci-xl-native-overlay`, `rpcd`, and `jsonfilter` remain present. Never use `--force-overwrite` or `--force-broken-world`. Production firmware must not be flashed at this step.

## Carrier limitation
Building and signing the core package do not unlock XLSMART's operator API or establish an authorized subscriber session; official XL quota remains unverified. No testing of v1-v10 is needed.
