# VeCI v2 release gate - LTE, Wi-Fi, UI functions (26 November 2026)

## Grounded hardware baseline
One ZBT-WE5927-DSIM router, OpenWrt 25.12.6 custom v2, connected to office Windows laptop.
- SIM1 selected: UCI=1, GPIO46=1, selector-slot=1, AT+CPIN READY.
- LTE registration CEREG=0,1; CGATT=1; CGACT CID1=1; operator XL LTE.
- Public HTTPS 204 explicitly bound via usb0.
- Wi-Fi: WPA2, phy0-ap0 and hostapd ENABLED; no mt76 timeout in then-current boot log.
- User confirms SSID visible on phone, password works, internet browsing via Wi-Fi works.
- These are point-in-time observations of the ALREADY BOOTED router, NOT acceptance of
  a firmware binary built from this branch or proof of 72-hour reliability.

## Source defects and fixes
1. Factory-safe AP off with no working native activation wizard. One opt-in,
   guarded WPA2 activation path is now in the v2 Wi-Fi RPC. Explicit consent,
   clean UCI, exact board, PHY, hostapd verification, one bounded netifd reload,
   backup and fail-closed watchdog. Never auto-retry a failed attempt.
2. Wi-Fi v2 required optional hexdump for SSID/status. Use existing libubox JSON
   encoder instead and preserve the prior hex response as an accepted UI input.
3. Wi-Fi SSID/security/visibility controls were located in Network Overview,
   not the actual Wi-Fi menu. Controls are now together in Wi-Fi.
4. Services frontend called addon profile methods on veci.v2.services although
   only veci.v2.addon provides them. Calls now route to correct provider.
5. Manual SIM switch applied APN before checking SIM readiness, generating
   misleading APN error; now readiness check runs first, original selector is
   restored on error, and repeated selection of same SIM avoids power-cycle.
6. Every literal frontend RPC must exist in a staged backend provider, verified
   by automated discovery tests. Login/logout UI resets stale services state.

## Outstanding mandatory physical acceptance
- Browser UAT of every menu/button/form in desktop and mobile Firefox.
- LTE SIM1 cold boot, correct APN, registration/PDP, public internet check;
  a single tested restoration from invalid SIM, if owner approves.
- Wi-Fi SSID/WPA2 authentication, hostapd, client DHCP, DNS and HTTP on
  the NEW signed firmware, including reboot/persistence and driver health.
- SMS, guest isolation, firewall, DHCP, DNS, scheduling, addons, OTA, backup
  and restore all tested in runtime, not inferred from source only.
- Exact target signing/trust anchor and sysupgrade -T proof.
- Continuous 72-hour link and client stability monitoring. Not yet started.
- No destructive recovery, second stack, repeated firmware flash or blind
  rebuild when the source package is still incomplete.

The current owner router remains untouched. All changes are source-only.

## Development / CI gate results at 26 November 2026
- 54 focused source regression tests passed before additional GUI fixture repair.
- Comprehensive local suite: 505 tests; 15 failures from missing native host
  UCI/libubox fixture and 1 browser mock missing document.body.classList.
  Browser session mock repaired and isolated test passed. Remaining native
  tests have NOT been counted as passed.
- Historical source-provenance tests now verify original bytes at their
  original Git commits, plus exact current committed worktree, rather than
  requiring modern fixes to keep obsolete hashes.
- Source-completion gate remains BLOCKED on 31 source hash mismatches in
  owner-final-source-evidence.json. Preserve this block; regenerate accurate
  test receipts and manifest hashes only after new source testing.
- The host-only native UCI provisioner is allowed to run ahead of source
  completion so that stale source receipts can actually be renewed.
  It does not build a firmware image or relax release-gate.py.
- Native test tool provisioning on andre-nas attempted; missing json-c
  development headers stopped cmake. The GitHub CI workflow already installs
  libjson-c-dev before provisioning. Native full-suite result: PENDING CI.
- No GUI/browser full E2E, real new-binary LTE/Wi-Fi UAT, signing or 72h
  acceptance has been completed.
