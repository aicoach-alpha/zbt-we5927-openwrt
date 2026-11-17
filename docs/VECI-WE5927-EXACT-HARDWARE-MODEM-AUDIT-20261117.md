# WE5927 / WE2825-2SIM: hardware, LTE and firmware audit

Audit date: 2026-11-17.
Scope: physical-router SSH logs supplied by the user, older live MTD inventory,
extracted installed image, exact custom DTS/board patch, pinned OpenWrt sources.
State: source audit done; physical/electrical recheck still incomplete. DO NOT FLASH.

## Evidence classes
- FIELD: user-supplied router commands and earlier actual /proc/mtd inventory
- IMAGE: extracted 25.12.5 firmware rootfs
- SOURCE: current source tree and custom DTS; not direct electrical measurements
- OEM: reference material for OTHER WE5927-A/B variants, never proof of PCB match
- UNKNOWN: not inspected, not inferred

## Board, storage, silicon
- Historical unit identifier: ZBT-WE5927 / WE2825-2SIM. Actual PCB revision
  silkscreen and chip-top markings UNKNOWN.
- Source DTS compatible: zbtlink,zbt-we5927, mediatek,mt7628an-soc.
- MT7628AN-class MIPS24KEc, 64 MiB RAM class (~58.6 MiB usable historically).
  Physical RAM IC and true current available memory UNKNOWN.
- 8 MiB SPI NOR (based on historical /proc/mtd and exact custom DTS).
- Layout: u-boot 0x00000+0x30000, u-boot-env 0x30000+0x10000,
  factory 0x40000+0x10000, firmware 0x50000+0x7a0000,
  ART 0x7f0000+0x10000. No NAND nor A/B firmware slots.
- Firmware hard limit 7,995,392 bytes, 64 KiB flash erase blocks.
- Wi-Fi: only integrated 2.4 GHz radio. MT7603/mt76 driver in source.
- Ports: OEM WE5927 class 1 x 10/100 WAN, 3 x 10/100 LAN; only one
  physical link observed in field UAT, NOT individual cable qualification.
- OEM model WE5927-A differs in SIM/PCB assembly from the historical
  WE2825-2SIM unit. Do not substitute firmware purely on model-name similarity.

## Exact custom-DTS mapping (SOURCE, not bench electrical verification)
- EEPROM factory offset 0x0 / length 0x400.
- Ethernet MAC NVMEM factory offset 0x28 / 6 bytes.
- Modem power GPIO1; dual-SIM switch GPIO46.
- Hardware watchdog GPIO37 active-high toggle; 2-second hardware margin.
  Do not change polarity or margin based on a different WE5927 variant.
- Reset GPIO38 active-low; WLAN LED GPIO44; LAN LEDs 43,42,41;
  WAN LED GPIO39.
- NEVER write raw factory/ART partition; these hold calibration data.

## LTE module and RNDIS
- Modem identified in prior work as CX07E, USB VID:PID 05c6:902e.
  VID:PID alone does not identify the physical LTE IC or PCB revision.
- Data: USB RNDIS on usb0, DHCP from gateway 192.168.7.1.
  Do not silently switch to QMI/MBIM or direct-PDP-IP assumptions.
- Safe AT: sysfs USB interface 1.4, normally ttyUSB2, protected by a
  serialized AT lock. Function 1.5 (historically ttyUSB3) is excluded from
  automatic probing due to a prior uninterruptible-I/O incident.
- PCB LTE chips, bands and baseband firmware version UNKNOWN.
- Physical SIM sockets, power supply voltage under load, modem antenna
  matching and temperature remain UNKNOWN.

## Runtime network and Wi-Fi fault
- On 2026-11-16 an erroneous diagnostic shell pipeline accidentally launched
  a second netifd; PID parent proved it was not the procd-owned instance.
  Stopping only that orphan restored a single netifd. Do not blame a
  permanent netifd startup bug without independent evidence.
- Subsequently LTE lease 192.168.7.179/24 via 192.168.7.1 on usb0 persisted.
  Router-originated public ping 30/30 PASS across 15 minute-samples,
  gateway ping PASS, DNS PASS; later wired office UAT router-LTE 3/3 PASS.
  Router-originated ICMP is NOT evidence of client-side NAT/DNS reliability.
- Historical DHCP flap messages from 2026-11-16 17:08 precede corrective
  action. Subsequent successful renews at 23:08 and 05:08 contradict a claim
  of continuous DHCP flapping afterward.
