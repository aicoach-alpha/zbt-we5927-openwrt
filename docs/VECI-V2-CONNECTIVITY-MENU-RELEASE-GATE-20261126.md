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

## Signed offline candidate f87e7ec5 — 27 Nov 2026 (NO FLASH APPROVAL)

- GitHub Actions full lab image [run 45901493124](https://github.com/aicoach-alpha/zbt-we5927-openwrt/actions/runs/45901493124): **SUCCESS**, exact source f87e7ec5fec2c437d65fd95e7139bff90eb3019a, OpenWrt 25.12.6, zbtlink,zbt-we5927.
- UNSIGNED CI source image 5,898,530 bytes, checksum and CI verification report passed, 77 source ROM payloads recorded.
- Offline-only signing (existing trust key fingerprint 1d8759d36251c36c) produced VeCI-v2-WE5927-2SIM-f87e7ec5-SIGNED-CANDIDATE-DO-NOT-FLASH.bin; signed SHA-256 3adc815e77a7c9b0e25f742601eb2dc94423aad540b26efa86423821a667abb1; signed size 5,899,090 bytes; flash partition 7,995,392 bytes; remaining 2,096,302 bytes.
- Cryptographic verification **PASS** against matching source trust anchor; extracted signed message equals unsigned source bytes; one-byte tamper and missing-trust-key controls both rejected.
- NAS offline evidence: /home/andre/projects/zbt-we2825-veci-openwrt/artifacts/veci-v2-f87e7ec-signed-offline-20261127/; **verify-only** ZIP at /home/andre/projects/zbt-we2825-veci-openwrt/artifacts/VeCI-v2-WE5927-2SIM-f87e7ec5-SIGNED-CANDIDATE-VERIFY-ONLY.zip, ZIP SHA256 375d2e56a7d09a308c4471c1e662133350e46924886323a7f802fa40a5125816; no private signing keys included.
- **Still BLOCKED:** installed key on owner's only router not inspected, sysupgrade -T on exact physical router not performed, OEM/VeCI frontend parity and connected-client MT76 UAT unproved, no rollback/recovery or 72-hour soak for this image. This signed result is **not** signed release approval. No production deployment, Wi-Fi reload, network reload or reboot was performed.
- Next action requires separate, explicit hardware-preflight consent and valid backups; production routing/Internet remain untouched.

## Owner physical VERIFY-ONLY result, 27 Nov 2026 10:40 WIB — exact signed candidate f87e7ec5

This section supersedes only the previous installed key and sysupgrade -T not verified
preflight statements. Owner pasted the actual PowerShell console output in ChatGPT;
the underlying full PowerShell session transcript was not uploaded independently.

- Exact signed firmware SHA256: 3adc815e77a7c9b0e25f742601eb2dc94423aad540b26efa86423821a667abb1. LOCAL_IMAGE_HASH=PASS; IMAGE_SIZE_BYTES=5899090.
- Physical router 192.168.1.1: INITIAL_HARDWARE_PREFLIGHT=PASS (board, wired LAN IP, 0x7a0000 firmware partition, tool and trust-anchor prerequisites).
- Router config backup generated and downloaded, local archive validation succeeded: LOCAL_CONFIG_BACKUP_VALIDATED, reported file size 7,452 bytes. It is **not a full MTD recovery backup**.
- Signed firmware temporarily transferred to router /tmp, sha256 checked UPLOADED_FILE_SHA256=PASS.
- On-router cryptographic verifier: SIGNATURE_VERIFIED_WITH_INSTALLED_TRUST=PASS after embedded ucert and installed public trust verification. BOARD_METADATA=PASS.
- On-router sysupgrade -T on the exact candidate: SYSUPGRADE_TEST=PASS.
- TEMP_PREFLIGHT_FILES=CLEARED was reported by script. No firmware write/reboot/network reload occurs in this verify-only script.
- Script printed READY_FOR_SEPARATE_USER_APPROVED_FLASH=YES: this is **preflight technical compatibility only**, not permission to flash.
- Recovery equivalence, original complete MTD backup, post-flash Wi-Fi/MT76 active-client, LTE+SIM, SMS, GUI, and 72h endurance remain **NOT_PROVEN**. Release gate remains **BLOCKED**, flash_authorized=false and release_permitted=false.
- This result attaches only to exact source f87e7ec5fec2c437d65fd95e7139bff90eb3019a and signed SHA256 above, NOT later commits or OEM Updated firmware. No user permission to flash was given.

## Exact rollback backup inventory and local-only Windows checker (27 Nov 2026)

- Previous owner-observed, read-only MTD backup from 23 Nov 2026 exists as source evidence in artifacts/run-45126249641-signed-uat/LIVE_OWNER_MTD_BACKUP_20261123.json. It records five partitions, 5/5 size-and-SHA matches at that time: mtd0 u-boot 196608 B, mtd1 u-boot-env 65536 B, mtd2 factory 65536 B, mtd3 firmware 7995392 B, mtd7 art 65536 B.
- Previously recorded Windows folder: C:/Users/2024NB/Documents/VeCI-WE5927-Recovery-20261123-171236. Another reported later folder: D:/Report_CCB/WE5927-Recovery-20261125_135411. Neither folder can be directly inspected from andre-nas.
- Added scripts/veci-we5927-mtd-recovery-audit-Windows-20261127.ps1: LOCAL FILES ONLY, verifies sizes and expected 23 Nov SHA fingerprints for each partition, separately inventories later backups with computed hashes but does not mislabel unmatched current-router evidence as verified.
- The audit does not contact any router or run SSH, SCP, sysupgrade, network changes, reboot, flash, MTD write or erase. It writes one local audit JSON under D:/Report_CCB with metadata only. Partition bytes remain private on Windows.
- The lightweight source safety contract passed on NAS (three tests); **actual Windows execution is pending owner output**.
- Existing U-Boot image contains web-failsafe and TFTP-related strings according to prior offline evidence, but firmware image format requirements, physical recovery entry, restore success and suitability as current OEM rollback are NOT live-verified. Do not claim FULL RECOVERY PASS from static strings or file hashes alone.
- Signed candidate f87e7ec5 has on-router verify-only preflight PASS, but firmware flash remains BLOCKED absent separate explicit permission and adequate physical recovery plan.

## Owner Windows historical MTD audit result, 27 Nov 2026 11:51 WIB

Owner ran the local-only SHA256-pinned PowerShell recovery-audit script and pasted its terminal results. This proves file availability and previous November backup integrity, not on-device rollback:

- 23 Nov backup, all five unique partitions mtd0/u-boot, mtd1/u-boot-env, mtd2/factory, mtd3/firmware and mtd7/art: HISTORICAL_SHA_PASS for each exact size and previously recorded SHA-256. Report: HISTORICAL_NOV23_FIVE_MTD_SHA256=PASS.
- 25 Nov backup, all five partitions: SIZE_PASS_HASH_RECORDED_NOT_ROUTER_MATCHED for each; all hash values computed locally and kept in user's Windows JSON, but not compared against today's router or the 23 Nov dataset.
- Reported local audit report: D:/Report_CCB/WE5927-RECOVERY-AUDIT-20261127_115107.json. No source backup bytes or current hashes were uploaded into this repo.
- Explicit negative assertions remain CURRENT_ROUTER_MTD_EQUALS_BACKUP=NOT_TESTED and LIVE_BOOTLOADER_RECOVERY=NOT_TESTED; owner did NOT flash or contact router.
- Previous source documentation that laptop backup existence is 'not inspected' is superseded by this user-executed offline audit. However, format/restore capability and present-day image identity are still not proven. Firmware release gate remains BLOCKED.
- Next safe step: compare NOV23 and NOV25 individual SHA-256 values using ONLY local JSON. The firmware mtd3 hash may legitimately differ; don't interpret a difference as a corrupted backup. Do not alter unique calibration partitions or attempt blind MTD restoration.

## Owner Nov23 vs Nov25 cross-backup hashes, 27 November 2026

- Owner executed local-only PowerShell JSON comparison of SHA256 values for five MTD partitions; terminal shows mtd0=IDENTICAL, mtd1=IDENTICAL, mtd2=IDENTICAL, mtd3=DIFFERENT, mtd7=IDENTICAL.
- This confirms four unchanged backup contents between dates; the firmware (mtd3) was different. An intervening firmware change is plausible but cannot be concluded from hash difference alone.
- No comparison against current live router was performed, no recovery boot mode was tested, no firmware/image was flashed, and no restore image format has been verified.
- current_router_mtd_equals_backup=NOT_TESTED; live_bootloader_recovery=NOT_TESTED; flash_authorized=false; release_permitted=false. Preserve both backup generations; do not write MTD0/1/2/7.

## Next operation: live-vs-backup MTD SHA comparison (source only, not executed)

- New Windows script scripts/veci-we5927-compare-live-mtd-hashes-20261127.ps1 accepts the existing local JSON backup inventory. It rejects nonunique, non-size-matching or incomplete Nov23/Nov25 reference hashes *before* any SSH.
- After separately authorized invocation, the script uses a pinned known-host SSH connection on owner Windows and read-only sha256sum of /dev/mtd0, mtd1, mtd2, mtd3, mtd7 after exact board and MTD partition-layout validation, then compares with both old backups, saving local-only JSON. No raw MTD image leaves the router; on-router reads may temporarily use I/O resources.
- This script has NOT been executed against the physical router. Any hash mismatch must be investigated without automatically rewriting flash; matching hashes do NOT prove bootloader recovery or firmware restore format.
- REL-003 registry wording now reflects owner-reported exact f87e7ec5 installed trust and sysupgrade -T **preflight** PASS while preserving candidate_hardware=not_tested. Release-permitted remains false until restored recovery and new firmware hardware acceptance are independently established.

## Owner current-router live MTD SHA checks, 27 November 2026, 12:08 WIB

- Owner executed approved read-only physical SHA comparison script from commit b8f111f; owner-pasted console reported MTD0_CURRENT_VS_BACKUPS=MATCH_BOTH, MTD1_CURRENT_VS_BACKUPS=MATCH_BOTH, MTD2_CURRENT_VS_BACKUPS=MATCH_BOTH, MTD3_CURRENT_VS_BACKUPS=MATCH_NEITHER, MTD7_CURRENT_VS_BACKUPS=MATCH_BOTH.
- The current u-boot, u-boot-env, factory and ART hashes match both November 23 and 25 owner backups. MTD3 differs from both, but the observed partition layout has rootfs_data at mtd6 inside firmware mtd3: writable overlay changes may alter aggregate mtd3 without changing base kernel/rootfs. Full firmware hash mismatch is **not** proof of corruption or firmware version change.
- User's local report is D:/Report_CCB/WE5927-LIVE-MTD-HASH-COMPARISON-20261127_120800.json; its raw hashes/JSON were not shared here. Do not invent hashes or silently claim the current base firmware equals any archived firmware image.
- Script reported LIVE_HASH_COMPARISON_COMPLETE=YES, ROUTER_NOT_MODIFIED=YES, FLASH_AUTHORIZED=NO. No bootloader recovery, restore, flash, reboot or network configuration change was performed.
- Recovery requires an exact current restore-safe image and demonstrated bootloader recovery procedure; signed candidate f87e7ec5 still release_permitted=false and flash_authorized=false, pending user's separate explicit approval and post-flash UAT.

## New operation: read-only base firmware versus rootfs_data triage (27 Nov 2026)

- Added Windows PowerShell 5.1 tool scripts/veci-we5927-readonly-rootfs-overlay-triage-20261127.ps1: before contacting router, it validates the owner Nov23 and Nov25 local MTD3 backup references, actual file sizes and their current SHA256 hashes; rejects changed/missing references.
- A single known-host SSH command reads only /proc/mtd and the board ID, computes /dev/mtd4 kernel hash, /dev/mtd6 rootfs_data hash, SHA256 of the initial parent MTD3 section before the expected rootfs_data tail, and a separate MTD3 tail hash. Dynamic kernel/rootfs sizes must sum exactly to firmware partition size, and the pre-overlay boundary must be 64 KiB aligned.
- Parent-tail and rootfs_data hashes must agree before comparisons are labeled MATCH or DIFFERENT. When the alias does not match, results are flagged NOT_VERIFIED_LAYOUT_ALIAS rather than claiming the base firmware changed or remains identical. Live partition reads are not atomic; overlay may change during observation.
- For each Nov23 and Nov25 backup, the tool computes local-only kernel and pre-overlay SHA256 on the corresponding original MTD3 image with streaming .NET hashing. It compares these independently with live hashes, emits only semantic MATCH/DIFFERENT and saves a local evidence JSON; it does not upload raw MTD bytes or any backup.
- Synthetic, executable BusyBox ash checks cover valid layout, exact prefix/overlay hashes, changed overlay hashes, malformed partition map and a safety contract. Five tests PASSED on development NAS. Windows PowerShell 5.1 syntax and pure local segment-hash correctness are now checked by a targeted offline GitHub Actions job; any CI result must be confirmed separately, not inferred from source tests.
- The tool has not yet accessed production hardware. No flash, bootloader recovery, backup restoration, power-cycle, network reload, or post-flash UAT was performed; signed candidate f87e7ec5 remains exactly unchanged and release_permitted=false.

### Offline PS5.1 CI evidence run 45944971177 — 27 Nov 2026

- GitHub Actions https://github.com/aicoach-alpha/zbt-we5927-openwrt/actions/runs/45944971177 at commit 5e921af41e2b5865a8c55b5b6cc8ea72d85b2d33: SUCCESS for both windows-ps51-stream-sha and real-busybox-mtd-layout.
- Windows PowerShell 5.1 parsing and real .NET SHA256 range hashing passed using local synthetic data only. BusyBox ash real command execution on generated fake MTD partitions passed, including malformed-layout and wrong-tail alias cases. Source test suite 5/5 PASS.
- Earlier duplicate run 45944736686 failed during apt-get update due to a third-party Microsoft source returning HTTP 403, NOT due to MTD logic. CI commit 5e921af restricts fallback apt update to official Ubuntu sources and suppresses duplicate push+PR runs; the corrected workflow was run to SUCCESS.
- No live physical MTD4/5/6 values have been collected by this operation. No firmware build or signed binary changed. Historical firmware candidate f87e7ec5 remains only device-preflight-verified, not release approved.

## Owner live MTD4 kernel and base-versus-overlay triage, 27 Nov 2026 12:21 WIB

- On-owner Windows script results: ROOTFS_DATA_IS_PARENT_TAIL=HASH_MATCH. For **both** NOV23 and NOV25: KERNEL_VS_CURRENT=DIFFERENT, PRE_OVERLAY_VS_CURRENT=DIFFERENT, OVERLAY_TAIL_VS_CURRENT=DIFFERENT. Receipt path D:/Report_CCB/WE5927-ROOTFS-OVERLAY-TRIAGE-20261127_122110.json (only owner-pasted console inspected, not raw report JSON).
- Parent mtd3 changed **outside** the rootfs_data overlay: different kernel and pre-overlay parent prefix. That is evidence of different base bytes, NOT proof of corruption, botched flash or network failure. It is not safe to assume either Nov23 or Nov25 image restores the currently operational system.
- New script scripts/veci-we5927-current-mtd3-stream-backup-20261127.ps1 (source-only until owner execution): binary-safe SSH stdout stream directly into a new local .partial file using .NET ProcessStartInfo.BaseStream.CopyTo, not PowerShell text redirection. No 8 MiB staging file on router or mtd writes. Checks board and exact critical partition sizes, checks router MTD3 SHA256 both before and after, validates exact 7,995,392 byte transfer and matching local hash before marking as valid.
- A raw MTD3 backup is NOT a verified sysupgrade or bootloader rescue image; no restore format or live recovery was tested. Running any live backup remains an explicit separate owner action. Firmware release stays BLOCKED.

### Windows raw MTD3 stream CI successful, run 45945649043 — 27 Nov 2026

- https://github.com/aicoach-alpha/zbt-we5927-openwrt/actions/runs/45945649043 at commit 8610d9febc4e03df8eaab7def00c19f2fad6fa23: windows-ps51-binary-stdout = SUCCESS. PowerShell 5.1 parser accepts source, extracted native .NET BaseStream copying function preserved all 256 possible byte values 0x00..0xFF byte for byte on a Windows 2022 runner; no SSH, router, or live firmware touched.
- Additional source tests 3/3 PASS confirm only read-only MTD3 DD-to-stdout and hash operations are performed remotely. SHA256 of the published script = 2605b07996a9da7241fd11f6a378df0bfdc7b71bd7f74a555a844af737bd983e.
- Owner physical invocation remains NOT_RUN; a script that PASSES synthetic binary tests is not evidence a current binary dump was taken, that overlay is quiescent, or that a raw MTD3 file can be loaded by U-Boot or sysupgrade. Keep existing 23/25 Nov backups and do not flash.

## Owner newly captured current firmware RAW MTD3 backup — 27 November 2026 12:27 WIB

- Owner executed the SHA256-pinned, CI-tested **read-only** Windows native binary-stream backup script. Physical router MTD3 streamed to D:/Report_CCB/WE5927-CURRENT-MTD3-RAW-NOT-FLASHABLE-20261127_122757.bin (7,995,392 bytes), with receipt in the corresponding .json.
- Exact owner console: CURRENT_MTD3_BACKUP_SHA256_BEFORE_AND_AFTER=PASS, CURRENT_MTD3_SIZE_BYTES=7995392, BACKUP_COMPLETE=YES, ROUTER_NOT_MODIFIED=YES, FLASH_AUTHORIZED=NO. The tool checked local SHA against live router SHA256 **before and after** transfer. Source report is owner-pasted console, not an independent inspection of the user's files.
- Compared with earlier Nov23/Nov25 backup, current MTD3 main kernel and pre-overlay content differ. This new snapshot preserves actual current firmware bytes while historical backups also remain intact. RAW MTD3 is **not** proven to be a valid U-Boot rescue or sysupgrade payload.
- **Next gates unresolved**: backup restore image format, demonstrated physical recovery capability, active-client Wi-Fi/MT76, LTE/SMS post-install UAT and 72h soak. Flash candidate f87e7ec5 remains release_permitted=false and flash_authorized=false, NO physical flash/reboot/network reload performed.
- Preserve raw MTD3 and accompanying JSON strictly on owner's Windows. MTD backup may include live network and access credentials; do not upload to public repository.

## Owner offline MTD3 legacy uImage initial header — 27 Nov 2026

- Owner Windows, from the exact current 7,995,392 byte RAW MTD3 image: HEADER_MAGIC=27051956, UIMAGE_PAYLOAD_BYTES=1959054, UIMAGE_HEADER_BOUNDS=PLAUSIBLE. This indicates a potential legacy U-Boot uImage header at the partition start but **does not** validate header or data CRC32, nor the U-Boot recovery loader's accepted firmware format.
- Source format is U-Boot legacy image.h: header is 64 bytes, CRC32 header at offset 4 (computed with its field zeroed), payload size at offset 12 and CRC32 payload at offset 24, encoded in network byte order. Reference: https://qemu.googlesource.com/u-boot/+/e9a1ff9724348408144c7f1c5b5cc26130ba46e5/include/image.h
- New offline Windows tool scripts/veci-we5927-uimage-offline-integrity-20261127.ps1 checks the matching current backup receipt and SHA256 before calculating both CRC32s with exact payload boundaries. It performs no router action or recovery; live user output is pending. CRC32 is integrity evidence, not authenticity, secure boot, hardware rescue compatibility, or flash authorization.
- Historical stable backup retention and signed f87e7ec5 candidate preflight PASS remain unchanged; release_permitted=false until recovery and post-flash physical UAT.

### Offline uImage CRC CI Windows PASS run 45947184115 — 27 November 2026

- Exact published offline legacy uImage script SHA-256: 9f75e9642f8d23019614a680252f3a3a3ab60feff7b9820a15a7a97ec4fc50e7. The script requires a matching backup receipt, size 7995392 bytes and SHA256 matching local MTD3 before parsing; no SSH or router calls.
- GitHub Actions https://github.com/aicoach-alpha/zbt-we5927-openwrt/actions/runs/45947184115, source commit e221aeef452392f25acbf2014d049a6405eb213e: SUCCESS for both synthetic-crc Ubuntu and windows-ps51 jobs.
- Windows real execution: valid 7,995,392-byte fixture produced header/payload CRC32 PASS. Tampered header, tampered payload and tampered uImage magic were each rejected with nonzero exits. Earlier 2 CI runs initially failed only due to harness handling of expected PowerShell native stderr and LASTEXITCODE; the corrected run passed both jobs.
- **Owner current backup CRCs have not been tested** by the new script yet, so do not label CRC32 PASS on that user's physical MTD3 backup. No bootloader restore capability was verified; flash authorization is still absent and release_permitted=false.

## Owner real MTD3 legacy uImage header and payload CRC32, 27 November 2026

- Owner ran SHA256-pinned local-only Windows verifier on D:/Report_CCB/WE5927-CURRENT-MTD3-RAW-NOT-FLASHABLE-20261127_122757.bin and matching .json receipt.
- Owner-pasted console: LOCAL_BACKUP_AND_RECEIPT_SHA256=PASS, UIMAGE_MAGIC=27051956, UIMAGE_PAYLOAD_BYTES=1959054, UIMAGE_TOTAL_BYTES=1959118.
- Header CRC32: expected=1bde8bfb, calculated=1bde8bfb, PASS. Payload CRC32: expected=f3c0fa95, calculated=f3c0fa95, PASS.
- UIMAGE_OS_CODE=5, UIMAGE_ARCH_CODE=5, UIMAGE_TYPE_CODE=2, UIMAGE_COMPRESSION_CODE=3; UIMAGE_METADATA=LINUX_MIPS_KERNEL; UIMAGE_LEGACY_CHECKSUMS=PASS.
- This authenticates neither file origin nor U-Boot recovery acceptance; CRCs apply only to the legacy uImage header and kernel payload, not the entire MTD3 rootfs/overlay. Earlier SHA256 check proves backup matches router at time of transfer, not bootloader restorability.
- Source evidence is pasted owner PowerShell console, not an independent import of the sensitive binary or JSON. RAW backup stays on owner laptop and is NOT a verified sysupgrade/bootloader rescue image. No router contact in this CRC test. flash_authorized=false, release_permitted=false.

## New operation: U-Boot local web-failsafe reconnaissance and image-format comparison, 27 Nov 2026

- Exact physical MTD0 bootloader backups are preserved on owner's Windows, November 23 and 25, both SHA256 b2acbf1e762e310d467cfcbae853257a9f63ce311511134bc9d0d5953f835330. Earlier owner read-only audit showed live MTD0 identical to both. The NAS does not contain the actual MTD0 bytes, so string markers previously reported by owner are **not** independently proven from the binary here.
- Historical owner string evidence reported web-failsafe menu, reset-trigger, HTTP firmware form, HTTP server and HTTP upload messages. Critically, 'HTTP upload is done! Upgrading...' suggests upload may initiate flashing, so **DO NOT** upload a test image merely to probe the recovery UI or assume a harmless validation step.
- A new pure-local Windows PS5.1 script scripts/veci-we5927-uboot-webfailsafe-offline-audit-20261127.ps1 checks the owner's already verified Nov23 and Nov25 MTD0 hashes against the exact known fingerprint and then scans only a small defined set of ASCII markers. It outputs marker presence/offsets as a local JSON receipt, not binary bytes, credentials, IPs or proprietary strings. NO router contact, no U-Boot recovery entry, no firmware upload.
- Independently on NAS, offline vendor research reference WE2825-2SIM 7,471,108 B, SHA256 80529b8e9c31d686eb7f63a1517d6dbcf781f26cb4aceb7b8b1ff27c2d51d1f9, and the exact VeCI signed f87e7ec5 5,899,090 B SHA256 3adc815e77a7c9b0e25f742601eb2dc94423aad540b26efa86423821a667abb1 have uImage Linux/MIPS/kernel compressed-header metadata and both header/data CRC32 PASS, with SquashFS markers present. Their kernel payload sizes differ (1,184,708 vs 1,959,204 bytes).
- These are *format observations*, **NOT** compatibility proof with an actual bootloader HTTP rescue endpoint or actual vendor UI, and not proof the WE2825 vendor reference can safely restore this WE5927. There is still no verified physical U-Boot recovery entry/upload procedure or accepted rescue-image format, even though device signed sysupgrade -T preflight passed.
- release_permitted=false, flash_authorized=false; existing signed firmware image is unchanged.

### U-Boot Windows offline scan CI, run 45948209204 — 27 Nov 2026

- CI https://github.com/aicoach-alpha/zbt-we5927-openwrt/actions/runs/45948209204 on commit b59ad5683525e43f9d00ee7a44f84d5ab4c69035: SUCCESS for Windows PowerShell 5.1 parsing, synthetic 196,608-byte U-Boot marker fixture with 9 different markers, mixed-case lookup and absent-string negative control.
- Exact source audit script SHA256 2f01ca583c90bdb932487002193522cc98bfd0c0b75b7f9affa6f9698d0448b3, with read-only local file hash verification for both owner Nov23 and Nov25 MTD0 backups, and no router command.
- **Owner's actual raw mtd0 marker scan remains NOT_RUN** for this new script. CI is not a physical recovery test and does not authorize HTTP firmware upload or flashing.

## Owner actual Nov23 and Nov25 U-Boot offline web-failsafe marker audit, 27 November 2026 13:00 WIB

- Owner executed the SHA256-pinned local-only Windows script. Output reported EXACT_MTD0_NOV23_AND_NOV25_SHA256=PASS. Each of the nine markers was FOUND in both backup copies: UBOOT_SIGNATURE, HTTP_SERVER_START, HTTP_SERVER_READY, WEB_FAILSAFE_MENU, RESET_UPDATE_MODE, HTTP_FIRMWARE_FORM, MT76X8_UPDATE_PAGE, UPLOAD_TRIGGERS_UPGRADE, TFTP_COMMAND.
- Aggregate owner console WEB_FAILSAFE_STATIC_MARKERS=9_OF_9_FOUND. Report stored only on Windows: D:/Report_CCB/WE5927-UBOOT-WEBFAILSAFE-OFFLINE-AUDIT-20261127_130023.json. Source is pasted owner console, NOT raw MTD0 or JSON evidence inspected remotely.
- Owner console explicitly warned DANGER=HTTP_FIRMWARE_UPLOAD_MAY_TRIGGER_IMMEDIATE_FLASH. No router contact, recovery UI entry, test upload, flash or reboot occurred. Source markers are code-string presence evidence and DO NOT prove U-Boot actually reaches web failsafe, validates image format, or can restore firmware.
- Preserve backup and avoid visiting Web Failsafe via reset until an owner-approved maintenance window and recovery plan. Uploading a 'test' firmware through HTTP form would be an unsafe flash experiment.
- CURRENT STATUS: bootloader marker static audit PASS; restoration acceptance NOT_VERIFIED; release_permitted=false; flash_authorized=false.

## Actual OEM-reference versus VeCI signed binary format gate, 27 Nov 2026

- Created scripts/ci/we5927_recovery_image_format_gate_20261127.py and JSON receipt docs/VECI-V2-WE5927-EXACT-IMAGE-RECOVERY-FORMAT-20261127.json. Unlike static string searches, this analyzer read BOTH real stored binary files on andre-nas, verified their exact expected SHA256, verified legacy uImage header and kernel-data CRC32, parsed SquashFS v4.0 superblock, and analyzed trailer markers, all OFFLINE. No bootloader or router I/O occurred.
- **WE2825-2SIM vendor reference** size 7,471,108 bytes; uImage payload 1,184,708, SquashFS starts 1,184,772, SquashFS bytes_used 6,263,516; trailing 22,820 bytes, OEM_STYLE_DEADC0DE_TERMINATOR with final marker deadc0de. Vendor WE2825 binary is a RESEARCH REFERENCE, **NOT proven to be the recovery image for this physical WE5927**.
- **VeCI signed sysupgrade f87e7ec5** size 5,899,090 bytes; uImage payload 1,959,204, SquashFS starts 1,959,268, SquashFS bytes_used 3,904,380; trailing 35,442 bytes, OPENWRT_METADATA_SIGNATURE_TRAILER with FWx0 and ucert markers, and not the vendor-style final deadc0de terminator. Presence of ucert markers here is structural evidence, NOT cryptographic signature verification; the candidate's installed trust and sysupgrade -T were independently owner-verified earlier.
- Format parity verdict: SAME uImage/SquashFS outer structure but DIFFERENT trailing packaging; **no evidence that U-Boot HTTP failsafe accepts signed sysupgrade format or vendor reference**. NO image conversion, footer stripping, re-signing, or flashing is authorized by this analysis.
- Three real parser regression tests PASS against synthetic OEM/OpenWrt fixture bytes and deliberate corruption of CRC, magic, SHA, SquashFS and partition length; targeted source-only GitHub CI added. Gate remains release_permitted=false, flash_authorized=false and physical recovery NOT_TESTED.

### Offline format parity GitHub CI PASS run 45949793732 (27 Nov 2026)

- https://github.com/aicoach-alpha/zbt-we5927-openwrt/actions/runs/45949793732 at commit 2f913cc55a32abbcf7d3a5457c6eb8e295c8d52a: the no-flash-format-gate job completed SUCCESS. The production parser was executed against synthetic OEM and signed-OpenWrt style footer fixtures and rejected deliberately corrupt CRC, magic, SHA, SquashFS size and partition length cases.
- Source artifact docs/VECI-V2-WE5927-EXACT-IMAGE-RECOVERY-FORMAT-20261127.json was produced on NAS from the genuine SHA256-pinned OEM research file and signed VeCI f87e7ec5 file. CI tests the code and receipt, not physical U-Boot acceptance.
- Neither image becomes a verified U-Boot Web Failsafe restore payload because of this CI pass. Do not remove FWx0/ucert metadata or forge vendor end-markers to fake a safe recovery image.

## Offline MIPS instruction-reference reconnaissance — 27 November 2026

- Previous format hardening commit 670f516 passed GitHub Actions run 45952389690 (no-flash-format-gate), plus 8/8 local unit tests.
- New scripts/ci/we5927_uboot_mips_xref_20261127.py scans only two distinct, exact-hash 196608-byte owner MTD0 copies. It enumerates adjacent MIPS little-endian LUI/ADDIU or LUI/ORI candidate references to known HTTP/TFTP strings, inferring page-aligned candidate virtual bases only when multiple instruction and string sites agree. It exports offsets and candidate base values, not binary content.
- Five unit tests passed on NAS using synthetic data, including signed ADDIU carry, ORI, missing code, register mismatch and exact backup hash rejection. Windows and Linux CI added; real owner MTD0 scan is NOT_RUN because the bytes remain exclusively on the office laptop.
- This is reconnaissance, not a disassembly of the actual handler. Adjacent instruction pairs can be data, relocated code and non-adjacent instructions can be missed; no xref is not proof of absence. No HTTP control flow, accepted image or recovery capability is certified. release_permitted=false; flash_authorized=false; no router access.

## Exact owner MTD0 centralized and offline mapping reconnaissance — 27 Nov 2026

- Both original 196608-byte owner snapshots independently hash-verified and byte-identical on restricted NAS storage. Encrypted private GitHub archive verified after decryption; no plaintext bootloader or key committed to public source.
- Actual adjacent MIPS XREF scan found all five selected markers but zero qualifying groups. This is not evidence of absent HTTP handler.
- New linked pointer-table analyzer found one consistent candidate address mapping on the actual owner MTD0, with 127 consecutive linked pointer pairs and one direct TFTP marker pointer; no direct HTTP marker pointer found. This is a mapping candidate, not proven control flow. Detailed offsets kept in restricted NAS report. Three synthetic tests pass.
- No physical router action; image acceptance and recovery remain unverified. Flash authorization remains false.

## Exact owner MTD0 PIC/GOT static references — 27 Nov 2026

- Previous commit 01de819: all seven executed workflows succeeded; two build workflows skipped. MTD0 hash reverified.
- New conservative PIC/GOT analyzer resolves a unique mapping candidate and 220 matching GP prologue patterns on the real MTD0. Two HTTP string argument-load patterns converge on the same indirect call site and callee candidate. Exact offsets retained only in the restricted NAS report. This does not establish what the callee does or which validation checks precede flash.
- Five synthetic tests passed, covering exact call pattern, wrong branch, wrong delay slot, GP disagreement and absent mapping. No physical router access, no image compatibility proof or flash approval.
