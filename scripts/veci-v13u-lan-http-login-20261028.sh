#!/bin/sh
# VeCI v13u: LAN-only HTTP and one bounded internal login diagnosis.
# HTTPS remains available as fallback; no password, LTE or firewall changes.
set -eu
umask 077
PATH=/usr/sbin:/usr/bin:/sbin:/bin
export PATH
MODE="$1"
CFG=/etc/config/uhttpd
BACK=/etc/config/uhttpd.veci-v13u-before-http-20261028
SERVICE=/etc/init.d/uhttpd
fail(){ echo "VECI_V13U_ERROR=$1"; exit 1; }
diagnose(){
 echo VECI_LOGIN_DIRECT_UBUS_CHECK=one_invalid_account
 start="$(date +%s)"
 rc=0
 ubus -S -t 6 call session login '{"username":"__veci_probe_nonexistent__","password":"__invalid_probe_no_secret__"}' >/dev/null 2>&1 || rc="$?"
 stop="$(date +%s)"
 duration=$((stop-start))
 echo "VECI_LOGIN_DIRECT_UBUS_SECONDS=$duration"
 echo "VECI_LOGIN_DIRECT_UBUS_EXIT=$rc"
 if [ "$duration" -ge 5 ]; then
  echo VECI_LOGIN_DIRECT_UBUS=timeout_or_stalled
 else
  if [ "$rc" -eq 0 ]; then
   echo VECI_LOGIN_DIRECT_UBUS=unexpected_dummy_accepted
  else
   echo VECI_LOGIN_DIRECT_UBUS=responded_to_invalid_login
  fi
 fi
}
[ "$(id -u)" -eq 0 ] || fail root_required
[ "$(cat /tmp/sysinfo/board_name 2>/dev/null || :)" = 'zbtlink,zbt-we5927' ] || fail wrong_board
grep -Fqx "DISTRIB_RELEASE='25.12.5'" /etc/openwrt_release || fail unexpected_firmware
[ -s "$CFG" ] && [ -f "$CFG" ] && [ ! -L "$CFG" ] &&
 [ -x "$SERVICE" ] || fail uhttpd_config_or_service_missing
[ "$(uci -q get network.lan.ipaddr || :)" = '192.168.1.1' ] || fail lan_ip_not_expected
ip -4 addr show 2>/dev/null | grep -Fq '192.168.1.1/' || fail lan_address_not_assigned
case "$MODE" in
 --status)
  echo "VECI_V13U_HTTP_LISTEN=$(uci -q get uhttpd.main.listen_http || echo none)"
  echo "VECI_V13U_REDIRECT=$(uci -q get uhttpd.main.redirect_https || echo unset)"
  if pidof uhttpd >/dev/null 2>&1; then echo VECI_V13U_UHTTPD=running
  else echo VECI_V13U_UHTTPD=not_running; fi
  diagnose
  echo VECI_V13U_PRODUCTION=unchanged
  exit 0 ;;
 --rollback)
  [ -s "$BACK" ] && [ ! -L "$BACK" ] || fail original_backup_missing
  cp -p "$BACK" "$CFG" || fail rollback_copy_failed
  "$SERVICE" restart || fail rollback_webserver_restart_failed
  pidof uhttpd >/dev/null 2>&1 || fail rollback_webserver_not_running
  echo VECI_V13U_ROLLBACK=restored_original_uhttpd
  exit 0 ;;
 --apply) ;;
 *) fail use_apply_status_or_rollback ;;
esac
diagnose
if [ "$(uci -q get uhttpd.main.redirect_https || :)" = '0' ] &&
 [ "$(uci -q get uhttpd.main.listen_http || :)" = '192.168.1.1:80' ]; then
 echo VECI_V13U_HTTP_CONFIG=already_current
 pidof uhttpd >/dev/null 2>&1 || fail existing_uhttpd_not_running
 echo VECI_V13U_INTEGRITY=pass
 echo VECI_V13U_RELEASE=live_config_pass
 exit 0
fi
[ ! -e "$BACK" ] && [ ! -L "$BACK" ] || fail existing_backup_requires_review
cp -p "$CFG" "$BACK" || fail original_backup_failed
chmod 600 "$BACK"
uci -q delete uhttpd.main.listen_http || :
uci add_list uhttpd.main.listen_http='192.168.1.1:80' || fail http_listener_set_failed
uci set uhttpd.main.redirect_https='0' || fail redirect_disable_failed
uci commit uhttpd || fail config_commit_failed
if ! "$SERVICE" restart; then
 cp -p "$BACK" "$CFG" || fail restart_failed_rollback_copy_failed
 "$SERVICE" restart || fail rollback_restart_failed
 fail uhttpd_restart_failed_rolled_back
fi
if [ "$(uci -q get uhttpd.main.listen_http || :)" != '192.168.1.1:80' ] ||
 [ "$(uci -q get uhttpd.main.redirect_https || :)" != '0' ] ||
 ! pidof uhttpd >/dev/null 2>&1; then
 cp -p "$BACK" "$CFG" || fail integrity_failed_restore_copy_failed
 "$SERVICE" restart || fail integrity_failed_rollback_restart_failed
 fail integrity_failed_original_restored
fi
echo VECI_V13U_HTTP_LISTEN=192.168.1.1:80
echo VECI_V13U_REDIRECT_HTTPS=disabled
echo VECI_V13U_HTTPS_LISTENER=unchanged
echo VECI_V13U_PASSWORD=unchanged
echo VECI_V13U_LTE=untouched
echo VECI_V13U_INTEGRITY=pass
echo VECI_V13U_RELEASE=live_config_pass
