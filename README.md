# ZBT WE5927 / WE2825-2SIM OpenWrt

Community firmware overlay and LTE/Dual-SIM management stack for the **ZBT WE5927 / WE2825-2SIM** MT7628 family.

> **Status:** tested on one WE5927/WE2825-2SIM unit with a CX07E LTE modem in RNDIS mode. This repository is currently a **source/overlay release**, not a universal flash image. Do not flash images from this project onto a different WE5927 hardware variant without verifying the board, flash layout, GPIOs and modem first.

## Tested hardware

- SoC: MediaTek MT7628
- Architecture: mipsel_24kc
- RAM: 64 MB class (58.6 MiB usable on the tested unit)
- NOR flash: 8 MB class
- LTE data: RNDIS on `usb0`
- AT port: `/dev/ttyUSB2`
- Dual-SIM selector: GPIO 46
- Modem power: GPIO 1
- Tested modem USB ID: `05c6:902e`

The live router identifies itself as:

```
OpenWrt 25.12.5 r33051-f5dae5ece4
Linux 6.12.94
Target: ramips/mt76x8
Arch: mipsel_24kc
```

## What this project changes

The focus is not adding lots of packages to an 8 MB flash router. The focus is **reliable LTE recovery, a responsive LuCI status page, low resource usage, safer Wi-Fi defaults, and low-overhead DNS filtering**.

Key features:

- CX07E-aware LTE manager for `usb0`/RNDIS.
- Safe AT-port selection; avoids automatically probing the unsafe secondary serial function.
- Serialized AT access with a lock to prevent concurrent modem queries.
- Fast LuCI status path backed by a cached full-status refresh.
- Cached modem details remain visible if the AT port is temporarily busy.
- Interface-first recovery: restart only the LTE logical interface before escalating to modem CFUN or a hard modem power-cycle.
- 30-second health checks with 6 consecutive failures before recovery (~3 minutes).
- Optional dual-SIM failover, disabled by default.
- External filtered DNS can be used instead of a large on-router blocklist.
- No OpenClash, Pi-hole, AdGuard Home daemon, Squid, or other heavy services.

## Recovery ladder

```text
Internet OK
   |
   +--> keep connection untouched

Internet fails continuously for ~3 minutes
   |
   v
ifdown lte -> ifup lte
   |
   +--> recovered: stop here
   |
   v
soft modem reconnect (CFUN)
   |
   +--> recovered: stop here
   |
   v
hard modem power-cycle (after repeated recovery cycles)
   |
   v
optional SIM failover (only when explicitly enabled)
```

The goal is to avoid unnecessary full router reboots and avoid power-cycling the modem for a single transient packet loss event.

## LuCI LTE page

The custom LuCI page exposes:

- connection state
- active SIM
- IPv4 and gateway
- signal percentage and dBm
- SIM status
- operator
- access technology
- registration status
- packet attach
- registration denial
- extended network error
- ICCID
- modem manufacturer/model/revision
- IMEI
- data interface
- AT port
- data mode

Full AT data is refreshed in the background and cached. The page itself uses the fast status path so a slow modem query does not block LuCI until the browser reports an XHR timeout.

## Current package philosophy

This hardware has very little flash and RAM. On the tested unit the overlay is only about 2.1 MiB total, so the project deliberately stays small.

- **Watchcat:** not installed. The custom LTE daemon already performs modem-aware health checks and recovery.
- **SQM:** not installed. On the tested OpenWrt 25.12.5 feed, required kernel packages such as `kmod-sched-core`, `kmod-ifb` and `kmod-sched-cake` were not available for the running kernel ABI.
- **nlbwmon:** not installed by default.
- **zram:** not installed by default.
- **Local ad-block daemon:** not used.
- **DNS filtering:** recommended through an external resolver.

The tested unit already has `fq_codel` as the qdisc on `usb0` and `eth0`, but that is **not the same as full SQM bandwidth shaping**.

## External DNS filtering

For low-overhead ad/tracker filtering, use an external filtered resolver rather than storing large lists on the router.

The tested configuration uses AdGuard Public DNS:

```
94.140.14.14
94.140.15.15
```

This can reduce some advertising, tracking and telemetry traffic. It will not materially reduce quota consumed by video streaming, large downloads, cloud sync or OS updates.

## Wi-Fi

The tested hardware is 2.4 GHz 802.11n. Stable baseline settings are:

- country code appropriate to your location
- HT20 for congested 2.4 GHz environments
- WPA2/WPA3 mixed mode (SAE + CCMP) when client compatibility allows
- visible SSID is generally preferred; hiding an SSID is not a security feature
- choose channel 1, 6 or 11 based on local interference

Do **not** copy the example SSID/password from somebody else's router. This repository intentionally does not contain the tested unit's Wi-Fi credentials.

## Official ZBT firmware vs this build

See [docs/STOCK-VS-CUSTOM.md](docs/STOCK-VS-CUSTOM.md).

In short:

- choose **official ZBT firmware** when vendor support, broad modem compatibility and the factory software stack matter most;
- choose this **community OpenWrt build/overlay** when you want a current OpenWrt/kernel base, a leaner system, and a modem manager tuned specifically for this hardware/modem combination.

## Repository layout

```
files/
  etc/
    config/we5927_lte
    init.d/we5927-lte
  usr/
    sbin/we5927-lte
    share/luci/menu.d/luci-app-we5927-lte.json
    share/rpcd/acl.d/luci-app-we5927-lte.json
  www/luci-static/resources/view/we5927_lte.js

docs/
  HARDWARE.md
  RECOVERY.md
  STOCK-VS-CUSTOM.md
```

## Important limitation: AT helper

The running firmware currently uses a small MIPS helper at `/usr/sbin/we5927-at` to perform bounded serial AT transactions. Its source was not present on the router when this repository was prepared, so the first public revision intentionally does **not** redistribute an opaque binary of uncertain provenance.

That means the overlay in this repository is useful for documentation, review and development, but a clean reproducible flash image will only be published after the AT helper is replaced with a source-built implementation and the resulting image is tested on hardware.

## Safety

Flashing the wrong image can brick an 8 MB NOR router.

Before installing anything:

1. Confirm the exact board and modem.
2. Save the factory calibration/ART partition.
3. Save the U-Boot environment.
4. Keep serial/UART or U-Boot web recovery available.
5. Never publish backups containing Wi-Fi keys, router passwords, ICCID, IMEI or other device-specific secrets.

The ZBT product family contains several similarly named WE5927 variants. **WE5927-A (Nano-SIM/eSIM) must not be assumed to have the same flash/GPIO layout as WE2825-2SIM.**

## Disclaimer

This is an independent community project and is not affiliated with or endorsed by Shenzhen Zhibotong / ZBTLink. ZBT, WE5927 and WE2825 product names are used only to identify compatible hardware.

## License

Project-authored source and documentation are released under GPL-2.0-only unless a file states otherwise.
