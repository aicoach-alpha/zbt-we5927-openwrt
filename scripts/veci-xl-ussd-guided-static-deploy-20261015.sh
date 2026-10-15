#!/bin/sh
# Signed Core and XL package are PRESERVED. Adds only two SHA256-pinned native
# VeCI static USSD guide files. Never dials, restarts services or touches LuCI.
# Source commit and content hashes are both immutable.
set -eu
umask 077
LC_ALL=C
PATH=/usr/sbin:/usr/bin:/sbin:/bin
export PATH LC_ALL
REV=b412695a088d8cd625b3231f60b8d1fd49d9483c
SOURCE="https://raw.githubusercontent.com/aicoach-alpha/zbt-we5927-openwrt/$REV/source/veci-telco-xl-native/files/www/veci"
HTML_SHA=7878226966d40fbdeea0daab66088660a29c0f5a396b61a5675681594cb84023
JS_SHA=7fe4df1ee56cf64fdc1d04239ee59ffc29b09db3deb51a0b2b657049201874b4
CELL_SHA=b075a4852d3eeb5f717e4db568a0929fc732b225f025a154beb24961a3f85379
CORE_QUOTA_SHA=5c1f66b5a5aa292be202897ef538f67ed7933e857ff3e11bcaabb075b75c692d
HTML=/www/veci/xl-ussd-guide.html
JS=/www/veci/xl-ussd-guide.js
LOCK=/tmp/veci-xl-ussd-guide-install.lock
WORK=
DIRTY=0
DONE=0
fail(){ printf 'VECI_XL_GUIDE=blocked\nVECI_XL_GUIDE_REASON=%s\n' "$1"; exit 1; }
hash(){ sha256sum "$1" | awk '{print $1}'; }
same(){ [ -f "$1" ] && [ ! -L "$1" ] && [ "$(hash "$1")" = "$2" ]; }
absent(){ [ ! -e "$1" ] && [ ! -L "$1" ]; }
board(){
 [ "$(id -u)" = 0 ] || fail root_required
 [ "$(cat /tmp/sysinfo/board_name 2>/dev/null || :)" = zbtlink,zbt-we5927 ] || fail wrong_router
 grep -qx "DISTRIB_RELEASE='25.12.5'" /etc/openwrt_release || fail wrong_firmware
 [ -d /www/veci ] && [ ! -L /www/veci ] || fail veci_dir_missing
 command -v sha256sum >/dev/null 2>&1 || fail sha256sum_missing
}
live_guards(){
 same /www/veci/js/pages/cellular.js "$CELL_SHA" || fail veci_core_modified
 same /www/veci/js/lib/native-quota.js "$CORE_QUOTA_SHA" || fail veci_quota_core_modified
 apk list -I 2>/dev/null | grep -q '^veci-telco-xl-native-0.3.7-' || fail xl_037_missing
 ubus -S list veci.ussd 2>/dev/null | grep -qx 'veci.ussd' || fail xl_ussd_rpc_missing
 ubus -S list veci.xl 2>/dev/null | grep -qx 'veci.xl' || fail xl_native_rpc_missing
 [ -z "$(uci -q get uhttpd.main.listen_http 2>/dev/null || :)" ] || fail http_listener_on
 [ -n "$(uci -q get uhttpd.main.listen_https 2>/dev/null || :)" ] || fail https_listener_missing
}
installed(){ same "$HTML" "$HTML_SHA" && same "$JS" "$JS_SHA"; }
status(){
 if installed; then echo VECI_XL_GUIDE=installed
 elif absent "$HTML" && absent "$JS"; then echo VECI_XL_GUIDE=not_installed
 else echo VECI_XL_GUIDE=unexpected_or_partial; fi
 echo VECI_XL_GUIDE_CORE_CHANGED=false
 echo VECI_XL_GUIDE_MODEM_CALLS=false
}
cleanup(){
 code="$1"
 trap - EXIT INT TERM
 if [ "$DIRTY" = 1 ] && [ "$DONE" = 0 ]; then
  same "$HTML" "$HTML_SHA" && rm -f "$HTML" || :
  same "$JS" "$JS_SHA" && rm -f "$JS" || :
  echo VECI_XL_GUIDE_INSTALL_ROLLBACK=attempted
 fi
 [ -n "$WORK" ] && [ -d "$WORK" ] && rm -rf "$WORK" || :
 rmdir "$LOCK" 2>/dev/null || :
 exit "$code"
}
fetch_verified(){
 WORK="$(mktemp -d /tmp/veci-xl-guide.XXXXXX)" || fail temp_unavailable
 for item in xl-ussd-guide.html xl-ussd-guide.js; do
  wget -qO "$WORK/$item" "$SOURCE/$item" || fail download_failed
 done
 same "$WORK/xl-ussd-guide.html" "$HTML_SHA" || fail html_sha256_mismatch
 same "$WORK/xl-ussd-guide.js" "$JS_SHA" || fail js_sha256_mismatch
 echo VECI_XL_GUIDE_SHA256=pass
}
[ "$#" -eq 1 ] || fail usage
case "$1" in --status|--verify|--install|--rollback) MODE="$1";; *) fail usage;; esac
board
if [ "$MODE" = --status ]; then status; exit 0; fi
mkdir "$LOCK" 2>/dev/null || fail operation_in_progress
trap 'cleanup $?' EXIT
trap 'exit 130' INT TERM
live_guards
if [ "$MODE" = --rollback ]; then
 installed || fail unexpected_files_cannot_rollback
 rm -f "$HTML" "$JS" || fail rollback_remove_failed
 echo VECI_XL_GUIDE_ROLLBACK=pass
 DONE=1
 exit 0
fi
if [ "$MODE" = --install ] && installed; then
 echo VECI_XL_GUIDE=already_installed
 DONE=1
 exit 0
fi
absent "$HTML" && absent "$JS" || fail existing_unknown_guide_file
free="$(df -k /overlay | awk 'NR==2 {print $4}')"
case "$free" in ''|*[!0-9]*) fail overlay_unknown;; esac
[ "$free" -ge 48 ] || fail overlay_low
fetch_verified
if [ "$MODE" = --verify ]; then
 echo VECI_XL_GUIDE_INSTALL=false
 DONE=1
 exit 0
fi
# File names are new: never overwrite signed APK, Core or existing UI files.
DIRTY=1
cp "$WORK/xl-ussd-guide.html" "$HTML.new.$$" || fail html_stage_failed
cp "$WORK/xl-ussd-guide.js" "$JS.new.$$" || fail js_stage_failed
chmod 644 "$HTML.new.$$" "$JS.new.$$" || fail stage_mode_failed
mv -f "$HTML.new.$$" "$HTML" || fail html_activate_failed
mv -f "$JS.new.$$" "$JS" || fail js_activate_failed
installed || fail asset_verification_failed
live_guards
DONE=1
echo VECI_XL_GUIDE_INSTALL=pass
echo VECI_XL_GUIDE_URL=https://192.168.1.1/veci/xl-ussd-guide.html
echo VECI_XL_GUIDE_CORE_PRESERVED=pass
echo VECI_XL_GUIDE_ROLLBACK=available
echo VECI_XL_GUIDE_MODEM_CALLS=false
