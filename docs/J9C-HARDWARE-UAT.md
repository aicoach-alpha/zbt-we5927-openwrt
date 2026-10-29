# J9C — Router Apps and Firmware Updater UAT Readiness

Status: STATIC SOURCE AUDIT ONLY; PHYSICAL UAT NOT TESTED; FINAL FIRMWARE FLASH NO_GO.

J8c paired firmware/feed: GitHub run 37913407078, source a919b15bc43f91071c9c655e1a557d8a0e4d5962, kernel 6.12.112, firmware SHA256 c569381ec3fd0cad7491e1ec4befed497927d25d237ef0bee4782a43eedb7a50. J9B final run 38194131118 validated four signed APK indexes, seven selected package payloads and five offline dependency simulations. That does not demonstrate install/configure/remove behavior on physical WE5927.

Automated source readiness: workflow .github/workflows/j9c-readiness.yml; unit tests tests/test_j9c_readiness.py; script scripts/j9c_readiness_audit.py; output j9c-readiness.json. Workflow checks syntax, app catalog, package lifecycle and reports structural safety risks without network/router access. A green audit never authorizes firmware flashing.

## Mandatory pre-UAT setup

Test ONLY on a separate recoverable router after explicit owner approval of device, image SHA256 and maintenance window. First verify backed-up settings, wired recovery/serial or bootloader access, flash/RAM/overlay headroom, power backup, firmware board identity and signed feed match. Never install the J8c packages on the live 6.12.94 kernel. If any runtime source code changes after the paired J8c build, rebuild both firmware and feed in one run and repeat J9/J9B before testing.

## Case matrix

| ID | Test on approved sacrificial hardware | PASS requires | Current |
|---|---|---|---|
| U01 | VeCI auth/login/logout and unauthenticated ubus | Block unauthorized reads and writes | NOT_TESTED |
| U02 | LuCI default GUI fallback | Recover management GUI reliably | NOT_TESTED |
| U03 | LAN, Wi-Fi, DHCP and DNS after reboot | No router lockout or service loss | NOT_TESTED |
| U04 | LTE/RNDIS and SIM switching/reconnection | Data/Internet recovers without modem writes | NOT_TESTED |
| U05 | Cached vs direct AT IMEI | Source labeled, privacy auto-hide, no IMEI modification | NOT_TESTED |
| U06 | Guest portal provision, enable, disable, uninstall | Captive auth, guest isolation and partial-failure rollback | NOT_TESTED |
| U07 | SQM CAKE/IFB under load and uninstall | Config valid, stable queue, no OOM or leak | NOT_TESTED |
| U08 | DDNS provider update/retry/uninstall | Correct DNS, no credential leaks, clean removal | NOT_TESTED |
| U09 | WireGuard peer add/handshake/revoke | Only intended route, no unexpected LAN exposure | NOT_TESTED |
| U10 | Voucher login, expire and revoke active client | Deny invalid, expire/revoke disconnect, no orphan state | NOT_TESTED |
| U11 | Five Router Apps install/config/remove and failure injection | No false success, app lifecycle and rollback reliable | NOT_TESTED |
| U12 | Manual firmware chunk upload, hash and board checks | Reject malformed, truncated, repeated, oversized and wrong-image inputs | NOT_TESTED |
| U13 | Signature, token expiry and auto updater | Fail closed, sysupgrade -T, no unapproved install | NOT_TESTED |
| U14 | Safe rollback and power-loss recovery | Restore bootloader, LAN, LuCI and LTE | NOT_TESTED |
| U15 | Flash/RAM/CPU usage repeated app toggles | No OOM, space exhaustion or CPU lockup | NOT_TESTED |
| U16 | Independent client-side network isolation | Trusted LAN protected from guest and unintended VPN routes | NOT_TESTED |

## Open source-review findings before live UAT

- Guest activation changes network, firewall, uHTTPd, Wi-Fi; full rollback after partial service restart failures not yet verified.
- Voucher status currently invokes cleanup_expired; querying state can mutate and restart guest authentication.
- WireGuard peer creation automatically sets route_allowed_ips=1; full-tunnel peer routes could change uplink/default route.
- Firmware validation token checks token, board and SHA but does not visibly include a timestamp/expiry window.
- Generic VeCI appAction allows proceeding if an app cleanup call returns no response; missing acknowledgement must fail closed.

Treat these as unresolved risks, not proof of exploitation. Close by correcting source, adding negative tests, rebuilding a matched firmware/feed pair, and rerunning full offline gates before physical UAT.

Evidence for each executed UAT case must record exact build/device, UTC timestamp, expected/observed outcome, masked screenshots/logs, rollback result, and operator approval. Do not copy IMEI, SIM identifiers, DDNS passwords, voucher codes or WireGuard private keys into shared reports.

Release remains NO_GO until all production-relevant tests PASS with physical evidence, signed updater + recovery PASS, and explicit operator permission for the exact final device/image. This workflow does not connect to or change a physical router.


## 2026-10-29 source remediation status (not hardware evidence)

The original review findings above are retained as historical audit observations, not current source conclusions. They have been addressed at source level and regression tested:

- Guest provision and enable use pre-change UCI snapshots with rollback; production restart and connection recovery remain UAT U06/U14.
- Voucher status is read-only; the separate expiry cleaner performs mutations; active-session revoke still requires UAT U10.
- WireGuard does not auto-install peer default routes; actual peer handling remains UAT U09/U16.
- Firmware validation token freshness and signed-image requirements are checked in non-live negative tests; actual firmware flow remains UAT U12/U13.
- App cleanup requires an explicit positive acknowledgement, and APK simulation/core-package checks fail closed; actual install/uninstall remains UAT U11.

The current General Core is r4, source commit 81853a6. The source and firmware integration have automated test coverage but **NO new r4 sysupgrade image or paired r4 signed app feed** is published by this handover. U01–U16 remain NOT_TESTED until their physical observations are recorded. FINAL FLASH remains NO_GO; only the owner can authorize manual deployment.

## Manual evidence log

| UAT ID | Device / image SHA256 | Observation and masked evidence | Rollback tested? | Tester / UTC | State |
| --- | --- | --- | --- | --- | --- |
| U01–U16 | Not provided | No physical test performed | Not verified | Unassigned | NOT_TESTED |

Log each real test as a separate row before changing any NOT_TESTED state. Never copy credentials, IMEI, SIM ID, voucher codes, or encryption keys into evidence.
