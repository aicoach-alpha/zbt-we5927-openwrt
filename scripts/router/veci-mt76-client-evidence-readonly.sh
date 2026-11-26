#!/bin/sh
# MT76 on-router evidence collector: READ ONLY. Safe to stream over SSH stdin.
# Does NOT write UCI, send AT, reload WiFi/network, reboot, scan or alter LTE.
set -u
export LC_ALL=C
echo '===VECI_MT76_CLIENT_EVIDENCE_V1==='
if [ "$(cat /tmp/sysinfo/board_name 2>/dev/null || :)" != zbtlink,zbt-we5927 ]; then
  echo 'BOARD=UNEXPECTED; RESULT=ABORT'; exit 3
fi
echo 'BOARD=WE5927'
for cmd in ubus jsonfilter iw awk; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "MISSING_COMMAND=$cmd; RESULT=INCONCLUSIVE"; exit 2
  fi
done
net="$(ubus -S -t 3 call network.wireless status '{}' 2>/dev/null)" || net=
if [ -z "$net" ]; then echo 'NETIFD_STATUS=UNAVAILABLE; RESULT=INCONCLUSIVE'; exit 2; fi
iface="$(printf '%s' "$net" | jsonfilter -e '@.radio0.interfaces[@.section="default_radio0"].ifname' 2>/dev/null || :)"
case "$iface" in ''|-*|*[!A-Za-z0-9_.-]*)
  echo 'PRIMARY_AP_IFACE=UNKNOWN; RESULT=INCONCLUSIVE'; exit 2 ;;
esac
echo "PRIMARY_AP_IFACE=$iface"
radio="$(printf '%s' "$net" | jsonfilter -e '@.radio0.up' 2>/dev/null || :)"
echo "RADIO0_UP=$radio"
info="$(iw dev "$iface" info 2>/dev/null)" || info=
if ! printf '%s\n' "$info" | grep -Eq '^[[:space:]]*type AP$'; then
  echo 'AP_MODE=NOT_VERIFIED; RESULT=INCONCLUSIVE'; exit 2
fi
echo 'AP_MODE=AP'
if [ ! -r /usr/share/libubox/jshn.sh ]; then
  echo 'HOSTAPD_JSON_LIBRARY=MISSING; RESULT=INCONCLUSIVE'; exit 2
fi
# This happens in an isolated subshell; json_get_keys produces MAC-address
# keys but only a numeric count is printed. No station/MAC/IP is output.
hostapd_count() (
  set +u
  set -f
  . /usr/share/libubox/jshn.sh || exit 1
  json_load "$1" || exit 1
  json_select clients || exit 1
  json_get_keys keys || exit 1
  set -- $keys
  printf '%s\n' "$#"
)
samples=5
i=1
valid=0
positive=0
errors=0
while [ "$i" -le "$samples" ]; do
  iw_output="$(iw dev "$iface" station dump 2>/dev/null)"
  iw_code=$?
  iw_count=UNKNOWN
  if [ "$iw_code" -eq 0 ]; then
    iw_count="$(printf '%s\n' "$iw_output" | awk '$1=="Station" {n++} END {print n+0}')"
  else errors=$((errors+1)); fi
  hp_output="$(ubus -S -t 4 call "hostapd.$iface" get_clients '{}' 2>/dev/null)"
  hp_code=$?
  hp_count=UNKNOWN
  if [ "$hp_code" -eq 0 ]; then
    hp_count="$(hostapd_count "$hp_output" 2>/dev/null || echo UNKNOWN)"
  else errors=$((errors+1)); fi
  case "$iw_count:$hp_count" in
    UNKNOWN:*|*:UNKNOWN) match=UNVERIFIED ;;
    *) if [ "$iw_count" = "$hp_count" ]; then
         match=MATCH
         valid=$((valid+1))
       else
         match=MISMATCH
         errors=$((errors+1))
       fi
       if [ "$iw_count" -gt 0 ] || [ "$hp_count" -gt 0 ]; then
         positive=$((positive+1))
       fi ;;
  esac
  echo "SAMPLE=$i IW_EXIT=$iw_code IW_CLIENTS=$iw_count HOSTAPD_EXIT=$hp_code HOSTAPD_CLIENTS=$hp_count MATCH=$match"
  i=$((i+1))
  if [ "$i" -le "$samples" ]; then sleep 2; fi
done
echo "VALID_COUNT_COMPARISONS=$valid/$samples POSITIVE_CLIENT_SAMPLES=$positive/$samples READ_ERRORS_OR_MISMATCHES=$errors"
if [ "$valid" -eq "$samples" ] && [ "$positive" -gt 0 ]; then
  echo 'RESULT=CLIENT_ASSOCIATION_OBSERVED_NOT_STRESS_PASS'
elif [ "$valid" -eq "$samples" ] && [ "$positive" -eq 0 ]; then
  echo 'RESULT=NO_ASSOCIATED_CLIENT_OBSERVED'
else
  echo 'RESULT=INCONCLUSIVE_COUNTER_FAILURE_OR_MISMATCH'
fi
echo 'MT76_DRIVER_ROOT_CAUSE_RESOLVED=NOT_PROVEN'
echo 'NEW_FIRMWARE_HARDWARE_UAT=NOT_RUN'
echo 'READ_ONLY_DONE'
