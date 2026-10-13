#!/bin/sh
# VeCI SMS v1.5.3: storage source and selected-message delete.
# Install NEVER issues modem AT, CMGD, SIM command or reboot.
set -eu
umask 077
LC_ALL=C;export LC_ALL
PIN=848a5ab01f23fd0408325f9ade67cc08056e9d5d
URL=https://raw.githubusercontent.com/aicoach-alpha/zbt-we5927-openwrt
SRC=scripts/veci-sms-mifi-v15-staged
UI=/www/veci/js/pages/cellular.js
RPC=/usr/libexec/rpcd/veci.sms
INBOX=/usr/libexec/veci-sms-mifi-inbox
ACL=/usr/share/rpcd/acl.d/veci-sms-inbox-we5927.json
DEL=/usr/libexec/veci-sms-delete-one
FLAG=/etc/veci-sms-feature
BACK=/root/veci-sms-mifi-v153-rollback
OLD_UI_V151=990799cb94e78617c5a6ce1000b6ab0dce47508d25cf8c7a735e3f7ee36ddf45
OLD_UI_V152=13f2246b165b6f7a3271dcec1f9599c20fa2aad08d497d092fd9f66d77b91156
OLD_RPC=fca9c3d16537d2ab2bcba6ecff973913a3d56261940d20f0e19d1396df301a82
OLD_INBOX=99aa086fba307b4a6070345eea73f8acb9268c5ba51d3776f7290b6baed52186
OLD_ACL=c41849a66f4f3f53ca84def2db3b58486c40899bac51896258f1a5c6296327d0
NEW_UI=d91cfd149a3680b3a1803207ade311c69f63b794a25f83759eaf55c3a8b3a0f8
NEW_RPC=b4f9ae924f66b44d65d8df663bfbac76d828abc801af6cc8929b9e179f37a505
NEW_INBOX=da2ae0236d618c86b334d59c6f08c9f1ee75a0241234f42fdb6eb0eba1881b64
NEW_ACL=19bffb2761a74dca2b116383ebcfd7254b0610b0c573108afcafaa3fbd0a104e
NEW_DEL=5e32de1aa289699c23daea5f6c6669b2d5e8fdfd3641c848611237c7d056cdda
fail(){ echo "VECI_SMS_V153_ERROR=$1" >&2;exit 1;}
sha(){ sha256sum "$1" 2>/dev/null|awk '{print $1}';}
board(){
 [ "$(id -u)" = 0 ] || fail root
 [ "$(cat /tmp/sysinfo/board_name 2>/dev/null || :)" = zbtlink,zbt-we5927 ] || fail wrong_device
}
old(){
 case "$(sha "$UI")" in "$OLD_UI_V151"|"$OLD_UI_V152");;*)return 1;;esac
 [ "$(sha "$RPC")" = "$OLD_RPC" ] &&
 [ "$(sha "$INBOX")" = "$OLD_INBOX" ] &&
 [ "$(sha "$ACL")" = "$OLD_ACL" ] &&
 [ ! -e "$DEL" ] && [ ! -L "$DEL" ]
}
new(){
 [ "$(sha "$UI")" = "$NEW_UI" ] &&
 [ "$(sha "$RPC")" = "$NEW_RPC" ] &&
 [ "$(sha "$INBOX")" = "$NEW_INBOX" ] &&
 [ "$(sha "$ACL")" = "$NEW_ACL" ] &&
 [ "$(sha "$DEL")" = "$NEW_DEL" ]
}
healthy(){
 ubus -S list 2>/dev/null | grep -qx 'veci.sms' &&
 ubus -S list 2>/dev/null | grep -qx 'veci.cellular'
}
anon_denied(){
 for method in listMessages deleteMessage;do
   result="$(ubus call session access "{\"ubus_rpc_session\":\"00000000000000000000000000000000\",\"scope\":\"ubus\",\"object\":\"veci.sms\",\"function\":\"$method\"}" 2>/dev/null)" || return 1
   access="$(printf '%s' "$result"|jsonfilter -e '@.access' 2>/dev/null || :)"
   [ "$access" = false ] || [ "$access" = 0 ] || return 1
 done
}
restart_rpc(){
 /etc/init.d/rpcd restart >/dev/null 2>&1 || return 1
 i=0
 while [ "$i" -lt 12 ];do
   healthy && return 0
   i=$((i+1));sleep 1
 done
 return 1
}
atomic(){
 src="$1";dest="$2";mode="$3"
 tmp="$dest.new153.$$"
 cp "$src" "$tmp" && chmod "$mode" "$tmp" && mv -f "$tmp" "$dest"
}
restore(){
 [ -f "$BACK/SHA256SUMS" ] || return 1
 (cd "$BACK" && sha256sum -c SHA256SUMS >/dev/null 2>&1) || return 1
 atomic "$BACK/ui" "$UI" 644 || return 1
 atomic "$BACK/rpc" "$RPC" 755 || return 1
 atomic "$BACK/inbox" "$INBOX" 700 || return 1
 atomic "$BACK/acl" "$ACL" 644 || return 1
 rm -f "$DEL" || return 1
 [ "$(sha "$UI")" = "$(sha "$BACK/ui")" ]
}
status(){
 board
 if new;then echo 'VECI_SMS_V153_FILES=installed'
 elif old;then echo 'VECI_SMS_V153_FILES=old_v15'
 else echo 'VECI_SMS_V153_FILES=unrecognized';fi
 if [ -f "$FLAG" ] && [ ! -L "$FLAG" ];then
   case "$(cat "$FLAG" 2>/dev/null || :)" in
    1)echo 'SMS_FEATURE=ON';;
    0)echo 'SMS_FEATURE=OFF';;
    *)echo 'SMS_FEATURE=unknown';;
   esac
 fi
 healthy && echo 'SMS_RPC=registered' || echo 'SMS_RPC=unavailable'
 [ -f "$BACK/ui" ] && echo 'SMS_V153_BACKUP=present' || echo 'SMS_V153_BACKUP=absent'
 echo 'MODEM_COMMANDS_DURING_INSTALL=false'
}
apply(){
 board
 if new;then echo 'VECI_SMS_V153_ALREADY_LIVE_PASS';status;return;fi
 old || fail unsupported_existing_version
 [ ! -e "$BACK" ] || fail backup_exists
 [ -f "$FLAG" ] && [ ! -L "$FLAG" ] || fail missing_sms_setting
 state="$(cat "$FLAG" 2>/dev/null || :)"
 case "$state" in 0|1);;*)fail invalid_sms_setting;;esac
 [ -x /etc/init.d/rpcd ] || fail no_rpcd
 healthy || fail no_sms_rpc
 for cmd in wget sha256sum ubus jsonfilter awk grep flock;do
  command -v "$cmd" >/dev/null 2>&1 || fail missing_dependency
 done
 free="$(df -k /overlay|awk 'NR==2{print $4}')"
 case "$free" in ''|*[!0-9]*)fail overlay_unknown;;esac
 [ "$free" -ge 200 ] || fail overlay_full
 work="$(mktemp -d /tmp/veci-v153.XXXXXX)" || fail temp
 touched=0;complete=0;made_backup=0
 cleanup(){
  rc=$?;trap - EXIT
  if [ "$touched" = 1 ] && [ "$complete" != 1 ];then
    echo 'VECI_SMS_V153_AUTO_ROLLBACK=started' >&2
    if restore && restart_rpc;then echo 'VECI_SMS_V153_AUTO_ROLLBACK=PASS' >&2
    else echo 'VECI_SMS_V153_AUTO_ROLLBACK=manual_recovery_needed' >&2;fi
  fi
  if [ "$made_backup" = 1 ] && [ "$touched" != 1 ];then rm -rf "$BACK";fi
  rm -rf "$work";exit "$rc"
 }
 trap cleanup EXIT
 trap 'exit 130' INT TERM
 wget -qO "$work/ui" "$URL/$PIN/$SRC/cellular.js" || fail download_ui
 wget -qO "$work/rpc" "$URL/$PIN/$SRC/rpcd-veci.sms" || fail download_rpc
 wget -qO "$work/inbox" "$URL/$PIN/$SRC/veci-sms-mifi-inbox" || fail download_inbox
 wget -qO "$work/acl" "$URL/$PIN/$SRC/acl.json" || fail download_acl
 wget -qO "$work/delete" "$URL/$PIN/scripts/veci-sms-mifi-v153-staged/veci-sms-delete-one" || fail download_delete
 [ "$(sha "$work/ui")" = "$NEW_UI" ] || fail ui_hash
 [ "$(sha "$work/rpc")" = "$NEW_RPC" ] || fail rpc_hash
 [ "$(sha "$work/inbox")" = "$NEW_INBOX" ] || fail inbox_hash
 [ "$(sha "$work/acl")" = "$NEW_ACL" ] || fail acl_hash
 [ "$(sha "$work/delete")" = "$NEW_DEL" ] || fail delete_hash
 sh -n "$work/rpc" && sh -n "$work/inbox" && sh -n "$work/delete" || fail bad_syntax
 old || fail concurrent_change
 mkdir "$BACK" || fail backup
 made_backup=1
 cp -p "$UI" "$BACK/ui" || fail backup_ui
 cp -p "$RPC" "$BACK/rpc" || fail backup_rpc
 cp -p "$INBOX" "$BACK/inbox" || fail backup_inbox
 cp -p "$ACL" "$BACK/acl" || fail backup_acl
 (cd "$BACK" && sha256sum ui rpc inbox acl > SHA256SUMS) || fail backup_manifest
 (cd "$BACK" && sha256sum -c SHA256SUMS >/dev/null 2>&1) || fail backup_verify
 touched=1
 atomic "$work/delete" "$DEL" 700 || fail install_delete
 atomic "$work/rpc" "$RPC" 755 || fail install_rpc
 atomic "$work/inbox" "$INBOX" 700 || fail install_inbox
 atomic "$work/acl" "$ACL" 644 || fail install_acl
 atomic "$work/ui" "$UI" 644 || fail install_ui
 new || fail bad_installed_hash
 restart_rpc || fail registration
 anon_denied || fail anonymous_granted
 [ "$(cat "$FLAG")" = "$state" ] || fail sms_toggle_changed
 complete=1
 echo 'VECI_SMS_V153_STORAGE_AND_DELETE_BACKEND_LIVE_PASS'
 echo 'VECI_SMS_V153_ANONYMOUS_DENIED_PASS'
 echo 'VECI_SMS_V153_SMS_TOGGLE_PRESERVED_PASS'
 echo 'VECI_SMS_V153_NO_MODEM_COMMAND_DURING_INSTALL=true'
 status
}
rollback(){
 board
 new || fail unexpected_live_files
 restore || fail restore_failed
 restart_rpc || fail rpcd_restart
 echo 'VECI_SMS_V153_ROLLBACK_PASS'
 status
}
[ "$#" -eq 1 ] || fail usage
case "$1" in apply)apply;;rollback)rollback;;status)status;;*)fail action;;esac
