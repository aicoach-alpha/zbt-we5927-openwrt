#!/bin/sh
# VeCI WE5927 SMS v1.6.0 -- user-approved up-to-four-part GSM7/UCS2 SMS.
# SHA-pinned reversible UI + native binary only. NO modem AT/SMS/LTE/RPCD.
set -eu
umask 077
LC_ALL=C;export LC_ALL
PIN=77f6a5bc14bb3d16da37813dc36fe161feeb929f
BASE=https://raw.githubusercontent.com/aicoach-alpha/zbt-we5927-openwrt
BIN_URL=https://github.com/aicoach-alpha/zbt-we5927-openwrt/releases/download/veci-sms-cmgs-648e1ab5955b/veci-sms-cmgs-mipsel
UI=/www/veci/js/pages/cellular.js
BIN=/usr/libexec/veci-sms-cmgs
CSS=/www/veci/sms-center.css
RPC=/usr/libexec/rpcd/veci.sms
ACL=/usr/share/rpcd/acl.d/veci-sms-inbox-we5927.json
SEND=/usr/libexec/veci-sms-send-one
FLAG=/etc/veci-sms-feature
SENT=/etc/veci-sms-sent-history
DRAFTS=/etc/veci-sms-drafts
BACK=/root/veci-sms-multipart-v160-rollback
OLD_UI=5899ae061c0ccaa7a6d9c4c9626d54d5242c735b4a9c1639e5ec6dcd996a5ccb
NEW_UI=be7706e19a6e1548cfb63a1e29c95da5ce67a8934f274bbd44d4edfd9aea2aef
OLD_BIN=e2f1aef02ed031bbbc70421abcad02426273b196eeec8f5d482004f1f44304de
NEW_BIN=ccb6f066f0be2fa0fbb5131a98f90ded88e28ae0442a57d0d73b1949b07016fb
CSS_SHA=fd3b3540109d815d9b3cb5151298af04ef865e55557d8a8a91d9c30f1548fdb2
RPC_SHA=669c6d753f14eb7c8b7d77c1aea28059eb25e20f71511efa301942707f1e0615
ACL_SHA=827fd96f101ece20e6a4e307cc82fb4d3a463989c2cd4b09cdc72cd8d9a2193c
SEND_SHA=51c13afc282936ae0e1d06692ce9df2d0a310058499ac6961ba8cd622f55efeb
fail(){ printf 'SMS_MULTIPART_V160_ERROR=%s\n' "$1" >&2;exit 1; }
sha(){ sha256sum "$1" 2>/dev/null|awk '{print $1}'; }
board(){
 [ "$(id -u)" = 0 ] || fail root_required
 [ "$(cat /tmp/sysinfo/board_name 2>/dev/null || :)" = zbtlink,zbt-we5927 ] || fail wrong_router
}
old(){ [ "$(sha "$UI")" = "$OLD_UI" ] && [ "$(sha "$BIN")" = "$OLD_BIN" ]; }
new(){ [ "$(sha "$UI")" = "$NEW_UI" ] && [ "$(sha "$BIN")" = "$NEW_BIN" ]; }
base_integrity(){
 [ "$(sha "$CSS")" = "$CSS_SHA" ] &&
 [ "$(sha "$RPC")" = "$RPC_SHA" ] &&
 [ "$(sha "$ACL")" = "$ACL_SHA" ] &&
 [ "$(sha "$SEND")" = "$SEND_SHA" ] &&
 [ -f "$FLAG" ] && [ ! -L "$FLAG" ] &&
 [ -f "$SENT" ] && [ ! -L "$SENT" ] &&
 [ -f "$DRAFTS" ] && [ ! -L "$DRAFTS" ]
}
verified_backup(){
 [ -d "$BACK" ] && [ ! -L "$BACK" ] &&
 [ -f "$BACK/SHA256SUMS" ] &&
 (cd "$BACK" && sha256sum -c SHA256SUMS >/dev/null 2>&1) &&
 [ "$(sha "$BACK/ui")" = "$OLD_UI" ] &&
 [ "$(sha "$BACK/bin")" = "$OLD_BIN" ]
}
atomic(){
 src="$1";dst="$2";mode="$3";tmp="$dst.new160.$$"
 cp "$src" "$tmp" && chmod "$mode" "$tmp" && mv -f "$tmp" "$dst"
}
restore(){
 verified_backup || return 1
 atomic "$BACK/bin" "$BIN" 700 &&
 atomic "$BACK/ui" "$UI" 644 &&
 old
}
status(){
 board
 if new;then echo 'SMS_MULTIPART_V160_FILES=installed'
 elif old;then echo 'SMS_MULTIPART_V160_FILES=v159'
 else echo 'SMS_MULTIPART_V160_FILES=unrecognized';fi
 if verified_backup;then echo 'SMS_MULTIPART_V160_BACKUP=verified'
 else echo 'SMS_MULTIPART_V160_BACKUP=absent_or_invalid';fi
 echo 'SMS_MULTIPART_MODEM_COMMAND_DURING_INSTALL=false'
}
apply(){
 board
 for cmd in wget awk sha256sum grep;do
  command -v "$cmd" >/dev/null 2>&1 || fail missing_dependency
 done
 [ -f "$UI" ] && [ ! -L "$UI" ] &&
 [ -f "$BIN" ] && [ ! -L "$BIN" ] || fail missing_expected_files
 base_integrity || fail base_integrity_mismatch
 if new;then echo 'SMS_MULTIPART_V160_ALREADY_INSTALLED_PASS';status;return;fi
 old || fail expected_v159_files_mismatch
 [ ! -e "$BACK" ] && [ ! -L "$BACK" ] || fail backup_exists
 setting="$(cat "$FLAG" 2>/dev/null || :)"
 case "$setting" in 0|1);;*)fail invalid_sms_setting;;esac
 free="$(df -k /overlay|awk 'NR==2{print $4}')"
 case "$free" in ''|*[!0-9]*)fail overlay_unknown;;esac
 [ "$free" -ge 250 ] || fail insufficient_overlay
 stage="$(mktemp -d /tmp/veci-v160.XXXXXX)" || fail staging_failed
 backup_made=0;changed=0;complete=0
 cleanup(){
  code=$?;trap - EXIT
  if [ "$changed" = 1 ] && [ "$complete" != 1 ];then
   echo 'SMS_MULTIPART_V160_AUTO_ROLLBACK=started' >&2
   if restore;then echo 'SMS_MULTIPART_V160_AUTO_ROLLBACK=PASS' >&2
   else echo 'SMS_MULTIPART_V160_AUTO_ROLLBACK=manual_review_required' >&2;fi
  elif [ "$backup_made" = 1 ] && [ "$changed" != 1 ];then
   rm -rf "$BACK"
  fi
  rm -rf "$stage";exit "$code"
 }
 trap cleanup EXIT
 trap 'exit 130' INT TERM
 wget -qO "$stage/ui" "$BASE/$PIN/scripts/veci-sms-mifi-v15-staged/cellular.js" || fail ui_download
 wget -qO "$stage/bin" "$BIN_URL" || fail binary_download
 [ "$(sha "$stage/ui")" = "$NEW_UI" ] || fail ui_checksum
 [ "$(sha "$stage/bin")" = "$NEW_BIN" ] || fail binary_checksum
 grep -Fq 'function buildSmsSubmitSegments(' "$stage/ui" || fail multipart_ui_missing
 grep -Fq "link.href = '/veci/sms-center.css?v=159'" "$stage/ui" || fail csp_css_link_missing
 grep -Fq 'Do not automatically resend.' "$stage/ui" || fail partial_failure_guard_missing
 grep -Fq "api.call('veci.sms','sendMessage'" "$stage/ui" || fail send_rpc_ui_missing
 grep -Fq "api.call('veci.sms','saveDraft'" "$stage/ui" || fail draft_ui_missing
 old || fail concurrent_change
 mkdir -m 700 "$BACK" || fail backup_create
 backup_made=1
 cp -p "$UI" "$BACK/ui" && cp -p "$BIN" "$BACK/bin" || fail backup_copy
 (cd "$BACK" && sha256sum ui bin > SHA256SUMS &&
  sha256sum -c SHA256SUMS >/dev/null 2>&1) || fail backup_checksum
 changed=1
 atomic "$stage/bin" "$BIN" 700 || fail binary_install
 atomic "$stage/ui" "$UI" 644 || fail ui_install
 new || fail installed_files_checksum
 base_integrity || fail existing_components_changed
 [ "$(cat "$FLAG")" = "$setting" ] || fail sms_setting_changed
 complete=1
 echo 'SMS_MULTIPART_V160_UI_NATIVE_BINARY_LIVE_INSTALL_PASS'
 echo 'SMS_MULTIPART_V160_NATIVE_MIPS_SHA256_PASS'
 echo 'SMS_MULTIPART_V160_INBOX_SENT_DRAFTS_BACKEND_UNCHANGED=true'
 echo 'SMS_MULTIPART_V160_NO_MODEM_COMMAND_OR_SERVICE_RESTART=true'
 echo 'SMS_MULTIPART_ACTUAL_MESSAGE=not_sent_during_install'
 status
}
rollback(){
 board
 new || fail unexpected_live_files
 restore || fail rollback_corrupt
 echo 'SMS_MULTIPART_V160_ROLLBACK_PASS'
 status
}
[ "$#" = 1 ] || fail usage
case "$1" in apply)apply;;rollback)rollback;;status)status;;*)fail invalid_action;;esac
