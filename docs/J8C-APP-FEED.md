# J8c — VeCI matched app feed

## Goal

Build optional VeCI router apps from the exact same OpenWrt source, feed revisions and WE5927 patch set as the firmware image. This avoids installing kernel modules compiled against the official WE5927 kernel ABI when VeCI uses a custom kernel ABI.

## Immutable maintenance baseline

The source of truth is `source/openwrt-maintenance-pins.env`.

The J8c baseline tracks the OpenWrt 25.12 maintenance line but converts every moving branch into an immutable commit SHA before building.

## Package policy

VeCI must never perform a blind `apk upgrade`.

Packages that touch the kernel, networking core or firmware base are upgraded by rebuilding and testing a coherent firmware image.

Optional apps are exposed to VeCI through small wrapper packages built from the same immutable source set as the firmware:

- `veci-app-guest` -> `uspot` + `uspot-www`.
- `veci-app-sqm` -> `sqm-scripts` + `luci-app-sqm` and exact-ABI kernel dependencies.
- `veci-app-ddns` -> `ddns-scripts` + `luci-app-ddns`.
- `veci-app-wireguard` -> `wireguard-tools` + `luci-proto-wireguard` and exact-ABI kernel dependencies.
- `veci-app-voucher` remains blocked until its guest-credential provider is implemented and tested.

The base image contains only `veci-app-catalog-we5927`, which installs root-owned app manifests. VeCI Core never accepts arbitrary package names from the browser; install/remove actions resolve only through those manifests.

`opennds` is not selected for this baseline because it is not present in the pinned OpenWrt 25.12 packages branch used by this reproducible build.

## CI output

`.github/workflows/j8c-app-feed.yml` performs a clean source build and uploads:

1. `veci-j8c-maintenance-candidate` — the firmware candidate, manifest, checksums and compatibility inventory.
2. `veci-j8c-matched-app-feed` — packages built against the exact firmware ABI.

These artifacts are development candidates only. A public VeCI feed remains disabled until project signing keys, signed metadata and compatibility metadata are finalized.
