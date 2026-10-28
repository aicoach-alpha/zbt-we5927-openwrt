#!/bin/sh
# v14a: classify rpcd session request responsiveness (no credential or session data).
# NEVER restart/kill daemons, alter files, or expose session responses.
set -u
PATH=/usr/sbin:/usr/bin:/sbin:/bin; export PATH
echo VECI_V14A=started
[ "$(id -u)" -eq 0 ] || { echo VECI_V14A_ERROR=root_required; exit 1; }
[ "$(cat /tmp/sysinfo/board_name 2>/dev/null)" = zbtlink,zbt-we5927 ] ||
 { echo VECI_V14A_ERROR=wrong_router; exit 1; }
echo VECI_V14A_DIAGNOSIS=prior_login_code_7_means_ubus_timeout
echo VECI_V14A_STAGE=rpcd_process_snapshot
count=0
for pid in $(pidof rpcd 2>/dev/null); do
 count=$((count+1))
 [ "$count" -le 4 ] || break
 if [ -r "/proc/$pid/status" ]; then
  state="$(awk '$1=="State:"{print $2;exit}' "/proc/$pid/status")"
  threads="$(awk '$1=="Threads:"{print $2;exit}' "/proc/$pid/status")"
  rss="$(awk '$1=="VmRSS:"{print $2;exit}' "/proc/$pid/status")"
  chan="$(cat "/proc/$pid/wchan" 2>/dev/null || echo unavailable)"
  echo "VECI_V14A_RPCD_PROCESS=pid:$pid,state:$state,threads:$threads,rss_kib:$rss,wchan:$chan"
 fi
done
echo "VECI_V14A_RPCD_PID_COUNT=$count"
# Two non-authenticating calls on same session object. Suppress response bodies.
check(){
 label="$1"; shift
 echo "VECI_V14A_CHECK_$label=started"
 rc=0
 ubus -S -t 3 call session "$@" >/dev/null 2>&1 || rc="$?"
 echo "VECI_V14A_CHECK_$label-CODE=$rc"
 case "$rc" in
  7) echo "VECI_V14A_CHECK_$label=timed_out" ;;
  0|2|3|4|5|6) echo "VECI_V14A_CHECK_$label=rpcd_replied" ;;
  *) echo "VECI_V14A_CHECK_$label=other_error" ;;
 esac
}
echo VECI_V14A_STAGE=method_responsiveness
check SESSION_ACCESS access '{"ubus_rpc_session":"00000000000000000000000000000000","scope":"ubus","object":"session","function":"login"}'
check SESSION_LIST list '{}'
echo VECI_V14A_STAGE=complete
echo VECI_V14A_PRODUCTION=unchanged
