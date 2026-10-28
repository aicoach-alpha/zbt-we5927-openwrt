#!/bin/sh
# Conditional, bounded VeCI authentication recovery. NOT a password reset.
set -eu
PATH=/usr/sbin:/usr/bin:/sbin:/bin
export PATH
fail(){ echo "VECI_AUTH_ERROR=$1"; exit 1; }
[ "$#" -eq 1 ] || fail invalid_arguments
MODE="$1"
[ "$(id -u)" = 0 ] || fail root_required
[ "$(cat /tmp/sysinfo/board_name 2>/dev/null || :)" = zbtlink,zbt-we5927 ] || fail unexpected_router
[ -f /etc/openwrt_release ] && grep -Fq "DISTRIB_RELEASE='25.12.5'" /etc/openwrt_release || fail unexpected_firmware
[ -x /etc/init.d/rpcd ] && [ -x /etc/init.d/uhttpd ] || fail service_scripts_missing
command -v ubus >/dev/null 2>&1 || fail ubus_missing
# Dummy credentials cannot create a valid session. Never print an unexpected
# response which could contain sensitive session details.
probe_local(){
 local code response
 code=0
 response="$(ubus -S -t 4 call session login '{"username":"__veci_nonexistent_probe__","password":"__deliberately_invalid__"}' 2>&1)" || code=$?
 if [ "$code" = 6 ] || printf '%s' "$response" | grep -qi 'Permission denied'; then
  echo denied_fast
 elif [ "$code" = 7 ] || printf '%s' "$response" | grep -qi 'Request timed out'; then
  echo timeout
 elif [ "$code" = 0 ]; then
  echo unexpected_success
 else
  echo other_error
 fi
}
[ "$MODE" = inspect ] || [ "$MODE" = recover-rpcd ] || [ "$MODE" = recover-uhttpd ] || fail invalid_mode
[ -x /usr/sbin/rpcd ] || fail rpcd_binary_missing
[ -x /usr/sbin/uhttpd ] || fail uhttpd_binary_missing
if [ "$MODE" = inspect ]; then
 echo "VECI_AUTH_LOCAL=$(probe_local)"
 echo VECI_AUTH_ACTION=read_only
 exit 0
fi
if [ "$MODE" = recover-rpcd ]; then
 before="$(probe_local)"
 if [ "$before" = denied_fast ]; then
  echo VECI_AUTH_RPCD=already_responding_no_restart
  echo VECI_AUTH_LOCAL=denied_fast
  exit 0
 fi
 [ "$before" = timeout ] || fail rpcd_not_confirmed_hung_no_restart
 echo VECI_AUTH_RPCD=one_targeted_restart
 /etc/init.d/rpcd restart || fail rpcd_restart_command_failed
 after="$(probe_local)"
 echo "VECI_AUTH_LOCAL=$after"
 [ "$after" = denied_fast ] || fail rpcd_login_still_unresponsive
 echo VECI_AUTH_RPCD=recovered
 exit 0
fi
[ "$(probe_local)" = denied_fast ] || fail rpcd_not_ready_refuse_http_restart
echo VECI_AUTH_UHTTPD=one_targeted_restart
/etc/init.d/uhttpd restart || fail uhttpd_restart_command_failed
echo VECI_AUTH_UHTTPD=restart_complete
