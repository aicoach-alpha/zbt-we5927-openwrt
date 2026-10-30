#!/bin/sh
# Read-only VeCI General app readiness. Never prints Wi-Fi, SIM, WAN or auth secrets.
set -u
item() { printf '%s=%s\n' "$1" "$2"; }
board="$(ubus call system board 2>/dev/null | jsonfilter -e '@.board_name' 2>/dev/null || true)"
target="$(ubus call system board 2>/dev/null | jsonfilter -e '@.release.target' 2>/dev/null || true)"
item BOARD "$board"
item TARGET "$target"
if [ "$board" != 'zbtlink,zbt-we5927' ] || [ "$target" != 'ramips/mt76x8' ]; then
    item RESULT WRONG_ROUTER
    exit 3
fi
version="$(. /etc/openwrt_release 2>/dev/null; printf '%s' "$DISTRIB_RELEASE")"
kernel="$(uname -r 2>/dev/null || true)"
item OPENWRT "$version"
item KERNEL "$kernel"
item PACKAGE_MANAGER "$(command -v apk >/dev/null 2>&1 && echo apk || (command -v opkg >/dev/null 2>&1 && echo opkg || echo none))"
if command -v apk >/dev/null 2>&1; then
    item PACKAGE_ARCH "$(apk --print-arch 2>/dev/null | head -n 1 | tr -cd 'A-Za-z0-9_-')"
fi
overlay="$(df -Pk /overlay 2>/dev/null | awk 'NR==2 {print $4}')"
mem="$(awk '/^MemAvailable:/ {print $2; exit}' /proc/meminfo 2>/dev/null)"
case "$overlay" in ''|*[!0-9]*) overlay=0;; esac
case "$mem" in ''|*[!0-9]*) mem=0;; esac
item OVERLAY_AVAILABLE_KB "$overlay"
item MEM_AVAILABLE_KB "$mem"
installed() {
    if command -v apk >/dev/null 2>&1; then apk info -e "$1" >/dev/null 2>&1
    elif command -v opkg >/dev/null 2>&1; then opkg status "$1" 2>/dev/null | grep -q '^Status: install ok installed$'
    else return 1
    fi
}
for name in veci veci-app-catalog-we5927 veci-app-guest veci-app-voucher uspot uspot-www sqm-scripts ddns-scripts wireguard-tools; do
    if installed "$name"; then item "PKG_$name" INSTALLED; else item "PKG_$name" MISSING; fi
done
item APP_MANIFEST_GUEST "$(test -f /usr/share/veci/apps/guest.json && echo PRESENT || echo MISSING)"
item APP_MANIFEST_VOUCHER "$(test -f /usr/share/veci/apps/voucher.json && echo PRESENT || echo MISSING)"
item RPC_GUEST "$(ubus list 2>/dev/null | grep -qx 'veci.app.guest' && echo REGISTERED || echo MISSING)"
item RPC_VOUCHER "$(ubus list 2>/dev/null | grep -qx 'veci.app.voucher' && echo REGISTERED || echo MISSING)"
item RPC_APPS_FEED "$(ubus list 2>/dev/null | grep -qx 'veci.apps' && echo REGISTERED || echo MISSING)"
build=''
if [ -f /etc/veci-release.json ]; then
    build="$(jsonfilter -i /etc/veci-release.json -e '@.build_id' 2>/dev/null || true)"
fi
case "$build" in
    ????????????????????????????????????????) item BUILD_ID "$build";;
    *) item BUILD_ID MISSING; build='';;
esac
feed_on="$(uci -q get veci.main.app_feed_enabled 2>/dev/null || true)"
feed_pin="$(uci -q get veci.main.app_feed_build_id 2>/dev/null || true)"
verified="$(uci -q get veci.main.app_feed_verified_build_id 2>/dev/null || true)"
repo_ok=false
if [ -n "$build" ] && [ -r /etc/apk/repositories.d/veci-apps.list ]; then
    grep -Fq "/feeds/$build/" /etc/apk/repositories.d/veci-apps.list && repo_ok=true
fi
item REPO_MATCHES_BUILD "$repo_ok"
item FEED_ENABLED "$(test "$feed_on" = 1 && echo true || echo false)"
item FEED_PIN_MATCHES_BUILD "$(test -n "$build" && test "$feed_pin" = "$build" && echo true || echo false)"
item FEED_VERIFIED_BUILD_MATCH "$(test -n "$build" && test "$verified" = "$build" && echo true || echo false)"
ready=false
if ubus list 2>/dev/null | grep -qx 'veci.apps'; then
    status="$(ubus call veci.apps status '{}' 2>/dev/null || true)"
    feed_ready="$(printf '%s' "$status" | jsonfilter -e '@.feed_ready' 2>/dev/null || true)"
    feed_verified="$(printf '%s' "$status" | jsonfilter -e '@.feed_verified' 2>/dev/null || true)"
    item SIGNED_FEED_PROVIDER_READY "$(test "$feed_ready" = true && echo true || echo false)"
    item SIGNED_FEED_PROVIDER_VERIFIED "$(test "$feed_verified" = true && echo true || echo false)"
    if [ "$feed_ready" = true ] && [ "$feed_verified" = true ]; then ready=true; fi
else
    item SIGNED_FEED_PROVIDER_READY false
    item SIGNED_FEED_PROVIDER_VERIFIED false
fi
if [ "$feed_on" = 1 ] && [ -n "$build" ] && [ "$feed_pin" = "$build" ] &&
   [ "$verified" = "$build" ] && [ "$repo_ok" = true ] && [ "$ready" = true ] &&
   [ "$overlay" -ge 2048 ] && [ "$mem" -ge 8192 ] &&
   command -v apk >/dev/null 2>&1; then
    item APPS_INSTALL_GATE SIGNED_FEED_READY
else
    item APPS_INSTALL_GATE BLOCKED
fi
# This is diagnostic only; it NEVER installs packages or changes network state.
item ACTION READ_ONLY_NO_ROUTER_CONFIG_CHANGES
