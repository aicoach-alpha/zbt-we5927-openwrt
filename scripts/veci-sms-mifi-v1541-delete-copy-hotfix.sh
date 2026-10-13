#!/bin/sh
# WE5927 SMS v1.5.4.1: Delete AWK keyword bug + HTTP clipboard fallback.
# NO AT/modem calls during install, no SMS deletion, no LTE/rpcd restart.
set -eu
umask 077
LC_ALL=C;export LC_ALL
PIN=b72d4ed9e419a5665c2d6e816405ca7642f66f6a
URL=https://raw.githubusercontent.com/aicoach-alpha/zbt-we5927-openwrt
UI=/www/veci/js/pages/cellular.js
WORKER=/usr/libexec/veci-sms-delete-one
SETTING=/etc/veci-sms-feature
BACK=/root/veci-sms-mifi-v153-rollback/v1541-delete-copy
OLD_UI=691c2bf4cb157258e970f1e93d3ab5c65947a2b86a64eacb16de8b9dcde0dbaa
OLD_WORKER=5e32de1aa289699c23daea5f6c6669b2d5e8fdfd3641c848611237c7d056cdda
NEW_UI=5161c9c7a2a270dc8dfa9124d6299aa125e78defbd04de257a7c750eaab9a776
NEW_WORKER=4a735bffbd92bfa36e27b4f928286df1c0a43b0b2864c12c74947ab4a7fad926
fail(){ printf 'VECI_SMS_V1541_ERROR=%s\n' "$1" >&2;exit 1;}
sha(){ sha256sum "$1" 2>/dev/null|awk '{print $1}';}
board(){
 [ "$(id -u)" -eq 0 ] || fail root_required
 [ "$(cat /tmp/sysinfo/board_name 2>/dev/null || :)" = zbtlink,zbt-we5927 ] || fail wrong_router
}
state(){
 [ -f "$SETTING" ] && [ ! -L "$SETTING" ] || fail sms_setting_missing
 state_now="$(cat "$SETTING" 2>/dev/null || :)"
 case "$state_now" in 0|1);;*)fail invalid_sms_setting;;esac
}
status(){
 board
 if [ "$(sha "$UI")" = "$NEW_UI" ] && [ "$(sha "$WORKER")" = "$NEW_WORKER" ];then
  echo 'VECI_SMS_V1541_FILES=installed'
 elif [ "$(sha "$UI")" = "$OLD_UI" ] && [ "$(sha "$WORKER")" = "$OLD_WORKER" ];then
  echo 'VECI_SMS_V1541_FILES=older_v154'
 else
  echo 'VECI_SMS_V1541_FILES=unknown'
 fi
 [ -f "$BACK/ui" ] && echo 'VECI_SMS_V1541_BACKUP=present' || echo 'VECI_SMS_V1541_BACKUP=absent'
 [ -f "$SETTING" ] && echo 'VECI_SMS_ON_OFF=preserved' || echo 'VECI_SMS_ON_OFF=missing'
 echo 'NO_MODEM_COMMAND_OR_SERVICE_RESTART=true'
}
atomic(){
 from="$1";to="$2";mode="$3"
 tmp="$to.new1541.$$"
 cp "$from" "$tmp" && chmod "$mode" "$tmp" && mv -f "$tmp" "$to"
}
restore(){
 [ -f "$BACK/SHA256SUMS" ] || return 1
 (cd "$BACK" && sha256sum -c SHA256SUMS >/dev/null 2>&1) || return 1
 [ "$(sha "$BACK/ui")" = "$OLD_UI" ] || return 1
 [ "$(sha "$BACK/worker")" = "$OLD_WORKER" ] || return 1
 atomic "$BACK/worker" "$WORKER" 700 &&
 atomic "$BACK/ui" "$UI" 644 &&
 [ "$(sha "$WORKER")" = "$OLD_WORKER" ] &&
 [ "$(sha "$UI")" = "$OLD_UI" ]
}
apply(){
 board
 state
 [ -f "$UI" ] && [ ! -L "$UI" ] || fail ui_unexpected
 [ -f "$WORKER" ] && [ ! -L "$WORKER" ] || fail worker_unexpected
 [ -d /root/veci-sms-mifi-v153-rollback ] && [ ! -L /root/veci-sms-mifi-v153-rollback ] || fail backup_dir_missing
 if [ "$(sha "$UI")" = "$NEW_UI" ] && [ "$(sha "$WORKER")" = "$NEW_WORKER" ];then
  echo 'VECI_SMS_V1541_ALREADY_INSTALLED_PASS';status;return
 fi
 [ "$(sha "$UI")" = "$OLD_UI" ] || fail old_ui_hash_mismatch
 [ "$(sha "$WORKER")" = "$OLD_WORKER" ] || fail old_worker_hash_mismatch
 [ ! -e "$BACK" ] && [ ! -L "$BACK" ] || fail backup_exists
 for tool in wget sha256sum awk grep;do
  command -v "$tool" >/dev/null 2>&1 || fail missing_dependency
 done
 setting_before="$state_now"
 staged="$(mktemp -d /tmp/veci-v1541.XXXXXX)" || fail tmp_failed
 changed=0;complete=0;made_backup=0
 cleanup(){
  rc=$?;trap - EXIT
  if [ "$changed" = 1 ] && [ "$complete" != 1 ];then
   echo 'VECI_SMS_V1541_ROLLBACK=started' >&2
   restore && echo 'VECI_SMS_V1541_ROLLBACK=PASS' >&2 ||
    echo 'VECI_SMS_V1541_ROLLBACK=manual_recovery_required' >&2
  elif [ "$made_backup" = 1 ] && [ "$changed" = 0 ];then
   rm -rf "$BACK"
  fi
  rm -rf "$staged";exit "$rc"
 }
 trap cleanup EXIT
 trap 'exit 130' INT TERM
 wget -qO "$staged/ui" "$URL/$PIN/scripts/veci-sms-mifi-v15-staged/cellular.js" || fail ui_download
 wget -qO "$staged/worker" "$URL/$PIN/scripts/veci-sms-mifi-v153-staged/veci-sms-delete-one" || fail worker_download
 [ "$(sha "$staged/ui")" = "$NEW_UI" ] || fail ui_checksum
 [ "$(sha "$staged/worker")" = "$NEW_WORKER" ] || fail worker_checksum
 sh -n "$staged/worker" || fail worker_syntax
 grep -Fq "document.execCommand('copy')" "$staged/ui" || fail copy_fallback_absent
 grep -Fq 'awk -v slot_id="$slot"' "$staged/worker" || fail parser_fix_absent
 if grep -Fq 'awk -v index=' "$staged/worker";then fail reserved_awk_keyword;fi
 [ "$(sha "$UI")" = "$OLD_UI" ] && [ "$(sha "$WORKER")" = "$OLD_WORKER" ] || fail concurrent_change
 mkdir "$BACK" || fail backup_creation
 made_backup=1
 cp -p "$UI" "$BACK/ui" || fail backup_ui
 cp -p "$WORKER" "$BACK/worker" || fail backup_worker
 (cd "$BACK" && sha256sum ui worker > SHA256SUMS) || fail backup_manifest
 (cd "$BACK" && sha256sum -c SHA256SUMS >/dev/null 2>&1) || fail backup_corrupt
 changed=1
 atomic "$staged/worker" "$WORKER" 700 || fail worker_install
 atomic "$staged/ui" "$UI" 644 || fail ui_install
 [ "$(sha "$WORKER")" = "$NEW_WORKER" ] && [ "$(sha "$UI")" = "$NEW_UI" ] || fail installed_hash
 [ "$(cat "$SETTING")" = "$setting_before" ] || fail sms_setting_changed
 complete=1
 echo 'VECI_SMS_V1541_DELETE_PARSER_INSTALLED_PASS'
 echo 'VECI_SMS_V1541_COPY_HTTP_FALLBACK_INSTALLED_PASS'
 echo 'VECI_SMS_V1541_SMS_TOGGLE_PRESERVED_PASS'
 echo 'VECI_SMS_V1541_NO_MODEM_COMMAND_DURING_INSTALL=true'
 status
}
rollback(){
 board
 [ "$(sha "$UI")" = "$NEW_UI" ] && [ "$(sha "$WORKER")" = "$NEW_WORKER" ] || fail unexpected_ui_or_worker
 restore || fail backup_corrupt
 echo 'VECI_SMS_V1541_ROLLBACK_PASS'
 status
}
[ "$#" -eq 1 ] || fail usage_apply_status_rollback
case "$1" in apply)apply;;status)status;;rollback)rollback;;*)fail action;;esac
