#!/bin/sh
# Stage a complete *source-tree* reliability candidate into pinned OpenWrt.
# This NEVER runs on a router and NEVER creates a deployable/flashable image.
set -eu

[ "$#" -eq 1 ] || { echo 'usage: stage-veci-reliability-rc.sh <openwrt-source-root>' >&2; exit 2; }
srcroot="$1"
here="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd -P)"
[ -d "$srcroot" ] && [ ! -L "$srcroot" ] || { echo 'source_root_missing_or_symlink' >&2; exit 2; }
root="$(CDPATH= cd -- "$srcroot" && pwd -P)"
case "$root" in /|/etc|/rom|/overlay|/tmp|/root) echo 'unsafe_build_root' >&2; exit 2;; esac
[ -f "$root/include/toplevel.mk" ] && [ -f "$root/package/kernel/mt76/Makefile" ] ||
 { echo 'not_openwrt_source_tree' >&2; exit 2; }
[ -d "$root/.git" ] || { echo 'source_git_missing' >&2; exit 2; }
want="$(cat "$here/source/openwrt-source-commit.txt")"
actual="$(git -C "$root" rev-parse HEAD 2>/dev/null)" || exit 2
[ "$actual" = "$want" ] || { echo 'openwrt_source_revision_mismatch' >&2; exit 3; }
[ -f "$root/package/we5927-lte/Makefile" ] ||
 { echo 'WE5927_board_patch_required_before_staging' >&2; exit 3; }
[ -f "$root/package/we5927-lte/files/usr/sbin/we5927-lte" ] ||
 { echo 'WE5927_embedded_LTE_source_missing' >&2; exit 3; }

# The LTE copies must agree BEFORE any file is changed in the OpenWrt tree.
a="$here/files/usr/sbin/we5927-lte"
b="$here/source/we5927-lte/files/usr/sbin/we5927-lte"
cmp -s "$a" "$b" || { echo 'LTE_source_mirror_mismatch' >&2; exit 3; }
sh -n "$a"
grep -Fq 'manual_reconnect() {' "$a" ||
 { echo 'LTE_low_downtime_guard_not_present' >&2; exit 3; }
grep -Fq '&& radio_or_link_lost; then' "$a" ||
 { echo 'LTE_radio_reset_guard_not_present' >&2; exit 3; }
grep -Fq 'PKG_SOURCE_VERSION:=39c960c3ada558b4c2e7915772483d3731573d09'  "$root/package/kernel/mt76/Makefile" ||
 { echo 'mt76_driver_revision_mismatch' >&2; exit 3; }

# Validated in separate PRs. Two MT7603 fixes are revision-guarded and
# copied atomically; guardian never auto-reloads radio.
sh "$here/scripts/stage-mt7603-deadlock-fix.sh" "$root"
sh "$here/scripts/reconcile-we5927-lte-build-tree.sh" "$root"
sh "$here/scripts/stage-veci-wifi-guardian.sh" "$root"

cmp -s "$a" "$root/package/we5927-lte/files/usr/sbin/we5927-lte" ||
 { echo 'LTE_build_tree_stale' >&2; exit 4; }
test "$(grep -c 'auto_recover=0' "$root/package/veci-wifi-guardian/veci-wifi-guardian")" -ge 1 ||
 { echo 'guardian_observe_only_guard_missing' >&2; exit 4; }
if grep -Eq '(^|[[:space:]])wifi[[:space:]]+(up|reload|down)'  "$root/package/veci-wifi-guardian/veci-wifi-guardian"; then
 echo 'unsafe_guardian_radio_reload' >&2
 exit 4
fi
echo 'WE5927_RELIABILITY_SOURCE_STAGED=PASS'
echo 'PINNED_OPENWRT=25.12.5'
echo 'MT7603_PATCHES=2'
echo 'LTE_MANUAL_RECOVERY_GUARDED=PASS'
echo 'WIFI_GUARDIAN_OBSERVE_ONLY=PASS'
echo 'FIRMWARE_NOT_BUILT_OR_HARDWARE_TESTED'
