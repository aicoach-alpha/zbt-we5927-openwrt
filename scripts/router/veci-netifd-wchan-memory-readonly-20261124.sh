#!/bin/sh
# Minimal read-only snapshot for low-memory ZBT-WE5927; no UCI/restarts.
set -u
LC_ALL=C; export LC_ALL
board="$(cat /tmp/sysinfo/board_name 2>/dev/null || :)"
if [ "$board" != zbtlink,zbt-we5927 ]; then echo TRIAGE_ABORT=wrong_board; exit 3; fi
echo TRIAGE_START=VECI_NETIFD_WCHAN_MEMORY_20261124
printf 'TIME_UTC=%s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
awk '$1=="MemAvailable:" || $1=="MemFree:" || $1=="SwapFree:" {print "MEM_" $1 "_KIB=" $2}' /proc/meminfo
for pid in 1366 16862 16854; do
  [ -r "/proc/$pid/status" ] || { printf 'PROC_%s=absent\n' "$pid"; continue; }
  awk -v pid="$pid" '$1=="Name:" || $1=="State:" || $1=="PPid:" || $1=="VmRSS:" || $1=="Threads:" {print "PROC_" pid "_" $1 "=" $2}' "/proc/$pid/status"
  chan="$(cat "/proc/$pid/wchan" 2>/dev/null || echo unavailable)"
  case "$chan" in ''|*[!a-zA-Z0-9_.-]*) chan=unavailable;; esac
  printf 'PROC_%s_WCHAN=%s\n' "$pid" "$chan"
done
if [ -r /proc/pressure/memory ]; then
  echo '===MEMORY_PRESSURE==='
  sed -n '1,2p' /proc/pressure/memory
fi
echo '===LTE_CONTROL_STATE==='
lte="$(ubus -S -t 2 call network.interface.lte status '{}' 2>/dev/null || :)"
if [ -n "$lte" ]; then
  for field in up pending available; do
    v="$(printf '%s' "$lte" | jsonfilter -e "@.$field" 2>/dev/null || :)"
    case "$v" in true|false) :;; *) v=unknown;; esac
    printf 'LTE_%s=%s\n' "$field" "$v"
  done
else
  echo LTE_STATUS=unavailable
fi
if ip -4 addr show dev usb0 2>/dev/null | grep -q ' inet '; then echo USB0_IPV4=assigned; else echo USB0_IPV4=absent; fi
if ip -4 route show default 2>/dev/null | grep -q ' dev usb0 '; then echo USB0_DEFAULT_ROUTE=present; else echo USB0_DEFAULT_ROUTE=absent; fi
printf 'UDHCPC_COUNT=%s\n' "$(pidof udhcpc 2>/dev/null | wc -w | tr -d ' ')"
echo '===KERNEL_BLOCK_OR_OOM_SIGNALS_FILTERED==='
dmesg 2>/dev/null | grep -Ei 'out of memory|oom-killer|memory allocation failure|blocked for more than|hung task|soft lockup|watchdog:.*lockup' | tail -n 12 || :
echo TRIAGE_END=OK
