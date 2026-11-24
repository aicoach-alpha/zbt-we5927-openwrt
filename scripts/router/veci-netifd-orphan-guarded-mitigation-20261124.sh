#!/bin/sh
# Exact-pid guarded mitigation for owner ONE physical WE5927.
# No UCI write, network restart, reboot, Wi-Fi activation or modem command.
# Only terminates positively identified NON-procd netifd, never canonical PID.
set -eu
LC_ALL=C; export LC_ALL
stop() { printf 'MITIGATION_STOP=%s\n' "$1"; exit 3; }
say() { printf '%s=%s\n' "$1" "$2"; }
get_field() { awk -v k="$2" '$1==k {print $2}' "/proc/$1/status" 2>/dev/null || :; }
check_proc() {
  [ -r "/proc/$1/status" ] || return 1
  [ "$(get_field "$1" 'Name:')" = "$2" ] || return 1
  [ "$(get_field "$1" 'PPid:')" = "$3" ] || return 1
  [ "$(readlink "/proc/$1/exe" 2>/dev/null || :)" = "$4" ] || return 1
}
board="$(cat /tmp/sysinfo/board_name 2>/dev/null || :)"
[ "$board" = 'zbtlink,zbt-we5927' ] || stop wrong_board
[ "$#" -eq 1 ] && [ "$1" = "--apply" ] || stop requires_explicit_apply_argument
[ "$(id -u)" = 0 ] || stop not_root
command -v jsonfilter >/dev/null 2>&1 || stop jsonfilter_missing
[ -d /sys/class/net/br-lan ] || stop wired_lan_missing
[ -d /sys/class/net/usb0 ] || stop usb0_missing
canonical=1366
orphan=16862
orphan_parent=16854
procd_network_pid() {
  ubus -S -t 4 call service list '{"name":"network","verbose":true}' 2>/dev/null |
    jsonfilter -e '@.network.instances[*].pid' 2>/dev/null
}
owner="$(procd_network_pid)" || stop procd_network_query_failed
[ "$owner" = "$canonical" ] || stop canonical_pid_changed
say PROCD_NETWORK_PID "$owner"
check_proc "$canonical" netifd 1 /sbin/netifd || stop canonical_netifd_identity_changed
check_proc "$orphan" netifd "$orphan_parent" /sbin/netifd || stop orphan_netifd_identity_changed
check_proc "$orphan_parent" ash 1 /bin/busybox || stop orphan_parent_identity_changed
all_pids="$(pidof netifd 2>/dev/null || :)"
set -- $all_pids
[ "$#" -eq 2 ] || stop unexpected_netifd_count
case " $all_pids " in *" $canonical "*) :;; *) stop canonical_pid_not_listed;; esac
case " $all_pids " in *" $orphan "*) :;; *) stop orphan_pid_not_listed;; esac
if ip -4 addr show dev usb0 2>/dev/null | grep -q ' inet '; then
  stop lte_ipv4_already_assigned_do_not_touch
fi
if ip -4 route show default 2>/dev/null | grep -q ' dev usb0 '; then
  stop lte_route_already_present_do_not_touch
fi
starttime="$(awk '{print $22}' "/proc/$orphan/stat" 2>/dev/null || :)"
case "$starttime" in ''|*[!0-9]*) stop orphan_process_starttime_unavailable;; esac
say SAFE_CANONICAL_PROCD_PID "$canonical"
say SAFE_ORPHAN_PID "$orphan"
say SAFE_ORPHAN_PARENT_PID "$orphan_parent"
echo 'PRECHECK=PASS_IDENTITIES_MATCH_ONLY_ORPHAN_TARGETED'
# Check every identity immediately before a single TERM, protecting against
# PID reuse / new procd ownership / changing process ancestry.
[ "$(procd_network_pid)" = "$canonical" ] || stop procd_owner_changed_before_signal
check_proc "$canonical" netifd 1 /sbin/netifd || stop canonical_changed_before_signal
check_proc "$orphan" netifd "$orphan_parent" /sbin/netifd || stop orphan_changed_before_signal
check_proc "$orphan_parent" ash 1 /bin/busybox || stop parent_changed_before_signal
[ "$(awk '{print $22}' "/proc/$orphan/stat" 2>/dev/null || :)" = "$starttime" ] || stop orphan_pid_reused
# Explicitly NEVER send a signal to procd-owned PID 1366 or parent ash 16854.
kill -TERM "$orphan" || stop orphan_term_failed
echo 'ORPHAN_TERM=REQUESTED'
i=0
while [ "$i" -lt 5 ]; do
  if [ ! -r "/proc/$orphan/status" ]; then break; fi
  state="$(get_field "$orphan" 'State:')"
  [ "$state" = Z ] && break
  sleep 1
  i=$((i+1))
done
if [ -r "/proc/$orphan/status" ] && [ "$(get_field "$orphan" 'State:')" != Z ]; then
  echo 'ORPHAN_TERM=STILL_RUNNING_NO_ESCALATION'
else
  echo 'ORPHAN_TERM=PROCESS_ENDED_OR_ZOMBIE'
fi
check_proc "$canonical" netifd 1 /sbin/netifd || stop canonical_netifd_missing_after_term
[ "$(procd_network_pid)" = "$canonical" ] || stop procd_owner_changed_after_term
[ -d /sys/class/net/br-lan ] || stop lan_bridge_missing_after_term
echo 'CANONICAL_NETIFD=STILL_ALIVE'
echo 'LAN_BRIDGE=STILL_PRESENT'
if ip -4 addr show dev usb0 2>/dev/null | grep -q ' inet '; then
  echo 'LTE_USB0_IPV4=assigned'
else
  echo 'LTE_USB0_IPV4=absent_further_repair_needed'
fi
if ip -4 route show default 2>/dev/null | grep -q ' dev usb0 '; then
  echo 'LTE_USB0_DEFAULT_ROUTE=present'
else
  echo 'LTE_USB0_DEFAULT_ROUTE=absent_further_repair_needed'
fi
echo 'MITIGATION_END=CANONICAL_NETWORK_PRESERVED_NO_LTE_RENEW_ATTEMPTED'
