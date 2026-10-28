#!/bin/sh
# VeCI v13y: bounded, read-only diagnosis of stalled rpcd login and UCI.
# Does not read password hashes, authenticate, restart services or change config.
set -u
PATH=/usr/sbin:/usr/bin:/sbin:/bin; export PATH
echo VECI_V13Y_STAGE=started
[ "$(id -u)" = 0 ] || { echo VECI_V13Y_ERROR=root_required; exit 1; }
[ "$(cat /tmp/sysinfo/board_name 2>/dev/null)" = zbtlink,zbt-we5927 ] || {
 echo VECI_V13Y_ERROR=wrong_board; exit 1;
}
grep -Fqx "DISTRIB_RELEASE='25.12.5'" /etc/openwrt_release || {
 echo VECI_V13Y_ERROR=wrong_firmware; exit 1;
}
if [ -f /etc/config/rpcd ] && [ ! -L /etc/config/rpcd ]; then
 echo "VECI_V13Y_RPCD_CONFIG_BYTES=$(wc -c < /etc/config/rpcd | tr -d ' ')"
 # Count only the login sections; never print their username/password entries.
 echo "VECI_V13Y_RPCD_LOGIN_SECTIONS=$(awk '$1=="config" {t=$2;gsub(/[\047\042]/,"",t);if(t=="login")n++} END{print n+0}' /etc/config/rpcd)"
 echo "VECI_V13Y_RPCD_USERNAME_OPTION_COUNT=$(awk '$1=="option" && $2=="username"{n++} END{print n+0}' /etc/config/rpcd)"
 echo "VECI_V13Y_RPCD_PASSWORD_OPTION_COUNT=$(awk '$1=="option" && $2=="password"{n++} END{print n+0}' /etc/config/rpcd)"
else
 echo VECI_V13Y_RPCD_CONFIG=missing_or_symlink
fi
if pidof rpcd >/dev/null 2>&1; then
 echo VECI_V13Y_RPCD_PROCESS=running
else
 echo VECI_V13Y_RPCD_PROCESS=not_running
fi
# Each subprocess is exec'd (no wrapper) and can be terminated by its exact PID.
# Wait only for completed/zombie children, never on a stalled D-state process.
bounded(){
 label="$1"; shift
 echo "VECI_V13Y_CHECK_$label=started"
 ( exec "$@" >/dev/null 2>&1 ) &
 pid=$!
 elapsed=0
 while [ "$elapsed" -lt 4 ]; do
  state="$(awk '{print $3}' "/proc/$pid/stat" 2>/dev/null || echo gone)"
  case "$state" in
   Z|X|gone)
    rc=0
    wait "$pid" || rc="$?"
    echo "VECI_V13Y_CHECK_$label=completed_rc_$rc"
    return 0 ;;
  esac
  sleep 1
  elapsed=$((elapsed+1))
 done
 state="$(awk '{print $3}' "/proc/$pid/stat" 2>/dev/null || echo gone)"
 if [ "$state" = Z ] || [ "$state" = X ] || [ "$state" = gone ]; then
  rc=0
  wait "$pid" || rc="$?"
  echo "VECI_V13Y_CHECK_$label=completed_rc_$rc"
  return 0
 fi
 # Kill only the child launched by this function, never any router daemon.
 kill -TERM "$pid" 2>/dev/null || :
 sleep 1
 state="$(awk '{print $3}' "/proc/$pid/stat" 2>/dev/null || echo gone)"
 case "$state" in
  Z|X|gone) wait "$pid" 2>/dev/null || :; echo "VECI_V13Y_CHECK_$label=timed_out_terminated" ;;
  *) echo "VECI_V13Y_CHECK_$label=timed_out_child_state_$state" ;;
 esac
 return 0
}
echo VECI_V13Y_STAGE=bounded_uci
if command -v uci >/dev/null 2>&1; then
 bounded rpcd_uci uci -q show rpcd
 bounded network_uci uci -q get network.lan.ipaddr
 bounded uhttpd_uci uci -q get uhttpd.main.redirect_https
else
 echo VECI_V13Y_UCI=not_installed
fi
echo VECI_V13Y_STAGE=complete
echo VECI_V13Y_PRODUCTION=unchanged
