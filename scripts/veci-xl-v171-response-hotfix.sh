#!/bin/sh
# VeCI XL v1.7.1: fix rpcd double-JSON + preserve sanitized native errors.
# status | preflight | apply | rollback. NO AT/USSD/SMS, reboot or service restart.
set -eu
umask 077
LC_ALL=C;export LC_ALL
RPC=/usr/libexec/rpcd/veci.ussd
WORKER=/usr/libexec/veci-xl-ussd
BACK=/root/veci-xl-ussd-response-rollback
OLD_RPC=790dd1f6e1bf95b6cf01d4fdb3c06dbbec1633962be6ef5d8b58f17b38e235aa
NEW_RPC=07efdc56e7a346793841980f4c1f00674160d7c1769c934b612c43cc19938f99
OLD_WORKER=a15f922315e28c5d17fe165b10aed7d100ff87ad392c11f72a52a07b87c6a886
NEW_WORKER=9c7da0a046a65fc800067efd24af5733611f56efa5ffbf5cfecb4662af1e8960
COMMIT=18954815408e952c085a8a19e97d3a09249f5a30
BASE=https://raw.githubusercontent.com/aicoach-alpha/zbt-we5927-openwrt
fail(){ printf 'VECI_XL_RESPONSE_HOTFIX_ERROR=%s\n' "$1" >&2;exit 1; }
digest(){ sha256sum "$1" 2>/dev/null|awk '{print $1}'; }
board(){
 [ "$(id -u)" = 0 ] || fail root_required
 [ "$(cat /tmp/sysinfo/board_name 2>/dev/null || :)" = zbtlink,zbt-we5927 ] || fail wrong_router
}
safe_path(){
 [ -f "$RPC" ] && [ ! -L "$RPC" ] &&
 [ -f "$WORKER" ] && [ ! -L "$WORKER" ] || fail unsafe_existing_files
}
backup_ok(){
 [ -d "$BACK" ] && [ ! -L "$BACK" ] &&
 [ -f "$BACK/rpc" ] && [ ! -L "$BACK/rpc" ] &&
 [ -f "$BACK/worker" ] && [ ! -L "$BACK/worker" ] &&
 [ "$(digest "$BACK/rpc")" = "$OLD_RPC" ] &&
 [ "$(digest "$BACK/worker")" = "$OLD_WORKER" ]
}
mode(){
 r="$(digest "$RPC")";w="$(digest "$WORKER")"
 if [ "$r" = "$NEW_RPC" ] && [ "$w" = "$NEW_WORKER" ];then echo patched
 elif [ "$r" = "$OLD_RPC" ] && [ "$w" = "$OLD_WORKER" ];then echo original
 else echo unknown_or_partial;fi
}
status(){
 board;safe_path
 echo "VECI_XL_RESPONSE_HOTFIX=$(mode)"
 if backup_ok;then echo "VECI_XL_RESPONSE_BACKUP=verified"
 else echo "VECI_XL_RESPONSE_BACKUP=absent_or_invalid";fi
 echo "SMS_LTE_AND_QUOTA_FILES_CHANGED=false"
 echo "MODEM_COMMANDS=false"
 echo "REBOOT_OR_SERVICE_RESTART=false"
}
install_one(){
 from="$1";to="$2"
 stage="$to.newresponse.$$"
 cp "$from" "$stage" && chmod 700 "$stage" && mv -f "$stage" "$to"
}
restore(){
 backup_ok || return 1
 install_one "$BACK/rpc" "$RPC" &&
 install_one "$BACK/worker" "$WORKER" &&
 [ "$(mode)" = original ]
}
preflight(){
 board;safe_path
 for cmd in flock jsonfilter head sha256sum awk date readlink;do
  command -v "$cmd" >/dev/null 2>&1 || {
   echo "VECI_XL_PREFLIGHT=missing_dependency_$cmd";return 1;
  }
 done
 echo "VECI_XL_PREFLIGHT_DEPENDENCIES=pass"
 if [ ! -c /dev/ttyUSB2 ];then
  echo "VECI_XL_PREFLIGHT=ttyUSB2_missing";return 1
 fi
 port="$(readlink -f /sys/class/tty/ttyUSB2/device 2>/dev/null || :)"
 case "$port" in /sys/devices/*:1.4/ttyUSB2)
  echo "VECI_XL_PREFLIGHT_USB_PATH=expected_pattern";;
  *)echo "VECI_XL_PREFLIGHT_USB_PATH=unexpected_pattern";return 1;;
 esac
 parent="$(dirname "$(dirname "$port")")"
 if [ "$(cat "$parent/idVendor" 2>/dev/null || :)" != 05c6 ] ||
    [ "$(cat "$parent/idProduct" 2>/dev/null || :)" != 902e ];then
  echo "VECI_XL_PREFLIGHT_USB_ID=unexpected";return 1
 fi
 echo "VECI_XL_PREFLIGHT_USB_ID=pass"
 if [ ! -x /usr/sbin/we5927-lte ];then
  echo "VECI_XL_PREFLIGHT=lte_helper_missing";return 1
 fi
 # status-fast is cached-safe; do not expose IMEI, ICCID or raw status JSON.
 snapshot="$(/usr/sbin/we5927-lte status-fast 2>/dev/null)" || {
  echo "VECI_XL_PREFLIGHT=lte_cache_unavailable";return 1;
 }
 sim="$(jsonfilter -s "$snapshot" -e '@.sim' 2>/dev/null || :)"
 operator="$(jsonfilter -s "$snapshot" -e '@.operator' 2>/dev/null || :)"
 case "$sim" in 1|2)echo "VECI_XL_PREFLIGHT_SIM=valid";;
 *)echo "VECI_XL_PREFLIGHT_SIM=invalid";return 1;;esac
 case "$operator" in XL|XL\ *|*XL\ Axiata*|*XL\ SMART*|*XL\ AXIATA*)
  echo "VECI_XL_PREFLIGHT_OPERATOR=xl";;
 *)echo "VECI_XL_PREFLIGHT_OPERATOR=not_xl";return 1;;esac
 if [ -s /tmp/veci-xl-ussd.session ];then
  echo "VECI_XL_PREFLIGHT_SESSION=present"
 else echo "VECI_XL_PREFLIGHT_SESSION=absent";fi
 if command -v pidof >/dev/null 2>&1 &&
    pidof veci-xl-ussd-once >/dev/null 2>&1;then
  echo "VECI_XL_PREFLIGHT_NATIVE=running"
 else echo "VECI_XL_PREFLIGHT_NATIVE=not_running";fi
 echo "VECI_XL_PREFLIGHT=pass_read_only"
}
apply(){
 board;safe_path
 if [ "$(mode)" = patched ];then
  echo "VECI_XL_RESPONSE_HOTFIX_ALREADY_APPLIED_PASS";status;return
 fi
 [ "$(mode)" = original ] || fail unexpected_live_hash
 [ ! -e "$BACK" ] && [ ! -L "$BACK" ] || fail backup_already_exists
 for cmd in wget cp chmod mv mktemp sha256sum awk;do
  command -v "$cmd" >/dev/null 2>&1 || fail missing_dependency
 done
 work="$(mktemp -d /tmp/veci-xl-response.XXXXXX)" || fail temp_failed
 changed=0;finished=0;backup_started=0
 cleanup(){
  rc=$?;trap - EXIT
  if [ "$changed" = 1 ] && [ "$finished" != 1 ];then
   echo 'VECI_XL_RESPONSE_AUTOROLLBACK=started' >&2
   if restore;then echo 'VECI_XL_RESPONSE_AUTOROLLBACK=PASS' >&2
   else echo 'VECI_XL_RESPONSE_AUTOROLLBACK=manual_review_required' >&2;fi
  elif [ "$backup_started" = 1 ] && [ "$changed" != 1 ];then
   rm -rf "$BACK"
  fi
  rm -rf "$work"
  exit "$rc"
 }
 trap cleanup EXIT
 trap 'exit 130' INT TERM
 wget -qO "$work/rpc" "$BASE/$COMMIT/scripts/veci-xl-ussd-v17-staged/rpcd-veci.ussd" ||
  fail rpc_download
 wget -qO "$work/worker" "$BASE/$COMMIT/scripts/veci-xl-ussd-v17-staged/veci-xl-ussd" ||
  fail worker_download
 [ "$(digest "$work/rpc")" = "$NEW_RPC" ] || fail rpc_checksum
 [ "$(digest "$work/worker")" = "$NEW_WORKER" ] || fail worker_checksum
 sh -n "$work/rpc" && sh -n "$work/worker" || fail syntax_invalid
 [ "$(mode)" = original ] || fail changed_during_download
 mkdir -m 700 "$BACK" || fail backup_failed
 backup_started=1
 cp -p "$RPC" "$BACK/rpc" && cp -p "$WORKER" "$BACK/worker" ||
  fail backup_copy
 backup_ok || fail backup_verification
 changed=1
 install_one "$work/rpc" "$RPC" || fail install_rpc
 install_one "$work/worker" "$WORKER" || fail install_worker
 [ "$(mode)" = patched ] || fail installed_checksum
 # Exec plugin scripts are freshly executed for each rpcd call.
 # NO rpcd restart, NO AT/USSD, NO test call to operator.
 finished=1
 echo "VECI_XL_RESPONSE_HOTFIX_LIVE_PASS"
 status
}
rollback(){
 board;safe_path
 [ "$(mode)" = patched ] || fail unknown_live_state
 restore || fail rollback_failed
 echo "VECI_XL_RESPONSE_HOTFIX_ROLLBACK_PASS"
 status
}
[ "$#" -eq 1 ] || fail usage
case "$1" in
 status)status;;preflight)preflight;;apply)apply;;rollback)rollback;;
 *)fail usage;;
esac
