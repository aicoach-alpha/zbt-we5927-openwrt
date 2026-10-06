# Hardware notes

## Tested unit

This repository was prepared from a live unit identifying as:

```
ZBT-WE5927 / WE2825-2SIM
MediaTek MT7628
mipsel_24kc
64 MB RAM class
8 MB NOR flash class
```

Observed live network layout:

```
LAN: br-lan 192.168.1.1/24
LTE data: usb0
LTE mode: RNDIS
LTE DHCP address: modem-provided
LTE metric: 5
```

The repository intentionally does not contain the tested unit's public/private IP history, Wi-Fi credentials, ICCID or IMEI.

## Flash layout observed

```
dev:    size       erasesize  name
mtd0:   00030000   00010000   u-boot
mtd1:   00010000   00010000   u-boot-env
mtd2:   00010000   00010000   factory
mtd3:   007a0000   00010000   firmware
mtd4:   001dc72d   00010000   kernel
mtd5:   005c38d3   00010000   rootfs
mtd6:   00220000   00010000   rootfs_data
mtd7:   00010000   00010000   art
```

Do not assume this partition map applies to another WE5927-labelled model.

## LTE modem assumptions

The tested setup uses:

- USB vendor/product: `05c6:902e`
- data device: `usb0`
- modem mode: RNDIS
- safe AT function: USB interface 1.4
- usual AT node: `/dev/ttyUSB2`

The LTE manager resolves the AT port from sysfs and deliberately avoids automatically probing USB interface 1.5 because the wrong serial function can enter uninterruptible I/O on this modem/driver combination.

## Dual-SIM GPIOs

Observed defaults:

- modem power GPIO: `1`
- SIM select GPIO: `46`
- SIM 1 value: `1`
- SIM 2 value: `0`

The script also understands named sysfs aliases when present:

- `/sys/class/gpio/modem_power`
- `/sys/class/gpio/sim_select`

GPIO values are hardware-specific. Verify them before enabling automatic SIM switching on another unit.

## Wi-Fi hardware

The tested radio is the MT7628 integrated 2.4 GHz 802.11b/g/n radio.

A stable baseline on the tested unit is:

- 2.4 GHz only
- HT20
- country set correctly
- WPA2/WPA3 mixed where all clients support it
- visible SSID recommended
- channel 1, 6 or 11 selected based on local interference

## Resources

Observed on the tested OpenWrt 25.12.5 image:

- usable memory: ~58.6 MiB
- overlay total: ~2.1 MiB
- overlay free during repository preparation: ~1.3 MiB

That is why this project avoids heavy proxy, VPN and local ad-block stacks by default.
