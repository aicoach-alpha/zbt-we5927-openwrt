#!/bin/sh
# Exact-PID owner WE5927 rescue: remove non-procd netifd once, then LTE-only retry.
# NEVER kill procd network manager, restart all networking, reset modem, or flash.
set -u
stop() { printf 'RESCUE_STOP=%s\n' "$1"; exit 3; }
say() { printf '%s=%s\n' "$1" "$2"; }
procfield() { awk -v n="$2" '$1==n {print $2}' "/proc/$1/status" 2>/dev/null || :; }
checkproc() {
  [ -r "/proc/$1/status" ] || return 1
  [ "$(procfield "$1" 'Name:')" = "$2" ] || return 1
  [ "$(procfield "$1" 'PPid:')" = "$3" ] || return 1
  [ "$(readlink "/proc/$1/exe" 2>/dev/null || :)" = "$4" ] || return 1
}
procdpid() { ubus -S -t 4 call service list '{"name":"network","verbose":true}' 2>/dev/null | jsonfilter -e '@.network.instances[*].pid' 2>/dev/null || :; }
board="$(cat /tmp/sysinfo/board_name 2>/dev/null || :)"
[ "$board" = zbtlink,zbt-we5927 ] || stop wrong_board
[ "$(id -u)" = 0 ] || stop not_root
[ "${1:-}" = --apply ] && [ "$#" -eq 1 ] || stop explicit_apply_required
[ -d /sys/class/net/br-lan ] && [ -d /sys/class/net/usb0 ] || stop lan_or_usb0_missing
ip -4 addr show dev br-lan 2>/dev/null | grep -q ' inet 192.168.1.1/' || stop lan_ip_not_expected
[ "$(procdpid)" = 1366 ] || stop procd_network_owner_changed
checkproc 1366 netifd 1 /sbin/netifd || stop procd_netifd_identity_wrong
[ "$(procfield 1366 'State:')" = S ] || stop procd_netifd_not_healthy
memory="$(awk '$1=="MemAvailable:" {print $2}' /proc/meminfo 2>/dev/null || :)"
case "$memory" in ''|*[!0-9]*) stop memory_unknown;; esac
[ "$memory" -ge 12000 ] || stop memory_below_12mib
ubus -S list network.interface.lte 2>/dev/null | grep -qx 'network.interface.lte' || stop lte_ubus_missing_before_term
checkproc 16862 netifd 16854 /sbin/netifd || stop extra_netifd_identity_changed
checkproc 16854 ash 1 /bin/busybox || stop extra_netifd_parent_changed
pids="$(pidof netifd 2>/dev/null || :)"
set -- $pids
[ "$#" -eq 2 ] || stop unexpected_netifd_count
case " $pids " in *' 1366 '*) :;; *) stop procd_pid_missing;; esac
case " $pids " in *' 16862 '*) :;; *) stop extra_pid_missing;; esac
if ip -4 addr show dev usb0 2>/dev/null | grep -q ' inet '; then
  stop usb0_ipv4_recovered_avoid_kill
fi
if ip -4 route show default 2>/dev/null | grep -q ' dev usb0 '; then
  stop usb0_route_recovered_avoid_kill
fi
starttime="$(awk '{print $22}' /proc/16862/stat 2>/dev/null || :)"
case "$starttime" in ''|*[!0-9]*) stop extra_pid_starttime_unavailable;; esac
say PRECHECK "PASS_PROCD_1366_AND_EXTRA_16862_CONFIRMED"
# Repeat all dangerous identity/state assertions immediately before signal.
[ "$(procdpid)" = 1366 ] || stop procd_owner_changed_before_signal
checkproc 1366 netifd 1 /sbin/netifd || stop canonical_changed_before_signal
[ "$(procfield 1366 'State:')" = S ] || stop canonical_not_sleeping_before_signal
checkproc 16862 netifd 16854 /sbin/netifd || stop extra_changed_before_signal
checkproc 16854 ash 1 /bin/busybox || stop parent_changed_before_signal
[ "$(awk '{print $22}' /proc/16862/stat 2>/dev/null || :)" = "$starttime" ] || stop extra_pid_reused
[ -d /sys/class/net/br-lan ] || stop lan_missing_before_signal
ip -4 addr show dev br-lan 2>/dev/null | grep -q ' inet 192.168.1.1/' || stop lan_ip_changed_before_signal
if ip -4 addr show dev usb0 2>/dev/null | grep -q ' inet '; then stop usb0_ipv4_reappeared_before_signal; fi
if ip -4 route show default 2>/dev/null | grep -q ' dev usb0 '; then stop usb0_route_reappeared_before_signal; fi
memory="$(awk '$1=="MemAvailable:" {print $2}' /proc/meminfo 2>/dev/null || :)"
case "$memory" in ''|*[!0-9]*) stop memory_unknown_before_signal;; esac
[ "$memory" -ge 12000 ] || stop memory_dropped_before_signal
echo ACTION=TERM_ONLY_NONPROCD_NETIFD_16862
kill -TERM 16862 || { echo ORPHAN_TERM=REJECTED; exit 4; }
i=0
while [ "$i" -lt 5 ]; do
  if [ ! -r /proc/16862/status ] || [ "$(procfield 16862 'State:')" = Z ]; then break; fi
  sleep 1
  i=$((i+1))
