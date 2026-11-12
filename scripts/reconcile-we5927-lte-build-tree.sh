#!/bin/sh
# Fail-closed source reconciliation for OpenWrt WE5927 firmware build trees.
# The historical board patch embeds an older we5927-lte script. Always copy
# the verified source after applying that patch, before building the image.
# Never accesses a running router.
set -eu

if [ "$#" -ne 1 ]; then
  echo "usage: $0 <openwrt-source-root>" >&2
  exit 2
fi
root="$1"
here="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
src="$here/source/we5927-lte/files/usr/sbin/we5927-lte"
mirror="$here/files/usr/sbin/we5927-lte"
dst="$root/package/we5927-lte/files/usr/sbin/we5927-lte"

[ -f "$root/include/toplevel.mk" ] || {
  echo "not an OpenWrt build tree: missing include/toplevel.mk" >&2
  exit 1
}
[ -f "$root/package/we5927-lte/Makefile" ] || {
  echo "we5927-lte package missing; apply board patch first" >&2
  exit 1
}
[ -f "$src" ] && [ -f "$mirror" ] && [ -f "$dst" ] || {
  echo "expected source or package file missing" >&2
  exit 1
}
[ ! -L "$dst" ] || {
  echo "target is symlink; refusing to overwrite" >&2
  exit 1
}
cmp -s "$src" "$mirror" || {
  echo "firmware LTE source copies differ; fail closed" >&2
  exit 1
}
sh -n "$src"
tmp="$(mktemp "$dst.next.XXXXXX")"
trap 'rm -f "$tmp"' EXIT HUP INT TERM
cp "$src" "$tmp"
chmod 755 "$tmp"
sh -n "$tmp"
mv -f "$tmp" "$dst"
cmp -s "$src" "$dst"
echo "VERIFIED_LTE_SOURCE_STAGED=PASS"
echo "NOTE=source-tree-only; no live router changes; no image built"
