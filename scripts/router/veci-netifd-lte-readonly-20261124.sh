#!/bin/sh
# Read-only WE5927 netifd/usb0 triage. No secrets, no state changes.
set -u
LC_ALL=C; export LC_ALL
board="$(cat /tmp/sysinfo/board_name 2>/dev/null || :)"
if [ "$board" != 'zbtlink,zbt-we5927' ]; then
  echo TRIAGE_ABORT=WRONG_BOARD
  exit 3
fi
report() { printf '%s=%s\n' "$1" "$2"; }
echo TRIAGE_START=VECI_NETIFD_LTE_READONLY_20261124
report BOARD "$board"
report CLOCK_UTC "$(date -u '+%Y-%m-%dT%H:%M:%SZ' 2>/dev/null || echo unknown)"
report UPTIME_SECONDS "$(awk '{printf "%.0f",$1}' /proc/uptime 2>/dev/null)"
report MEM_AVAILABLE_KIB "$(awk '/^MemAvailable:/ {print $2}' /proc/meminfo 2>/dev/null)"
echo ===NETIFD_PROCESS_IDENTITIES===
count=0
for pid in $(pidof netifd 2>/dev/null || :); do
  case "$pid" in ''|*[!0-9]*) continue;; esac
  [ -r "/proc/$pid/status" ] || continue
  name="$(awk '$1=="Name:" {print $2}' "/proc/$pid/status" 2>/dev/null)"
  [ "$name" = netifd ] || continue
  count=$((count+1))
  parent="$(awk '$1=="PPid:" {print $2}' "/proc/$pid/status" 2>/dev/null)"
  state="$(awk '$1=="State:" {print $2}' "/proc/$pid/status" 2>/dev/null)"
  exe="$(readlink "/proc/$pid/exe" 2>/dev/null || :)"
  case "$exe" in '/sbin/netifd'|'/usr/sbin/netifd') :;; *) exe=other_or_unavailable;; esac
  report NETIFD_PID "$pid"
  report NETIFD_PPID "$parent"
  report NETIFD_STATE "$state"
  report NETIFD_EXE "$exe"
done
report NETIFD_PROCESS_COUNT "$count"
echo ===UBUS_OBJECT_HEALTH===
for object in network network.interface network.interface.lte network.interface.wan network.device network.wireless; do
  if ubus -S -t 3 list "$object" 2>/dev/null | grep -Fxq "$object"; then
    report UBUS_OBJECT "$object:present"
  else
    report UBUS_OBJECT "$object:absent"
  fi
done
echo ===LTE_INTERFACE_UBUS===
lte="$(ubus -S -t 3 call network.interface.lte status '{}' 2>/dev/null)" || lte=
if [ -n "$lte" ] && command -v jsonfilter >/dev/null 2>&1; then
  for field in up pending available autostart proto device; do
    value="$(printf '%s' "$lte" | jsonfilter -e "@.$field" 2>/dev/null || :)"
    case "$value" in ''|*[!a-zA-Z0-9_.:/-]*) value=unknown;; esac
    upper="$(printf '%s' "$field" | tr 'a-z' 'A-Z')"
    report "LTE_$upper" "$value"
  done
else
  echo LTE_UBUS_STATUS=unavailable
fi
echo ===INTERFACE_AND_DEFAULT_ROUTE===
if [ -d /sys/class/net/usb0 ]; then
  echo USB0=present
  report USB0_OPERSTATE "$(cat /sys/class/net/usb0/operstate 2>/dev/null || echo unknown)"
  report USB0_CARRIER "$(cat /sys/class/net/usb0/carrier 2>/dev/null || echo unknown)"
  if ip -4 addr show dev usb0 2>/dev/null | grep -q ' inet '; then
    echo USB0_IPV4=assigned
  else
    echo USB0_IPV4=unassigned
  fi
else
  echo USB0=absent
fi
if ip -4 route show default 2>/dev/null | grep -q ' dev usb0 '; then
  echo DEFAULT_ROUTE_USB0=present
else
  echo DEFAULT_ROUTE_USB0=absent
fi
if [ -d /sys/class/net/br-lan ]; then echo LAN_BRIDGE=present; else echo LAN_BRIDGE=absent; fi
echo ===DHCP_CLIENTS===
report UDHCPC_PROCESS_COUNT "$(pidof udhcpc 2>/dev/null | wc -w | tr -d ' ')"
echo ===RECENT_PERMISSION_DENIAL_COUNTS===
report NOTIFY_PROTO_PERMISSION_DENIED_COUNT "$(logread 2>/dev/null | grep -F 'network.interface notify_proto' | grep -F 'Permission denied' | wc -l | tr -d ' ')"
echo ===BOUNDED_CELLULAR_EGRESS===
if command -v curl >/dev/null 2>&1 && [ -d /sys/class/net/usb0 ]; then
  code="$(curl --disable --ipv4 --noproxy '*' --interface 'if!usb0' \
    --connect-timeout 3 --max-time 9 --silent --output /dev/null \
    --write-out '%{http_code}' http://1.1.1.1/ 2>/dev/null)" && rc=0 || rc=$?
  report LTE_HTTP_EXIT "$rc"
  case "$code" in ''|*[!0-9]*) code=0;; esac
  report LTE_HTTP_CODE "$code"
  code="$(curl --disable --ipv4 --noproxy '*' --interface 'if!usb0' \
    --connect-timeout 3 --max-time 9 --silent --output /dev/null \
    --write-out '%{http_code}' 'https://www.cloudflare.com/cdn-cgi/trace' 2>/dev/null)" && rc=0 || rc=$?
  report LTE_HTTPS_EXIT "$rc"
  case "$code" in ''|*[!0-9]*) code=0;; esac
  report LTE_HTTPS_CODE "$code"
else
  echo LTE_CURL_TEST=unavailable
fi
echo TRIAGE_END=OK
