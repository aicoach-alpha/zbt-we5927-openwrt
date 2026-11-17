#!/bin/sh
# WE5927 read-only Wi-Fi runtime snapshot; no iw/radio reload/UCI write/modem AT.
set -u
title() { printf '\n===== %s =====\n' "$1"; }
call_json() { ubus -S -t 3 call "$1" "$2" '{}' 2>/dev/null || true; }
print_field() {
  value="$(printf '%s\n' "$1" | jsonfilter -e "$2" 2>/dev/null || true)"
  [ -n "$value" ] || value=unknown
  printf '%s=%s\n' "$3" "$value"
}
title BOARD
board="$(call_json system board)"
print_field "$board" '@.model' model
print_field "$board" '@.release.version' openwrt
print_field "$board" '@.kernel' kernel
title RADIO_CONFIG
value="$(uci -q get wireless.radio0.disabled 2>/dev/null || true)"
printf 'radio0.disabled=%s\n' "${value:-unset}"
# Never print wireless passwords or SSIDs.
uci -q show wireless 2>/dev/null | grep -E '^wireless\.[A-Za-z0-9_]+\.(mode|disabled|device)=' || true
title RADIO_RUNTIME
wireless="$(call_json network.wireless status)"
print_field "$wireless" '@.radio0.up' radio0.up
print_field "$wireless" '@.radio0.pending' radio0.pending
print_field "$wireless" '@.radio0.disabled' radio0.disabled
title HOSTAPD_RPC
objects="$(ubus -S -t 3 list 'hostapd.*' 2>/dev/null || true)"
if [ -z "$objects" ]; then
  echo 'hostapd_rpc=none_or_timeout'
else
  printf '%s\n' "$objects" | while IFS= read -r object; do
    case "$object" in hostapd.*) : ;; *) continue ;; esac
    response="$(call_json "$object" get_status)"
    status="$(printf '%s\n' "$response" | jsonfilter -e '@.status' 2>/dev/null || true)"
    printf '%s.status=%s\n' "$object" "${status:-unknown}"
  done
fi
title WIFI_KERNEL_NETDEVS
found=0
for dev in /sys/class/net/*; do
  [ -e "$dev/phy80211" ] || continue
  printf 'wifi_netdev=%s\n' "${dev##*/}"
  found=1
done
[ "$found" -eq 1 ] || echo 'wifi_netdev=none'
title DRIVER_MODULES
for mod in mt7603e mt76 mac80211 cfg80211; do
  if [ -d "/sys/module/$mod" ]; then
    printf '%s=loaded\n' "$mod"
  else
    printf '%s=not_loaded\n' "$mod"
  fi
done
title GUARDIAN
if [ -r /tmp/veci-wifi-performance.state ]; then
  cat /tmp/veci-wifi-performance.state
else
  echo 'guardian_state=missing'
fi
title OPTIONAL_IW
if command -v iw >/dev/null 2>&1; then echo 'iw=installed (not invoked)'; else echo 'iw=not_installed'; fi
title DONE
