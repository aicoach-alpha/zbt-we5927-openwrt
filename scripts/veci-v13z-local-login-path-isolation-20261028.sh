#!/bin/sh
# VeCI v13z: isolate rpcd session.login dispatch versus credential lookup.
# Two invalid/empty local ubus calls; no real credentials, no config edits.
set -u
PATH=/usr/sbin:/usr/bin:/sbin:/bin
export PATH
echo VECI_V13Z_STAGE=started
[ "$(id -u)" = 0 ] || { echo VECI_V13Z_ERROR=root_required; exit 1; }
[ "$(cat /tmp/sysinfo/board_name 2>/dev/null)" = 'zbtlink,zbt-we5927' ] ||
 { echo VECI_V13Z_ERROR=wrong_router; exit 1; }
command -v ubus >/dev/null 2>&1 || { echo VECI_V13Z_ERROR=ubus_missing; exit 1; }
# Bounded direct ubus child; status only. Never emit session IDs or payloads.
probe() {
 label="$1"
 payload="$2"
 printf 'VECI_V13Z_%s=started\n' "$label"
 ubus -S -t 4 call session login "$payload" >/dev/null 2>&1 &
 pid=$!
 n=0
 while [ "$n" -lt 5 ]; do
  if [ -r "/proc/$pid/stat" ]; then
   state="$(awk '{print $3}' "/proc/$pid/stat" 2>/dev/null)"
  else
   state=gone
  fi
  case "$state" in
   Z|X|gone)
    rc=0
    wait "$pid" || rc="$?"
    printf 'VECI_V13Z_%s=returned\n' "$label"
    printf 'VECI_V13Z_%s_CODE=%s\n' "$label" "$rc"
    return 0 ;;
  esac
  sleep 1
  n=$((n+1))
 done
 # Kill only child spawned above; don't touch rpcd, uhttpd or ubusd.
 kill -TERM "$pid" 2>/dev/null || :
 sleep 1
 if [ -r "/proc/$pid/stat" ]; then
  state="$(awk '{print $3}' "/proc/$pid/stat" 2>/dev/null)"
 else
  state=gone
 fi
 case "$state" in
  Z|X|gone) wait "$pid" 2>/dev/null || :; printf 'VECI_V13Z_%s=timed_out_terminated\n' "$label"; return 0 ;;
  D) printf 'VECI_V13Z_%s=blocked_in_D_state\n' "$label"; return 1 ;;
  *)
   if [ -r "/proc/$pid/cmdline" ] &&
      tr '\000' '\n' <"/proc/$pid/cmdline" | grep -Fqx 'ubus'; then
    kill -KILL "$pid" 2>/dev/null || :
   fi
   printf 'VECI_V13Z_%s=timed_out_signal_sent\n' "$label"
   return 1 ;;
 esac
}
# No username/password: handler rejects before UCI parsing.
if probe EMPTY_ARGUMENTS '{}'; then
 echo VECI_V13Z_STAGE=empty_arguments_checked
else
 echo VECI_V13Z_STOP=rpcd_method_unresponsive
 echo VECI_V13Z_PRODUCTION=unchanged
 exit 0
fi
# Nonexistent user: enters UCI login lookup, skips shadow/crypt if name unmatched.
probe UNKNOWN_USER '{"username":"__veci_nonexistent_probe__","password":"__invalid_no_secret__"}' || :
echo VECI_V13Z_STAGE=finished
echo VECI_V13Z_PRODUCTION=unchanged
