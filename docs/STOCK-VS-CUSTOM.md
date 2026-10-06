# Official ZBT firmware vs community OpenWrt build

This comparison was prepared from two sources:

1. the current ZBT download published for **WE2825-2SIM**; and
2. a live WE5927/WE2825-2SIM unit running this community OpenWrt build.

## Official ZBT firmware examined

ZBT's public download page listed the following image on 2026-10-06:

- Product entry: `WE2825-2SIM`
- Vendor filename: `WE2825-2SIM_V26.03.04_V26.08.09.bin`
- Vendor page date: **2026-08-17**
- Vendor page listed size: **8.5Mb**
- Downloaded file size observed: **7,471,108 bytes**
- SHA-256: `80529B8E9C31D686EB7F63A1517D6DBCF781F26CB4ACEB7B8B1FF27C2D51D1F9`

Official source:

https://www.zbtlink.com/pages/download-list-starts-with-we

Direct vendor download used for inspection:

https://cdn.shopify.com/s/files/1/0760/0416/3873/files/WE2825-2SIM_V26.03.04_V26.08.09.bin?v=1786953217

The image was inspected locally without flashing it.

### What the official image contains

The uImage header reports:

```
MIPS LEDE Linux-4.4.61
uImage timestamp: 2019-11-20 03:46:03 UTC
kernel payload: 1,184,708 bytes
```

The SquashFS root filesystem reports:

```
SquashFS 4.0
XZ compression
filesystem creation: 2026-08-11 13:40:13
compressed filesystem size: ~5.97 MiB
```

Its `/etc/openwrt_release` says:

```
DISTRIB_ID='LEDE'
DISTRIB_RELEASE='SNAPSHOT'
DISTRIB_REVISION='26.0305_112700'
DISTRIB_CODENAME='reboot'
DISTRIB_TARGET='ramips/mt7628'
DISTRIB_ARCH='mipsel_24kc'
DISTRIB_DESCRIPTION='LEDE Reboot SNAPSHOT 17.01'
DISTRIB_TAINTS='no-all no-ipv6 busybox override'
```

The image contains a legacy Lua LuCI tree. Its LuCI version file reports:

```
git-19.324.13563-3eb814a
```

The extracted `opkg` status database contains about **235 packages**.

The stock image also contains ZBT/AnyWiFi modem tooling for a broad set of modem families, including multiple manual-dial/chat-script profiles and a network watchdog implementation.

## Community build examined

The live tested unit reports:

```
OpenWrt 25.12.5 r33051-f5dae5ece4
Linux 6.12.94
Target: ramips/mt76x8
Arch: mipsel_24kc
Package manager: apk
```

The tested live system had about **149 installed packages**.

The firmware partition layout observed on the tested unit is:

```
mtd0  0x00030000  u-boot
mtd1  0x00010000  u-boot-env
mtd2  0x00010000  factory
mtd3  0x007a0000  firmware
mtd4  0x001dc72d  kernel
mtd5  0x005c38d3  rootfs
mtd6  0x00220000  rootfs_data
mtd7  0x00010000  art
```

The tested unit had approximately:

- 58.6 MiB usable RAM
- 2.1 MiB overlay
- about 1.3 MiB overlay free during preparation of this repository

## Comparison

| Area | Official ZBT WE2825-2SIM | Community OpenWrt build |
|---|---|---|
| Release channel | Vendor-supported | Community/unofficial |
| Vendor portal date | 2026-08-17 | Built around OpenWrt 25.12.5 |
| Base userspace | LEDE 17.01 snapshot lineage | OpenWrt 25.12.5 |
| Kernel | 4.4.61 | 6.12.94 |
| Package manager | opkg | apk |
| Package count observed | ~235 | ~149 |
| LuCI generation | Legacy Lua LuCI | Current JavaScript LuCI |
| IPv6 | Image explicitly tainted `no-ipv6` | IPv6 available on tested build |
| Modem support | Broad vendor AnyWiFi profiles | Narrower, tuned to CX07E/RNDIS |
| Dual-SIM logic | Vendor stack | Explicit GPIO-based manager |
| LTE recovery | Vendor watchdog/network scripts | Interface-first -> CFUN -> hard reset |
| LuCI modem status | Vendor-specific pages | Fast cached full-status page |
| Resource footprint | Larger feature set | Intentionally lean |
| Security maintenance | Depends on vendor backports | Newer upstream OpenWrt/kernel base |
| SQM on tested image | Not evaluated | Not installed; required kmods unavailable for running ABI |
| Support path | ZBT vendor | GitHub/community |
| Flash risk | Factory-supported for matching model | Higher; exact hardware validation required |

## Advantages of the official ZBT firmware

- Vendor-supported image for the matching hardware family.
- Factory modem framework supports a wider range of cellular modules.
- Factory UI and network logic are familiar to ZBT support.
- Best first choice when warranty/supportability is more important than upstream freshness.
- Useful as a recovery/reference image.

## Disadvantages of the official ZBT firmware

- The inspected 2026 image still carries a **Linux 4.4.61** kernel and a **LEDE 17.01** userspace lineage.
- The image declares `no-ipv6`.
- The modem/watchdog stack is broad and comparatively complex.
- Legacy LuCI generation.
- Public release date alone does not mean all underlying components are recent; security quality depends on vendor backports.

## Advantages of this community build

- Much newer OpenWrt and kernel base.
- Leaner package set for 64 MB RAM / 8 MB flash hardware.
- Modern LuCI.
- IPv6-capable base.
- LTE manager is designed around the actual tested CX07E behavior.
- Avoids unsafe automatic probing of the secondary serial function.
- LuCI status uses cached full modem data so a slow AT command does not block the page.
- Recovery is conservative: logical interface first, then CFUN, then hard modem power-cycle only after escalation.
- External DNS filtering avoids a large local ad-block database.

## Disadvantages of this community build

- Unofficial and not supported by ZBT.
- Tuned to one hardware/modem combination; it is less generic than the factory AnyWiFi stack.
- Tiny overlay leaves little space for optional packages.
- Full SQM is not currently practical on the tested image because matching kernel modules are not available from the configured feed.
- The project remains unofficial and must be matched to the exact board/modem combination.
- The public sysupgrade image is a release candidate for compatible OpenWrt installs, not a vendor-web-UI factory image.
- The source-built AT helper is included, but broader clean-flash and hardware-variant testing is still limited.

## Which one should you use?

Use **official ZBT firmware** when:

- you need factory support;
- you use a different modem than the tested CX07E;
- you want the vendor's broad modem database;
- you need the easiest path back to a known factory state.

Use this **community build/overlay** when:

- the hardware exactly matches the tested WE5927/WE2825-2SIM layout;
- you use the CX07E/RNDIS path;
- you value a newer OpenWrt/kernel base;
- you want conservative LTE recovery and a lightweight system;
- you understand serial/U-Boot recovery and can recover from a bad flash.

## Compatibility warning

ZBT also sells a **WE5927-A** variant with Nano-SIM/eSIM. Similar product names do not guarantee the same GPIO wiring, flash partitions, modem slot or board definition.

Do not assume the WE2825-2SIM image or this community overlay is safe for every WE5927-labelled unit.
