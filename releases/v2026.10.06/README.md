# v2026.10.06 — first public binary release candidate

This directory contains the first public flashable build for the tested ZBT WE5927 / WE2825-2SIM hardware.

## Artifacts

- **sysupgrade.bin** — normal OpenWrt upgrade image for an already compatible WE5927 OpenWrt installation.
- **initramfs-kernel.bin** — RAM boot / recovery kernel.
- **manifest** — installed package list.
- **sysupgrade-meta.json** — metadata embedded into the sysupgrade image.
- **SHA256SUMS** — integrity hashes.

## Validation

The final sysupgrade image was copied to the live router and validated with OpenWrt's own compatibility checker:

```
sysupgrade -T openwrt-25.12.5-zbt-we5927-v2026.10.06-sysupgrade.bin
```

Result: **PASS**.

Final sysupgrade SHA-256:

```
e921a9630d719c3d760e7fb2602376f3e4c66cb03e95585792e0668d41b401e9
```

## Safety changes in this build

- modem status cache prevents LuCI from blocking on slow AT queries;
- AT serial access is locked and bounded;
- known unsafe secondary CX07E serial probing is avoided;
- LTE health checks use 30-second intervals and 6 consecutive failures;
- recovery is interface-first, then CFUN, then hard modem power-cycle;
- automatic SIM failover stays disabled by default;
- clean installs no longer ship a public fixed Wi-Fi password;
- existing Wi-Fi/network settings are preserved during normal sysupgrade migrations.

## Important

This is a **community release candidate**, not an official ZBT image. It is not intended as a vendor-web-UI factory image. See [../../docs/INSTALL.md](../../docs/INSTALL.md) before flashing.
