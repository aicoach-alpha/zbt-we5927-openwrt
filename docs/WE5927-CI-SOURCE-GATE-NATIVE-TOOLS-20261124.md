# WE5927 CI native-test ordering incident (2026-11-24)

After the historical 40/40 source tree was merged into the newer LTE/GUI branch (39 active modules, USSD retired), two GitHub workflows ran native-dependent unit tests before provisioning pinned host UCI and libubox. CI failed on missing VECI_HOST_UCI and jshn.sh; those same tests passed when native dependencies were present. These are CI-environment setup errors, not evidence of 19 broken hardware functions.

Fixed workflow ordering:
1. Run the strict 39-module source-completion gate before dependency installation or compilation.
2. Install host dependencies including libjson-c-dev, cmake, pkg-config, and toolchains.
3. Compile pinned native UCI and libubox using scripts/ci/provision-native-uci-tests.sh.
4. Source the generated native-test-env.sh and check UCI/jshn paths.
5. Verify pinned Git provenance, run complete source suite and secondary suite.
6. Only after these pass, fetch exact OpenWrt source, stage firmware packages, compile, and inspect ROM payload.
7. Export binary only through explicit workflow_dispatch from allowlisted integration branch, as UNSIGNED / DO NOT FLASH pending offline signature and physical trust/compatibility checks.

Regression test scripts/tests/test_owner_integration_export_strict_20261124.py enforces this ordering for both CI workflows and ensures export requires a manual opt-in. Physical router unchanged.
