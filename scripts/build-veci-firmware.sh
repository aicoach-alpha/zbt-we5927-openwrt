#!/bin/sh
set -eu

OPENWRT_ROOT="${1:-}"
JOBS="${JOBS:-4}"

[ -n "$OPENWRT_ROOT" ] || {
	echo "usage: JOBS=4 $0 /path/to/clean-openwrt-tree" >&2
	exit 2
}

git -C "$OPENWRT_ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1 || {
	echo "error: $OPENWRT_ROOT is not a Git OpenWrt tree" >&2
	exit 1
}

SELF_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
EXPECTED="$(tr -d '[:space:]' < "$SELF_DIR/source/openwrt-source-commit.txt")"
ACTUAL="$(git -C "$OPENWRT_ROOT" rev-parse HEAD)"

[ "$ACTUAL" = "$EXPECTED" ] || {
	echo "error: OpenWrt source commit mismatch" >&2
	echo " expected: $EXPECTED" >&2
	echo " actual:   $ACTUAL" >&2
	exit 1
}

[ -z "$(git -C "$OPENWRT_ROOT" status --porcelain)" ] || {
	echo "error: OpenWrt tree must be clean before applying the firmware overlay" >&2
	exit 1
}

PATCH="$SELF_DIR/source/openwrt-zbt-we5927-current.patch"
git -C "$OPENWRT_ROOT" apply --check "$PATCH"
git -C "$OPENWRT_ROOT" apply "$PATCH"

"$SELF_DIR/scripts/prepare-veci.sh" "$OPENWRT_ROOT"
cp "$SELF_DIR/source/openwrt-we5927.config" "$OPENWRT_ROOT/.config"

sh "$SELF_DIR/scripts/install-veci-feeds.sh" "$OPENWRT_ROOT"

cd "$OPENWRT_ROOT"
make defconfig

grep -q '^CONFIG_TARGET_ramips=y' .config
grep -q '^CONFIG_TARGET_ramips_mt76x8=y' .config
grep -q '^CONFIG_TARGET_ramips_mt76x8_DEVICE_zbtlink_zbt-we5927=y' .config
grep -q '^CONFIG_PACKAGE_veci=y' .config
grep -q '^CONFIG_PACKAGE_veci-default-ui=y' .config
grep -q '^CONFIG_PACKAGE_veci-cellular-we5927=y' .config
grep -q '^CONFIG_PACKAGE_veci-app-catalog-we5927=y' .config
grep -q '^CONFIG_PACKAGE_veci-app-guest=m' .config
grep -q '^CONFIG_PACKAGE_veci-app-sqm=m' .config
grep -q '^CONFIG_PACKAGE_veci-app-ddns=m' .config
grep -q '^CONFIG_PACKAGE_veci-app-wireguard=m' .config
grep -q '^CONFIG_PACKAGE_px5g-mbedtls=y' .config

make -j"$JOBS"

TARGET_DIR="$OPENWRT_ROOT/bin/targets/ramips/mt76x8"
IMAGE="$(find "$TARGET_DIR" -maxdepth 1 -type f -name '*zbt-we5927*sysupgrade.bin' | head -n 1)"

[ -n "$IMAGE" ] && [ -f "$IMAGE" ] || {
	echo "error: WE5927 sysupgrade image was not produced" >&2
	exit 1
}

SIZE="$(wc -c < "$IMAGE" | tr -d '[:space:]')"
MAX=$((7808 * 1024))
[ "$SIZE" -le "$MAX" ] || {
	echo "error: image exceeds the 7808 KiB firmware budget: $SIZE bytes" >&2
	exit 1
}

echo
echo "VeCI firmware build complete"
echo "image=$IMAGE"
echo "bytes=$SIZE"
sha256sum "$IMAGE"
