#!/bin/sh
# VeCI SMS v1.5.6 Sent Messages: 30 bounded, private router-persisted records.
# Does not send/delete/read modem SMS on install; preserves live Inbox/Send.
set -eu
umask 077
LC_ALL=C;export LC_ALL
PIN=6af65479de50a602ee1daf796153a7c03f8d9dc4
RAW=https://raw.githubusercontent.com/aicoach-alpha/zbt-we5927-openwrt
UI=/www/veci/js/pages/cellular.js
RPC=/usr/libexec/rpcd/veci.sms
ACL=/usr/share/rpcd/acl.d/veci-sms-inbox-we5927.json
HELP=/usr/libexec/veci-sms-sent-history
STORE=/etc/veci-sms-sent-history
SWITCH=/etc/veci-sms-feature
BACK=/root/veci-sms-sent-v156-rollback
OLD_UI=3be28a22f950d08eeb1252b2d707350da71e17547674465f844f6cd472656566
OLD_RPC=1492dba6c60db9a79ed520f79cf4c261546c957f89c0dabab817409ada387691
OLD_ACL=131c440e658b3233e9ab202e57de0331b7266bab90d3278ea4d24c218a988985
NEW_UI=f4740513068b7e96734b4ef9059d1ce840df780eb326aa8510e53438063f3253
NEW_RPC=ffe1f036b97f14a28476ec79faa3c223c0bba062b8f13e117620820455a10532
NEW_ACL=ab7df6175c5f9675d6a5787cdcc0fc619b62905d0d2e72458f9e04fea207eb83
NEW_HELP=dc2a5a04d192561ea531463e7e809992f325bee6b6ecf88834f5c75ac95760cc
fail(){ printf 'VECI_SMS_SENT_V156_ERROR=%s\n' "$1" >&2;exit 1;}
sha(){ sha256sum "$1" 2>/dev/null | awk '{print $1}'; }
board(){
 [ "$(id -u)" -eq 0 ] || fail root_required
 [ "$(cat /tmp/sysinfo/board_name 2>/dev/null || :)" = zbtlink,zbt-we5927 ] || fail wrong_router
}
old(){
 [ "$(sha "$UI")" = "$OLD_UI" ] &&
 [ "$(sha "$RPC")" = "$OLD_RPC" ] &&
 [ "$(sha "$ACL")" = "$OLD_ACL" ] &&
 [ ! -e "$HELP" ] && [ ! -L "$HELP" ] &&
 [ ! -e "$STORE" ] && [ ! -L "$STORE" ]
}
new(){
 [ "$(sha "$UI")" = "$NEW_UI" ] &&
 [ "$(sha "$RPC")" = "$NEW_RPC" ] &&
 [ "$(sha "$ACL")" = "$NEW_ACL" ] &&
 [ "$(sha "$HELP")" = "$NEW_HELP" ] &&
 [ -f "$STORE" ] && [ ! -L "$STORE" ]
}
rpc_ready(){
 ubus -S list 2>/dev/null | grep -qx 'veci.sms' &&
 ubus -v list veci.sms 2>/dev/null | grep -q '"getSent"' &&
 ubus -v list veci.sms 2>/dev/null | grep -q '"sendMessage"'
}
restart_rpc(){
 /etc/init.d/rpcd restart >/dev/null 2>&1 || return 1
 n=0
 while [ "$n" -lt 25 ];do
  rpc_ready && return 0
  n=$((n+1));sleep 1
 done
 return 1
}
acl_denied(){
 res="$(ubus call session access '{"ubus_rpc_session":"00000000000000000000000000000000","scope":"ubus","object":"veci.sms","function":"getSent"}' 2>/dev/null)" || return 1
 flag="$(printf '%s' "$res" | jsonfilter -e '@.access' 2>/dev/null || :)"
 [ "$flag" = 0 ] || [ "$flag" = false ]
}
atomic(){
 a="$1";b="$2";mode="$3";t="$b.new156.$$"
 cp "$a" "$t" && chmod "$mode" "$t" && mv -f "$t" "$b"
}
restore(){
 [ -f "$BACK/SHA256SUMS" ] || return 1
 (cd "$BACK" && sha256sum -c SHA256SUMS >/dev/null 2>&1) || return 1
 atomic "$BACK/ui" "$UI" 644 &&
 atomic "$BACK/rpc" "$RPC" 755 &&
 atomic "$BACK/acl" "$ACL" 644 || return 1
 rm -f "$HELP" "$STORE" || return 1
 [ "$(sha "$UI")" = "$OLD_UI" ] &&
 [ "$(sha "$RPC")" = "$OLD_RPC" ] &&
 [ "$(sha "$ACL")" = "$OLD_ACL" ]
}
status(){
 board
 if new;then echo 'SMS_SENT_V156_FILES=installed'
 elif old;then echo 'SMS_SENT_V156_FILES=v155'
 else echo 'SMS_SENT_V156_FILES=unknown';fi
 [ -f "$STORE" ] && echo 'SMS_SENT_V156_HISTORY=present' || echo 'SMS_SENT_V156_HISTORY=absent'
 [ -f "$BACK/ui" ] && echo 'SMS_SENT_V156_BACKUP=present' || echo 'SMS_SENT_V156_BACKUP=absent'
 echo 'SMS_MODEM_COMMAND_DURING_INSTALL=false'
}
apply(){
 board
 if new;then echo 'SMS_SENT_V156_ALREADY_INSTALLED_PASS';status;return;fi
 old || fail expected_v155_live_files_mismatch
 [ ! -e "$BACK" ] && [ ! -L "$BACK" ] || fail backup_exists
 [ -f "$SWITCH" ] && [ ! -L "$SWITCH" ] || fail sms_switch_missing
 original="$(cat "$SWITCH" 2>/dev/null || :)"
 case "$original" in 0|1);;*)fail switch_invalid;;esac
 [ -x /etc/init.d/rpcd ] || fail rpcd_missing
 for cmd in wget sha256sum ubus jsonfilter awk grep;do
  command -v "$cmd" >/dev/null 2>&1 || fail dependency
 done
 available="$(df -k /overlay | awk 'NR==2{print $4}')"
 case "$available" in ''|*[!0-9]*)fail storage_unknown;;esac
 [ "$available" -ge 250 ] || fail insufficient_storage
 temp="$(mktemp -d /tmp/veci-sent156.XXXXXX)" || fail stage
 started=0;complete=0;backup_made=0
 cleanup(){
  rc=$?;trap - EXIT
  if [ "$started" = 1 ] && [ "$complete" != 1 ];then
   echo 'SMS_SENT_V156_AUTO_ROLLBACK=started' >&2
   if restore && /etc/init.d/rpcd restart >/dev/null 2>&1;then
    echo 'SMS_SENT_V156_AUTO_ROLLBACK=PASS' >&2
   else echo 'SMS_SENT_V156_AUTO_ROLLBACK=manual_recovery_required' >&2;fi
  elif [ "$backup_made" = 1 ] && [ "$started" != 1 ];then rm -rf "$BACK"
  fi
  rm -rf "$temp";exit "$rc"
 }
 trap cleanup EXIT
 trap 'exit 130' INT TERM
 wget -qO "$temp/ui" "$RAW/$PIN/scripts/veci-sms-mifi-v15-staged/cellular.js" || fail ui_download
 wget -qO "$temp/rpc" "$RAW/$PIN/scripts/veci-sms-mifi-v15-staged/rpcd-veci.sms" || fail rpc_download
 wget -qO "$temp/acl" "$RAW/$PIN/scripts/veci-sms-mifi-v15-staged/acl.json" || fail acl_download
 wget -qO "$temp/help" "$RAW/$PIN/scripts/veci-sms-mifi-v156-staged/veci-sms-sent-history" || fail history_download
 [ "$(sha "$temp/ui")" = "$NEW_UI" ] || fail ui_hash
 [ "$(sha "$temp/rpc")" = "$NEW_RPC" ] || fail rpc_hash
 [ "$(sha "$temp/acl")" = "$NEW_ACL" ] || fail acl_hash
 [ "$(sha "$temp/help")" = "$NEW_HELP" ] || fail helper_hash
 sh -n "$temp/rpc" && sh -n "$temp/help" || fail syntax
 sh "$temp/rpc" list | jsonfilter -e '@.getSent' >/dev/null 2>&1 || fail rpc_missing_getSent
 grep -Fq "api.call('veci.sms','getSent'" "$temp/ui" || fail ui_missing_getSent
 old || fail concurrent_modification
 mkdir "$BACK" || fail backup_create
 backup_made=1
 cp -p "$UI" "$BACK/ui" && cp -p "$RPC" "$BACK/rpc" &&
 cp -p "$ACL" "$BACK/acl" || fail backup_copy
 (cd "$BACK" && sha256sum ui rpc acl > SHA256SUMS &&
 sha256sum -c SHA256SUMS >/dev/null 2>&1) || fail backup_verify
 started=1
 (umask 077; : > "$STORE") || fail history_create
 chmod 600 "$STORE" || fail history_permissions
 atomic "$temp/help" "$HELP" 700 || fail worker_install
 atomic "$temp/rpc" "$RPC" 755 || fail rpc_install
 atomic "$temp/acl" "$ACL" 644 || fail acl_install
 atomic "$temp/ui" "$UI" 644 || fail ui_install
 new || fail installed_hash
 restart_rpc || fail rpc_registration
 acl_denied || fail anonymous_access
 [ "$(cat "$SWITCH")" = "$original" ] || fail sms_setting_changed
 complete=1
 echo 'SMS_SENT_V156_BACKEND_UI_LIVE_INSTALL_PASS'
 echo 'SMS_SENT_V156_GETSENT_ANONYMOUS_DENIED_PASS'
 echo 'SMS_SENT_V156_SMS_ON_OFF_PRESERVED_PASS'
 echo 'SMS_SENT_V156_EXISTING_MESSAGES_UNCHANGED=true'
 echo 'SMS_SENT_V156_NO_MODEM_COMMAND_DURING_INSTALL=true'
 status
}
rollback(){
 board
 new || fail unexpected_live_files
 restore || fail rollback
 /etc/init.d/rpcd restart >/dev/null 2>&1 || fail rpcd_restart
 echo 'SMS_SENT_V156_ROLLBACK_PASS';status
}
[ "$#" -eq 1 ] || fail usage
case "$1" in apply)apply;;status)status;;rollback)rollback;;*)fail invalid_action;;esac
