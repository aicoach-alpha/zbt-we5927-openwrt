#!/bin/sh
# VeCI WE5927 hardware snapshot, READ ONLY. No credentials/identifiers in output.
set -u
LC_ALL=C; export LC_ALL
board="$(cat /tmp/sysinfo/board_name 2>/dev/null || :)"
if [ "$board" != "zbtlink,zbt-we5927" ]; then
  echo "AUDIT_ABORT=wrong_board"; exit 3
fi
safe_int() { case "$1" in ''|*[!0-9]*) printf 'unknown';; *) printf '%s' "$1";; esac; }
get() { uci -q get "$1" 2>/dev/null || :; }
flag() {
  case "$1" in 1|true|on|yes) echo enabled;; 0|false|off|no) echo disabled;; '') echo unset;; *) echo invalid;; esac
}
present() { if [ -e "$1" ]; then echo present; else echo absent; fi; }
cmd() { if command -v "$1" >/dev/null 2>&1; then echo installed; else echo missing; fi; }
printf '=== VECI-ROUTER-READONLY-AUDIT v20261124 ===\n'
printf 'AUDIT_TIME_UTC=%s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ' 2>/dev/null || echo unknown)"
printf 'BOARD=%s\n' "$board"
. /etc/openwrt_release 2>/dev/null || :
printf 'OPENWRT_VERSION=%s\n' "$DISTRIB_RELEASE"
printf 'KERNEL=%s\n' "$(uname -r)"
printf 'UPTIME_SECONDS=%s\n' "$(awk '{print int($1)}' /proc/uptime 2>/dev/null)"
printf 'CPU_LOAD=%s\n' "$(cut -d' ' -f1-3 /proc/loadavg)"
printf 'MEM_AVAILABLE_KIB=%s\n' "$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo)"
printf 'FLASH_OVERLAY_KIB=%s\n' "$(df -Pk /overlay 2>/dev/null | awk 'NR==2 {print $4}')"
printf 'MTD_FIRMWARE_BYTES_HEX=%s\n' "$(awk '$0 ~ /"firmware"/ {print $2;exit}' /proc/mtd)"
printf 'ROOT_PASSWORD_CONFIGURED=%s\n' "$(awk -F: '$1=="root" {print $2=="*"||$2=="!"||$2=="" ? "no":"yes"}' /etc/shadow 2>/dev/null)"
printf 'ROOT_SSH_SERVICE=%s\n' "$(if pidof dropbear >/dev/null 2>&1; then echo running; else echo missing; fi)"
printf 'HTTPS_SERVICE=%s\n' "$(if pidof uhttpd >/dev/null 2>&1; then echo running; else echo missing; fi)"
printf 'SYSTEM_CLOCK_UTC=%s\n' "$(date -u '+%Y-%m-%d %H:%M:%S' 2>/dev/null)"
printf 'NETIFD_PROCESS_COUNT=%s\n' "$(pidof netifd 2>/dev/null | wc -w)"
printf 'LAN_IP=%s\n' "$(get network.lan.ipaddr)"
printf 'LAN_IFACE_UP=%s\n' "$(if ip link show br-lan 2>/dev/null | grep -q 'state UP'; then echo yes; else echo unverified; fi)"
printf 'DEFAULT_ROUTE_USB0=%s\n' "$(if ip -4 route show default 2>/dev/null | grep -q ' dev usb0 '; then echo present; else echo absent; fi)"
printf 'USB0_INTERFACE=%s\n' "$(present /sys/class/net/usb0)"
printf 'USB0_IPV4=%s\n' "$(if ip -4 addr show dev usb0 2>/dev/null | grep -q 'inet '; then echo assigned; else echo unassigned; fi)"
printf 'USB0_RX_BYTES=%s\n' "$(safe_int "$(cat /sys/class/net/usb0/statistics/rx_bytes 2>/dev/null)")"
printf 'USB0_TX_BYTES=%s\n' "$(safe_int "$(cat /sys/class/net/usb0/statistics/tx_bytes 2>/dev/null)")"
printf 'LAN_RX_BYTES=%s\n' "$(safe_int "$(cat /sys/class/net/br-lan/statistics/rx_bytes 2>/dev/null)")"
printf 'LAN_TX_BYTES=%s\n' "$(safe_int "$(cat /sys/class/net/br-lan/statistics/tx_bytes 2>/dev/null)")"
printf 'LAN_DHCP_PROCESS=%s\n' "$(if pidof dnsmasq >/dev/null 2>&1; then echo running; else echo stopped; fi)"
printf 'FIREWALL4_EXEC=%s\n' "$(cmd fw4)"
printf 'FIREWALL_WAN_MASQ=%s\n' "$(flag "$(get firewall.@zone[1].masq)")"
printf 'NTP_SERVICE=%s\n' "$(if pidof sysntpd >/dev/null 2>&1; then echo running; else echo stopped_or_unknown; fi)"
printf 'WIRELESS_CONFIG=%s\n' "$(present /etc/config/wireless)"
printf 'WIFI_RADIO_SECTION=%s\n' "$(get wireless.radio0)"
printf 'WIFI_RADIO_BAND=%s\n' "$(get wireless.radio0.band)"
printf 'WIFI_RADIO_DISABLED=%s\n' "$(flag "$(get wireless.radio0.disabled)")"
printf 'WIFI_AP_SECTION=%s\n' "$(get wireless.default_radio0)"
printf 'WIFI_AP_DEVICE=%s\n' "$(get wireless.default_radio0.device)"
printf 'WIFI_AP_MODE=%s\n' "$(get wireless.default_radio0.mode)"
printf 'WIFI_AP_DISABLED=%s\n' "$(flag "$(get wireless.default_radio0.disabled)")"
printf 'WIFI_AP_NETWORK=%s\n' "$(get wireless.default_radio0.network)"
printf 'WIFI_AP_SECURITY=%s\n' "$(get wireless.default_radio0.encryption)"
apkey="$(get wireless.default_radio0.key)"
if [ -n "$apkey" ]; then echo 'WIFI_AP_PSK_CONFIGURED=yes'; else echo 'WIFI_AP_PSK_CONFIGURED=no'; fi
unset apkey
printf 'WIFI_PHY0=%s\n' "$(present /sys/class/ieee80211/phy0)"
printf 'WIFI_MT7603E=%s\n' "$(if grep -q '^mt7603e ' /proc/modules 2>/dev/null; then echo loaded; else echo not_loaded; fi)"
printf 'WIFI_WPAD=%s\n' "$(cmd wpad)"
printf 'WIFI_HOSTAPD_PROCESS=%s\n' "$(if pidof hostapd >/dev/null 2>&1 || pidof wpad >/dev/null 2>&1; then echo present; else echo absent; fi)"
printf 'WIFI_KERNEL_DEVICE_COUNT=%s\n' "$(find /sys/class/net -maxdepth 2 -name phy80211 2>/dev/null | wc -l)"
wireless="$(ubus -S -t 3 call network.wireless status '{}' 2>/dev/null || :)"
if [ -n "$wireless" ] && command -v jsonfilter >/dev/null 2>&1; then
  printf 'WIFI_RADIO_RUNTIME_UP=%s\n' "$(printf '%s' "$wireless" | jsonfilter -e '@.radio0.up' 2>/dev/null || echo unknown)"
  iface="$(printf '%s' "$wireless" | jsonfilter -e '@.radio0.interfaces[@.section="default_radio0"].ifname' 2>/dev/null || :)"
  case "$iface" in ''|*[!A-Za-z0-9_.-]*) iface= ;; esac
  if [ -n "$iface" ]; then
    printf 'WIFI_AP_RUNTIME_IFACE=%s\n' "$(if [ -e "/sys/class/net/$iface/phy80211" ]; then echo present; else echo absent; fi)"
    printf 'WIFI_HOSTAPD_RPC=%s\n' "$(if ubus -S -t 3 list "hostapd.$iface" 2>/dev/null | grep -Fxq "hostapd.$iface"; then echo registered; else echo absent; fi)"
    printf 'WIFI_HOSTAPD_STATE=%s\n' "$(ubus -S -t 3 call "hostapd.$iface" get_status '{}' 2>/dev/null | jsonfilter -e '@.status' 2>/dev/null || echo unavailable)"
  fi
