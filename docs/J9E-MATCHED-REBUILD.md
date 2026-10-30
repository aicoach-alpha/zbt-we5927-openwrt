# J9E — J9D-pinned rebuild + same-run J9/J9B release gate

**Date:** October 12, 2026. **No live router changes authorized.**

## Target build

- Firmware integration source branch: `feat/veci-default-ui`.
- J9D Core pin: `e76aa29be080dbfeaa01d163afa6faff677436be`.
- Build workflow hardening commit: `4e7adac5e9b03a675803d48f317b3a02f608ed1e`.
- J9E build workflow run: [38195466214](https://github.com/aicoach-alpha/zbt-we5927-openwrt/actions/runs/38195466214).
- The earlier build run 38195018385 was based on pre-J9D source `ec907c55` and is **NOT a J9E candidate**.

## Automatic gate design

Workflow `.github/workflows/j8c-app-feed.yml` now:
1. Pins the firmware integration commit and VeCI Core commit in release metadata.
2. Runs all seven J9D negative-regression tests against exactly the staged VeCI Core code before compiling.
3. Requires five J9D static mitigations in the existing J9C scanner, while confirming `flash_decision: NO_GO`.
4. Builds firmware and five optional Router App APKs from a pinned OpenWrt tree and exact package feeds, as a SINGLE paired build.
5. Uploads the firmware artifact and matching app-feed artifact.
6. Starts `j9e-artifact-audit`, which downloads both artifacts from this exact workflow run, never a fixed old run.
7. Re-runs J9 file hashes, manifest, size, kernel ABI and app inventory.
8. Re-runs J9B with firmware-derived public keys, all 4 signed repository indexes, 7 package payload checks and all 5 offline dependency simulations.
9. Emits `j9e-provenance.json` with GitHub build SHA, pinned Core SHA, kernel, firmware SHA256, signed index count, payload count, and solver count. The audit job must fail if any mandatory check is not PASS, and always asserts `release_decision: NO_GO`.

## Acceptance

- **J9E_BUILD_PASS** requires GitHub `build` job success and both paired artifacts present.
- **J9E_OFFLINE_PASS** requires the second `j9e-artifact-audit` job success, checksums and signer/solver gates PASS, a complete provenance report and no artifact mismatch.
- **J9E_LIVE_UAT_NOT_TESTED** is never promoted to product PASS or release GO on CI evidence alone.
- Hardware UAT requires a separately approved, recoverable test WE5927, backups, serial/TFTP rescue, wiring and recovery proof, owner authorization, and all five Router Apps and native updater functional tests.
- The live WE5927 must not be flashed, rebooted, have the J8c feed installed, or have its modem identity modified without direct explicit approval.

## Current status

See [J9E Actions run](https://github.com/aicoach-alpha/zbt-we5927-openwrt/actions/runs/38195466214). A green J9D/preflight status does not imply that the long OpenWrt rebuild has finished. Never substitute the original J8c run 37913407078 when reporting J9E.
