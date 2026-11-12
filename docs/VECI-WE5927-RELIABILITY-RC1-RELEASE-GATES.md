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

## Work remaining
No live 72h/SSID hardware evidence; no verified final signing; current VeCI SPA and guest package ownership unresolved; no full firmware build result until CI completes. The release candidate is a **build candidate**, not a firmware release.