done
if [ -r /proc/16862/status ] && [ "$(procfield 16862 'State:')" != Z ]; then
  echo ORPHAN_TERM=STILL_RUNNING_NO_ESCALATION
  exit 5
fi
echo ORPHAN_TERM=ENDED_OR_ZOMBIE
[ "$(procdpid)" = 1366 ] || stop canonical_owner_lost_after_term
checkproc 1366 netifd 1 /sbin/netifd || stop canonical_process_lost_after_term
[ "$(procfield 1366 'State:')" = S ] || stop canonical_unhealthy_after_term
ubus -S list network.interface.lte 2>/dev/null | grep -qx 'network.interface.lte' || stop lte_ubus_lost_after_term
ip -4 addr show dev br-lan 2>/dev/null | grep -q ' inet 192.168.1.1/' || stop wired_lan_lost_after_term
echo LAN=STILL_192_168_1_1
sleep 3
if curl --disable --ipv4 --insecure --noproxy '*' --interface 'if!usb0' --connect-timeout 2 --max-time 4 -s -o /dev/null https://1.1.1.1/ 2>/dev/null && curl --disable --ipv4 --noproxy '*' --interface 'if!usb0' --connect-timeout 2 --max-time 4 -s -o /dev/null https://www.cloudflare.com/cdn-cgi/trace 2>/dev/null; then
  echo RESCUE_RESULT=EXTERNAL_EGRESS_RECOVERED_NO_LTE_CYCLE_NEEDED
  exit 0
fi
echo ACTION=ONE_LTE_ONLY_DOWN_UP_AFTER_ORPHAN_TERM
ubus -S -t 8 call network.interface.lte down '{}'
rc=$?
echo LTE_DOWN_EXIT=$rc
[ "$rc" = 0 ] || { echo REPAIR_STOP=lte_down_failed; exit 6; }
sleep 5
ip -4 addr show dev br-lan 2>/dev/null | grep -q ' inet 192.168.1.1/' || stop wired_lan_changed_after_down
[ "$(procdpid)" = 1366 ] || stop canonical_owner_lost_after_down
[ "$(procfield 1366 'State:')" = S ] || stop canonical_not_healthy_after_down
ubus -S -t 8 call network.interface.lte up '{}'
rc=$?
echo LTE_UP_EXIT=$rc
[ "$rc" = 0 ] || { echo REPAIR_STOP=lte_up_failed; exit 7; }
sleep 18
echo ===AFTER_RECOVERY===
if ip -4 addr show dev usb0 2>/dev/null | grep -q ' inet '; then echo USB0_IPV4=assigned; else echo USB0_IPV4=absent; fi
if ip -4 route show default 2>/dev/null | grep -q ' dev usb0 '; then echo USB0_DEFAULT_ROUTE=present; else echo USB0_DEFAULT_ROUTE=absent; fi
echo UDHCPC_COUNT="$(pidof udhcpc 2>/dev/null | wc -w | tr -d ' ')"
if ip -4 addr show dev br-lan 2>/dev/null | grep -q ' inet 192.168.1.1/'; then echo LAN=STILL_192_168_1_1; else echo LAN=NOT_VERIFIED; fi
curl --disable --ipv4 --insecure --noproxy '*' --interface 'if!usb0' --connect-timeout 3 --max-time 8 -s -o /dev/null -w 'PUBLIC_IP_HTTPS_CODE=%{http_code}\n' https://1.1.1.1/
echo PUBLIC_IP_HTTPS_EXIT=$?
curl --disable --ipv4 --noproxy '*' --interface 'if!usb0' --connect-timeout 3 --max-time 8 -s -o /dev/null -w 'PUBLIC_DNS_HTTPS_CODE=%{http_code}\n' https://www.cloudflare.com/cdn-cgi/trace
echo PUBLIC_DNS_HTTPS_EXIT=$?
echo RESCUE_END=COMPLETE_NO_FURTHER_MUTATION
