#!/bin/sh
# VeCI 2026-11-24 physical ZBT-WE5927 Wi-Fi failure triage: READ ONLY.
# Deliver over SSH stdin (PowerShell here-string, NOT inline ssh command).
# No UCI writes, network reload, driver actions, LTE reset, or credential logs.
set -u
LC_ALL=C; export LC_ALL
board="$(cat /tmp/sysinfo/board_name 2>/dev/null || :)"
if [ "$board" != zbtlink,zbt-we5927 ]; then
  echo 'TRIAGE_ABORT=wrong_board'; exit 3
fi
uci_safely() { uci -q get "$1" 2>/dev/null || :; }
p() { printf '%s=%s\n' "$1" "$2"; }
p TRIAGE_START VECI_WIFI_READONLY_20261124
p BOARD "$board"
p OPENWRT "$(awk -F"'" '/^DISTRIB_RELEASE=/ {print $2}' /etc/openwrt_release 2>/dev/null)"
p KERNEL "$(uname -r)"
p UPTIME_SECONDS "$(awk '{print int($1)}' /proc/uptime)"
p CLOCK_UTC "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
p NETIFD_PROCESS_COUNT "$(pidof netifd 2>/dev/null | wc -w | tr -d ' ')"
p HOSTAPD_PROCESS_COUNT "$(pidof hostapd 2>/dev/null | wc -w | tr -d ' ')"
p RADIO0_DISABLED "$(uci_safely wireless.radio0.disabled)"
p AP_DISABLED "$(uci_safely wireless.default_radio0.disabled)"
p AP_MODE "$(uci_safely wireless.default_radio0.mode)"
p AP_ENCRYPTION "$(uci_safely wireless.default_radio0.encryption)"
p AP_NETWORK "$(uci_safely wireless.default_radio0.network)"
p RADIO0_BAND "$(uci_safely wireless.radio0.band)"
if [ -n "$(uci_safely wireless.default_radio0.key)" ]; then
  echo 'AP_KEY_PRESENT=yes'
else
  echo 'AP_KEY_PRESENT=no'
fi
if [ -d /sys/class/ieee80211/phy0 ]; then
  echo 'PHY0=present'
else
  echo 'PHY0=missing'
fi
echo '===UBUS_RADIO_STATE==='
wireless="$(ubus -S -t 3 call network.wireless status 2>/dev/null)" || wireless=
if [ -n "$wireless" ]; then
  p RADIO0_UP "$(printf '%s' "$wireless" | jsonfilter -e '@.radio0.up' 2>/dev/null || echo unknown)"
  p RADIO0_PENDING "$(printf '%s' "$wireless" | jsonfilter -e '@.radio0.pending' 2>/dev/null || echo unknown)"
  p RADIO0_AUTOSTART "$(printf '%s' "$wireless" | jsonfilter -e '@.radio0.autostart' 2>/dev/null || echo unknown)"
  p RADIO0_RETRY "$(printf '%s' "$wireless" | jsonfilter -e '@.radio0.retry_setup_failed' 2>/dev/null || echo unknown)"
  iface="$(printf '%s' "$wireless" | jsonfilter -e '@.radio0.interfaces[@.section="default_radio0"].ifname' 2>/dev/null || :)"
  case "$iface" in ''|*[!a-zA-Z0-9_.-]*) iface=;; esac
  if [ -n "$iface" ]; then p RADIO0_PRIMARY_IFNAME "$iface"; else echo RADIO0_PRIMARY_IFNAME=none; fi
else
  echo 'RADIO0_STATUS=unavailable'
fi
echo '===KERNEL_INTERFACES==='
ls /sys/class/net 2>/dev/null
echo '===HOSTAPD_OBJECTS==='
ubus -S -t 3 list 2>/dev/null | grep -E '^hostapd([.-]|$)' || echo 'no_hostapd_rpc'
echo '===HOSTAPD_PRIMARY_STATUS==='
for ap in phy0-ap0 wlan0; do
  if ubus -S -t 3 list "hostapd.$ap" 2>/dev/null | grep -Fxq "hostapd.$ap"; then
    p HOSTAPD_OBJECT "$ap"
    status="$(ubus -S -t 3 call "hostapd.$ap" get_status 2>/dev/null | jsonfilter -e '@.status' 2>/dev/null || :)"
    if [ -n "$status" ]; then p HOSTAPD_PRIMARY_STATUS "$status"; else echo HOSTAPD_PRIMARY_STATUS=unknown; fi
  fi
done
echo '===HOSTAPD_NETIFD_ERRORS_FILTERED==='
logread 2>/dev/null |
  grep -Ei 'netifd|hostapd|wpad|mt76|mt7603|wireless|radio0|phy0' |
  grep -Ei 'fail|error|invalid|timeout|setup|teardown|remove|restart|reload|not found|publish|ap.*disabled|ap.*enabled' |
  grep -Eiv 'ssid|psk|password|passphrase|secret|private|key|iccid|imei|imsi|station |sta |eapol|wps|bssid|([[:xdigit:]]{2}:){5}[[:xdigit:]]{2}' |
  tail -n 40 || :
echo '===KERNEL_MT76_ERRORS_FILTERED==='
dmesg 2>/dev/null |
  grep -Ei 'mt76|mt7603|mac80211|ieee80211|phy0' |
  grep -Ei 'fail|error|invalid|timeout|reset|pse|stuck|firmware|setup|remove|probe' |
  grep -Eiv 'ssid|psk|password|key|iccid|imei|imsi|station |bssid|([[:xdigit:]]{2}:){5}[[:xdigit:]]{2}' |
  tail -n 30 || :
echo '===LTE_LAN_POST_ROLLBACK==='
if ip -4 route show default 2>/dev/null | grep -q ' dev usb0 '; then
  echo 'DEFAULT_ROUTE_USB0=present'
else
  echo 'DEFAULT_ROUTE_USB0=absent'
fi
if [ -d /sys/class/net/br-lan ]; then
  echo 'LAN_BRIDGE=present'
else
  echo 'LAN_BRIDGE=absent'
fi
if command -v curl >/dev/null 2>&1; then
  result="$(curl --disable --ipv4 --noproxy '*' --interface 'if!usb0' \
      --connect-timeout 3 --max-time 9 --silent --output /dev/null \
      --write-out '%{http_code}' \
      'https://www.cloudflare.com/cdn-cgi/trace' 2>/dev/null)" && code=0 || code=$?
  if [ "$code" -eq 0 ] && [ "$result" = 200 ]; then
    echo 'LTE_BOUND_HTTPS=PASS_200'
  else
    echo 'LTE_BOUND_HTTPS=NOT_VERIFIED'
  fi
else
  echo 'LTE_BOUND_HTTPS=CURL_UNAVAILABLE'
fi
echo 'TRIAGE_END=OK'
