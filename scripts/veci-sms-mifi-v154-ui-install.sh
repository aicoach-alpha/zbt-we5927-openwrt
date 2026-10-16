#!/bin/sh
# VeCI SMS v1.5.4 - SMS card layout, search/filter/copy. UI only.
# No AT/modem commands, SMS deletion, rpcd restart, firmware flash or LTE changes.
set -eu
umask 077
LC_ALL=C; export LC_ALL
PIN=7396c71c43e5c04cf797b5a0aee6326e04707ce6
URL=https://raw.githubusercontent.com/aicoach-alpha/zbt-we5927-openwrt
SOURCE=scripts/veci-sms-mifi-v15-staged/cellular.js
LIVE=/www/veci/js/pages/cellular.js
BACK=/root/veci-sms-mifi-v153-rollback/cellular-before-v154-ui.js
BEFORE=d91cfd149a3680b3a1803207ade311c69f63b794a25f83759eaf55c3a8b3a0f8
AFTER=691c2bf4cb157258e970f1e93d3ab5c65947a2b86a64eacb16de8b9dcde0dbaa
fail(){ printf 'VECI_SMS_V154_ERROR=%s\n' "$1" >&2;exit 1;}
sha(){ sha256sum "$1" 2>/dev/null|awk '{print $1}'; }
board(){
 [ "$(id -u)" -eq 0 ] || fail root_required
 [ "$(cat /tmp/sysinfo/board_name 2>/dev/null || :)" = zbtlink,zbt-we5927 ] || fail wrong_router
}
status(){
 board
 case "$(sha "$LIVE" || :)" in
 "$AFTER")echo 'VECI_SMS_V154_UI=installed';;
 "$BEFORE")echo 'VECI_SMS_V154_UI=older_v153';;
 *)echo 'VECI_SMS_V154_UI=unrecognized';;
 esac
 [ -f "$BACK" ] && echo 'VECI_SMS_V154_BACKUP=present' || echo 'VECI_SMS_V154_BACKUP=absent'
 [ -f /etc/veci-sms-feature ] && echo 'VECI_SMS_SWITCH=preserved' || echo 'VECI_SMS_SWITCH=missing'
 echo 'MODEM_COMMANDS_EXECUTED=false'
}
restore(){
 [ "$(sha "$BACK")" = "$BEFORE" ] || return 1
 cp "$BACK" "$LIVE.rollback.$$" &&
 chmod 644 "$LIVE.rollback.$$" &&
 mv -f "$LIVE.rollback.$$" "$LIVE" &&
 [ "$(sha "$LIVE")" = "$BEFORE" ]
}
apply(){
 board
 [ -f "$LIVE" ] && [ ! -L "$LIVE" ] || fail invalid_live_ui
 [ -d /root/veci-sms-mifi-v153-rollback ] && [ ! -L /root/veci-sms-mifi-v153-rollback ] || fail v153_backup_missing
 [ -f /etc/veci-sms-feature ] && [ ! -L /etc/veci-sms-feature ] || fail sms_setting_missing
 if [ "$(sha "$LIVE")" = "$AFTER" ];then
  echo 'VECI_SMS_V154_ALREADY_LIVE_PASS';status;return
 fi
 [ "$(sha "$LIVE")" = "$BEFORE" ] || fail unexpected_live_ui
 [ ! -e "$BACK" ] && [ ! -L "$BACK" ] || fail preexisting_backup
 for tool in wget sha256sum awk grep; do
  command -v "$tool" >/dev/null 2>&1 || fail missing_dependency
 done
 setting_before="$(cat /etc/veci-sms-feature)" || fail sms_setting_unknown
 work="$(mktemp -d /tmp/veci154.XXXXXX)" || fail staging_failed
 changed=0;completed=0;backup_created=0
 cleanup(){
  rc=$?;trap - EXIT
  if [ "$changed" = 1 ] && [ "$completed" != 1 ];then
   restore && echo 'VECI_SMS_V154_AUTO_ROLLBACK=PASS' >&2 ||
   echo 'VECI_SMS_V154_AUTO_ROLLBACK=manual_recovery_needed' >&2
  elif [ "$backup_created" = 1 ] && [ "$changed" = 0 ];then
   rm -f "$BACK"
  fi
  rm -rf "$work";exit "$rc"
 }
 trap cleanup EXIT
 trap 'exit 130' INT TERM
 wget -qO "$work/new-ui" "$URL/$PIN/$SOURCE" || fail download
 [ "$(sha "$work/new-ui")" = "$AFTER" ] || fail sha_mismatch
 grep -Fq "id=\"cellular-sms-search\"" "$work/new-ui" || fail search_ui_missing
 grep -Fq "smsSearchItems = indexed;" "$work/new-ui" || fail search_index_missing
 grep -Fq "Copy message" "$work/new-ui" || fail copy_ui_missing
 grep -Fq "api.call('veci.sms','deleteMessage'" "$work/new-ui" || fail delete_ui_missing
 [ "$(sha "$LIVE")" = "$BEFORE" ] || fail concurrent_edit
 cp -p "$LIVE" "$BACK" || fail backup
 backup_created=1
 chmod 600 "$BACK" || fail backup_mode
 [ "$(sha "$BACK")" = "$BEFORE" ] || fail backup_hash
 cp "$work/new-ui" "$LIVE.new154.$$" || fail stage
 chmod 644 "$LIVE.new154.$$" || fail stage_mode
 [ "$(sha "$LIVE")" = "$BEFORE" ] || fail concurrent_edit
 changed=1
 mv -f "$LIVE.new154.$$" "$LIVE" || fail replace
 [ "$(sha "$LIVE")" = "$AFTER" ] || fail installed_hash
 [ "$(cat /etc/veci-sms-feature)" = "$setting_before" ] || fail sms_setting_changed
 completed=1
 echo 'VECI_SMS_V154_SEARCH_FILTER_CARDS_LIVE_PASS'
 echo 'VECI_SMS_V154_BACKEND_UNCHANGED=true'
 echo 'VECI_SMS_V154_NO_AT_OR_RPCD_RESTART=true'
 status
}
rollback(){
 board
 [ "$(sha "$LIVE")" = "$AFTER" ] || fail unexpected_ui
 restore || fail backup_integrity
 echo 'VECI_SMS_V154_ROLLBACK_PASS';status
}
[ "$#" -eq 1 ] || fail usage_apply_status_rollback
case "$1" in apply)apply;;status)status;;rollback)rollback;;*)fail invalid_action;;esac
