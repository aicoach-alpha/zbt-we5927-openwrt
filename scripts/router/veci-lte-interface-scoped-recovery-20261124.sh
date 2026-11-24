#!/bin/sh
# Owner WE5927: scoped LTE interface restart only, retain wired LAN.
# Guard live board, procd ownership, healthy canonical netifd and memory.
set -u
stop() { printf 'REPAIR_STOP=%s\n' "$1"; exit 3; }
board="$(cat /tmp/sysinfo/board_name 2>/dev/null || :)"
[ "$board" = zbtlink,zbt-we5927 ] || stop wrong_board
[ "$(id -u)" = 0 ] || stop not_root
[ -d /sys/class/net/br-lan ] || stop lan_bridge_missing
ip -4 addr show dev br-lan 2>/dev/null | grep -q ' inet 192.168.1.1/' || stop lan_ip_not_as_expected
[ -d /sys/class/net/usb0 ] || stop modem_usb0_missing
owner="$(ubus -S -t 5 call service list '{"name":"network","verbose":true}' 2>/dev/null | jsonfilter -e '@.network.instances[*].pid' 2>/dev/null || :)"
[ "$owner" = 1366 ] || stop canonical_procd_network_pid_changed
[ -r /proc/1366/status ] || stop netifd_missing
[ "$(awk '$1=="Name:" {print $2}' /proc/1366/status)" = netifd ] || stop netifd_name_wrong
[ "$(awk '$1=="State:" {print $2}' /proc/1366/status)" = S ] || stop canonical_netifd_unhealthy
mem="$(awk '$1=="MemAvailable:" {print $2}' /proc/meminfo 2>/dev/null || :)"
case "$mem" in ''|*[!0-9]*) stop memory_unknown;; esac
[ "$mem" -ge 10000 ] || stop memory_too_low
ubus -S list network.interface.lte 2>/dev/null | grep -qx 'network.interface.lte' || stop lte_ubus_object_missing
echo 'PRECHECK=PASS_LAN_SAFE_PROCD_VERIFIED'
if curl --disable --ipv4 --insecure --noproxy '*' --interface 'if!usb0' --connect-timeout 2 --max-time 5 -s -o /dev/null https://1.1.1.1/ 2>/dev/null; then
  if curl --disable --ipv4 --noproxy '*' --interface 'if!usb0' --connect-timeout 2 --max-time 5 -s -o /dev/null https://www.cloudflare.com/cdn-cgi/trace 2>/dev/null; then
    echo REPAIR_SKIPPED=PUBLIC_IP_AND_DNS_ALREADY_WORK
    exit 0
  fi
  echo REPAIR_REASON=PUBLIC_IP_WORKS_BUT_DNS_FAILS
fi
# The OpenWrt per-interface method is explicitly scoped to interface lte.
# Do NOT use /sbin/ifup, which can invoke `network reload`.
[ -d /sys/class/net/br-lan ] || stop lan_disappeared_before_restart
[ "$(awk '$1=="State:" {print $2}' /proc/1366/status 2>/dev/null || :)" = S ] || stop netifd_state_changed_before_restart
echo 'LTE_INTERFACE_RESTART=REQUESTED'
ubus -S -t 8 call network.interface.lte restart '{}' >/dev/null 2>&1 || stop lte_interface_restart_rejected
echo 'LTE_INTERFACE_RESTART=ACCEPTED'
sleep 12
[ -d /sys/class/net/br-lan ] || stop lan_missing_after_restart
echo 'LAN_BRIDGE=present'
if ip -4 addr show dev usb0 2>/dev/null | grep -q ' inet '; then echo 'USB0_IPV4=assigned'; else echo 'USB0_IPV4=absent'; fi
if ip -4 route show default 2>/dev/null | grep -q ' dev usb0 '; then echo 'LTE_DEFAULT_ROUTE=present'; else echo 'LTE_DEFAULT_ROUTE=absent'; fi
curl --disable --ipv4 --insecure --noproxy '*' --interface 'if!usb0' --connect-timeout 3 --max-time 8 -s -o /dev/null -w 'PUBLIC_IP_HTTPS_CODE=%{http_code}\n' https://1.1.1.1/
public_rc=$?
echo PUBLIC_IP_HTTPS_EXIT=$public_rc
if [ "$public_rc" -eq 0 ]; then
  curl --disable --ipv4 --noproxy '*' --interface 'if!usb0' --connect-timeout 3 --max-time 8 -s -o /dev/null -w 'PUBLIC_DNS_HTTPS_CODE=%{http_code}\n' https://www.cloudflare.com/cdn-cgi/trace
  dns_rc=$?
  echo PUBLIC_DNS_HTTPS_EXIT=$dns_rc
  if [ "$dns_rc" -eq 0 ]; then echo 'REPAIR_RESULT=LTE_PUBLIC_IP_AND_DNS_OK'; else echo 'REPAIR_RESULT=IP_EGRESS_OK_DNS_STILL_FAILS'; fi
else
  echo 'REPAIR_RESULT=LTE_PUBLIC_IP_STILL_FAILS_NO_GLOBAL_RESTART'
fi
echo 'REPAIR_END=OK'
