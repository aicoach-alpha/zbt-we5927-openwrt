#!/bin/sh
# VeCI-only XL USSD guide error visibility: one JavaScript file, pinned SHA256.
# Preserves Core, installed XL APK, modem, SMS and uhttpd. Reversible.
set -eu
umask 077
LC_ALL=C
PATH=/usr/sbin:/usr/bin:/sbin:/bin
export LC_ALL PATH
REV=c55d458ca1a3cc95967297eb8fab285c404c3c89
URL="https://raw.githubusercontent.com/aicoach-alpha/zbt-we5927-openwrt/$REV/source/veci-telco-xl-native/files/www/veci/xl-ussd-guide.js"
OLD_SHA=7fe4df1ee56cf64fdc1d04239ee59ffc29b09db3deb51a0b2b657049201874b4
NEW_SHA=7c3141c0903e8af9b4c45f3faac794dd8bae8daa7029863a1a02821a41fd5e14
HTML_SHA=7878226966d40fbdeea0daab66088660a29c0f5a396b61a5675681594cb84023
CELL_SHA=b075a4852d3eeb5f717e4db568a0929fc732b225f025a154beb24961a3f85379
RPC_SHA=d08edadd38f0d9b992fc54d879eabf9f797bf54df83fa8c8cf7b59e55b9e99ce
FILE=/www/veci/xl-ussd-guide.js
HTML=/www/veci/xl-ussd-guide.html
BACKUP=/root/veci-xl-guide-error-rollback-20261015.js
LOCK=/tmp/veci-xl-guide-error-update.lock
TEMP=
SWAPPED=0
SUCCESS=0
fail(){ printf 'VECI_XL_GUIDE_DIAG_UPDATE=blocked\nVECI_XL_GUIDE_DIAG_REASON=%s\n' "$1"; exit 1; }
hash(){ sha256sum "$1" | awk '{print $1}'; }
same(){ [ -f "$1" ] && [ ! -L "$1" ] && [ "$(hash "$1")" = "$2" ]; }
guard(){
 [ "$(id -u)" = 0 ] || fail root_required
 [ "$(cat /tmp/sysinfo/board_name 2>/dev/null || :)" = zbtlink,zbt-we5927 ] || fail wrong_router
 grep -qx "DISTRIB_RELEASE='25.12.5'" /etc/openwrt_release || fail wrong_firmware
 same "$HTML" "$HTML_SHA" || fail guide_html_modified
 same /www/veci/js/pages/cellular.js "$CELL_SHA" || fail veci_core_modified
 same /usr/libexec/rpcd/veci "$RPC_SHA" || fail core_rpc_modified
 apk list -I 2>/dev/null | grep -q '^veci-telco-xl-native-0.3.7-' || fail xl_native_missing
 ubus -S list veci.ussd 2>/dev/null | grep -qx 'veci.ussd' || fail ussd_rpc_missing
 [ -z "$(uci -q get uhttpd.main.listen_http 2>/dev/null || :)" ] || fail http_listener_enabled
}
cleanup(){
 code="$1"
 trap - EXIT INT TERM
 if [ "$SWAPPED" = 1 ] && [ "$SUCCESS" = 0 ]; then
  if same "$BACKUP" "$OLD_SHA" && same "$FILE" "$NEW_SHA"; then
   cp "$BACKUP" "$FILE.rollback.$$" &&
     chmod 644 "$FILE.rollback.$$" &&
     mv -f "$FILE.rollback.$$" "$FILE" || :
  fi
  echo VECI_XL_GUIDE_DIAG_ROLLBACK=attempted
 fi
 [ -n "$TEMP" ] && [ -f "$TEMP" ] && rm -f "$TEMP" || :
 [ -f "$FILE.next.$" ] && rm -f "$FILE.next.$" || :
 [ -f "$FILE.rollback.$" ] && rm -f "$FILE.rollback.$" || :
 rmdir "$LOCK" 2>/dev/null || :
 exit "$code"
}
[ "$#" -eq 1 ] || fail usage
case "$1" in --status|--verify|--install|--rollback) MODE="$1";; *) fail usage;; esac
guard
if [ "$MODE" = --status ]; then
 if same "$FILE" "$NEW_SHA"; then
  echo VECI_XL_GUIDE_DIAG_UPDATE=installed
 elif same "$FILE" "$OLD_SHA"; then
  echo VECI_XL_GUIDE_DIAG_UPDATE=original
 else
  echo VECI_XL_GUIDE_DIAG_UPDATE=unknown
 fi
 echo VECI_XL_GUIDE_CORE_CHANGED=false
 echo VECI_XL_GUIDE_MODEM_CALLS=false
 exit 0
fi
mkdir "$LOCK" 2>/dev/null || fail operation_in_progress
trap 'cleanup $?' EXIT
trap 'exit 130' INT TERM
if [ "$MODE" = --rollback ]; then
 same "$FILE" "$NEW_SHA" || fail target_not_matching_new
 same "$BACKUP" "$OLD_SHA" || fail immutable_backup_missing_or_changed
 cp "$BACKUP" "$FILE.rollback.$$" || fail rollback_copy
 chmod 644 "$FILE.rollback.$$" || fail rollback_mode
 mv -f "$FILE.rollback.$$" "$FILE" || fail rollback_switch
 same "$FILE" "$OLD_SHA" || fail rollback_digest
 SUCCESS=1
 echo VECI_XL_GUIDE_DIAG_ROLLBACK=pass
 exit 0
fi
if [ "$MODE" = --install ] && same "$FILE" "$NEW_SHA"; then
 SUCCESS=1
 echo VECI_XL_GUIDE_DIAG_UPDATE=already_installed
 exit 0
fi
same "$FILE" "$OLD_SHA" || fail original_guide_modified
TEMP="$(mktemp /tmp/veci-xl-guide-fix.XXXXXX)" || fail temp_file_unavailable
wget -qO "$TEMP" "$URL" || fail verified_source_unavailable
same "$TEMP" "$NEW_SHA" || fail verified_source_sha256_mismatch
echo VECI_XL_GUIDE_DIAG_SHA256=pass
if [ "$MODE" = --verify ]; then
 SUCCESS=1
 echo VECI_XL_GUIDE_DIAG_UPDATE=not_installed
 exit 0
fi
if [ -e "$BACKUP" ] || [ -L "$BACKUP" ]; then
 same "$BACKUP" "$OLD_SHA" || fail existing_backup_mismatch
else
 cp "$FILE" "$BACKUP" || fail backup_copy_failed
 chmod 600 "$BACKUP" || fail backup_chmod_failed
 same "$BACKUP" "$OLD_SHA" || fail backup_integrity_failed
fi
cp "$TEMP" "$FILE.next.$$" || fail stage_copy_failed
chmod 644 "$FILE.next.$$" || fail stage_chmod_failed
mv -f "$FILE.next.$$" "$FILE" || fail stage_activate_failed
SWAPPED=1
same "$FILE" "$NEW_SHA" || fail postinstall_digest_failed
guard
SUCCESS=1
echo VECI_XL_GUIDE_DIAG_UPDATE=pass
echo VECI_XL_GUIDE_CORE_PRESERVED=pass
echo VECI_XL_GUIDE_MODEM_CALLS=false
echo VECI_XL_GUIDE_DIAG_ROLLBACK=available
