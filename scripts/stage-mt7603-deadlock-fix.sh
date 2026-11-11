#!/bin/sh
# Stage pinned mt7603 source fixes into the exact OpenWrt build tree.
# Source-tree only: NEVER touches router/flash/kernel modules.
set -eu
if [ "$#" -ne 1 ]; then
  echo "usage: $0 <openwrt-source-root>" >&2
  exit 2
fi

root="$1"
here="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
makefile="$root/package/kernel/mt76/Makefile"
directory="$root/package/kernel/mt76/patches"
patches="
950-mt7603-defer-watchdog-on-channel-failure.patch
951-mt7603-free-beacon-skb-on-error.patch
"

[ -f "$makefile" ] || { echo "missing mt76 Makefile" >&2; exit 1; }
grep -Fqx 'PKG_SOURCE_VERSION:=39c960c3ada558b4c2e7915772483d3731573d09' "$makefile" || {
  echo "mt76 revision mismatch: refusing to stage patches" >&2
  exit 1
}
# Validate both patches before copying either: prevent partial staging.
for patch in $patches; do
  src="$here/source/mt76-patches/$patch"
  dst="$directory/$patch"
  [ -r "$src" ] || { echo "missing source patch $patch" >&2; exit 1; }
  [ ! -L "$dst" ] || { echo "refusing symlink patch $dst" >&2; exit 1; }
  if [ -e "$dst" ]; then
    cmp -s "$src" "$dst" || {
      echo "different patch with same name already exists: $dst" >&2
      exit 1
    }
  fi
done
mkdir -p "$directory"
for patch in $patches; do
  src="$here/source/mt76-patches/$patch"
  dst="$directory/$patch"
  if [ -e "$dst" ]; then
    echo "patch already staged: $dst"
  else
    cp "$src" "$dst"
  fi
  cmp -s "$src" "$dst"
done
echo "TWO_EXACT_REVISION_MT7603_PATCHES_STAGED=PASS"
echo "NOT BUILT; NOT HARDWARE-TESTED; NOT DEPLOYED"
