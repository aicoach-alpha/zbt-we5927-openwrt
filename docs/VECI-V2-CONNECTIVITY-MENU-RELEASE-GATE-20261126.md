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

## Actual owner MT76 production observation, 26 November 2026
- Owner ran read-only script via Windows PowerShell and SSH to the sole existing router.
- 10/10 samples: radio0.up=true, hostapd ENABLED; LTE HTTPS via usb0 HTTP 204.
- WPA2 configuration valid, 0 baseline mt76 errors and 0 new errors during approximately 4.5 minutes sampling.
- CLIENT_COUNT=0 in every sample. No associated-client MT76 test was performed in this run.
- No network reload, Wi-Fi restart, reboot, SIM change or flash performed.
- WIFI-003 remains awaiting true MT76 fault-condition testing and new candidate hardware acceptance; passive idle PASS does not prove root cause fixed.
- Machine evidence: rebuild/veci-v2/contracts/owner-mt76-production-passive-20261126.json.

## Second owner passive MT76 production run, 26 November 2026
- 20 samples at 30-second intervals: Wi-Fi control plane PASS 20/20; LTE HTTPS 204 PASS 20/20; MT76 new errors 0.
- CLIENT_COUNT=0 for all 20 samples, again. Across both sessions: 30/30 control-plane and LTE PASS, zero detected new MT76 errors, and zero observed clients.
- Original script discards iw station dump stderr and pipes output through grep -c, which may report 0 even if iw fails. Client association remains unverified until iw exit and station count are checked independently.
- WIFI-003 remains NOT PROVEN RESOLVED; no new-image physical hardware acceptance. No router configuration mutated.

## MT76 diagnostic after second production passive run (26 Nov 2026)
- Owner query: iw dev phy0-ap0 station dump exit 0, Station lines=0.
- Hostapd UBUS get_clients call exit 0, but jsonfilter wildcard authorized counter=UNKNOWN.
- This proves the station dump returned 0 associations at that instant, not that the phone was connected or MT76 failed.
- Use native libubox jshn json_load, json_select clients, json_get_keys to distinguish empty hostapd client map from JSON parse failure. Keep MACs hidden.
- WIFI-003 remains requires_hardware_verification, root cause unresolved and next-image hardware not tested.

## MT76 station diagnostic with native JSON parser (26 Nov 2026)
- Owner read-only command confirmed iw dev has phy0-ap0 of type AP.
- iw station dump: exit 0, stations 0; hostapd.phy0-ap0 get_clients: exit 0, native jshn client map count 0.
- Both sources show zero associated stations at this sampling instant; prior JSON-filter UNKNOWN is resolved.
- Still not evidence of MT76 fault or stability under actual client load. Next safe step is phone airplane mode plus manually enabled Wi-Fi, confirmed SSID and a brief read-only association check.

## Five-sample live association diagnostic, 26 Nov 2026
- Owner read-only script checked every two seconds over five samples: iw exit 0, IW_CLIENTS=0; hostapd get_clients exit 0, HOSTAPD_CLIENTS=0 on all samples.
- Phone connection, airplane mode, and successful Wi-Fi internet during the exact sampling window were not explicitly confirmed in this message.
- No observed association under load, no demonstrated driver failure. WIFI-003 stays pending active-client testing; no router changes.

## Read-only client association counter correction
- Added scripts/router/veci-mt76-client-evidence-readonly.sh: discovers primary AP from netifd, checks real iw AP mode, and compares iw station dump with hostapd clients parsed by libubox jshn. No MACs or credentials are displayed.
- Counts are UNKNOWN rather than fabricated 0 when either API or parser fails; five 2-second spaced samples distinguish empty, positive and inconsistent associations.
- Regression tests simulate empty map, one station, disagreement and wrong-board denial; no radio, network, SIM, modem or firmware mutations.
- A positive association is still NOT equivalent to traffic/stress stability. WIFI-003 remains a physical UAT blocker for the new firmware.

## Production client evidence V2, 26 Nov 2026 at 16:35 local
- Owner Windows log VeCI-WE5927-MT76-ClientEvidence-V2-20261126_163538.log was pasted into chat; original full logfile has not been uploaded.
- Five read-only samples: WIFI and LTE HTTPS 204 PASS 5/5; baseline and new MT76 errors zero; IW and hostapd APIs exit 0, station counters match 5/5, both 0 clients throughout.
- Across monitored Wi-Fi/LTE sets, 35/35 samples passed control-plane health (10 + 20 + 5). The earlier five-sample association-only probe is tracked separately.
- Client presence with live Wi-Fi Internet remains unconfirmed; no stress test or proof the driver root cause is resolved. Candidate hardware UAT remains NOT RUN.