else
  echo 'WIFI_RADIO_RUNTIME_UP=unknown'
fi
printf 'WIFI_FIRST_FAULT=%s\n' "$(if [ -f /tmp/veci-wifi-first-fault.txt ]; then grep -m1 '^reason=' /tmp/veci-wifi-first-fault.txt | cut -d= -f2; else echo no_first_fault_record; fi)"
if dmesg 2>/dev/null | grep -Eiq 'mt76.*(mcu.*timeout|reset failed|timed out)|mt7603.*(timeout|failed)'; then
  echo 'WIFI_KERNEL_MCU_FAULT_EVIDENCE=present'
else
  echo 'WIFI_KERNEL_MCU_FAULT_EVIDENCE=not_observed'
fi
printf 'SMS_RPC_REGISTERED=%s\n' "$(if ubus -S -t 3 list veci.sms 2>/dev/null | grep -Fxq veci.sms; then echo yes; else echo no; fi)"
printf 'SMS_CONFIG_ENABLED=%s\n' "$(flag "$(get veci_sms.main.enabled)")"
printf 'SIM_SELECTOR_CONFIG=%s\n' "$(get veci_lte.main.sim_slot)"
printf 'TRUST_ANCHOR=%s\n' "$(present /etc/opkg/keys/1d8759d36251c36c)"
if command -v curl >/dev/null 2>&1 && [ -d /sys/class/net/usb0 ]; then
  code="$(curl --disable --ipv4 --noproxy '*' --interface 'if!usb0' --silent --output /dev/null --connect-timeout 3 --max-time 7 --write-out '%{http_code}' 'https://www.cloudflare.com/cdn-cgi/trace' 2>/dev/null || :)"
  if [ "$code" = 200 ]; then echo 'LTE_BOUND_HTTPS=PASS_HTTP_200'; else echo 'LTE_BOUND_HTTPS=NOT_VERIFIED'; fi
else
  echo 'LTE_BOUND_HTTPS=NOT_VERIFIED'
fi
echo 'WIFI_BEACON_AND_CLIENT_UAT=NOT_TESTED_FROM_THIS_SNAPSHOT'
echo 'SMS_SEND_RECEIVE_UAT=NOT_TESTED_FROM_THIS_SNAPSHOT'
echo 'STABILITY_72H=NOT_PROVEN_FROM_SNAPSHOT'
echo 'AUDIT_END=OK'
