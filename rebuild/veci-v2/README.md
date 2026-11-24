# VeCI v2 — rebuild for ZBT-WE5927-DSIM (WE2825-2SIM)

**SOURCE DEVELOPMENT ONLY — NOT FLASHABLE.** New independent native VeCI
architecture. The verified MT7628AN / dual-SIM / RNDIS hardware adapter is
reused as a proven low-level interface. Vendor LEDE binaries are NOT reused.

## Verified baselines

- Board: user's historical physical WE2825-2SIM. Original vendor image
  identifies ZBT-WE5927-DSIM, WE2825-2SIM, firmware vendor 26.08.09 and
  hardware watchdog GPIO37.
- Exact vendor image: 7,471,108 bytes, SHA256
  80529b8e9c31d686eb7f63a1517d6dbcf781f26cb4aceb7b8b1ff27c2d51d1f9.
  It is LEDE Linux 4.4.61 and was extracted for a feature inventory ONLY.
  No OEM binaries, vendor code, passwords, or private SIM data are in Git.
- OpenWrt 25.12.6 stable, commit
  64900e756efa667774214f9c6b17c113222e01f7.
- Stable kernel 6.12.112; mt76 revision
  39c960c3ada558b4c2e7915772483d3731573d09 with two source-reviewed
  MT7603 reliability patches. Driver compatibility != hardware UAT.
- LuCI openwrt-25.12 commit 53312862521a4b02d7e45ae483537132dbcf63ad.
  11 core modules and 107 optional luci-app packages inventoried. This does
  NOT mean all 107 apps run on this 8MB router.
- Hardware: 8 MiB NOR, 64 MiB RAM, single 0x7a0000 (7,995,392 B)
  firmware partition. This custom board needs matching EEPROM and GPIO map.

## One source of truth

- contracts/oem-we5927-2sim.json: 20 OEM enabled and 13 disabled features.
- contracts/luci-25.12-feature-index.json: every one of 107 upstream
  luci-app directories, explicitly not yet migrated.
- contracts/veci-v2-rebuild-contract.json: 37 mandatory modules with source
  and physical-UAT statuses. Required gates refuse release when incomplete.
- packages/veci-v2-runtime: live read-only health; no false LTE internet
  assumption and no false Wi-Fi radio-up equals AP-ready assumption.
- packages/veci-v2-sms: full SMS transport from the previously tested
  canonical AT/PDU code, with ONE serial lock and no duplicate modem daemon.
  Native v2 SMS UI now includes inbox/on-demand read, send with
  explicit confirmation, sent history, draft management, PDU decoding and
  deletion. These are source-tested, NOT modem-verified on hardware.
- packages/veci-v2-package-manager: signed APK feed only, exact board/release,
  hardware-critical package blacklist, space/RAM check and explicit manual
  confirmation. No arbitrary URLs or unsigned installs.
- packages/veci-v2-ui: compact JS-free-dependency development preview.
- ci/stage-v2-source.sh: stages only exact-match package source in isolated
  OpenWrt checkout and references one SMS transport source owner.
- ci/release-gate.py: fail-closed flash permission verification.

## Requirements vs current implementation

| Requested | V2 plan | Current result |
|---|---|---|
| Entire current LuCI | Native core + optional modules, source-verified parity | 11+107 inventory; NOT migrated |
| Entire stock ZBT features | Exact OEM feature mapping, modern dual-SIM and watchdog | OEM inventory complete; migration pending |
| SMS Center | Dedicated AT/PDU provider, send/receive/drafts/history/encoding, native UI | Source-tested SMS UI, hardware UAT pending |
| Live addons from OpenWrt/GitHub | APK 3 signed repository + exact-build packages, extroot if needed | Protected package API implemented; hardware pending |
| Manual and GitHub OTA | Signed manifest, SHA256, board lock, sysupgrade -T, explicit install, rollback | Previous VeCI reference exists; v2 pending |
| Tiny core firmware | Optional heavyweight services removed from ROM | Not built in full image yet |
| Stable newest kernel/OpenWrt | 25.12.6 stable, kernel 6.12.112 | Source pinned; physical pending |
| New drivers | Only exact stable mt76, USB RNDIS, Ethernet/GPIO compatible revisions | Source patches staged; physical pending |
| 24/7 readiness | No automatic network flapping, observability, watchdog limits | 72h test pending |

## Physical constraints

Single-slot 8 MiB NOR **requires reboot during firmware upgrade**, so
literal zero-downtime firmware replacement is not possible. All 107 LuCI
apps cannot reside in ROM. Addons must fit verified flash/RAM, or install
only with a reliable tested extroot. A kernel-dependent addon must match
exact kernel ABI or be included in a rebuilt firmware image.

## Production release gates

Source regressions -> APK crosscompile -> whole clean image -> hard image
size and headroom -> metadata board/version match -> trusted-image signing
-> offline verification -> config backup/rollback -> sysupgrade -T ->
physical Wi-Fi BSSID/beacon/join -> physical LAN ports/NAT/DNS -> LTE
dual-SIM/SMS (USSD permanently retired) -> 72-hour wired/Wi-Fi/cellular soak.

No signed artifact or physical UAT evidence means NO FLASH PERMISSION.

References:
- https://downloads.openwrt.org/releases/25.12.6/
- https://github.com/openwrt/luci/tree/openwrt-25.12
- https://www.zbtlink.com/pages/download-list-starts-with-we
- https://openwrt.org/docs/guide-user/additional-software/apk
