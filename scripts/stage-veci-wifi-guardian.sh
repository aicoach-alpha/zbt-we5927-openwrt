#!/bin/sh
# Source-tree only: inject current read-only Wi-Fi Guardian OpenWrt package.
# Must be run after the WE5927 board patch, before make defconfig/build.
set -eu
[ "$#" -eq 1 ] || { echo "usage: $0 <openwrt-source-root>" >&2; exit 2; }
root="$1"
here="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
src="$here/source/veci-wifi-guardian"
dst="$root/package/veci-wifi-guardian"
[ -f "$root/include/toplevel.mk" ] || { echo "not an OpenWrt source tree" >&2; exit 1; }
[ -f "$src/Makefile" ] && [ -f "$src/veci-wifi-guardian" ] && \
[ -f "$src/files/etc/init.d/veci-wifi-guardian" ] || exit 1
sh -n "$src/veci-wifi-guardian"
sh -n "$src/files/etc/init.d/veci-wifi-guardian"
if [ -e "$dst" ]; then
  [ -d "$dst" ] && [ ! -L "$dst" ] || exit 1
  cmp -s "$src/Makefile" "$dst/Makefile" &&
  cmp -s "$src/veci-wifi-guardian" "$dst/veci-wifi-guardian" &&
  cmp -s "$src/files/etc/init.d/veci-wifi-guardian" "$dst/files/etc/init.d/veci-wifi-guardian" || {
    echo "existing package differs; refusing overwrite" >&2
    exit 1
  }
else
  mkdir -p "$dst/files/etc/init.d"
  cp "$src/Makefile" "$dst/Makefile"
  cp "$src/veci-wifi-guardian" "$dst/veci-wifi-guardian"
  cp "$src/files/etc/init.d/veci-wifi-guardian" "$dst/files/etc/init.d/veci-wifi-guardian"
  chmod 755 "$dst/veci-wifi-guardian" "$dst/files/etc/init.d/veci-wifi-guardian"
fi
echo "GUARDIAN_SOURCE_PACKAGE_STAGED=PASS"
echo 'NOTE=select CONFIG_PACKAGE_veci-wifi-guardian=y before build; no live router changes'
