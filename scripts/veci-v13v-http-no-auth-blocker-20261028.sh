#!/bin/sh
# v13v: recover LAN-only HTTP without calling stalled ubus session.login.
# HTTPS remains configured as fallback. No network/modem/rpcd restart.
set -eu
umask 077
PATH=/usr/sbin:/usr/bin:/sbin:/bin
export PATH
MODE="${1:-}"
CFG=/etc/config/uhttpd
BACK=/etc/config/uhttpd.veci-v13v-before-http-20261028
PREVIOUS_BACK=/etc/config/uhttpd.veci-v13u-before-http-20261028
SERVICE=/etc/init.d/uhttpd
fail(){ echo "VECI_V13V_ERROR=$1"; exit 1; }
echo VECI_V13V_STAGE=started_no_ubus
[ "$(id -u)" = 0 ] || fail root_required
[ "$(cat /tmp/sysinfo/board_name 2>/dev/null || :)" = zbtlink,zbt-we5927 ] || fail wrong_router
grep -Fqx "DISTRIB_RELEASE='25.12.5'" /etc/openwrt_release || fail firmware_mismatch
[ -f "$CFG" ] && [ ! -L "$CFG" ] && [ -s "$CFG" ] && [ -x "$SERVICE" ] || fail uhttpd_missing
echo VECI_V13V_STAGE=preflight_ok
if [ -f "$PREVIOUS_BACK" ] && [ ! -L "$PREVIOUS_BACK" ]; then echo VECI_V13V_OLD_BACKUP=present; else echo VECI_V13V_OLD_BACKUP=absent; fi
if [ -f "$BACK" ] && [ ! -L "$BACK" ]; then echo VECI_V13V_NEW_BACKUP=present; else echo VECI_V13V_NEW_BACKUP=absent; fi
echo "VECI_V13V_HTTP_CURRENT=$(uci -q get uhttpd.main.listen_http || echo unavailable)"
echo "VECI_V13V_REDIRECT_CURRENT=$(uci -q get uhttpd.main.redirect_https || echo unavailable)"
status(){
 if pidof uhttpd >/dev/null 2>&1; then echo VECI_V13V_UHTTPD=running; else echo VECI_V13V_UHTTPD=not_running; fi
 echo VECI_V13V_STATUS=complete
}
case "$MODE" in
 --status) status; exit 0 ;;
 --rollback)
  if [ -s "$BACK" ] && [ ! -L "$BACK" ]; then ORIGINAL="$BACK"
  elif [ -s "$PREVIOUS_BACK" ] && [ ! -L "$PREVIOUS_BACK" ]; then ORIGINAL="$PREVIOUS_BACK"
  else fail original_backup_missing; fi
  cp -p "$ORIGINAL" "$CFG" || fail rollback_copy_failed
  "$SERVICE" restart || fail rollback_uhttpd_restart_failed
  pidof uhttpd >/dev/null 2>&1 || fail rollback_uhttpd_not_running
  echo VECI_V13V_ROLLBACK=original_uhttpd_restored
  exit 0 ;;
 --apply) ;;
 *) fail invalid_arguments ;;
esac
if [ "$(uci -q get uhttpd.main.listen_http || :)" = 192.168.1.1:80 ] &&
   [ "$(uci -q get uhttpd.main.redirect_https || :)" = 0 ]; then
 pidof uhttpd >/dev/null 2>&1 || fail configured_but_uhttpd_not_running
 echo VECI_V13V_CONFIG=already_applied
 echo VECI_V13V_INTEGRITY=pass
 exit 0
fi
# Avoid layering another change over a partly applied old cutover.
[ ! -e "$PREVIOUS_BACK" ] && [ ! -L "$PREVIOUS_BACK" ] || fail previous_cutover_incomplete_review
[ ! -e "$BACK" ] && [ ! -L "$BACK" ] || fail new_backup_already_exists
[ "$(uci -q get network.lan.ipaddr || :)" = 192.168.1.1 ] || fail unknown_lan_ip
ip -4 addr show 2>/dev/null | grep -Fq '192.168.1.1/' || fail no_lan_address
echo VECI_V13V_STAGE=backing_up
cp -p "$CFG" "$BACK" || fail backup_failed
chmod 600 "$BACK"
echo VECI_V13V_STAGE=updating_lan_http
uci -q delete uhttpd.main.listen_http || :
uci add_list uhttpd.main.listen_http='192.168.1.1:80' || fail listen_http_write_failed
uci set uhttpd.main.redirect_https='0' || fail redirect_write_failed
uci commit uhttpd || fail config_commit_failed
echo VECI_V13V_STAGE=restarting_uhttpd_only
if ! "$SERVICE" restart; then
 cp -p "$BACK" "$CFG" || fail restart_failed_restore_copy_failed
 "$SERVICE" restart || fail rollback_restart_failed
 fail webserver_restart_failed_rolled_back
fi
if [ "$(uci -q get uhttpd.main.listen_http || :)" != 192.168.1.1:80 ] ||
   [ "$(uci -q get uhttpd.main.redirect_https || :)" != 0 ] ||
   ! pidof uhttpd >/dev/null 2>&1; then
 cp -p "$BACK" "$CFG" || fail integrity_failed_restore_copy_failed
 "$SERVICE" restart || fail integrity_rollback_restart_failed
 fail config_integrity_failed_restored
fi
echo VECI_V13V_HTTP_LISTEN=192.168.1.1:80
echo VECI_V13V_REDIRECT_HTTPS=disabled
echo VECI_V13V_HTTPS_CONFIG=preserved
echo VECI_V13V_INTEGRITY=pass
echo VECI_V13V_CONFIG_APPLY=complete
