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
   guarded WPA2 preparation path now exists in the v2 Wi-Fi RPC. Exact-board,
   clean UCI, PHY and credential checks, backup and rollback. It SAVES UCI only;
   there is NO network reload or radio restart. A separately authorized manual
   reboot is required to apply the AP; then external client UAT is mandatory.
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

## Follow-up whole-firmware bug audit, 26 November 2026
Machine register: rebuild/veci-v2/contracts/veci-v2-bug-registry-20261126.json
Audit runner: rebuild/veci-v2/ci/bug-regression-gate.py
The register covers all 39 mandatory active modules and distinguishes:
- confirmed bugs repaired in source, NOT confirmed on a newly built image;
- known unresolved defects and driver/kernel risks;
- cases that can only be accepted on physical hardware or in native CI.
A known unresolved source defect now blocks the source-completion gate.
An incomplete bug record, missing test mapping, or missing module coverage
also blocks the gate. A signed firmware is still prohibited until the
existing independent physical acceptance gates are passed.
Uncertainties are never converted into PASS on the strength of source code.

## Whole-suite test evidence before this audit commit
- 517 source tests executed on andre-nas using repository suite.
- 15 failures recorded: 14 required pinned native UCI/libubox unavailable
  on the development host, plus 1 provenance test that intentionally
  rejects the uncommitted edited services.js. The latter is to be rerun
  after committing its exact reviewed source.
- Native UCI host provisioning cannot complete locally without json-c
  development headers. The source-only CI workflow installs that dependency.
- Focused regression tests for complete UI module startup, actual Addon/
  Services DOM bindings, canonical RPC discovery, bug-registry coverage,
  and exact ROM helper inclusion passed separately.
- The firmware build/source-completion gate is BLOCKED and will stay
  blocked until actual source acceptance and risk closure; the one physical
  router is untouched.

## Accepted exact-source native CI evidence
- CI workflow run: 45758892212; source: e275946043ceebce061a97042041620c0a80edf7.
- Native UCI/libubox source suite: passed.
- 39/39 scoped modules, 175 executed scoped unittest methods; all checked-in
  transcripts are byte copies of the verified CI artifact.
- Every transcript digest and each implementation/test SHA256 independently
  matched the exact tested source; zero test skips or synthetic PASS receipts.
- WIFI-003 moved from unresolved SOURCE build-blocker to unresolved HARDWARE
  verification: its kernel MCU failure remains unproven fixed. This does NOT
  relax the flash gate or the 39 physical acceptance requirements.
- REL-001 source receipts renewed based on actual CI evidence. A lab build
  remains UNSIGNED and cannot be used as an owner flash image.
