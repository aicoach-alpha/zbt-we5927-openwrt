# J8c — VeCI matched app feed

## Goal

Build optional VeCI router apps from the exact same OpenWrt source, feed revisions and WE5927 patch set as the firmware image. This avoids installing kernel modules compiled against the official WE5927 kernel ABI when VeCI uses a custom kernel ABI.

## Immutable maintenance baseline

The source of truth is `source/openwrt-maintenance-pins.env`.

The J8c baseline tracks the OpenWrt 25.12 maintenance line but converts every moving branch into an immutable commit SHA before building.

## Package policy

VeCI must never perform a blind `apk upgrade`.

Packages that touch the kernel, networking core or firmware base are upgraded by rebuilding and testing a coherent firmware image.

Optional apps are shipped as modules in the matched VeCI package feed:

- Smart Queue: `sqm-scripts`, `luci-app-sqm` and exact-ABI kernel dependencies.
- Dynamic DNS: `ddns-scripts`, `luci-app-ddns`.
- WireGuard: `wireguard-tools`, `luci-proto-wireguard` and exact-ABI `kmod-wireguard`.
- Guest portal candidates: `simple-captive-portal` and `uspot`/ `uspot-www`; choose after measured flash/RAM cost.
- Voucher: VeCI-specific package, not yet implemented.

`opennds` is not selected for this baseline because it is not present in the pinned OpenWrt 25.12 packages branch used by this reproducible build.

## CI output

`.github/workflows/j8c-app-feed.yml` performs a clean source build and uploads:

1. `veci-j8c-maintenance-candidate` — the firmware candidate, manifest, checksums and compatibility inventory.
2. `veci-j8c-matched-app-feed` — packages built against the exact firmware ABI.

These artifacts are development candidates only. A public VeCI feed remains disabled until project signing keys, signed metadata and compatibility metadata are finalized.
