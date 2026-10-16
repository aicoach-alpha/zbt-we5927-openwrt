#!/bin/sh
# VeCI WE5927 v1.5.9 - fix SMS Compose layout under style-src 'self' CSP.
# Install external local CSS first, update page JS second. Reversible, UI-only.
# Never accesses modem, SMS storage, Sent, Drafts, rpcd or LTE.
set -eu
umask 077
LC_ALL=C;export LC_ALL
PIN=72f2fc71b5862f55ab6cd61362de18dc5c47d3b8
RAW=https://raw.githubusercontent.com/aicoach-alpha/zbt-we5927-openwrt
UI=/www/veci/js/pages/cellular.js
CSS=/www/veci/sms-center.css
BACKDIR=/root/veci-sms-v159-csp-css-backup
BACK=$BACKDIR/cellular.js
OLD_JS=66e2475380ef2b1e465f134a06697c7795f771587ba80dfa30dd34096b568686
NEW_JS=5899ae061c0ccaa7a6d9c4c9626d54d5242c735b4a9c1639e5ec6dcd996a5ccb
NEW_CSS=fd3b3540109d815d9b3cb5151298af04ef865e55557d8a8a91d9c30f1548fdb2
fail(){ printf 'SMS_CSP_V159_ERROR=%s\n' "$1" >&2;exit 1; }
sha(){ sha256sum "$1" 2>/dev/null | awk '{print $1}'; }
board(){
 [ "$(id -u)" = 0 ] || fail root_required
 [ "$(cat /tmp/sysinfo/board_name 2>/dev/null || :)" = zbtlink,zbt-we5927 ] || fail wrong_router
}
installed(){
 [ "$(sha "$UI")" = "$NEW_JS" ] &&
 [ "$(sha "$CSS")" = "$NEW_CSS" ]
}
previous(){
 [ "$(sha "$UI")" = "$OLD_JS" ] &&
 [ ! -e "$CSS" ] && [ ! -L "$CSS" ]
}
status(){
 board
 if installed;then
  echo 'SMS_CSP_V159_FILES=installed'
 elif previous;then echo 'SMS_CSP_V159_FILES=v158'
 else echo 'SMS_CSP_V159_FILES=unknown';fi
 [ -f "$BACK" ] && [ ! -L "$BACK" ] &&
  [ "$(sha "$BACK")" = "$OLD_JS" ] &&
  echo 'SMS_CSP_V159_BACKUP=verified' ||
  echo 'SMS_CSP_V159_BACKUP=absent_or_invalid'
 echo 'SMS_CSP_V159_MODEM_COMMANDS=false'
}
restore(){
 [ -f "$BACK" ] && [ ! -L "$BACK" ] &&
 [ "$(sha "$BACK")" = "$OLD_JS" ] || return 1
 tmp="$UI.rollback159.$$"
 cp "$BACK" "$tmp" && chmod 644 "$tmp" &&
 mv -f "$tmp" "$UI" || return 1
 # We own only the exact installed CSS asset; refuse to remove other content.
 case "$(sha "$CSS" 2>/dev/null || :)" in
  "$NEW_CSS")rm -f "$CSS" || return 1;;
  *)[ ! -e "$CSS" ] && [ ! -L "$CSS" ] || return 1;;
 esac
 previous
}
apply(){
 board
 for cmd in wget sha256sum awk grep;do
  command -v "$cmd" >/dev/null 2>&1 || fail dependency_missing
 done
 [ -f "$UI" ] && [ ! -L "$UI" ] || fail invalid_ui
 [ -d /www/veci ] && [ ! -L /www/veci ] || fail invalid_webroot
 if installed;then
  echo 'SMS_CSP_V159_ALREADY_INSTALLED_PASS';status;return
 fi
 previous || fail expected_v158_files_mismatch
 [ ! -e "$BACKDIR" ] && [ ! -L "$BACKDIR" ] || fail backup_exists
 free="$(df -k /overlay | awk 'NR==2{print $4}')"
 case "$free" in ''|*[!0-9]*)fail overlay_unknown;;esac
 [ "$free" -ge 160 ] || fail insufficient_overlay
 tmpdir="$(mktemp -d /tmp/veci-csp159.XXXXXX)" || fail staging_unavailable
 changed=0;complete=0;backup_made=0
 cleanup(){
  result=$?
  trap - EXIT
  if [ "$changed" = 1 ] && [ "$complete" != 1 ];then
   echo 'SMS_CSP_V159_AUTO_ROLLBACK=started' >&2
   restore && echo 'SMS_CSP_V159_AUTO_ROLLBACK=PASS' >&2 ||
    echo 'SMS_CSP_V159_AUTO_ROLLBACK=manual_review_required' >&2
  elif [ "$backup_made" = 1 ] && [ "$changed" != 1 ];then
   rm -rf "$BACKDIR"
  fi
  rm -rf "$tmpdir"
  exit "$result"
 }
 trap cleanup EXIT
 trap 'exit 130' INT TERM
 wget -qO "$tmpdir/ui" "$RAW/$PIN/scripts/veci-sms-mifi-v15-staged/cellular.js" || fail js_download
 wget -qO "$tmpdir/css" "$RAW/$PIN/scripts/veci-sms-mifi-v159-staged/sms-center.css" || fail css_download
 [ "$(sha "$tmpdir/ui")" = "$NEW_JS" ] || fail js_checksum
 [ "$(sha "$tmpdir/css")" = "$NEW_CSS" ] || fail css_checksum
 grep -Fq "link.href = '/veci/sms-center.css?v=159'" "$tmpdir/ui" || fail stylesheet_link_missing
 grep -Fq 'flex-flow: column nowrap !important' "$tmpdir/css" || fail external_vertical_layout_missing
 grep -Fq "api.call('veci.sms','sendMessage'" "$tmpdir/ui" || fail sms_send_missing
 grep -Fq "api.call('veci.sms','saveDraft'" "$tmpdir/ui" || fail sms_drafts_missing
 previous || fail concurrent_change
 mkdir -m 700 "$BACKDIR" || fail backup_creation
 backup_made=1
 cp -p "$UI" "$BACK" && chmod 600 "$BACK" || fail backup_copy
 [ "$(sha "$BACK")" = "$OLD_JS" ] || fail backup_checksum
 # Stage both files first. CSS precedes JS so the new page cannot load
 # before the corresponding same-origin stylesheet exists.
 cp "$tmpdir/css" "$CSS.new159.$$" && chmod 644 "$CSS.new159.$$" || fail stage_css
 cp "$tmpdir/ui" "$UI.new159.$$" && chmod 644 "$UI.new159.$$" || fail stage_js
 previous || fail concurrent_change
 changed=1
 mv -f "$CSS.new159.$$" "$CSS" || fail install_css
 mv -f "$UI.new159.$$" "$UI" || fail install_js
 installed || fail install_checksums
 complete=1
 echo 'SMS_CSP_V159_EXTERNAL_STYLESHEET_LIVE_INSTALL_PASS'
 echo 'SMS_CSP_V159_COMPOSE_LAYOUT_CSP_FIXED_FILES_PASS'
 echo 'SMS_CSP_V159_BACKEND_INBOX_SENT_DRAFTS_UNCHANGED=true'
 echo 'SMS_CSP_V159_NO_MODEM_OR_RPCD_RESTART=true'
 status
}
rollback(){
 board
 installed || fail installed_files_mismatch
 restore || fail rollback_failed
 echo 'SMS_CSP_V159_ROLLBACK_PASS'
 status
}
[ "$#" -eq 1 ] || fail usage
case "$1" in apply)apply;;status)status;;rollback)rollback;;*)fail invalid_action;;esac
