#!/bin/sh
# Exact board, read-only physical modem USB/network/netifd presence.
set -u
board="$(cat /tmp/sysinfo/board_name 2>/dev/null || :)"
[ "$board" = zbtlink,zbt-we5927 ] || { echo TRIAGE_ABORT=WRONG_BOARD; exit 3; }
echo TRIAGE_START=VECI_USB_MODEM_LINK_READONLY
echo ===DEVICE_PRESENT===
if [ -d /sys/class/net/usb0 ]; then
 echo USB0_PRESENT=yes
 echo USB0_OPERSTATE="$(cat /sys/class/net/usb0/operstate 2>/dev/null || echo unknown)"
 echo USB0_CARRIER="$(cat /sys/class/net/usb0/carrier 2>/dev/null || echo unknown)"
else echo USB0_PRESENT=no; fi
found=no
for d in /sys/bus/usb/devices/*; do
 [ -r "$d/idVendor" ] || continue
 if [ "$(cat "$d/idVendor" 2>/dev/null)" = 05c6 ] && [ "$(cat "$d/idProduct" 2>/dev/null)" = 902e ]; then found=yes; fi
done
echo QUALCOMM_05C6_902E_PRESENT=$found
echo ===NETWORK_IP_ROUTE===
if ip -4 addr show dev usb0 2>/dev/null | grep -q ' inet '; then echo USB0_IPV4=assigned; else echo USB0_IPV4=absent; fi
if ip -4 route show default 2>/dev/null | grep -q ' dev usb0 '; then echo LTE_ROUTE=present; else echo LTE_ROUTE=absent; fi
echo ===LTE_CONTROL===
status="$(ubus -S -t 3 call network.interface.lte status '{}' 2>/dev/null || :)"
if [ -n "$status" ]; then
 for k in up pending available device; do
  v="$(printf '%s' "$status" | jsonfilter -e "@.$k" 2>/dev/null || :)"
  case "$v" in true|false|usb0) :;; *) v=unknown;; esac
  echo LTE_$k=$v
 done
else echo LTE_UBUS=unavailable; fi
echo ===NETIFD_STATE_AND_DHCP===
for pid in 1366 16862; do
 if [ -r "/proc/$pid/status" ]; then
  v="$(awk '$1=="State:" {print $2}' "/proc/$pid/status")"
  echo NETIFD_${pid}_STATE=$v
 else echo NETIFD_${pid}=absent; fi
done
echo UDHCPC_COUNT="$(pidof udhcpc 2>/dev/null | wc -w | tr -d ' ')"
echo MEM_AVAILABLE_KIB="$(awk '$1=="MemAvailable:" {print $2}' /proc/meminfo)"
echo TRIAGE_END=OK