- On 2026-11-17 radio0 up=true, hostapd global process and ubus hostapd
  object present, but NO hostapd.phy0-ap0 object, NO phy0-ap0 netdev,
  and only global hostapd socket. AP IS NOT OPERATIONAL.
- All seven exposed MT76 reset/error counters were zero.
  Do not infer chip failure or MCU hang.
- Dmesg contains repeated attach/detach of phy0-ap0 with final unregister
  around 1139 seconds uptime; initial trigger has rolled out of syslog.
- Main Wi-Fi configuration last showed 2.4GHz HT20, channel 6, country ID,
  SAE mixed security and isolate true. Configured radio != emitting beacon.
  Client isolation may affect peer-to-peer LAN but does not prove AP cause.

## Native firmware and services (extracted 25.12.5)
- Installed init sequence includes wpad, network, dnsmasq, firewall,
  rpcd, uhttpd, dropbear, LTE manager, Wi-Fi Guardian, and update-agent.
- Built-in wpad binary and hostapd symlink present; processes run.
  Missing BSS is a lifecycle problem, not a proven missing package.
- Old installed image contains veci.meter despite source retirement.
  New source removes Data Meter and duplicate firmware updater.
- No installed LuCI runtime directories in inspected image.
  Guest/voucher backends absent by default.
- Automatic OTA check/download/install defaults OFF in latest source;
  live UCI configuration not yet read. Never assume absence of auto-install
  solely from the existence of S95 init symlink.
- Wi-Fi Guardian is observe-only. Updated source logs one alert per outage,
  retains fault state, and never auto-reloads a potentially deadlocked radio.
- LTE manager must preserve a working USB DHCP interface; no reset based
  only on public ICMP failure when modem gateway still works.
- Source Cellular UI now distinguishes live data_link_up from stale
  internet_verified; that source is not yet installed in the user's router.

## Candidate 25.12.6 validation and release policy
- Official upstream OpenWrt 25.12.6 commit:
  64900e756efa667774214f9c6b17c113222e01f7.
- Exact target kernel 6.12.112 and mt76 source
  39c960c3ada558b4c2e7915772483d3731573d09.
- WE5927 is added by THIS PROJECT'S board patch, not an assumed upstream
  built-in device profile. Patch verified against exact source checkout.
- Both MT7603 source patches stage against the pinned mt76 revision.
  SOURCE COMPATIBILITY IS NOT A WI-FI RUNTIME PASS.
- Complete-image CI must check metadata and exact board target, full wpad
  + mt7603 package presence, no LuCI, no optional heavy apps, no Data Meter,
  all LTE/SMS/OTA core functions, image <= firmware partition, plus at
  least 1 MiB RAW image headroom. Raw headroom is not an overlay measurement.
- Firmware finalization now refuses images without authentic board/release
  metadata. No guessed 25.12.5 or 25.12.6 revision trailer.
- Release must be cryptographically signed with the already trusted key,
  SHA256 verified, pass sysupgrade -T, have a tested backup/rollback.
  A successful CI build is NOT production flash authorization.
- Physical acceptance after controlled install: LAN all external ports,
  Ethernet client NAT/DNS, Wi-Fi BSSID/beacon and association, LTE DHCP
  lease renewal, modem/SMS, no self-induced restarts, stability >=72h.
- Firmware update requires a planned reboot on this single-slot NOR
  device. Literal zero-downtime upgrade is physically impossible.

## Explicit unknowns
Physical PCB revision, exact modem IC and baseband firmware, RAM/flash
manufacturer and speed, actual power brick voltage/current under load,
temperature and thermal throttling, antenna/coax condition, all screw sizes,
connector corrosion, reset-button mechanics, chip RF calibration validity,
bootloader serial pinout, flash wear, actual wired/Wi-Fi client throughput,
all-port link reliability, and original phy0-ap0 teardown cause.
Do not invent these values; obtain trusted real hardware measurements.

## Primary reference websites (different variants are not proof)
- ZBT WE5927-A: https://www.zbt-china.com/productinfo/1463370.html
- ZBT alternate WE5927-A: https://www.zbtwifi.com/collections/4g-lte-wifi-router/products/we5927-a
- OpenWrt 25.12.6: https://lists.openwrt.org/pipermail/openwrt-announce/2026-October/000090.html
- OpenWrt support limitations: https://openwrt.org/supported_devices
