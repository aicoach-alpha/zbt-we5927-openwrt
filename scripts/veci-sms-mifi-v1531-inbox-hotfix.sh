#!/bin/sh
# VeCI WE5927 v1.5.3.1 hotfix: fix rpcd SMS Inbox response format only.
# No SMS AT commands, no LTE, SIM, UI, delete worker or modem modification.
set -eu
umask 077
LC_ALL=C; export LC_ALL
PIN=9542706fb9fb813698163cb8146c4bd2067ce158
URL=https://raw.githubusercontent.com/aicoach-alpha/zbt-we5927-openwrt
SOURCE=scripts/veci-sms-mifi-v15-staged/rpcd-veci.sms
LIVE=/usr/libexec/rpcd/veci.sms
BACK=/root/veci-sms-mifi-v153-rollback/rpc-before-storage-fix
OLD=b4f9ae924f66b44d65d8df663bfbac76d828abc801af6cc8929b9e179f37a505
NEW=0e13a208bbf83562b43ce924ea4c002574560dd28f9228edf7137268e26c11e7
fail(){ printf 'VECI_SMS_V1531_ERROR=%s\n' "$1" >&2; exit 1; }
sha(){ sha256sum "$1" 2>/dev/null | awk '{print $1}'; }
board(){
 [ "$(id -u)" = 0 ] || fail root_required
 [ "$(cat /tmp/sysinfo/board_name 2>/dev/null || :)" = zbtlink,zbt-we5927 ] || fail wrong_router
}
registered(){
 ubus -S list 2>/dev/null | grep -qx 'veci.sms' &&
 ubus -S list 2>/dev/null | grep -qx 'veci.cellular'
}
restart_rpc(){
 /etc/init.d/rpcd restart >/dev/null 2>&1 || return 1
 n=0
 while [ "$n" -lt 12 ]; do
  if registered;then return 0;fi
  n=$((n+1));sleep 1
 done
 return 1
}
anonymous_denied(){
 for method in listMessages deleteMessage; do
  result="$(ubus call session access "{\"ubus_rpc_session\":\"00000000000000000000000000000000\",\"scope\":\"ubus\",\"object\":\"veci.sms\",\"function\":\"$method\"}" 2>/dev/null)" || return 1
  access="$(printf '%s' "$result" | jsonfilter -e '@.access' 2>/dev/null || :)"
  [ "$access" = false ] || [ "$access" = 0 ] || return 1
 done
}
status(){
 board
 case "$(sha "$LIVE" || :)" in
  "$NEW") echo 'VECI_SMS_STORAGE_RESPONSE_FIX=installed' ;;
  "$OLD") echo 'VECI_SMS_STORAGE_RESPONSE_FIX=old_broken_v153' ;;
  *) echo 'VECI_SMS_STORAGE_RESPONSE_FIX=unknown' ;;
 esac
 [ -f "$BACK" ] && echo 'VECI_SMS_STORAGE_RESPONSE_BACKUP=present' || echo 'VECI_SMS_STORAGE_RESPONSE_BACKUP=absent'
 registered && echo 'VECI_SMS_RPC=registered' || echo 'VECI_SMS_RPC=not_ready'
 echo 'MODEM_COMMANDS_EXECUTED=false'
}
atomic_restore(){
 [ -f "$BACK" ] && [ ! -L "$BACK" ] && [ "$(sha "$BACK")" = "$OLD" ] || return 1
 cp "$BACK" "$LIVE.restore.$$" &&
 chmod 755 "$LIVE.restore.$$" &&
 mv -f "$LIVE.restore.$$" "$LIVE" &&
 [ "$(sha "$LIVE")" = "$OLD" ]
}
apply(){
 board
 [ -f "$LIVE" ] && [ ! -L "$LIVE" ] || fail missing_or_symlink_rpc
 [ -x /etc/init.d/rpcd ] || fail missing_rpcd
 [ -f /etc/veci-sms-feature ] && [ ! -L /etc/veci-sms-feature ] || fail sms_feature_missing
 for tool in wget awk grep sha256sum ubus jsonfilter; do
  command -v "$tool" >/dev/null 2>&1 || fail missing_dependency
 done
 if [ "$(sha "$LIVE")" = "$NEW" ];then
  echo 'VECI_SMS_V1531_ALREADY_LIVE_PASS'
  status
  return
 fi
 [ "$(sha "$LIVE")" = "$OLD" ] || fail unexpected_installed_rpc
 [ -d /root/veci-sms-mifi-v153-rollback ] && [ ! -L /root/veci-sms-mifi-v153-rollback ] || fail v153_backup_missing
 [ ! -e "$BACK" ] && [ ! -L "$BACK" ] || fail preexisting_hotfix_backup
 registered || fail sms_rpc_not_registered
 # The actual SMS ON/OFF setting must remain untouched.
 original_setting="$(cat /etc/veci-sms-feature 2>/dev/null || :)"
 case "$original_setting" in 0|1);; *)fail bad_sms_setting;;esac
 temp="$(mktemp -d /tmp/veci-v1531.XXXXXX)" || fail staging
 changed=0;completed=0;backup_created=0
 cleanup(){
  rc=$?
  trap - EXIT
  if [ "$changed" = 1 ] && [ "$completed" != 1 ]; then
   echo 'VECI_SMS_V1531_AUTOMATIC_ROLLBACK=started' >&2
   if atomic_restore && restart_rpc;then
    echo 'VECI_SMS_V1531_AUTOMATIC_ROLLBACK=PASS' >&2
   else
    echo 'VECI_SMS_V1531_AUTOMATIC_ROLLBACK=manual_recovery_required' >&2
   fi
  elif [ "$backup_created" = 1 ] && [ "$changed" != 1 ]; then
   rm -f "$BACK"
  fi
  rm -rf "$temp";exit "$rc"
 }
 trap cleanup EXIT
 trap 'exit 130' INT TERM
 wget -qO "$temp/new-rpc" "$URL/$PIN/$SOURCE" || fail download
 [ "$(sha "$temp/new-rpc")" = "$NEW" ] || fail sha_mismatch
 sh -n "$temp/new-rpc" || fail rpc_shell_syntax
 for store in SM ME MT;do
   grep -Fq "\"storage\":\"$store\",\"count\":" "$temp/new-rpc" || fail missing_storage_response_fix
 done
 [ "$(sha "$LIVE")" = "$OLD" ] || fail concurrent_rpc_change
 cp -p "$LIVE" "$BACK" || fail backup
 backup_created=1
 chmod 600 "$BACK" || fail backup_permissions
 [ "$(sha "$BACK")" = "$OLD" ] || fail backup_checksum
 cp "$temp/new-rpc" "$LIVE.newv1531.$$" || fail stage_write
 chmod 755 "$LIVE.newv1531.$$" || fail stage_mode
 [ "$(sha "$LIVE")" = "$OLD" ] || fail concurrent_rpc_change
 changed=1
 mv -f "$LIVE.newv1531.$$" "$LIVE" || fail replace
 [ "$(sha "$LIVE")" = "$NEW" ] || fail installed_checksum
 restart_rpc || fail rpcd_restart
 anonymous_denied || fail anonymous_access
 [ "$(cat /etc/veci-sms-feature)" = "$original_setting" ] || fail sms_toggle_changed
 completed=1
 echo 'VECI_SMS_V1531_INBOX_RESPONSE_LIVE_PASS'
 echo 'VECI_SMS_V1531_ANONYMOUS_DENIED_PASS'
 echo 'VECI_SMS_V1531_SMS_SETTING_PRESERVED_PASS'
 echo 'VECI_SMS_V1531_NO_MODEM_COMMAND_DURING_INSTALL=true'
 status
}
rollback(){
 board
 [ "$(sha "$LIVE")" = "$NEW" ] || fail unexpected_rpc
 atomic_restore || fail backup_corrupt
 restart_rpc || fail rpcd_restart
 echo 'VECI_SMS_V1531_ROLLBACK_PASS'
 status
}
[ "$#" -eq 1 ] || fail usage
case "$1" in apply)apply;;rollback)rollback;;status)status;;*)fail unknown_action;;esac
