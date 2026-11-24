#!/bin/sh
# Read-only ownership proof: identify netifd managed by procd vs extra processes.
# Intended only for owner's single physical ZBT-WE5927 over authenticated SSH.
set -u
LC_ALL=C; export LC_ALL
board="$(cat /tmp/sysinfo/board_name 2>/dev/null || :)"
if [ "$board" != 'zbtlink,zbt-we5927' ]; then
  echo 'TRIAGE_ABORT=WRONG_BOARD'; exit 3
fi
report() { printf '%s=%s\n' "$1" "$2"; }
read_proc() {
  pid="$1"
  case "$pid" in ''|*[!0-9]*) return;; esac
  [ -r "/proc/$pid/status" ] || return
  name="$(awk '$1=="Name:" {print $2}' "/proc/$pid/status" 2>/dev/null || :)"
  parent="$(awk '$1=="PPid:" {print $2}' "/proc/$pid/status" 2>/dev/null || :)"
  state="$(awk '$1=="State:" {print $2}' "/proc/$pid/status" 2>/dev/null || :)"
  binary="$(readlink "/proc/$pid/exe" 2>/dev/null || :)"
  case "$binary" in
    /sbin/netifd|/usr/sbin/netifd|/bin/ash|/bin/busybox|/usr/bin/ssh|/usr/sbin/dropbear|/usr/bin/dropbear|/sbin/procd|/bin/sh) :;;
    *) binary=other_or_unknown;;
  esac
  report PROC_PID "$pid"
  report PROC_NAME "${name:-unknown}"
  report PROC_PARENT "${parent:-unknown}"
  report PROC_STATE "${state:-unknown}"
  report PROC_EXE "$binary"
}
echo 'TRIAGE_START=VECI_NETIFD_OWNERSHIP_READONLY'
report BOARD "$board"
report TIME_UTC "$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
echo '===PROCD_MANAGED_NETWORK_PID==='
procd_json="$(ubus -S -t 4 call service list '{"name":"network","verbose":true}' 2>/dev/null || :)"
if [ -n "$procd_json" ]; then
  procd_pids="$(printf '%s\n' "$procd_json" | jsonfilter -e '@.network.instances[*].pid' 2>/dev/null || :)"
  if [ -n "$procd_pids" ]; then
    for pid in $procd_pids; do
      case "$pid" in ''|*[!0-9]*) :;; *) report PROCD_NETWORK_PID "$pid";; esac
    done
  else
    echo 'PROCD_NETWORK_PID=NOT_PARSED'
  fi
else
  echo 'PROCD_NETWORK_PID=SERVICE_NOT_AVAILABLE'
fi
echo '===NETIFD_PROCESS_AND_PARENTS==='
for pid in $(pidof netifd 2>/dev/null || :); do
  case "$pid" in ''|*[!0-9]*) continue;; esac
  [ -r "/proc/$pid/status" ] || continue
  report NETIFD_CANDIDATE "$pid"
  read_proc "$pid"
  ppid="$(awk '$1=="PPid:" {print $2}' "/proc/$pid/status" 2>/dev/null || :)"
  case "$ppid" in ''|0|1|*[!0-9]*) :;; *) echo '---PARENT---'; read_proc "$ppid";; esac
done
echo '===LIVE_UPLINK_STATE==='
if [ -d /sys/class/net/usb0 ]; then echo 'USB0=present'; else echo 'USB0=absent'; fi
if ip -4 addr show dev usb0 2>/dev/null | grep -q ' inet '; then
  echo 'USB0_IPV4=assigned'
else
  echo 'USB0_IPV4=absent'
fi
if ip -4 route show default 2>/dev/null | grep -q ' dev usb0 '; then
  echo 'USB0_DEFAULT_ROUTE=present'
else
  echo 'USB0_DEFAULT_ROUTE=absent'
fi
report UDHCPC_PROCESS_COUNT "$(pidof udhcpc 2>/dev/null | wc -w | tr -d ' ')"
if [ -d /sys/class/net/br-lan ]; then echo 'LAN_BRIDGE=present'; else echo 'LAN_BRIDGE=absent'; fi
echo 'TRIAGE_END=OK'