## Owner clarification: Wi-Fi association and Internet are functional
- Owner explicitly confirms Wi-Fi can connect and internet works (26 Nov 2026). This statement does not establish that a client was connected during the five V2 diagnostic samples.
- The zero-client counts from kernel station table and hostapd remain unexplained, not a proven driver failure. Check the serving AP BSSID/interface and count during the same active-traffic interval.
- Preserve read-only production state. WIFI-003 remains unverified until actual on-air association/traffic and stability are observed.

## Owner live primary AP metadata, 26 Nov 2026
- SSH read-only iw dev phy0-ap0 info: SSID VeCI-WE5927, type AP, wiphy 0, channel 1 / 2412 MHz / 20 MHz, TX power 20 dBm.
- Full AP BSSID was shown to owner but is intentionally excluded from public source evidence.
- TXQ counters are not evidence of associated clients. Compare phone BSSID and AP BSSID during live traffic before attributing zero stations to MT76.
- This does not change WIFI-003 source or candidate hardware acceptance status.

## Next-firmware client-status reconciliation fix (source only)
- WIFI-008 fixes the unsupported client-offline claim in GUI. The existing Wi-Fi info RPC now cross-checks iw station dump and hostapd get_clients using native libubox JSON parsing in a subshell.
- New response client_observation.state is observed, zero_observed, mismatch, or unavailable; counts are included only when the corresponding source succeeded. Existing clients array is retained for backwards compatibility.
- GUI distinguishes zero clients detected AT SAMPLE TIME (not proof of disconnect), disagreement, unavailable and positively observed clients. Client display is not a driver-level stress PASS.
- Native UCI fixture exercises real libubox parse; Node VM executes actual render function with five cases; three Wi-Fi core modules require NEW exact-source acceptance receipts before next image compilation.
- This source edit has NOT been flashed, deployed or hardware-tested. Current production LTE and Wi-Fi unchanged. WIFI-003 remains under physical verification.

## Next operation: read-only primary Wi-Fi AP identity and byte counter
- The existing veci.v2.wifi info RPC now returns an optional ap_snapshot containing the netifd-selected primary interface, validated AP BSSID, rx_bytes, tx_bytes, and explicit attribution marker.
- The existing native GUI Wi-Fi panel shows that AP identity and cumulative bytes on user refresh; it labels interface byte counters as inclusive of broadcast, **not proof of active clients or Internet traffic**.
- Reads sysfs and does not scan, reset, restart, reload, change SIM, or modify UCI; no new provider, router, control path or authorization scope.
- Native UCI/libubox host fixture and Node render regressions cover real payload shape. Physical/router production remains unchanged and WIFI-003 not resolved.

## Guest optional OFF default and actual runtime visibility — source update
- Reused existing veci.v2.guest status and veci.v2.addon setPortalStartup; no duplicate endpoint or manager.
- Guest inspector now separates saved UCI enabled_configured from guest_ap_runtime: unavailable, not_observed, ap_running_unverified, based on selected netifd guest interface + iw type AP + hostapd ENABLED, read-only.
- Guest and addon UI now clearly label startup configuration vs observed live AP. Guest isolation verification remains null until real firewall/guest-client UAT; enabling guest still requires separate manual restart/boot.
- Original guest provisioning default disabled remains unchanged. No Wi-Fi, LTE, modem, SIM, firewall or router mutation was executed.

## Development operation: pinned OpenWrt source download cache, 27 Nov 2026
- Laboratory full-image builds now reuse only OpenWrt dl/ downloaded source tarballs under a cache key pinned to the exact upstream source commit. Default GitHub Actions cache is immutable and first fill occurs during one successful build.
- Source completion gate still precedes dependency install, source stage and cache restoration. Every future run recompiles all build_dir and staging_dir binaries and repeats SHA256, board metadata, exact ROM content and signature prohibition checks.
- No cache of signed keys, firmware images, toolchains, compiled packages or physical UAT; benchmark speed improvement remains NOT MEASURED until the next build.
