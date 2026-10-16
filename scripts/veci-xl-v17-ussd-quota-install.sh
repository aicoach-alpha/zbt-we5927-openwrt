#!/bin/sh
# VeCI XL USSD/Quota v1.7.0 transactional overlay on verified SMS v1.6.0.
# Operations: status | apply | rollback. NO SIM change, SMS, AT or sysupgrade.
set -eu
umask 077
LC_ALL=C;export LC_ALL
TAG=veci-xl-v17-fbf0fc346a1b
PIN=f59f566c964f5dee70ce246c37a78e0a9eca01a16d1c530588adc6aebd23900c
URL=https://github.com/aicoach-alpha/zbt-we5927-openwrt/releases/download/veci-xl-v17-fbf0fc346a1b/veci-xl-v17.tar.gz
UI=/www/veci/js/pages/cellular.js
CMGS=/usr/libexec/veci-sms-cmgs
WRAPPER=/usr/libexec/veci-xl-ussd
CACHE=/usr/libexec/veci-xl-quota-cache
NATIVE=/usr/libexec/veci-xl-ussd-once
RPC=/usr/libexec/rpcd/veci.ussd
ACL=/usr/share/rpcd/acl.d/veci-xl-ussd.json
BACK=/root/veci-xl-v17-rollback
OLD_UI=be7706e19a6e1548cfb63a1e29c95da5ce67a8934f274bbd44d4edfd9aea2aef
OLD_CMGS=ccb6f066f0be2fa0fbb5131a98f90ded88e28ae0442a57d0d73b1949b07016fb
fail(){ printf 'VECI_XL_V17_ERROR=%s\n' "$1" >&2;exit 1; }
sha(){ sha256sum "$1" 2>/dev/null|awk '{print $1}'; }
board(){
 [ "$(id -u)" = 0 ] || fail root_required
 [ "$(cat /tmp/sysinfo/board_name 2>/dev/null || :)" = zbtlink,zbt-we5927 ] || fail wrong_board
 [ "$(uname -r)" = 6.12.94 ] || fail unexpected_kernel
}
baseline(){ [ "$(sha "$UI")" = "$OLD_UI" ] && [ "$(sha "$CMGS")" = "$OLD_CMGS" ]; }
new_absent(){
 [ ! -e "$WRAPPER" ] && [ ! -L "$WRAPPER" ] &&
 [ ! -e "$CACHE" ] && [ ! -L "$CACHE" ] &&
 [ ! -e "$NATIVE" ] && [ ! -L "$NATIVE" ] &&
 [ ! -e "$RPC" ] && [ ! -L "$RPC" ] &&
 [ ! -e "$ACL" ] && [ ! -L "$ACL" ]
}
old_backup(){
 [ -d "$BACK" ] && [ ! -L "$BACK" ] &&
 [ -f "$BACK/ui" ] && [ ! -L "$BACK/ui" ] &&
 [ "$(sha "$BACK/ui")" = "$OLD_UI" ] &&
 [ -f "$BACK/SHA256SUMS" ] && [ ! -L "$BACK/SHA256SUMS" ] &&
 (cd "$BACK" && sha256sum -c SHA256SUMS >/dev/null 2>&1) &&
 [ -f "$BACK/manifest" ] && [ ! -L "$BACK/manifest" ]
}
expected(){
 [ "$#" -eq 2 ] || return 1
 digest="$(awk -v name="$2" '$2==name{print $1}' "$BACK/manifest")"
 [ "$(printf %s "$digest"|wc -c)" = 64 ] && [ "$(sha "$1")" = "$digest" ]
}
deployed(){
 old_backup &&
 expected "$UI" cellular.js &&
 expected "$WRAPPER" veci-xl-ussd &&
 expected "$CACHE" veci-xl-quota-cache &&
 expected "$NATIVE" veci-xl-ussd-once &&
 expected "$RPC" veci.ussd &&
 expected "$ACL" veci-xl-ussd.json &&
 [ "$(sha "$CMGS")" = "$OLD_CMGS" ]
}
atomic(){
 from="$1";to="$2";mode="$3"
 temp="$to.newxl.$$"
 cp "$from" "$temp" && chmod "$mode" "$temp" && mv -f "$temp" "$to"
}
restore(){
 old_backup || return 1
 atomic "$BACK/ui" "$UI" 644 || return 1
 rm -f "$WRAPPER" "$CACHE" "$NATIVE" "$RPC" "$ACL" || return 1
 /etc/init.d/rpcd restart >/dev/null 2>&1 || return 1
 baseline && new_absent
}
status(){
 board
 if deployed;then echo 'VECI_XL_USSD_V17=installed'
 elif baseline && new_absent;then echo 'VECI_XL_USSD_V17=v160'
 else echo 'VECI_XL_USSD_V17=unrecognized';fi
 if old_backup;then echo 'VECI_XL_USSD_BACKUP=verified'
 else echo 'VECI_XL_USSD_BACKUP=absent_or_invalid';fi
 echo 'SMS_LIVE_BASELINE_CMGS_UNCHANGED=true'
 echo 'AT_COMMANDS_DURING_INSTALL=false'
 echo 'SMS_SENT_READ_DELETED=false'
 echo 'FIRMWARE_FLASH_OR_REBOOT=false'
}
apply(){
 board
 if deployed;then echo 'VECI_XL_USSD_ALREADY_INSTALLED_PASS';status;return;fi
 baseline || fail v160_ui_or_sms_transport_changed
 new_absent || fail existing_ussd_component
 # A prior automatic rollback intentionally keeps a verified backup.
 # Reuse only its exact original UI and the same pinned release manifest.
 reuse_backup=0
 if [ -e "$BACK" ] || [ -L "$BACK" ];then
   old_backup || fail preexisting_backup_invalid
   reuse_backup=1
 fi
 for cmd in wget tar sha256sum awk mktemp flock;do command -v "$cmd" >/dev/null 2>&1 || fail dependency_missing;done
 free="$(df -k /overlay|awk 'NR==2{print $4}')"
 case "$free" in ''|*[!0-9]*)fail disk_unknown;;esac
 [ "$free" -ge 500 ] || fail overlay_low
 work="$(mktemp -d /tmp/veci-xl-v17.XXXXXX)" || fail temp_unavailable
 changed=0;ready=0;backup_created=0
 cleanup(){
   rc=$?;trap - EXIT
   if [ "$changed" = 1 ] && [ "$ready" != 1 ];then
     echo 'VECI_XL_V17_AUTOROLLBACK=started' >&2
     if restore;then echo 'VECI_XL_V17_AUTOROLLBACK=PASS' >&2
     else echo 'VECI_XL_V17_AUTOROLLBACK=manual_review_required' >&2;fi
   elif [ "$backup_created" = 1 ] && [ "$changed" = 0 ];then rm -rf "$BACK";fi
   rm -rf "$work"
   exit "$rc"
 }
 trap cleanup EXIT
 trap 'exit 130' INT TERM
 wget -qO "$work/bundle.tar.gz" "$URL" || fail bundle_download
 [ "$(sha "$work/bundle.tar.gz")" = "$PIN" ] || fail bundle_digest
 tar -xzf "$work/bundle.tar.gz" -C "$work" || fail bundle_extract
 payload="$work/veci-xl-v17"
 [ -d "$payload" ] && [ ! -L "$payload" ] || fail invalid_layout
 (cd "$payload" && sha256sum -c SHA256SUMS >/dev/null 2>&1) || fail payload_corrupt
 grep -Fxq 'VERSION=v1.7.1-xl-ussd' "$payload/RELEASE_INFO" || fail wrong_release
 baseline && new_absent || fail concurrent_modification
 if [ "$reuse_backup" = 1 ];then
   old_backup || fail existing_backup_invalid
   [ "$(sha "$BACK/manifest")" = "$(sha "$payload/SHA256SUMS")" ] ||
     fail existing_backup_other_release
 else
   mkdir -m 700 "$BACK" || fail backup_unavailable
   backup_created=1
   cp -p "$UI" "$BACK/ui" && cp "$payload/SHA256SUMS" "$BACK/manifest" || fail backup_copy
   (cd "$BACK" && sha256sum ui > SHA256SUMS &&
      sha256sum -c SHA256SUMS >/dev/null 2>&1) || fail backup_corrupt
 fi
 [ "$(sha "$BACK/ui")" = "$OLD_UI" ] || fail baseline_changed
 changed=1
 atomic "$payload/veci-xl-ussd-once" "$NATIVE" 700 || fail native_install
 atomic "$payload/veci-xl-ussd" "$WRAPPER" 700 || fail worker_install
 atomic "$payload/veci-xl-quota-cache" "$CACHE" 700 || fail cache_install
 atomic "$payload/veci.ussd" "$RPC" 700 || fail rpc_install
 atomic "$payload/veci-xl-ussd.json" "$ACL" 644 || fail acl_install
 atomic "$payload/cellular.js" "$UI" 644 || fail ui_install
 deployed || fail installation_digest
 /etc/init.d/rpcd restart >/dev/null 2>&1 || fail rpcd_restart
 registered=0
 tries=0
 # rpcd startup and exec-plugin discovery need not finish before init
 # returns. A bounded readiness loop avoids a false registration failure.
 while [ "$tries" -lt 8 ];do
   if ubus -S list veci.ussd >/dev/null 2>&1;then
     registered=1;break
   fi
   tries=$((tries+1))
   sleep 1
 done
 if [ "$registered" != 1 ];then
   echo 'VECI_XL_RPC_REGISTRATION_DIAGNOSTIC=begin' >&2
   [ -x "$RPC" ] && echo 'VECI_XL_RPC_EXECUTABLE=true' >&2 ||
     echo 'VECI_XL_RPC_EXECUTABLE=false' >&2
   if "$RPC" list >/dev/null 2>&1;then
     echo 'VECI_XL_RPC_LIST_EXIT=success' >&2
   else
     echo 'VECI_XL_RPC_LIST_EXIT=failure' >&2
   fi
   if ubus -S list veci.sms >/dev/null 2>&1;then
     echo 'VECI_XL_EXISTING_SMS_RPC=registered' >&2
   else
     echo 'VECI_XL_EXISTING_SMS_RPC=unavailable' >&2
   fi
   echo 'VECI_XL_RPC_REGISTRATION_DIAGNOSTIC=end' >&2
   fail rpc_registration
 fi
 deployed || fail integrity_after_rpcd
 ready=1
 echo 'VECI_XL_USSD_V17_FILES_AND_RPC_LIVE_PASS'
 echo 'XL_USSD_ACTUAL_OPERATOR_RESPONSE=not_yet_verified'
 status
}
rollback(){
 board
 deployed || fail active_files_not_verified
 restore || fail rollback_failed
 echo 'VECI_XL_USSD_V17_ROLLBACK_PASS'
 status
}
[ "$#" -eq 1 ] || fail usage
case "$1" in
 status)status;;
 apply)apply;;
 rollback)rollback;;
 *)fail invalid_action;;
esac
