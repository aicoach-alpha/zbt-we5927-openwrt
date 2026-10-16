#!/bin/sh
# VeCI WE5927 SMS v1.5.8: responsive Compose SMS layout, UI-only.
# No modem commands, no SMS send/delete, no rpcd/LTE restart.
set -eu
umask 077
LC_ALL=C;export LC_ALL
PIN=ed61636987cccefc36fbf362f4f4753d4e2d9f30
URL=https://raw.githubusercontent.com/aicoach-alpha/zbt-we5927-openwrt
UI=/www/veci/js/pages/cellular.js
RPC=/usr/libexec/rpcd/veci.sms
ACL=/usr/share/rpcd/acl.d/veci-sms-inbox-we5927.json
SWITCH=/etc/veci-sms-feature
SENT=/etc/veci-sms-sent-history
DRAFTS=/etc/veci-sms-drafts
BACKDIR=/root/veci-sms-compose-v158-rollback
BACK=$BACKDIR/cellular.js
OLD_UI=e2bc2010d76cbef1327c8c7dcd372928e8170de835e14afe833799878fc144a5
NEW_UI=66e2475380ef2b1e465f134a06697c7795f771587ba80dfa30dd34096b568686
EXPECTED_RPC=669c6d753f14eb7c8b7d77c1aea28059eb25e20f71511efa301942707f1e0615
EXPECTED_ACL=827fd96f101ece20e6a4e307cc82fb4d3a463989c2cd4b09cdc72cd8d9a2193c
fail(){ printf 'SMS_COMPOSE_V158_ERROR=%s\n' "$1" >&2;exit 1; }
sha(){ sha256sum "$1" 2>/dev/null|awk '{print $1}'; }
board(){
 [ "$(id -u)" = 0 ] || fail root_required
 [ "$(cat /tmp/sysinfo/board_name 2>/dev/null || :)" = zbtlink,zbt-we5927 ] || fail wrong_device
}
status(){
 board
 case "$(sha "$UI")" in
 "$NEW_UI")echo 'SMS_COMPOSE_V158_UI=installed';;
 "$OLD_UI")echo 'SMS_COMPOSE_V158_UI=v157';;
 *)echo 'SMS_COMPOSE_V158_UI=unrecognized';;
 esac
 [ -f "$BACK" ] && [ ! -L "$BACK" ] && echo 'SMS_COMPOSE_V158_BACKUP=present' ||
  echo 'SMS_COMPOSE_V158_BACKUP=absent'
 echo 'SMS_COMPOSE_V158_MODEM_COMMANDS=false'
}
restore(){
 [ -f "$BACK" ] && [ ! -L "$BACK" ] && [ "$(sha "$BACK")" = "$OLD_UI" ] || return 1
 tmp="$UI.restore158.$$"
 cp "$BACK" "$tmp" && chmod 644 "$tmp" &&
  mv -f "$tmp" "$UI" && [ "$(sha "$UI")" = "$OLD_UI" ]
}
apply(){
 board
 for cmd in wget sha256sum awk grep;do
  command -v "$cmd" >/dev/null 2>&1 || fail dependency_missing
 done
 [ -f "$UI" ] && [ ! -L "$UI" ] || fail invalid_ui
 [ -f "$SWITCH" ] && [ ! -L "$SWITCH" ] || fail sms_setting_missing
 [ -f "$SENT" ] && [ ! -L "$SENT" ] || fail sent_history_missing
 [ -f "$DRAFTS" ] && [ ! -L "$DRAFTS" ] || fail drafts_storage_missing
 [ "$(sha "$RPC")" = "$EXPECTED_RPC" ] || fail unexpected_rpc_version
 [ "$(sha "$ACL")" = "$EXPECTED_ACL" ] || fail unexpected_acl_version
 if [ "$(sha "$UI")" = "$NEW_UI" ];then
  echo 'SMS_COMPOSE_V158_ALREADY_INSTALLED_PASS'
  status
  return 0
 fi
 [ "$(sha "$UI")" = "$OLD_UI" ] || fail expected_v157_ui_missing
 [ ! -e "$BACKDIR" ] && [ ! -L "$BACKDIR" ] || fail existing_backup
 setting="$(cat "$SWITCH")"
 case "$setting" in 0|1);;*)fail invalid_sms_setting;;esac
 sent_before="$(sha "$SENT")"
 drafts_before="$(sha "$DRAFTS")"
 temp="$(mktemp -d /tmp/veci-sms158.XXXXXX)" || fail temp_unavailable
 changed=0;complete=0;backup_created=0
 cleanup(){
  code=$?;trap - EXIT
  if [ "$changed" = 1 ] && [ "$complete" != 1 ];then
   restore && echo 'SMS_COMPOSE_V158_AUTO_ROLLBACK=PASS' >&2 ||
    echo 'SMS_COMPOSE_V158_AUTO_ROLLBACK=manual_review_needed' >&2
  elif [ "$backup_created" = 1 ] && [ "$changed" = 0 ];then
   rm -rf "$BACKDIR"
  fi
  rm -rf "$temp";exit "$code"
 }
 trap cleanup EXIT
 trap 'exit 130' INT TERM
 wget -qO "$temp/ui" "$URL/$PIN/scripts/veci-sms-mifi-v15-staged/cellular.js" || fail download
 [ "$(sha "$temp/ui")" = "$NEW_UI" ] || fail ui_checksum_mismatch
 grep -Fq 'veci-sms-center-v158-styles' "$temp/ui" || fail styles_missing
 grep -Fq '#cellular-sms-compose:not([hidden])' "$temp/ui" || fail compose_grid_missing
 grep -Fq "api.call('veci.sms','sendMessage'" "$temp/ui" || fail live_send_missing
 grep -Fq "api.call('veci.sms','saveDraft'" "$temp/ui" || fail live_drafts_missing
 [ "$(sha "$UI")" = "$OLD_UI" ] || fail concurrent_ui_change
 mkdir -m 700 "$BACKDIR" || fail backup_creation
 backup_created=1
 cp -p "$UI" "$BACK" || fail backup_copy
 chmod 600 "$BACK" || fail backup_permissions
 [ "$(sha "$BACK")" = "$OLD_UI" ] || fail backup_checksum
 cp "$temp/ui" "$UI.new158.$$" || fail stage_copy
 chmod 644 "$UI.new158.$$" || fail stage_mode
 [ "$(sha "$UI")" = "$OLD_UI" ] || fail concurrent_ui_change
 changed=1
 mv -f "$UI.new158.$$" "$UI" || fail install
 [ "$(sha "$UI")" = "$NEW_UI" ] || fail installed_checksum
 [ "$(cat "$SWITCH")" = "$setting" ] || fail sms_setting_changed
 [ "$(sha "$SENT")" = "$sent_before" ] || fail sent_changed_during_install
 [ "$(sha "$DRAFTS")" = "$drafts_before" ] || fail drafts_changed_during_install
 complete=1
 echo 'SMS_COMPOSE_V158_RESPONSIVE_UI_LIVE_INSTALL_PASS'
 echo 'SMS_COMPOSE_V158_SMS_SEND_DRAFTS_PRESERVED_PASS'
 echo 'SMS_COMPOSE_V158_NO_MODEM_OR_RPCD_RESTART=true'
 status
}
rollback(){
 board
 [ "$(sha "$UI")" = "$NEW_UI" ] || fail unexpected_ui
 restore || fail backup_invalid
 echo 'SMS_COMPOSE_V158_ROLLBACK_PASS'
 status
}
[ "$#" = 1 ] || fail usage
case "$1" in apply)apply;;status)status;;rollback)rollback;;*)fail action;;esac
