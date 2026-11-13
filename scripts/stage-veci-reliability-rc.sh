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
# Validate all boot-path sources and destinations before changing any file.
# Old historical board patches include a disruptive 'sleep 2; ifup lte'
# hotplug callback which must never survive the reliability RC staging.
for rel in etc/init.d/we5927-lte etc/hotplug.d/usb/30-we5927-lte; do
  live="$here/source/we5927-lte/files/$rel"
  dest="$root/package/we5927-lte/files/$rel"
  [ -f "$live" ] && [ -f "$dest" ] && [ ! -L "$dest" ] ||
    { echo "LTE_boot_source_or_target_missing:$rel" >&2; exit 3; }
  sh -n "$live"
done
grep -Fq 'procd_add_reload_trigger we5927_lte' "$here/source/we5927-lte/files/etc/init.d/we5927-lte" ||
 { echo 'LTE_procd_safe_trigger_missing' >&2; exit 3; }
if grep -Eq '^[[:space:]]*(ifup|ifdown|wifi|/usr/sbin/we5927-lte usb-repair)([[:space:]]|$)'   "$here/source/we5927-lte/files/etc/hotplug.d/usb/30-we5927-lte"; then
 echo 'LTE_disruptive_hotplug_source' >&2; exit 3
fi
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

# Both native admin UI packages are compiled into this *candidate* image.
# Pinned source is carried in-repo; do not silently fetch a moving branch.
# This does NOT establish parity with the currently running router overlay.
for pkg in veci-core veci-default-ui; do
  [ -f "$here/source/$pkg/Makefile" ] || {
    echo "veci_package_source_missing:$pkg" >&2
    exit 3
  }
done
[ -f "$here/source/veci-core/UPSTREAM_COMMIT" ] || {
  echo 'veci_core_pin_missing' >&2; exit 3
}
grep -Fxq 'bdf7bcf332c23b625e92fb1e00d1fb30edea88b6' "$here/source/veci-core/UPSTREAM_COMMIT" || {
  echo 'veci_core_unreviewed_revision' >&2; exit 3
}
[ -f "$here/source/veci-core/veci/index.html" ] &&
[ -f "$here/source/veci-core/rpcd-acl.json" ] &&
[ -f "$here/source/veci-core/files/rpcd-veci" ] || {
  echo 'veci_authenticated_frontend_source_missing' >&2; exit 3
}
for pair in 'veci-core veci' 'veci-default-ui veci-default-ui'; do
  set -- $pair
  src="$here/source/$1"
  dst="$root/package/$2"
  [ ! -L "$dst" ] || { echo "veci_package_symlink_refused:$2" >&2; exit 3; }
  mkdir -p "$dst"
  cp -a "$src/." "$dst/"
  cmp -s "$src/Makefile" "$dst/Makefile" || exit 4
done
echo 'VECI_CORE_AND_DEFAULT_UI_STAGED=PASS'

# Reconcile init/hotplug AFTER the historical board patch, not only
# the daemon binary. Write to the isolated build tree, never the router.
for rel in etc/init.d/we5927-lte etc/hotplug.d/usb/30-we5927-lte; do
  live="$here/source/we5927-lte/files/$rel"
  dest="$root/package/we5927-lte/files/$rel"
  if ! cmp -s "$live" "$dest"; then
    tmp="$(mktemp "$dest.next.XXXXXX")"
    cp "$live" "$tmp"
    chmod 755 "$tmp"
    mv -f "$tmp" "$dest"
  fi
  cmp -s "$live" "$dest" ||
    { echo "LTE_boot_tree_not_reconciled:$rel" >&2; exit 4; }
done
echo 'LTE_COLD_BOOT_SCRIPTS_STAGED=PASS'

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
