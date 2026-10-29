#!/bin/sh
# On NAS only. Builds INSIDE bounded Ubuntu container on external staging volume.
# No router connectivity or unattended flash, no host apt installation.
set -eu
[ "$#" -eq 2 ] || {
  echo "usage: $0 /mnt/data/andre-maintenance-archives/veci-cafe-build-20261029 <validate|download|build>" >&2
  exit 2
}
root="$1"
mode="$2"
case "$mode" in validate|download|build) ;; *) echo "INVALID_MODE" >&2; exit 2;; esac
case "$root" in /mnt/data/andre-maintenance-archives/veci-cafe-build-*) ;; *)
  echo "STOP: Build must run on external scratch, never NAS root disk or router" >&2; exit 3;;
esac
[ -d "$root/openwrt/.git" ] && [ -f "$root/openwrt/.config" ] || {
  echo "STOP: Pinned OpenWrt source and config not prepared" >&2; exit 4;
}
case "$(git -C "$root/openwrt" rev-parse HEAD)" in
  c740570351512e4400369b3c2aff49741f65580e) ;;
  *) echo "STOP: Wrong OpenWrt pinned commit" >&2; exit 5;;
esac
command -v docker >/dev/null 2>&1 || { echo "STOP: Docker unavailable" >&2; exit 6; }
# Service protection: never grant privileged/net=host, and cap CPU, RAM and swap.
repo="$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)"
case "$mode" in
  validate) cmd='make defconfig && /firmware/scripts/prepare-veci-general-cafe-profile.sh /build && grep -E "CONFIG_PACKAGE_(uspot|uspot-www|veci-app-guest|veci-app-voucher)=y" .config' ;;
  download) cmd='make download -j2' ;;
  build) cmd='make -j2' ;;
esac
exec docker run --rm --name veci-cafe-builder   --cpus=1.5 --memory=4g --memory-swap=6g --pids-limit=256   --security-opt=no-new-privileges --cap-drop=ALL   --network=bridge --user 1000:1000   -e HOME=/tmp -v "$root/openwrt:/build"   -w /build veci-general-cafe-builder:20261029   /bin/bash -lc "$cmd"
