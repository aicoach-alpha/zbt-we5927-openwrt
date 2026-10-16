#!/bin/sh
# Optional diagnostic-only JS overlay for signed generic USSD 0.1.0.
# Never changes APK, Core, rpcd, modem, HTTP, SMS, LuCI or active SIM.
set -eu
umask 077
LC_ALL=C; PATH=/usr/sbin:/usr/bin:/sbin:/bin; export LC_ALL PATH
REV=51ce9935ef2f4d63eeb3bb80e7d774cff107d44f
URL="https://raw.githubusercontent.com/aicoach-alpha/zbt-we5927-openwrt/$REV/source/veci-ussd-dialer/files/www/veci/ussd-dialer.js"
OLD_SHA=1b30bce5c5a52b1485290622f1342470d5f86bd6baacbfc2e37397118051b8e0
NEW_SHA=26e43698e48f72ba7c8a256c8f6cb469f803116ad1a92aae939a4bec33e2f304
CORE_SHA=d08edadd38f0d9b992fc54d879eabf9f797bf54df83fa8c8cf7b59e55b9e99ce
PAGE_SHA=b075a4852d3eeb5f717e4db568a0929fc732b225f025a154beb24961a3f85379
FILE=/www/veci/ussd-dialer.js
BACKUP=/root/veci-generic-ussd-browser-acl-rollback-20261016.js
LOCK=/tmp/veci-generic-ussd-ui-update.lock
TEMP=
SWAPPED=0
SUCCESS=0
fail(){ printf 'VECI_GENERIC_USSD_UI_UPDATE=blocked\nVECI_GENERIC_USSD_UI_REASON=%s\n' "$1"; exit 1; }
sha(){ sha256sum "$1" | awk '{print $1}'; }
same(){ [ -f "$1" ] && [ ! -L "$1" ] && [ "$(sha "$1")" = "$2" ]; }
guard(){
 [ "$(id -u)" = 0 ] || fail root_required
 [ "$(cat /tmp/sysinfo/board_name 2>/dev/null || :)" = zbtlink,zbt-we5927 ] || fail wrong_router
 grep -qx "DISTRIB_RELEASE='25.12.5'" /etc/openwrt_release || fail wrong_firmware
 same /usr/libexec/rpcd/veci "$CORE_SHA" || fail core_rpc_drift
 same /www/veci/js/pages/cellular.js "$PAGE_SHA" || fail core_cellular_drift
 apk list -I 2>/dev/null | grep -q '^veci-ussd-dialer-0.1.0-r1' || fail signed_dialer_not_installed
 ubus -S list veci.dialer 2>/dev/null | grep -qx 'veci.dialer' || fail dialer_rpc_unavailable
 [ -z "$(uci -q get uhttpd.main.listen_http 2>/dev/null || :)" ] || fail https_only_required
 [ -n "$(uci -q get uhttpd.main.listen_https 2>/dev/null || :)" ] || fail https_listener_missing
}
cleanup(){
 code="$1"
 trap - EXIT INT TERM
 if [ "$SWAPPED" = 1 ] && [ "$SUCCESS" = 0 ];then
  if same "$FILE" "$NEW_SHA" && same "$BACKUP" "$OLD_SHA";then
   cp "$BACKUP" "$FILE.restore.$$" &&
    chmod 644 "$FILE.restore.$$" &&
    mv -f "$FILE.restore.$$" "$FILE" || :
  fi
  echo VECI_GENERIC_USSD_UI_ROLLBACK=attempted
 fi
 [ -n "$TEMP" ] && [ -f "$TEMP" ] && rm -f "$TEMP" || :
 rm -f "$FILE.stage.$$" "$FILE.restore.$$"
 rmdir "$LOCK" 2>/dev/null || :
 exit "$code"
}
[ "$#" = 1 ] || fail usage
case "$1" in --status|--verify|--install|--rollback) MODE="$1";; *) fail usage;; esac
guard
if [ "$MODE" = --status ];then
 if same "$FILE" "$NEW_SHA";then
  echo VECI_GENERIC_USSD_UI_UPDATE=installed
 elif same "$FILE" "$OLD_SHA";then
  echo VECI_GENERIC_USSD_UI_UPDATE=original
 else
  echo VECI_GENERIC_USSD_UI_UPDATE=unknown
 fi
 echo VECI_GENERIC_USSD_UI_MODEM_CALLS=false
 echo VECI_GENERIC_USSD_CORE_CHANGED=false
 exit 0
fi
mkdir "$LOCK" 2>/dev/null || fail operation_in_progress
trap 'cleanup $?' EXIT
trap 'exit 130' INT TERM
if [ "$MODE" = --rollback ];then
 same "$FILE" "$NEW_SHA" || fail deployed_js_not_matching
 same "$BACKUP" "$OLD_SHA" || fail saved_backup_not_matching
 cp "$BACKUP" "$FILE.restore.$$" || fail restore_copy
 chmod 644 "$FILE.restore.$$" || fail restore_mode
 mv -f "$FILE.restore.$$" "$FILE" || fail restore_activate
 same "$FILE" "$OLD_SHA" || fail restore_sha
 SUCCESS=1
 echo VECI_GENERIC_USSD_UI_ROLLBACK=pass
 exit 0
fi
if [ "$MODE" = --install ] && same "$FILE" "$NEW_SHA";then
 SUCCESS=1
 echo VECI_GENERIC_USSD_UI_UPDATE=already_installed
 exit 0
fi
same "$FILE" "$OLD_SHA" || fail unexpected_live_js
TEMP="$(mktemp /tmp/veci-general-ussd-ui.XXXXXX)" || fail temp_unavailable
wget -qO "$TEMP" "$URL" || fail download_failed
same "$TEMP" "$NEW_SHA" || fail source_sha_mismatch
echo VECI_GENERIC_USSD_UI_SHA256=pass
if [ "$MODE" = --verify ];then
 SUCCESS=1
 echo VECI_GENERIC_USSD_UI_UPDATE=not_installed
 exit 0
fi
if [ -e "$BACKUP" ] || [ -L "$BACKUP" ];then
 same "$BACKUP" "$OLD_SHA" || fail backup_mismatch
else
 cp "$FILE" "$BACKUP" || fail backup_failed
 chmod 600 "$BACKUP" || fail backup_permissions_failed
 same "$BACKUP" "$OLD_SHA" || fail backup_sha_mismatch
fi
cp "$TEMP" "$FILE.stage.$$" || fail stage_failed
chmod 644 "$FILE.stage.$$" || fail stage_permissions_failed
mv -f "$FILE.stage.$$" "$FILE" || fail activate_failed
SWAPPED=1
same "$FILE" "$NEW_SHA" || fail deployed_sha_mismatch
guard
SUCCESS=1
echo VECI_GENERIC_USSD_UI_UPDATE=pass
echo VECI_GENERIC_USSD_UI_ROLLBACK=available
echo VECI_GENERIC_USSD_UI_MODEM_CALLS=false
echo VECI_GENERIC_USSD_CORE_PRESERVED=pass
