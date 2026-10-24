#!/bin/sh
set -eu

OPENWRT_ROOT="${1:-}"
[ -n "$OPENWRT_ROOT" ] || {
	echo "usage: $0 /path/to/openwrt" >&2
	exit 2
}
[ -x "$OPENWRT_ROOT/scripts/feeds" ] || {
	echo "error: $OPENWRT_ROOT does not look like an OpenWrt tree" >&2
	exit 1
}

cd "$OPENWRT_ROOT"
./scripts/feeds update -a

# Install only the feed roots VeCI actually builds. scripts/feeds recursively
# installs each package's feed dependencies, so installing every feed package
# is unnecessary and can import unrelated Kconfig conflicts.
for package in 	luci 	luci-app-sqm 	luci-app-ddns 	luci-proto-wireguard 	uspot-www 	curl
do
	./scripts/feeds install "$package"
done
