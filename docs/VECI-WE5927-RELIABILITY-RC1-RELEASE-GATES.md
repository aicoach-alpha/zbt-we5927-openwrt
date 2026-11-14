# VeCI Reliability RC1 — single image integration and release gates

Date: 2026-11-12. Board: tested **ZBT-WE5927 / WE2825-2SIM**, MT7628AN/mt7603, 8 MB NOR, 64 MB RAM, CX07E RNDIS modem (05c6:902e).

**Status: SOURCE CANDIDATE ONLY / DO NOT FLASH / DO NOT RESTART PRODUCTION.**

## Source of truth / staging
The reliability integration branch is based on draft PR #7, using the **exact pinned OpenWrt 25.12.5 commit** `f0a60eee2fe051741c643ea6118718aae1ef17fb` and mt76 `39c960c3ada558b4c2e7915772483d3731573d09`.
The same mt76 source pin was independently verified for upstream OpenWrt 25.12.6, but the **full image build is still on pinned 25.12.5**. No mixed kernel packages or driver binaries.

The integration branch includes:
- PR #7: MT7603 recovery-deadlock patch, beacon skb leak fix; these are **not proofs of beacon-hang repair**.
- PR #8: both production LTE manager source copies with no unnecessary DHCP release, conservative manual reconnect and CFUN guarded by radio attachment/link evidence. Preserve serial AT lock (SMS).
- PR #10: observe-only Wi-Fi Guardian; it **never issues `wifi up` or reloads a stuck radio** and stores only small tmpfs status.
- PR #9: guest provisioning non-disruptive source is staged for review, **not automatically installed** in the complete firmware until its native RPC package owner and SPA integration are known. Disabled guest remains the safe default.
- PR #11: wired external SSID UAT harness.
- PR #15: low-overhead 72-hour wired LTE/SSID monitor, with coverage measured against requested window.

`scripts/stage-veci-reliability-rc.sh` stages all built-in components **after applying the historical board patch**, explicitly overwriting only the older embedded LTE script after confirming current source mirrors match. It blocks wrong OpenWrt/mt76 pins and verifies Guardian does not call Wi-Fi reload. Run it only on an isolated OpenWrt source checkout.

## Build gates (automated)
- PR validation: source syntax, all offline modem/guardian/guest/monitor regression suites, source mirror parity, exact pinned driver patch staging, rerun idempotence and wrong revision rejection.
- Full-image CI: full OpenWrt build, **not just `mt7603e.ko`**; exact-board target and SquashFS; Guardian selected in `.config`; installed source matches latest LTE code. Verify actual sysupgrade file exists, `fwtool` supported-device metadata, and **image size <= 0x7a0000 bytes (7,995,392)**. Run with contained GitHub runner only; do not export a flashable artifact.
- Build success is not sufficient for signing. Signed package feeds (`CONFIG_SIGNED_PACKAGES`) do not imply signed OTA image. Trust anchor and image signature are separate mandatory release gates.
- **LuCI intentionally remains** in this integration branch. VeCI standalone parity, auth, backup, OTA and live HTML controllers still need physical verification before removing LuCI; see draft #13/#14.

## Hard no-go gates before production
1. Build entire release image from an exact source pin with no package or kernel ABI drift. Confirm image SHA/board metadata and MTD partition fit.
2. Confirm production source of complete VeCI SPA/guest RPC (repo currently only has UI fragments). No source package may overwrite newer working VeCI or guest logic.
3. Preserve ART/calibration, factory partitions, bootloader and existing config. Verify backups, known-good *signed* rollback image and UART/U-Boot recovery path. Do not force sysupgrade.
4. From **wired Ethernet**, run `sysupgrade -T` on the candidate only when image is signed/authorized and compatible; never flash on a failing test. Confirm login/SSH connectivity even with Wi-Fi down.
5. Test Wi-Fi externally (independent Windows scans plus two clients) under idle/load/reassociation. Neither radio0 up nor hostapd ENABLED proves beacon visible. Watch mt76 RX PSE resets and MCU timeouts.
6. Test LTE across >=3 of the former ~122-minute periods and continue a continuous >=72-hour observation window with >=99% collection coverage; classify local gateway, USB carrier, DHCP and HTTPS separately. Zero self-induced `ifdown` when gateway healthy.
7. Record speed from a wired client and Wi-Fi clients with relevant CPU/RAM/USB/LTE radio stats. Do not turn on HT40, SQM or flow offloading until safe A/B validation; no unsupported promise of full LTE speed or zero carrier outage.
8. SMS receive/send and AT lock must remain operational; guest disabled boot must not reload radio; VPN/addon installs limited by flash headroom.
9. Explicitly approve maintenance window and recovery before any production update; until then **keep original firmware live and leave router untouched**.

## Verified CI status (2026-11-12)

