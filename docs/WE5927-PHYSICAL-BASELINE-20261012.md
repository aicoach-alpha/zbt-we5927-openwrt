# WE5927 physical read-only baseline — 2026-10-12

Source: SSH output supplied by owner from **Windows office laptop**, Ethernet
192.168.1.223, WE5927 at 192.168.1.1. This is read-only operator evidence,
not independently completed hardware UAT or flash approval. The NAS can
reach a separate ZTE device at the same private IP; do not conflate networks.

## Device facts

- Board name: zbtlink,zbt-we5927; model Zbtlink ZBT-WE5927.
- SoC: MediaTek MT7628AN ver:1 eco:2.
- Installed: OpenWrt 25.12.5 r33051-f5dae5ece4, ramips/mt76x8,
  kernel 6.12.94, squashfs.
- Firmware MTD partition: mtd3 0x007a0000 (7,995,392 bytes, 7.625 MiB);
  erasesize 0x10000. mtd6 rootfs_data 0x00210000 (~2.1 MiB).
- Overlay: 2.1M capacity, 344K used, **1.7M free**. /tmp 28.6M
  capacity, 28.3M free at collection.
- BusyBox free -m displayed total 58568 and available 15700, apparently
  in KiB despite flag, ~57.2 MiB total. Do not assume 58 GB.
- USB VID:PID 05c6:902e on all four ports:
  ttyUSB0 interface 1.2, ttyUSB1 interface 1.3, **ttyUSB2 interface
  1.4 (AT)**, ttyUSB3 interface 1.5 (**NEVER PROBE**).
  Canonical prefix /sys/devices/platform/101c0000.ehci/usb1/1-1/.
- /etc/veci-release.json not found; /etc/veci-release-channel empty or
  missing; /usr/libexec/rpcd/veci.cellular present (2942 bytes) and
  /usr/sbin/we5927-at present (4120 bytes). The newer diagnostic helper
  /usr/libexec/veci-modem-capabilities is NOT installed.
- Windows HTTP GET: 200, title VeCI · OpenWrt. TCP/22 open and SSH root
  successfully logged in from office Windows laptop.

## Release implications and blockers

1. Existing VeCI dashboard **is live**; new SMS/USSD capabilities are
   **not live**. Missing helper and old 2942-byte RPC mean downloading
   the helper alone does not establish a dashboard feature. The source
   branch RPC is ~5784 bytes; never blindly replace production RPC.
2. Firmware image must match exact board, fit 7,995,392 bytes, have correct
   signature/ABI and signed matching packages. Newer build may have
   different kernel from running 6.12.94: do not install new kmods
   individually onto running firmware.
3. Any overlay-only patch must be under strict disk budget, syntax/ACL
   checked, backed up and atomically reversible. No silent rpcd/network
   restart.
4. Actual modem USB sysfs confirms the 1.4 port expected by the new
   *source-only* identity policy. It does not prove protocol behavior,
   lock/session attribution, SMS/USSD availability, physical retry safety,
   backup, updater verification, hardware rollback or flash readiness.
5. Scripts/veci-live-device-preflight.sh provides optional operator-run,
   read-only hardware facts. It deliberately always reports flash NO_GO.
6. Before any flashing require a verified local backup, router LAN
   recovery access, image and signature validation, enough memory to stage
   the image, exact candidate SHA256, sysupgrade -T success, and explicit
   owner approval for the exact device and image. Firmware LIVE gate
   remains NO_GO until evidence is collected.

This evidence was captured with NO hardware changes.
