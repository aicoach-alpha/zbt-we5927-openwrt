# Installation and recovery

## Supported target

This release is for the tested board identity:

```
model: Zbtlink ZBT-WE5927
board_name: zbtlink,zbt-we5927
SoC: MediaTek MT7628AN
target: ramips/mt76x8
```

The tested cellular configuration is CX07E / Qualcomm-based USB LTE in RNDIS mode with data on `usb0` and the AT function normally appearing as `/dev/ttyUSB2`.

**Do not assume that every product sold as WE5927 has the same flash layout, GPIO wiring or modem.** In particular, WE5927-A / eSIM variants must be validated separately.

## Release files

- `openwrt-25.12.5-zbt-we5927-v2026.10.06-sysupgrade.bin` — flash image for a compatible OpenWrt installation.
- `openwrt-25.12.5-zbt-we5927-v2026.10.06-initramfs-kernel.bin` — RAM-boot/recovery image.
- `openwrt-25.12.5-zbt-we5927-v2026.10.06.manifest` — package manifest.
- `SHA256SUMS` — release hashes.
- `sysupgrade-meta.json` — metadata embedded in the sysupgrade image.

## Before flashing

1. Confirm `ubus call system board` reports `zbtlink,zbt-we5927`.
2. Back up your configuration.
3. Back up factory calibration / ART and U-Boot environment if you have not already done so.
4. Keep a UART/U-Boot recovery method available.
5. Verify the downloaded SHA-256 hash.
6. Run an image compatibility test before writing flash.

Example on OpenWrt:

```sh
sysupgrade -T /tmp/openwrt-25.12.5-zbt-we5927-v2026.10.06-sysupgrade.bin
```

Proceed only if that command exits successfully.

## Upgrade from compatible OpenWrt

Using LuCI, upload the sysupgrade image under **System -> Backup / Flash Firmware** and keep settings when upgrading from this same WE5927 build family.

CLI equivalent:

```sh
sysupgrade /tmp/openwrt-25.12.5-zbt-we5927-v2026.10.06-sysupgrade.bin
```

Do **not** use `-F` to bypass compatibility checks for a normal upgrade.

## Clean install behavior

For security, this public build does not ship a fixed public Wi-Fi password.

On a clean configuration:

- LAN address defaults to `192.168.1.1`.
- LuCI and Dropbear are enabled.
- Wi-Fi is kept disabled until the administrator configures an SSID and password.
- LTE is configured for `usb0` / DHCP.
- External filtered DNS defaults to `94.140.14.14` and `94.140.15.15`.
- Automatic SIM failover is disabled by default.

Use Ethernet for the initial setup after a clean install.

On sysupgrade with settings preserved, existing Wi-Fi credentials, LTE options and DNS/network choices are not intentionally overwritten by the first-boot migration scripts.

## From original ZBT firmware

The sysupgrade image in this repository is **not a vendor web-UI factory image**.

Do not upload the community sysupgrade image directly into an unknown ZBT factory upgrade page. A rejected format is the best outcome; a vendor-specific raw flash path can also brick the device.

Use a tested RAM-boot / U-Boot recovery path first, verify the board in OpenWrt, then install the sysupgrade image.

## Validation performed for v2026.10.06

The image was built from the same OpenWrt 25.12.5 tree used for the live router and was checked on the live WE5927 with:

```
sysupgrade -T <image>
```

Result: `PASS`.

The release SHA-256 for the final sysupgrade image is recorded in `SHA256SUMS`.

The router was also cleanly rebooted with the current LTE daemon enabled. After boot, the modem recovered to RNDIS online state and the new 30-second / 6-failure recovery threshold was active.

The public binary was **not force-flashed merely to prove the upload**. Compatibility validation is separate from intentionally writing the flash.
