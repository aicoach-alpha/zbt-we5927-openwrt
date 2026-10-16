#!/bin/sh
# VeCI SMS v1.5.2: real receive timestamp/status/multipart UI. Frontend only.
set -eu
umask 077
LC_ALL=C;export LC_ALL
PIN=9d3a9d5fda5104d28dbde3a145e8782d44719ea6
URL=https://raw.githubusercontent.com/aicoach-alpha/zbt-we5927-openwrt
SRC=scripts/veci-sms-mifi-v15-staged/cellular.js
LIVE=/www/veci/js/pages/cellular.js
BACK=/root/veci-sms-mifi-v15-rollback/cellular-before-inbox-v152.js
OLD=990799cb94e78617c5a6ce1000b6ab0dce47508d25cf8c7a735e3f7ee36ddf45
NEW=13f2246b165b6f7a3271dcec1f9599c20fa2aad08d497d092fd9f66d77b91156
fail(){ echo "VECI_SMS_V152_ERROR=$1" >&2;exit 1;}
sha(){ sha256sum "$1" 2>/dev/null|awk '{print $1}';}
board(){
 [ "$(id -u)" -eq 0 ] || fail root_required
 [ "$(cat /tmp/sysinfo/board_name 2>/dev/null || :)" = zbtlink,zbt-we5927 ] || fail wrong_router
}
status(){
 board
 case "$(sha "$LIVE" || :)" in
  "$NEW") echo 'SMS_V152_INBOX_DETAILS=installed';;
  "$OLD") echo 'SMS_V152_INBOX_DETAILS=older_v151';;
  *) echo 'SMS_V152_INBOX_DETAILS=unknown_version';;
 esac
 [ -f "$BACK" ] && echo 'SMS_V152_BACKUP=present' || echo 'SMS_V152_BACKUP=absent'
 echo 'MODEM_COMMANDS_EXECUTED=false'
}
restore(){
 [ "$(sha "$BACK")" = "$OLD" ] || return 1
 cp "$BACK" "$LIVE.restore.$$" && chmod 644 "$LIVE.restore.$$" &&
 mv -f "$LIVE.restore.$$" "$LIVE" && [ "$(sha "$LIVE")" = "$OLD" ]
}
apply(){
 board
 [ -f "$LIVE" ] && [ ! -L "$LIVE" ] || fail invalid_ui
 [ -f /etc/veci-sms-feature ] && [ ! -L /etc/veci-sms-feature ] || fail sms_v15_missing
 [ -d /root/veci-sms-mifi-v15-rollback ] || fail missing_backup_dir
 [ "$(sha "$LIVE")" = "$OLD" ] || {
   [ "$(sha "$LIVE")" = "$NEW" ] && { echo 'SMS_V152_ALREADY_LIVE_PASS';status;return; }
   fail unexpected_live_ui
 }
 [ ! -e "$BACK" ] && [ ! -L "$BACK" ] || fail existing_backup
 tmp="$(mktemp -d /tmp/veci-sms152.XXXXXX)" || fail tmp_failed
 changed=0; success=0
 cleanup(){
  code=$?
  trap - EXIT
  if [ "$changed" = 1 ] && [ "$success" != 1 ];then
   restore && echo 'SMS_V152_AUTOMATIC_ROLLBACK=PASS' >&2 ||
   echo 'SMS_V152_AUTOMATIC_ROLLBACK=manual_recovery_required' >&2
  fi
  rm -rf "$tmp";exit "$code"
 }
 trap cleanup EXIT
 trap 'exit 130' INT TERM
 wget -qO "$tmp/cellular.js" "$URL/$PIN/$SRC" || fail download
 [ "$(sha "$tmp/cellular.js")" = "$NEW" ] || fail downloaded_sha
 grep -Fq 'function formatSmsDate' "$tmp/cellular.js" || fail date_missing
 grep -Fq 'function mergeSmsParts' "$tmp/cellular.js" || fail multipart_missing
 [ "$(sha "$LIVE")" = "$OLD" ] || fail concurrent_ui_edit
 cp -p "$LIVE" "$BACK" || fail backup
 chmod 600 "$BACK" || fail backup_mode
 [ "$(sha "$BACK")" = "$OLD" ] || fail backup_sha
 cp "$tmp/cellular.js" "$LIVE.v152.$$" || fail stage
 chmod 644 "$LIVE.v152.$$" || fail stage_mode
 mv -f "$LIVE.v152.$$" "$LIVE" || fail update
 changed=1
 [ "$(sha "$LIVE")" = "$NEW" ] || fail deployed_sha
 success=1
 echo 'SMS_V152_RECEIVED_TIME_STATUS_MULTIPART_LIVE_PASS'
 echo 'SMS_V152_BACKEND_UNCHANGED=true'
 echo 'NO_MODEM_COMMAND_OR_SERVICE_RESTART=true'
 status
}
rollback(){
 board
 [ "$(sha "$LIVE")" = "$NEW" ] || fail unexpected_ui
 restore || fail restore
 echo 'SMS_V152_ROLLBACK_PASS'
 status
}
[ "$#" -eq 1 ] || fail use_apply_status_rollback
case "$1" in apply)apply;;status)status;;rollback)rollback;;*)fail invalid_action;;esac
