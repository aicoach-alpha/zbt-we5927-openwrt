#!/bin/sh
# VeCI XL v1.7.1 missing BusyBox od applet — SHA-pinned, one-file hotfix.
# NO modem AT commands, SMS operations, RPC restart or router reboot.
set -eu
umask 077
LC_ALL=C;export LC_ALL
TARGET=/usr/libexec/veci-xl-ussd
BACK=/root/veci-xl-ussd-nood-rollback
OLD=7a8a8d0a64ebb1fd5e74bf7eff069ee3bae05fc3fdfc544b7e99d481a1050fea
NEW=a15f922315e28c5d17fe165b10aed7d100ff87ad392c11f72a52a07b87c6a886
URL=https://raw.githubusercontent.com/aicoach-alpha/zbt-we5927-openwrt/e117318a66a44a9af069dd41faa87678b4ac1964/scripts/veci-xl-ussd-v17-staged/veci-xl-ussd
fail(){ printf 'VECI_XL_OD_HOTFIX_ERROR=%s\n' "$1" >&2;exit 1; }
hash(){ sha256sum "$1" 2>/dev/null|awk '{print $1}'; }
board(){
 [ "$(id -u)" = 0 ] || fail root_required
 [ "$(cat /tmp/sysinfo/board_name 2>/dev/null || :)" = zbtlink,zbt-we5927 ] || fail wrong_router
}
backup_ok(){
 [ -f "$BACK" ] && [ ! -L "$BACK" ] &&
 [ "$(hash "$BACK")" = "$OLD" ]
}
status(){
 board
 case "$(hash "$TARGET")" in
 "$OLD")echo 'VECI_XL_USSD_TOKEN=original_requires_hotfix';;
 "$NEW")echo 'VECI_XL_USSD_TOKEN=patched';;
 *)echo 'VECI_XL_USSD_TOKEN=unknown';;
 esac
 if backup_ok;then echo 'VECI_XL_USSD_TOKEN_BACKUP=verified'
 else echo 'VECI_XL_USSD_TOKEN_BACKUP=absent_or_invalid';fi
 echo 'SMS_AND_LTE_UNCHANGED=true'
 echo 'MODEM_COMMANDS=false'
 echo 'REBOOT_OR_SERVICE_RESTART=false'
}
apply(){
 board
 if [ "$(hash "$TARGET")" = "$NEW" ];then
   echo 'VECI_XL_OD_HOTFIX_ALREADY_APPLIED_PASS';status;return
 fi
 [ "$(hash "$TARGET")" = "$OLD" ] || fail unknown_live_worker
 [ ! -e "$BACK" ] && [ ! -L "$BACK" ] || fail backup_collision
 for x in wget sha256sum awk mktemp cp chmod mv;do command -v "$x" >/dev/null 2>&1 || fail missing_dependency;done
 tmp="$(mktemp /tmp/veci-xl-ussd-nood.XXXXXX)" || fail staging_failed
 backup_created=0;changed=0;finished=0
 cleanup(){
   code=$?;trap - EXIT
   if [ "$changed" = 1 ] && [ "$finished" != 1 ];then
     echo 'VECI_XL_OD_HOTFIX_AUTOROLLBACK=started' >&2
     rest="$TARGET.restore.$$"
     if backup_ok && cp "$BACK" "$rest" &&
        chmod 700 "$rest" && mv -f "$rest" "$TARGET" &&
        [ "$(hash "$TARGET")" = "$OLD" ];then
       echo 'VECI_XL_OD_HOTFIX_AUTOROLLBACK=PASS' >&2
     else
       echo 'VECI_XL_OD_HOTFIX_AUTOROLLBACK=manual_review_required' >&2
     fi
   elif [ "$backup_created" = 1 ] && [ "$changed" != 1 ];then
     rm -f "$BACK"
   fi
   rm -f "$tmp"
   exit "$code"
 }
 trap cleanup EXIT
 trap 'exit 130' INT TERM
 wget -qO "$tmp" "$URL" || fail download_failed
 [ "$(hash "$tmp")" = "$NEW" ] || fail checksum_mismatch
 sh -n "$tmp" || fail syntax_invalid
 grep -Fq 'head -c 32 /dev/urandom | sha256sum' "$tmp" || fail missing_token_fix
 [ "$(hash "$TARGET")" = "$OLD" ] || fail changed_during_download
 cp -p "$TARGET" "$BACK" || fail backup_failed
 backup_created=1
 backup_ok || fail backup_checksum
 changed=1
 stage="$TARGET.newod.$$"
 cp "$tmp" "$stage" && chmod 700 "$stage" && mv -f "$stage" "$TARGET" ||
   fail install_failed
 [ "$(hash "$TARGET")" = "$NEW" ] || fail installed_checksum
 [ -x "$TARGET" ] || fail installed_not_executable
 finished=1
 echo 'VECI_XL_OD_HOTFIX_LIVE_PASS'
 status
}
rollback(){
 board
 [ "$(hash "$TARGET")" = "$NEW" ] || fail unknown_live_worker
 backup_ok || fail backup_invalid
 stage="$TARGET.restore.$$"
 cp "$BACK" "$stage" && chmod 700 "$stage" && mv -f "$stage" "$TARGET" ||
   fail rollback_failed
 [ "$(hash "$TARGET")" = "$OLD" ] || fail rollback_checksum
 echo 'VECI_XL_OD_HOTFIX_ROLLBACK_PASS'
 status
}
[ "$#" -eq 1 ] || fail usage
case "$1" in status)status;;apply)apply;;rollback)rollback;;*)fail usage;;esac
