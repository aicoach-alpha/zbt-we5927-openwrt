#!/bin/sh
# VeCI v13w: LAN HTTP enable without netlink, network UCI reads or ubus auth.
# Original configuration retained for explicit rollback; LTE/rpcd untouched.
set -eu
umask 077
PATH=/usr/sbin:/usr/bin:/sbin:/bin
export PATH
MODE="${1:-}"
CFG=/etc/config/uhttpd
BACK=/etc/config/uhttpd.veci-v13w-before-http-20261028
OLD_U=/etc/config/uhttpd.veci-v13u-before-http-20261028
OLD_V=/etc/config/uhttpd.veci-v13v-before-http-20261028
SVC=/etc/init.d/uhttpd
fail(){ echo "VECI_V13W_ERROR=$1"; exit 1; }
echo VECI_V13W_STAGE=started
[ "$(id -u)" = 0 ] || fail root_required
[ "$(cat /tmp/sysinfo/board_name 2>/dev/null || :)" = zbtlink,zbt-we5927 ] || fail wrong_router
grep -Fqx "DISTRIB_RELEASE='25.12.5'" /etc/openwrt_release || fail wrong_firmware
[ -s "$CFG" ] && [ -f "$CFG" ] && [ ! -L "$CFG" ] && [ -x "$SVC" ] || fail missing_http_config_or_service
echo VECI_V13W_STAGE=local_file_preflight_pass
if [ -e "$OLD_U" ] || [ -L "$OLD_U" ] || [ -e "$OLD_V" ] || [ -L "$OLD_V" ]; then
 echo VECI_V13W_PREVIOUS_BACKUP=present
else
 echo VECI_V13W_PREVIOUS_BACKUP=absent
fi
case "$MODE" in
 --rollback)
  [ -s "$BACK" ] && [ ! -L "$BACK" ] || fail original_v13w_backup_missing
  cp -p "$BACK" "$CFG" || fail original_restore_failed
  echo VECI_V13W_STAGE=restoring_uhttpd
  "$SVC" restart || fail rollback_restart_failed
  pidof uhttpd >/dev/null 2>&1 || fail rollback_service_not_running
  echo VECI_V13W_ROLLBACK=pass
  exit 0 ;;
 --apply) ;;
 *) fail usage_apply_or_rollback ;;
esac
# No HTTP source edit if an earlier script left a staged backup. This guard is
# independent of potentially hanging UCI reads of network and netlink.
if [ -e "$OLD_U" ] || [ -L "$OLD_U" ] || [ -e "$OLD_V" ] || [ -L "$OLD_V" ]; then
 fail prior_cutover_state_requires_manual_review
fi
[ ! -e "$BACK" ] && [ ! -L "$BACK" ] || fail v13w_backup_already_exists
echo VECI_V13W_STAGE=backup_uhttpd
cp -p "$CFG" "$BACK" || fail backup_copy_failed
chmod 600 "$BACK" || fail backup_permissions_failed
echo VECI_V13W_STAGE=editing_http_only
uci -q delete uhttpd.main.listen_http || :
uci add_list uhttpd.main.listen_http='192.168.1.1:80' || fail http_listener_edit_failed
uci set uhttpd.main.redirect_https='0' || fail redirect_edit_failed
uci commit uhttpd || fail commit_failed
echo VECI_V13W_STAGE=restart_uhttpd_only
if ! "$SVC" restart; then
 echo VECI_V13W_STAGE=restart_failed_restore_original
 cp -p "$BACK" "$CFG" || fail restore_after_restart_failed
 "$SVC" restart || fail rollback_restart_failed
 fail restart_failed_original_restored
fi
echo VECI_V13W_STAGE=integrity_gate
HTTP="$(uci -q get uhttpd.main.listen_http || :)"
REDIRECT="$(uci -q get uhttpd.main.redirect_https || :)"
if [ "$HTTP" != '192.168.1.1:80' ] || [ "$REDIRECT" != 0 ] ||
 ! pidof uhttpd >/dev/null 2>&1; then
 cp -p "$BACK" "$CFG" || fail integrity_restore_failed
 "$SVC" restart || fail integrity_rollback_restart_failed
 fail integrity_failed_original_restored
fi
echo VECI_V13W_HTTP=192.168.1.1:80
echo VECI_V13W_REDIRECT_HTTPS=disabled
echo VECI_V13W_HTTPS_CONFIG=retained
echo VECI_V13W_INTEGRITY=pass
echo VECI_V13W_RELEASE=live_config_pass
