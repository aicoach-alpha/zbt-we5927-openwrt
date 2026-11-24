#!/bin/sh
# ZBT-WE5927 only: one guarded LTE-only down/up recovery.
# Never reload LAN/network, change config, reset USB, terminate netifd, reboot or flash.
set -u
stop() { echo "LTE_REPAIR_STOP=$1"; exit 3; }
board="$(cat /tmp/sysinfo/board_name 2>/dev/null || :)"
[ "$board" = zbtlink,zbt-we5927 ] || stop wrong_board
[ "$(id -u)" = 0 ] || stop not_root
[ -d /sys/class/net/br-lan ] && [ -d /sys/class/net/usb0 ] || stop lan_or_usb_missing
ip -4 addr show dev br-lan 2>/dev/null | grep -q ' inet 192.168.1.1/' || stop lan_address_changed
canonical="$(ubus -S -t 4 call service list '{"name":"network","verbose":true}' 2>/dev/null | jsonfilter -e '@.network.instances[*].pid' 2>/dev/null || :)"
[ "$canonical" = 1366 ] || stop procd_network_owner_changed
[ "$(awk '$1=="State:" {print $2}' /proc/1366/status 2>/dev/null)" = S ] || stop canonical_netifd_blocked
mem="$(awk '$1=="MemAvailable:" {print $2}' /proc/meminfo)"
case "$mem" in ''|*[!0-9]*) stop unknown_memory;; esac
[ "$mem" -ge 10000 ] || stop low_memory
ubus -S list network.interface.lte 2>/dev/null | grep -qx 'network.interface.lte' || stop lte_ubus_missing
# Do not interrupt an uplink that has recovered since the owner's last check.
if curl --disable --ipv4 --insecure --noproxy '*' --interface 'if!usb0' --connect-timeout 2 --max-time 5 -s -o /dev/null https://1.1.1.1/ 2>/dev/null && curl --disable --ipv4 --noproxy '*' --interface 'if!usb0' --connect-timeout 2 --max-time 5 -s -o /dev/null https://www.cloudflare.com/cdn-cgi/trace 2>/dev/null; then
  echo 'REPAIR_SKIPPED=EXTERNAL_IP_AND_DNS_ALREADY_PASS'
  exit 0
fi
echo 'ACTION=LTE_ONLY_DOWN_UP_ONCE'
echo '===LTE_STATUS_BEFORE==='
ubus -S -t 4 call network.interface.lte status '{}' 2>&1 || echo 'LTE_STATUS_BEFORE=UNAVAILABLE'
echo '===LTE_ONLY_DOWN==='
ubus -S -t 8 call network.interface.lte down '{}'
rc=$?
echo "LTE_DOWN_EXIT=$rc"
[ "$rc" = 0 ] || { echo 'REPAIR_STOP=lte_down_failed'; exit 4; }
# netifd down may be asynchronous, allow teardown to finish before sending up.
sleep 5
[ -d /sys/class/net/br-lan ] || { echo 'REPAIR_STOP=lan_bridge_missing'; exit 5; }
[ "$(awk '$1=="State:" {print $2}' /proc/1366/status 2>/dev/null)" = S ] || stop netifd_blocked_after_down
echo '===LTE_ONLY_UP==='
ubus -S -t 8 call network.interface.lte up '{}'
rc=$?
echo "LTE_UP_EXIT=$rc"
[ "$rc" = 0 ] || { echo 'REPAIR_STOP=lte_up_failed'; exit 6; }
sleep 12
echo '===LAN_PRESERVATION==='
if ip -4 addr show dev br-lan 2>/dev/null | grep -q ' inet 192.168.1.1/'; then echo LAN=192.168.1.1_PRESENT; else echo LAN=NOT_VERIFIED; fi
echo '===LTE_ADDRESS_AND_ROUTE==='
ip -4 addr show dev usb0 2>/dev/null
ip -4 route show default 2>/dev/null
echo '===IP_ONLY_HTTPS==='
curl --disable --ipv4 --insecure --noproxy '*' --interface 'if!usb0' --connect-timeout 3 --max-time 8 -s -o /dev/null -w 'PUBLIC_IP_HTTP_CODE=%{http_code}\n' https://1.1.1.1/
echo "PUBLIC_IP_HTTPS_EXIT=$?"
echo '===DNS_HTTPS==='
curl --disable --ipv4 --noproxy '*' --interface 'if!usb0' --connect-timeout 3 --max-time 8 -s -o /dev/null -w 'PUBLIC_DNS_HTTP_CODE=%{http_code}\n' https://www.cloudflare.com/cdn-cgi/trace
echo "PUBLIC_DNS_HTTPS_EXIT=$?"
echo 'REPAIR_END=ONE_LTE_DOWN_UP_ATTEMPT_COMPLETE'
