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
for pkg in veci-core veci-default-ui veci-cellular-we5927 veci-app-catalog-we5927 veci-update-we5927 veci-data-meter; do
  [ -f "$here/source/$pkg/Makefile" ] || {
    echo "veci_package_source_missing:$pkg" >&2
    exit 3
  }
done
[ -f "$here/source/veci-core/UPSTREAM_COMMIT" ] || {
  echo 'veci_core_pin_missing' >&2; exit 3
}
grep -Fxq 'a1504e607d4b7b32ce9f6a6858cdf59dd777acfb' "$here/source/veci-core/UPSTREAM_COMMIT" || {
  echo 'veci_core_unreviewed_revision' >&2; exit 3
}
[ -f "$here/source/veci-core/veci/index.html" ] &&
[ -f "$here/source/veci-core/rpcd-acl.json" ] &&
[ -f "$here/source/veci-core/files/rpcd-veci" ] || {
  echo 'veci_authenticated_frontend_source_missing' >&2; exit 3
}
for pair in 'veci-core veci' 'veci-default-ui veci-default-ui' 'veci-cellular-we5927 veci-cellular-we5927' 'veci-app-catalog-we5927 veci-app-catalog-we5927' 'veci-update-we5927 veci-update-we5927' 'veci-data-meter veci-data-meter'; do
  set -- $pair
  src="$here/source/$1"
  dst="$root/package/$2"
  [ ! -L "$dst" ] || { echo "veci_package_symlink_refused:$2" >&2; exit 3; }
  mkdir -p "$dst"
  cp -a "$src/." "$dst/"
  cmp -s "$src/Makefile" "$dst/Makefile" || exit 4
done
# The APK feed and VeCI firmwareStatus both require the *actual checked-out*
# release build ID; the previous image omitted /etc/veci-release.json and
# rendered all future signed app-feed lookup impossible.
# This does NOT mark the image signed or flash-approved.
python3 "$here/scripts/veci_release_manifest.py" \
  --repo "$here" \
  --expected-head "$(git -C "$here" rev-parse HEAD)" \
  --out "$root/package/veci-app-catalog-we5927/files/etc/veci-release.json"
# Make the *root URL* resolve to VeCI, including on a normal sysupgrade that
# preserves the uHTTPd index-page order. Keep LuCI as a recovery-only fallback.
landing="$here/source/veci-default-ui/files/www/index.html"
[ -r "$landing" ] && grep -Fq 'url=/veci/' "$landing" || {
  echo 'native_veci_landing_missing' >&2; exit 4
}
mkdir -p "$root/files/www/veci" "$root/files/etc"
if [ -e "$root/files/www/index.html" ] &&
   ! cmp -s "$landing" "$root/files/www/index.html"; then
  echo 'existing_custom_landing_conflicts_with_veci' >&2; exit 4
fi
cp "$landing" "$root/files/www/index.html"
cp "$root/package/veci-app-catalog-we5927/files/etc/veci-release.json" \
  "$root/files/www/veci/build.json"
printf 'development\n' > "$root/files/etc/veci-release-channel"
echo 'VECI_NATIVE_LANDING_AND_REAL_RELEASE_ID_STAGED=PASS'
# Preserve reviewed latest LTE recovery while compiling the SMS CMGS helper.
# This helper is an explicit runtime dependency of SMS send on the live router.
[ -f "$here/source/we5927-lte/src/veci-sms-cmgs.c" ] || {
  echo 'sms_cmgs_source_missing' >&2; exit 3
}
cp "$here/source/we5927-lte/src/veci-sms-cmgs.c" "$root/package/we5927-lte/src/veci-sms-cmgs.c"
cp "$here/source/we5927-lte/Makefile" "$root/package/we5927-lte/Makefile"
grep -Fq '$(PKG_BUILD_DIR)/veci-sms-cmgs' "$root/package/we5927-lte/Makefile" || {
  echo 'sms_cmgs_package_build_missing' >&2; exit 3
}
# Carry the real optional-app sources into this exact ABI build tree without
# selecting them in ROM. Installation is deferred until the signed feed for
# the running firmware's build ID has been published and verified.
for pkg in veci-app-guest veci-app-voucher veci-app-sqm veci-app-ddns veci-app-wireguard veci-telco-indonesia; do
  src="$here/source/$pkg"
  dst="$root/package/$pkg"
  [ -f "$src/Makefile" ] || { echo "optional_app_source_missing:$pkg" >&2; exit 3; }
  [ ! -L "$dst" ] || { echo "optional_app_symlink_refused:$pkg" >&2; exit 3; }
  mkdir -p "$dst"
  cp -a "$src/." "$dst/"
  cmp -s "$src/Makefile" "$dst/Makefile" || exit 4
done
# Presence of source != installation or availability in the signed feed.
echo 'VECI_LIVE_CORE_CELLULAR_SMS_APPS_UPDATES_STAGED=PASS'
echo 'OPTIONAL_APP_SOURCE_STAGED=PASS'
echo 'GUEST_VOUCHER_OPTIONAL_NOT_BUNDLED=PASS'

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
