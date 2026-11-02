# J9D — Router Runtime Hardening and Negative Regression

**Status: source fixes under CI, live router untouched, FLASH NO_GO.**

Scope is FIVE risks identified in J9C:

1. Guest Portal activation creates an in-memory backup of UCI config files (network, DHCP, firewall, wireless, uHTTPd, uspot and veci_guest) before provisioning or enable. When a service or Wi-Fi reload fails, stop guest radio, restore config and restart services. Return explicit failure, and expose `rollback_incomplete` if recovery fails. This is a best-effort UCI rollback, NOT a power-loss atomic transaction. Need physical fault-injection testing.
2. Voucher `status` does not invoke expiry deletion or restart services. The background cleaner and explicit `cleanupExpired` continue to enforce actual removal; expired vouchers are not displayed in ordinary status reads. Test expiry timing and concurrent revoke on hardware.
3. WireGuard peers default to `route_allowed_ips=0`, and app creation rejects default routes. Verify no WAN/LAN route injection or other firewall exposure on test hardware.
4. VeCI Core firmware validation token now has 600-second TTL, disallows future/invalid timestamps, uses checksum+board+token binding and removes expired metadata. Validation status must not report an expired token as ready. Hardware `firmwareApply`, signature and interrupted upload still not tested.
5. VeCI Core app package removal requires a present cleanup provider and an explicit `ok:true` response. Missing provider, empty response and errors block the package operation. Application cleanup itself must still be demonstrated with real UCI/rpcd tests.

The source in aicoach-alpha/veci is pinned via source/veci.commit and must never be replaced with floating branch references in production builds. Tests: tests/test_j9d_runtime_guards.py and tests/test_j9c_readiness.py. CI: .github/workflows/j9d-negative-tests.yml. J9C scanner differentiates MITIGATED_STATIC from genuine runtime-tested PASS.

## Remaining mandatory gates

- J9D tests must run PASS and new code must be included in **new paired firmware + app feed** after J8c; J8c original must NOT be presented as containing J9D fixes.
- Rerun J9 and J9B against those NEW same-run artifacts, including signed-index content fetches and dependency simulation. Assess checksum, ABI and overlay capacity.
- UAT needs a separately approved, recoverable test WE5927 with wired recovery, backed-up configuration, prepared UART/TFTP rescue and owner approval of test device and exact build.
- Prove Guest captive isolation, rollback after partial failure, real Voucher login/expiry, WireGuard routes, DDNS/SQM, removal, updater upload/signing/token replay and recovery.
- The live WE5927 remains on its installed firmware and must not be flashed/updated until all five Router Apps, native updater and hardware UAT are PASS and the user separately approves.
