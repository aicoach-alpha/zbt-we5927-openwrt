#!/bin/sh
# Read-only, low-cost router snapshot. Execute via SSH stdin from a wired PC.
# NO configuration changes, AT commands, radio reloads, reboot or disk writes.
# Emits only a bounded allowlisted set of counters, not IP/SSID/IMEI/APN/SMS.
PATH=/usr/sbin:/usr/bin:/sbin:/bin
export PATH
export LC_ALL=C
num(){ case "$1" in ''|*[!0-9]*) printf '?';; *) printf '%s' "$1";; esac; }
yesno(){ if "$@" >/dev/null 2>&1; then echo 1; else echo 0; fi; }
sysval(){ if [ -r "$1" ]; then head -n1 "$1" 2>/dev/null | tr -cd '[:alnum:]_'; else printf '?'; fi; }
countlog(){
  if command -v logread >/dev/null 2>&1; then
    # Log ring may wrap: counts are diagnostic, NOT cumulative counters.
    logread 2>/dev/null | grep -Eic "$1" || :
  else printf '?'; fi
}
printf 'epoch_s=%s\n' "$(date +%s)"
printf 'uptime_s=%s\n' "$(awk '{printf "%.0f", $1}' /proc/uptime 2>/dev/null)"
printf 'usb0_carrier=%s\n' "$(sysval /sys/class/net/usb0/carrier)"
printf 'usb0_operstate=%s\n' "$(sysval /sys/class/net/usb0/operstate)"
printf 'usb0_ipv4=%s\n' "$(yesno sh -c "ip -4 -o addr show dev usb0 2>/dev/null | grep -q ' inet '")"
printf 'lte_default_route=%s\n' "$(yesno sh -c "ip -4 route show default dev usb0 2>/dev/null | grep -q '^default '")"
gateway="$(ip -4 route show default dev usb0 2>/dev/null | awk '/^default via /{print $3; exit}')"
if [ -n "$gateway" ]; then
  gateway_ok="$(yesno ping -I usb0 -c 1 -W 1 "$gateway")"
else gateway_ok='?'; fi
printf 'gateway_ping_ok=%s\n' "$gateway_ok"
printf 'public_ping_ok=%s\n' "$(if ping -I usb0 -c 1 -W 1 1.1.1.1 >/dev/null 2>&1 ||
 ping -I usb0 -c 1 -W 1 8.8.8.8 >/dev/null 2>&1; then echo 1; else echo 0; fi)"
for x in rx_errors tx_errors rx_dropped tx_dropped; do
  file="/sys/class/net/usb0/statistics/$x"
  if [ -r "$file" ]; then printf 'usb0_%s=%s\n' "$x" "$(num "$(cat "$file")")"
  else printf 'usb0_%s=?\n' "$x"; fi
done
# ubus 2 sec timeout. Never print the raw status JSON, which may contain IPs.
if command -v ubus >/dev/null 2>&1; then
  ubus -t 2 list 'hostapd.*' >/dev/null 2>&1
  printf 'ubus_responsive=%s\n' "$([ "$?" -eq 0 ] && echo 1 || echo 0)"
else printf 'ubus_responsive=?\n'; fi
printf 'mt76_mcu_timeout_log_count=%s\n' "$(countlog 'MCU message.*timed out')"
printf 'dhcp_release_log_count=%s\n' "$(countlog 'udhcpc.*(releas|deconfig|lease lost)')"
printf 'dhcp_renew_log_count=%s\n' "$(countlog 'udhcpc.*(renew|lease of .*obtained)')"
printf 'usb_disconnect_log_count=%s\n' "$(countlog 'usb .*disconnect')"
printf 'wifi_kernel_stall_log_count=%s\n' "$(countlog '(RX PSE busy stuck|Beacon stuck|TX DMA busy stuck)')"
printf 'mem_available_kib=%s\n' "$(awk '/^MemAvailable:/{print $2;f=1;exit}END{if(!f)print "?"}' /proc/meminfo 2>/dev/null)"
