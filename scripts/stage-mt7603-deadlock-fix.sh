#!/bin/sh
# Stage a source-level mt7603 patch into a matching OpenWrt build tree.
# Does not touch a live router or build/flash firmware.
set -eu

if [ "$#" -ne 1 ]; then
  echo "usage: $0 <openwrt-source-root>" >&2
  exit 2
fi

root="$1"
here="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
patch="950-mt7603-defer-watchdog-on-channel-failure.patch"
src="$here/source/mt76-patches/$patch"
makefile="$root/package/kernel/mt76/Makefile"
dst="$root/package/kernel/mt76/patches/$patch"

[ -f "$makefile" ] || { echo "missing mt76 Makefile" >&2; exit 1; }
[ -r "$src" ] || { echo "missing staged patch" >&2; exit 1; }
grep -Fqx 'PKG_SOURCE_VERSION:=39c960c3ada558b4c2e7915772483d3731573d09' "$makefile" || {
  echo "mt76 revision mismatch: refusing to stage patch" >&2
  exit 1
}
if [ -e "$dst" ]; then
  cmp -s "$src" "$dst" || {
    echo "different patch with same name already exists: $dst" >&2
    exit 1
  }
  echo "patch already staged: $dst"
  exit 0
fi
mkdir -p "$(dirname -- "$dst")"
cp "$src" "$dst"
cmp -s "$src" "$dst"
echo "patch staged for matching mt76 source: $dst"
echo "NOT BUILT; NOT TESTED ON HARDWARE; NOT DEPLOYED"
