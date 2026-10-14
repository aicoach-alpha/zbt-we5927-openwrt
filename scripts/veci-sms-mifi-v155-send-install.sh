#!/bin/sh
# VeCI WE5927 SMS v1.5.5 - real Compose/Reply/Send native transport.
# One-command reversible install. NO modem AT, SMS, SIM or LTE I/O on install.
set -eu
umask 077
LC_ALL=C;export LC_ALL
PIN=72a4f77d68ad38b13c7cd89779efb009f531cc62
RAW=https://raw.githubusercontent.com/aicoach-alpha/zbt-we5927-openwrt
RELEASE=https://github.com/aicoach-alpha/zbt-we5927-openwrt/releases/download/veci-sms-cmgs-e21b3b1bd9ec/veci-sms-cmgs-mipsel
UI=/www/veci/js/pages/cellular.js
RPC=/usr/libexec/rpcd/veci.sms
ACL=/usr/share/rpcd/acl.d/veci-sms-inbox-we5927.json
HELP=/usr/libexec/veci-sms-send-one
BIN=/usr/libexec/veci-sms-cmgs
FLAG=/etc/veci-sms-feature
BACK=/root/veci-sms-send-v1551-rollback
OLD_UI=5161c9c7a2a270dc8dfa9124d6299aa125e78defbd04de257a7c750eaab9a776
OLD_RPC=0e13a208bbf83562b43ce924ea4c002574560dd28f9228edf7137268e26c11e7
OLD_ACL=19bffb2761a74dca2b116383ebcfd7254b0610b0c573108afcafaa3fbd0a104e
NEW_UI=3be28a22f950d08eeb1252b2d707350da71e17547674465f844f6cd472656566
NEW_RPC=1492dba6c60db9a79ed520f79cf4c261546c957f89c0dabab817409ada387691
NEW_ACL=131c440e658b3233e9ab202e57de0331b7266bab90d3278ea4d24c218a988985
NEW_HELP=51c13afc282936ae0e1d06692ce9df2d0a310058499ac6961ba8cd622f55efeb
NEW_BIN=e2f1aef02ed031bbbc70421abcad02426273b196eeec8f5d482004f1f44304de
fail(){ echo "VECI_SMS_SEND_V155_ERROR=$1" >&2;exit 1;}
sha(){ sha256sum "$1" 2>/dev/null|awk '{print $1}'; }
board(){
 [ "$(id -u)" = 0 ] || fail root_required
 [ "$(cat /tmp/sysinfo/board_name 2>/dev/null || :)" = zbtlink,zbt-we5927 ] || fail wrong_router
}
old(){
 [ "$(sha "$UI")" = "$OLD_UI" ] &&
 [ "$(sha "$RPC")" = "$OLD_RPC" ] &&
 [ "$(sha "$ACL")" = "$OLD_ACL" ] &&
 [ ! -e "$HELP" ] && [ ! -L "$HELP" ] &&
 [ ! -e "$BIN" ] && [ ! -L "$BIN" ]
}
new(){
 [ "$(sha "$UI")" = "$NEW_UI" ] &&
 [ "$(sha "$RPC")" = "$NEW_RPC" ] &&
 [ "$(sha "$ACL")" = "$NEW_ACL" ] &&
 [ "$(sha "$HELP")" = "$NEW_HELP" ] &&
 [ "$(sha "$BIN")" = "$NEW_BIN" ]
}
registered(){
 # ubus documents OPTIONS before COMMAND, e.g. "ubus -v list veci.sms".
 # Do not pass -v after list: some builds interpret it as a path.
 ubus -S list 2>/dev/null | grep -qx 'veci.sms' &&
 ubus -S list 2>/dev/null | grep -qx 'veci.cellular' &&
 ubus -v list veci.sms 2>/dev/null | grep -q '"sendMessage"'
}
rpc_diagnostics(){
 # Only boolean registration probes; never show sessions, phone numbers,
 # SMS contents, credentials or full RPC responses.
 if ubus -S list 2>/dev/null | grep -qx 'veci.sms';then
  echo 'SMS_SEND_RPC_OBJECT=present'
 else echo 'SMS_SEND_RPC_OBJECT=missing';fi
 if ubus -S list 2>/dev/null | grep -qx 'veci.cellular';then
  echo 'SMS_CELLULAR_RPC_OBJECT=present'
 else echo 'SMS_CELLULAR_RPC_OBJECT=missing';fi
 if ubus -v list veci.sms 2>/dev/null | grep -q '"sendMessage"';then
  echo 'SMS_SEND_RPC_METHOD=registered'
 else echo 'SMS_SEND_RPC_METHOD=missing';fi
}
anonymous_denied(){
 for method in sendMessage deleteMessage listMessages; do
  response="$(ubus call session access "{\"ubus_rpc_session\":\"00000000000000000000000000000000\",\"scope\":\"ubus\",\"object\":\"veci.sms\",\"function\":\"$method\"}" 2>/dev/null)" || return 1
  access="$(printf '%s' "$response" | jsonfilter -e '@.access' 2>/dev/null || :)"
  [ "$access" = 0 ] || [ "$access" = false ] || return 1
 done
}
restart_rpc(){
 /etc/init.d/rpcd restart >/dev/null 2>&1 || return 1
 attempts=0
 while [ "$attempts" -lt 25 ]; do
  registered && return 0
  attempts=$((attempts+1)); sleep 1
 done
 return 1
}
atomic(){
 a="$1";b="$2";mode="$3";temp="$b.newv155.$$"
 cp "$a" "$temp" && chmod "$mode" "$temp" && mv -f "$temp" "$b"
}
restore(){
 [ -f "$BACK/SHA256SUMS" ] || return 1
 (cd "$BACK" && sha256sum -c SHA256SUMS >/dev/null 2>&1) || return 1
 [ "$(sha "$BACK/ui")" = "$OLD_UI" ] &&
 [ "$(sha "$BACK/rpc")" = "$OLD_RPC" ] &&
 [ "$(sha "$BACK/acl")" = "$OLD_ACL" ] || return 1
 atomic "$BACK/ui" "$UI" 644 &&
 atomic "$BACK/rpc" "$RPC" 755 &&
 atomic "$BACK/acl" "$ACL" 644 || return 1
 rm -f "$HELP" "$BIN" || return 1
 [ "$(sha "$RPC")" = "$OLD_RPC" ] && [ "$(sha "$UI")" = "$OLD_UI" ]
}
status(){
 board
 if new;then echo 'SMS_SEND_V155_FILES=installed'
 elif old;then echo 'SMS_SEND_V155_FILES=v1541'
 else echo 'SMS_SEND_V155_FILES=unrecognized';fi
 [ -f "$FLAG" ] && [ ! -L "$FLAG" ] && echo 'SMS_ON_OFF=preserved' || echo 'SMS_ON_OFF=unavailable'
 [ -f "$BACK/ui" ] && echo 'SMS_SEND_V155_BACKUP=present' || echo 'SMS_SEND_V155_BACKUP=absent'
 echo 'SMS_MODEM_COMMAND_DURING_INSTALL=false'
}
apply(){
 board
 if new;then echo 'SMS_SEND_V155_ALREADY_LIVE_FILES_PASS';status;return;fi
 old || fail expected_v1541_files_not_present
 [ ! -e "$BACK" ] && [ ! -L "$BACK" ] || fail backup_already_exists
 [ -f "$FLAG" ] && [ ! -L "$FLAG" ] || fail sms_feature_missing
 state="$(cat "$FLAG" 2>/dev/null || :)"
 case "$state" in 0|1);;*)fail invalid_sms_setting;;esac
 for command in wget sha256sum awk grep flock ubus jsonfilter uci;do
  command -v "$command" >/dev/null 2>&1 || fail missing_dependency
 done
 [ -x /etc/init.d/rpcd ] || fail no_rpcd
 ubus -S list 2>/dev/null | grep -qx 'veci.sms' || fail no_sms_rpc
 # Require the same authenticated uhttpd bridge already used by SMS Inbox.
 uci -q show uhttpd >/dev/null 2>&1 || fail uhttpd_unavailable
 if uci -q show uhttpd | awk -F= '$1 ~ /\.no_ubusauth$/ {
   v=$2;gsub(/[^[:alnum:]]/,"",v);
   if(v=="1"||v=="yes"||v=="true")bad=1
 } END{exit !bad}';then fail uhttpd_noauth_enabled;fi
 pids="$(pidof uhttpd 2>/dev/null || :)"
 [ -n "$pids" ] || fail uhttpd_missing
 for pid in $pids;do
  [ -r "/proc/$pid/cmdline" ] || fail uhttpd_unknown
  if tr '\000' '\n' < "/proc/$pid/cmdline" | grep -qx -- '-a';then
   fail uhttpd_noauth_enabled
  fi
 done
 free="$(df -k /overlay | awk 'NR==2{print $4}')"
 case "$free" in ''|*[!0-9]*)fail overlay_unknown;;esac
 [ "$free" -ge 300 ] || fail insufficient_overlay
 work="$(mktemp -d /tmp/veci-v155.XXXXXX)" || fail stage_failed
 changed=0;done_ok=0;back_created=0
 cleanup(){
  rc=$?;trap - EXIT
  if [ "$changed" = 1 ] && [ "$done_ok" != 1 ];then
   echo 'SMS_SEND_V155_AUTOMATIC_ROLLBACK=started' >&2
   restore && /etc/init.d/rpcd restart >/dev/null 2>&1 &&
    echo 'SMS_SEND_V155_AUTOMATIC_ROLLBACK=PASS' >&2 ||
    echo 'SMS_SEND_V155_AUTOMATIC_ROLLBACK=manual_review_required' >&2
  elif [ "$back_created" = 1 ] && [ "$changed" = 0 ];then
   rm -rf "$BACK"
  fi
  rm -rf "$work";exit "$rc"
 }
 trap cleanup EXIT
 trap 'exit 130' INT TERM
 wget -qO "$work/ui" "$RAW/$PIN/scripts/veci-sms-mifi-v15-staged/cellular.js" || fail ui_download
 wget -qO "$work/rpc" "$RAW/$PIN/scripts/veci-sms-mifi-v15-staged/rpcd-veci.sms" || fail rpc_download
 wget -qO "$work/acl" "$RAW/$PIN/scripts/veci-sms-mifi-v15-staged/acl.json" || fail acl_download
 wget -qO "$work/help" "$RAW/$PIN/scripts/veci-sms-mifi-v155-staged/veci-sms-send-one" || fail helper_download
 wget -qO "$work/bin" "$RELEASE" || fail mips_binary_download
 [ "$(sha "$work/ui")" = "$NEW_UI" ] || fail ui_checksum
 [ "$(sha "$work/rpc")" = "$NEW_RPC" ] || fail rpc_checksum
 [ "$(sha "$work/acl")" = "$NEW_ACL" ] || fail acl_checksum
 [ "$(sha "$work/help")" = "$NEW_HELP" ] || fail helper_checksum
 [ "$(sha "$work/bin")" = "$NEW_BIN" ] || fail binary_checksum
 sh -n "$work/rpc" && sh -n "$work/help" || fail shell_syntax
 "$({ echo /bin/sh; })" "$work/rpc" list | jsonfilter -e '@.sendMessage.pdu' 2>/dev/null | grep -qx str || fail send_rpc_signature
 grep -Fq "sendMessage" "$work/acl" || fail acl_missing_send
 grep -Fq "buildSmsSubmit" "$work/ui" || fail ui_missing_submit
 grep -Fq "veci-sms-cmgs" "$work/help" || fail helper_missing_binary
 old || fail concurrent_change
 mkdir "$BACK" || fail backup_creation
 back_created=1
 cp -p "$UI" "$BACK/ui" || fail backup_ui
 cp -p "$RPC" "$BACK/rpc" || fail backup_rpc
 cp -p "$ACL" "$BACK/acl" || fail backup_acl
 (cd "$BACK" && sha256sum ui rpc acl > SHA256SUMS) || fail backup_manifest
 (cd "$BACK" && sha256sum -c SHA256SUMS >/dev/null 2>&1) || fail backup_integrity
 changed=1
 atomic "$work/bin" "$BIN" 700 || fail binary_install
 atomic "$work/help" "$HELP" 700 || fail helper_install
 atomic "$work/rpc" "$RPC" 755 || fail rpc_install
 atomic "$work/acl" "$ACL" 644 || fail acl_install
 atomic "$work/ui" "$UI" 644 || fail ui_install
 new || fail installed_checksum
 restart_rpc || { rpc_diagnostics; fail rpc_registration; }
 anonymous_denied || fail anonymous_acl
 [ "$(cat "$FLAG")" = "$state" ] || fail sms_toggle_modified
 done_ok=1
 echo 'SMS_SEND_V155_BACKEND_AND_UI_LIVE_INSTALL_PASS'
 echo 'SMS_SEND_V155_MIPS_BINARY_SHA256_PASS'
 echo 'SMS_SEND_V155_ANONYMOUS_DENIED_PASS'
 echo 'SMS_SEND_V155_ON_OFF_PRESERVED_PASS'
 echo 'SMS_SEND_ACTUAL_MESSAGE=not_sent_during_install'
 echo 'NO_SMS_MODEM_COMMAND_DURING_INSTALL=true'
 status
}
rollback(){
 board
 new || fail unexpected_live_version
 restore || fail rollback_files
 /etc/init.d/rpcd restart >/dev/null 2>&1 || fail rpcd_restart
 echo 'SMS_SEND_V155_ROLLBACK_PASS';status
}
[ "$#" -eq 1 ] || fail usage
case "$1" in apply)apply;;status)status;;rollback)rollback;;*)fail invalid_action;;esac