Exact PR #16 source at commit `beb31b2c66521459895490b7477f5501c7c0c09b` passed:
- Complete OpenWrt source and image build: [run 43169286587](https://github.com/aicoach-alpha/zbt-we5927-openwrt/actions/runs/43169286587), PASS.
- Exact-source MT7603 kernel build: [run 43169286564](https://github.com/aicoach-alpha/zbt-we5927-openwrt/actions/runs/43169286564), PASS.
- Image size: **5,767,458 bytes**, under the tested firmware MTD limit of **7,995,392 bytes**, with **2,227,934 bytes** remaining.
- Image SHA-256: `3d3f0d3488d08e5b9558b330d876eff7dd493e3d9cf62a9bfd3d6fa83d7db57f`.
- Board metadata `zbtlink,zbt-we5927`, staged LTE code, and observe-only Guardian integration: CI PASS.
- **FLASH_PERMISSION=NO**. The original workflow intentionally did **not** export firmware binary artifacts. No physical router acceptance or trustworthy final signing is implied.

The follow-up workflow changes add an artifact containing **JSON build evidence only**, not a flashable image. This new artifact must be verified in its own GitHub Actions run before calling that improvement PASS.

## Work remaining

1. **Signing/authorization**: verify the final release signature against the router's trusted image key, independently of signed package feeds. Never treat a transient runner build key as the production trust anchor.
2. **VeCI image parity**: establish and stage the currently working full VeCI SPA, RPCs, guest owner, access control, and backup/OTA behavior; the current source-only candidate does not prove parity.
3. **Recovery**: independently verify config/firmware backups, wired access and the UART/U-Boot recovery method.
4. **External SSID and LTE UAT**: capture hostapd and independent client observations plus MT7603 counters, multiple ~122-minute windows, 72-hour monitor >=99% coverage, and SMS/AT lock.
5. **On-router read-only preflight**: SSH reachability does not establish authenticated login. Never auto-accept a new SSH host key or bypass pinned known_hosts. Perform `sysupgrade -T` only after a signed, authorized image exists and is made available over an approved wired maintenance path.

**Current gate: NO-GO FOR FLASH**. Keep the existing signed working production firmware and LuCI/VeCI access intact.

## 2026-11-13 release-candidate preparation (NOT flash approval)

The follow-up source update vendors the public aicoach-alpha/veci Core at exact
commit bdf7bcf332c23b625e92fb1e00d1fb30edea88b6, together with the
reviewed veci-default-ui package, and requires their SPA, authenticated rpcd
helper and ACL, HTTPS default settings, and LuCI fallback to be present inside
the built firmware rootfs. This closes a source packaging gap only; the
running production router has not been shown to contain identical frontend
and RPC versions. Additional live-only VeCI SMS/guest/OTA functionality remains
unverified and must not be assumed safe to replace.

The complete-image CI remains evidence-only on normal pushes and PRs. An
explicit, manually dispatched build with export_unsigned_candidate=true
may export an UNSIGNED_DO_NOT_FLASH image for offline inspection. The
artifact is tied to the exact source commit, checked against its evidence
SHA/size, and must never be treated as a signed production release.

Before flash approval require final image SHA, real image ucert signature
against the production router's existing trust anchor (not just APK feed signing),
full live VeCI/RPC parity, pinned SSH login, validated backups/rollback, native
sysupgrade -T, and board/LTE/Wi-Fi/SMS hardware acceptance. GitHub repo
currently has no signing secrets configured; existing production signing key
must be supplied only through an approved secure deployment channel, never
placed in repository source, CI logs or chat.

## 2026-11-13 Live VeCI parity and user-defined optional apps

Inspection of the authenticated physical router over pinned-key SSH found 24
production VeCI UI assets. All 24 asset hashes, the core rpcd service,
ACL, cellular provider, SMS RPC, Apps catalog RPC, and OTA checker source
match audited local worktrees:
- VeCI Core worktree a1504e607d4b7b32ce9f6a6858cdf59dd777acfb
- WE5927 package source worktree c62b85cbbb369ed79b69891a05006179b79874d3

The newer candidate must include VeCI Core, cellular/SMS provider, Apps
catalog, firmware update agent, default UI, LTE recovery, safe Guardian
and LuCI Expert. The SMS helper veci-sms-cmgs must be compiled for the
same MIPS ABI or the current SMS send-one service cannot operate.

Guest and Voucher are optional online-installable apps, NOT factory
firmware dependencies. The base image includes catalog descriptions for
them but must NOT bundle either veci.app.guest or veci.app.voucher RPC.
Existing deployments that have these optional apps installed require
a backup of their configuration, an installed-package inventory, signed
package feed verification, and a restore/reinstall plan across sysupgrade.
Do not auto-install optional apps on a clean router.

Production signature, sysupgrade -T, currently installed custom service
overlays, rollback, and hardware UAT remain independent gates. Only the
full signed image after real checks may be described as flash-ready.


## 2026-11-13 13:28+07 — successful latest-head build and provenance correction

GitHub Actions run 43367049750 **PASS** (PR #16 head
`3dd5a2b032300a4fd098c7839103757a66022cd2`), artifact
`veci-we5927-rc1-build-evidence` records a 5,898,530-byte unsigned
CI image, SHA-256
`ed588e931540ac61ce2f317791318b3cd7be0f1111cc06979058ef02031f1a87`.
Firmware partition limit 7,995,392 bytes; headroom 2,096,862 bytes.
MT7603 exact-source cross-build run 43367049486 **PASS**. The build
published JSON evidence only; there is no usable signed production image.

**Important:** pull-request builds use GitHub's synthetic merge checkout
(`GITHUB_SHA`), which can differ from the reviewed PR head commit.
Historical v1 evidence has `github_build_sha=d38bf6470d5994ad8fda95dc2eb1d42acf25808d`,
not the actual source-branch head `3dd5a2b...`. It is not evidence
of source mismatch by itself. The v2 generator now records both SHAs
and verifies the synthetic merge commit has exactly the reviewed base
and head as parents. For workflow_dispatch it requires the checked-out
SHA to equal the reviewed source, and only the RC branch may request
unsigned export. This is a **CI provenance improvement**, not signing,
device testing, or authorization to flash. Keep NO-GO until all hard
release gates are independently satisfied.


## 2026-11-14 — Feature-completeness integration (development only)

The 2026-11-13 image (source 4fa427d) is **not** the all-features image.
Verified by unsquashing its actual 5,898,530-byte firmware: native VeCI Core,
LTE/SMS, cellular RPC, apps catalog, update agent and LuCI fallback exist.
The full Guest/Voucher/SQM/DDNS/WireGuard implementations were not bundled.
The native VeCI screen intentionally uses a horizontal top navigation
(CSS override), so the menu position is not proof of hardware upgrade.
The operator quota registry is a read-only prototype with no authenticated
live carrier client. Do not report it as live quota retrieval.

The feature integration branch now includes the existing source and offline
tests for six independently developed optional application packages: Guest
Portal, Voucher, SQM, DDNS, WireGuard and Indonesia quota registry. Source
staging in the exact OpenWrt package ABI **does not** install those apps:
firmware only becomes app-ready when a real, signed, matching-build APK feed,
sufficient overlay/storage and successful on-router validation are proven.
Guest and voucher must never be automatically enabled on startup or migrate
Wi-Fi/bridge/firewall settings without safe service/recovery checks.

**Outstanding before claiming full feature completion:**
- Working authenticated operator quota retrieval (not placeholder registry).
- A tested matching-release signed APK feed and online app installation with
  dependencies, rollback and flash/overlay headroom checks.
- Guest/voucher physical isolation and captive-portal acceptance, including
  the no-guest normal-boot path.
- LAN/Wi-Fi/LTE/SMS/USSD end-to-end verification on a pinned router connection;
  72-hour stability evidence is missing.
- Full native VeCI parity with backup/restore and safe OTA. LuCI remains only
  an Expert/failsafe fallback until the native replacement is validated.
- Verify checksum and sysupgrade -T on target before any single final
  release/deployment. No auto-flash, no --force, no unreviewed build.


## 2026-11-14 — Native landing + exact release identity + real LTE meter

Found in actual 4fa427d SquashFS: /www/index.html still pointed
to LuCI and /etc/veci-release.json did not exist, so the root UI could
look unchanged and the signed APK feed could not map an installed build.
The feature integration branch corrects these source issues by staging a
root /veci/ landing, a SHA-derived /etc/veci-release.json, matching
/www/veci/build.json, and a visible VeCI build marker with cache-busted
client assets. The generator never claims the image is signed.

The native LTE Data Meter is now bundled as a base package from pinned
source. Its read-only interface counters and manual quota baseline are
NOT an authenticated carrier quota; it expires estimates on boot or
counter resets. The offline package tests are separate from physical UAT.

True optional app packages Guest, Voucher, SQM, DDNS, WireGuard and
Indonesia quota registry are staged as source for exact-ABI builds, not
installed automatically. There are currently no GitHub Actions signing
secrets configured for an APK feed; app installation cannot be declared
working until a matching signed release feed exists and is hardware-tested.

The old 4fa427d firmware is definitively not all-features-complete:
the actual-rootfs inventory fails Guest, Voucher, Data Meter,
operator quota, release ID and native root landing. Do not re-label
that image as the final release or claim a green build is enough.

No physical router changed by this source integration. Follow the
full-native parity checklist in docs/VECI-FULL-NATIVE-PARITY-RELEASE.md.
