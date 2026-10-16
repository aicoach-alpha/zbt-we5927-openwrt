#!/bin/sh
# VeCI WE5927 SMS Drafts v1.5.7 -- SHA-pinned reversible install.
# NO modem AT, no send/delete SMS, no SIM or LTE changes during installation.
set -eu
umask 077
LC_ALL=C;export LC_ALL
PIN=177df4d204d9767208da3d9fcce6198b2c1719a8
RAW=https://raw.githubusercontent.com/aicoach-alpha/zbt-we5927-openwrt
UI=/www/veci/js/pages/cellular.js
RPC=/usr/libexec/rpcd/veci.sms
ACL=/usr/share/rpcd/acl.d/veci-sms-inbox-we5927.json
HELP=/usr/libexec/veci-sms-drafts
STORE=/etc/veci-sms-drafts
SENT=/etc/veci-sms-sent-history
SENT_HELP=/usr/libexec/veci-sms-sent-history
SWITCH=/etc/veci-sms-feature
BACK=/root/veci-sms-drafts-v157-rollback
OLD_UI=f4740513068b7e96734b4ef9059d1ce840df780eb326aa8510e53438063f3253
OLD_RPC=ffe1f036b97f14a28476ec79faa3c223c0bba062b8f13e117620820455a10532
OLD_ACL=ab7df6175c5f9675d6a5787cdcc0fc619b62905d0d2e72458f9e04fea207eb83
NEW_UI=e2bc2010d76cbef1327c8c7dcd372928e8170de835e14afe833799878fc144a5
NEW_RPC=669c6d753f14eb7c8b7d77c1aea28059eb25e20f71511efa301942707f1e0615
NEW_ACL=827fd96f101ece20e6a4e307cc82fb4d3a463989c2cd4b09cdc72cd8d9a2193c
NEW_HELP=44bfc7dfe1e7a10ef15d4a475507ba7a884b1bc94216ab16643254c9e1f0381d
fail(){ printf 'SMS_DRAFTS_V157_ERROR=%s\n' "$1" >&2;exit 1;}
sha(){ sha256sum "$1" 2>/dev/null|awk '{print $1}'; }
board(){
 [ "$(id -u)" = 0 ] || fail root_required
 [ "$(cat /tmp/sysinfo/board_name 2>/dev/null || :)" = zbtlink,zbt-we5927 ] || fail wrong_router
}
old(){
 [ "$(sha "$UI")" = "$OLD_UI" ] &&
 [ "$(sha "$RPC")" = "$OLD_RPC" ] &&
 [ "$(sha "$ACL")" = "$OLD_ACL" ] &&
 [ ! -e "$HELP" ] && [ ! -L "$HELP" ]
}
new(){
 [ "$(sha "$UI")" = "$NEW_UI" ] &&
 [ "$(sha "$RPC")" = "$NEW_RPC" ] &&
 [ "$(sha "$ACL")" = "$NEW_ACL" ] &&
 [ "$(sha "$HELP")" = "$NEW_HELP" ] &&
 [ -f "$STORE" ] && [ ! -L "$STORE" ]
}
ready(){
 ubus -S list 2>/dev/null | grep -qx 'veci.sms' &&
 ubus -v list veci.sms 2>/dev/null | grep -q '"getDrafts"' &&
 ubus -v list veci.sms 2>/dev/null | grep -q '"saveDraft"' &&
 ubus -v list veci.sms 2>/dev/null | grep -q '"deleteDraft"' &&
 ubus -v list veci.sms 2>/dev/null | grep -q '"getSent"' &&
 ubus -v list veci.sms 2>/dev/null | grep -q '"sendMessage"'
}
restart_rpc(){
 /etc/init.d/rpcd restart >/dev/null 2>&1 || return 1
 i=0
 while [ "$i" -lt 25 ];do
  ready && return 0
  i=$((i+1));sleep 1
 done
 return 1
}
anonymous_denied(){
 for method in getDrafts saveDraft deleteDraft;do
  res="$(ubus call session access "{\"ubus_rpc_session\":\"00000000000000000000000000000000\",\"scope\":\"ubus\",\"object\":\"veci.sms\",\"function\":\"$method\"}" 2>/dev/null)" || return 1
  a="$(printf '%s' "$res"|jsonfilter -e '@.access' 2>/dev/null || :)"
  [ "$a" = 0 ] || [ "$a" = false ] || return 1
 done
}
atomic(){
 src="$1";dst="$2";mode="$3"
 tmp="$dst.new157.$$"
 cp "$src" "$tmp" && chmod "$mode" "$tmp" && mv -f "$tmp" "$dst"
}
backup_ok(){
 [ -d "$BACK" ] && [ ! -L "$BACK" ] &&
 [ -f "$BACK/SHA256SUMS" ] &&
 (cd "$BACK" && sha256sum -c SHA256SUMS >/dev/null 2>&1) &&
 [ "$(sha "$BACK/ui")" = "$OLD_UI" ] &&
 [ "$(sha "$BACK/rpc")" = "$OLD_RPC" ] &&
 [ "$(sha "$BACK/acl")" = "$OLD_ACL" ]
}
restore(){
 backup_ok || return 1
 atomic "$BACK/ui" "$UI" 644 &&
 atomic "$BACK/rpc" "$RPC" 755 &&
 atomic "$BACK/acl" "$ACL" 644 || return 1
 rm -f "$HELP" || return 1
 # Draft and Sent files are private USER DATA -- never delete on rollback.
 [ "$(sha "$UI")" = "$OLD_UI" ] && [ "$(sha "$RPC")" = "$OLD_RPC" ]
}
status(){
 board
 if new;then echo 'SMS_DRAFTS_V157_FILES=installed'
 elif old;then echo 'SMS_DRAFTS_V157_FILES=previous_v156'
 else echo 'SMS_DRAFTS_V157_FILES=unrecognized';fi
 [ -f "$STORE" ] && echo 'SMS_DRAFTS_V157_STORAGE=present' || echo 'SMS_DRAFTS_V157_STORAGE=absent'
 [ -f "$SENT" ] && echo 'SMS_SENT_HISTORY=preserved' || echo 'SMS_SENT_HISTORY=missing'
 backup_ok && echo 'SMS_DRAFTS_V157_BACKUP=present' || echo 'SMS_DRAFTS_V157_BACKUP=absent'
 echo 'MODEM_COMMANDS_EXECUTED=false'
}
apply(){
 board
 if new;then echo 'SMS_DRAFTS_V157_ALREADY_LIVE_FILES_PASS';status;return;fi
 old || fail expected_live_v156_files_mismatch
 [ -x "$SENT_HELP" ] && [ -f "$SENT" ] && [ ! -L "$SENT" ] || fail sent_history_missing
 [ -f "$SWITCH" ] && [ ! -L "$SWITCH" ] || fail sms_setting_missing
 [ ! -L "$STORE" ] && { [ ! -e "$STORE" ] || [ -f "$STORE" ]; } || fail invalid_draft_storage
 setting="$(cat "$SWITCH" 2>/dev/null || :)"
 case "$setting" in 0|1);;*)fail invalid_sms_setting;;esac
 sent_hash="$(sha "$SENT")"
 for cmd in wget sha256sum awk grep ubus jsonfilter;do
  command -v "$cmd" >/dev/null 2>&1 || fail missing_dependency
 done
 [ -x /etc/init.d/rpcd ] || fail missing_rpcd
 ubus -S list 2>/dev/null | grep -qx 'veci.sms' || fail sms_rpc_missing
 available="$(df -k /overlay|awk 'NR==2{print $4}')"
 case "$available" in ''|*[!0-9]*)fail storage_unknown;;esac
 [ "$available" -ge 180 ] || fail insufficient_overlay
 work="$(mktemp -d /tmp/veci-drafts157.XXXXXX)" || fail staging_unavailable
 changed=0;complete=0;made_backup=0
 cleanup(){
  rc=$?;trap - EXIT
  if [ "$changed" = 1 ] && [ "$complete" != 1 ];then
   echo 'SMS_DRAFTS_V157_AUTO_ROLLBACK=started' >&2
   if restore && /etc/init.d/rpcd restart >/dev/null 2>&1;then
    echo 'SMS_DRAFTS_V157_AUTO_ROLLBACK=PASS' >&2
   else echo 'SMS_DRAFTS_V157_AUTO_ROLLBACK=manual_recovery_required' >&2;fi
  elif [ "$made_backup" = 1 ] && [ "$changed" != 1 ];then
   rm -rf "$BACK"
  fi
  rm -rf "$work";exit "$rc"
 }
 trap cleanup EXIT
 trap 'exit 130' INT TERM
 wget -qO "$work/ui" "$RAW/$PIN/scripts/veci-sms-mifi-v15-staged/cellular.js" || fail download_ui
 wget -qO "$work/rpc" "$RAW/$PIN/scripts/veci-sms-mifi-v15-staged/rpcd-veci.sms" || fail download_rpc
 wget -qO "$work/acl" "$RAW/$PIN/scripts/veci-sms-mifi-v15-staged/acl.json" || fail download_acl
 wget -qO "$work/helper" "$RAW/$PIN/scripts/veci-sms-mifi-v157-staged/veci-sms-drafts" || fail download_helper
 [ "$(sha "$work/ui")" = "$NEW_UI" ] || fail ui_hash
 [ "$(sha "$work/rpc")" = "$NEW_RPC" ] || fail rpc_hash
 [ "$(sha "$work/acl")" = "$NEW_ACL" ] || fail acl_hash
 [ "$(sha "$work/helper")" = "$NEW_HELP" ] || fail worker_hash
 sh -n "$work/rpc" && sh -n "$work/helper" || fail shell_syntax
 sh "$work/rpc" list | grep -Fq '"saveDraft"' || fail draft_rpc_signature
 grep -Fq "api.call('veci.sms','saveDraft'" "$work/ui" || fail draft_ui_missing
 if [ -e "$BACK" ] || [ -L "$BACK" ];then
  backup_ok || fail preexisting_backup_corrupt
 else
  mkdir "$BACK" || fail backup_creation
  made_backup=1
  cp -p "$UI" "$BACK/ui" && cp -p "$RPC" "$BACK/rpc" &&
   cp -p "$ACL" "$BACK/acl" || fail backup_copy
  (cd "$BACK" && sha256sum ui rpc acl > SHA256SUMS &&
   sha256sum -c SHA256SUMS >/dev/null 2>&1) || fail backup_verify
 fi
 old || fail concurrent_live_change
 changed=1
 if [ ! -e "$STORE" ];then (umask 077; : > "$STORE") || fail create_drafts_storage;fi
 chmod 600 "$STORE" || fail draft_permissions
 atomic "$work/helper" "$HELP" 700 || fail helper_install
 atomic "$work/rpc" "$RPC" 755 || fail rpc_install
 atomic "$work/acl" "$ACL" 644 || fail acl_install
 atomic "$work/ui" "$UI" 644 || fail ui_install
 new || fail deployed_hash_mismatch
 restart_rpc || fail rpc_registration
 anonymous_denied || fail anonymous_acl
 [ "$(cat "$SWITCH")" = "$setting" ] || fail sms_setting_changed
 [ "$(sha "$SENT")" = "$sent_hash" ] || fail sent_history_changed_during_install
 complete=1
 echo 'SMS_DRAFTS_V157_BACKEND_UI_LIVE_INSTALL_PASS'
 echo 'SMS_DRAFTS_V157_ANONYMOUS_DENIED_PASS'
 echo 'SMS_DRAFTS_V157_SMS_ON_OFF_PRESERVED_PASS'
 echo 'SMS_DRAFTS_V157_EXISTING_SENT_PRESERVED_PASS'
 echo 'SMS_DRAFTS_V157_NO_MODEM_COMMAND_DURING_INSTALL=true'
 status
}
rollback(){
 board
 new || fail unexpected_live_files
 restore || fail rollback_files
 /etc/init.d/rpcd restart >/dev/null 2>&1 || fail rpcd_restart
 echo 'SMS_DRAFTS_V157_ROLLBACK_PASS'
 status
}
[ "$#" = 1 ] || fail usage
case "$1" in apply)apply;;status)status;;rollback)rollback;;*)fail invalid_action;;esac
