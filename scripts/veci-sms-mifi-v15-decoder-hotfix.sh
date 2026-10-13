#!/bin/sh
# VeCI WE5927 SMS v1.5.1 PDU decoder hotfix - frontend ONLY.
# No AT commands, modem access, rpcd restart, LTE operations, firmware flash.
set -eu
umask 077
LC_ALL=C; export LC_ALL

PIN=a2093a9d59cf55473ea337a2e8275f9ed1bd19ca
SRC=scripts/veci-sms-mifi-v15-staged/cellular.js
URL=https://raw.githubusercontent.com/aicoach-alpha/zbt-we5927-openwrt
LIVE=/www/veci/js/pages/cellular.js
BACK=/root/veci-sms-mifi-v15-rollback/cellular-before-decoder-hotfix.js
OLD_SHA=5ecd42fbb1b0e94db30a3590b9cba9e2fd4b8d6f2175c16ce97a755a2fff63dd
NEW_SHA=990799cb94e78617c5a6ce1000b6ab0dce47508d25cf8c7a735e3f7ee36ddf45

fail() { printf 'SMS_MIFI_DECODER_HOTFIX_ERROR=%s\n' "$1" >&2; exit 1; }
sha() { sha256sum "$1" 2>/dev/null | awk '{print $1}'; }
board() {
  [ "$(id -u)" -eq 0 ] || fail root_required
  [ "$(cat /tmp/sysinfo/board_name 2>/dev/null || :)" = zbtlink,zbt-we5927 ] ||
    fail wrong_router
}
valid_live() {
  [ -f "$LIVE" ] && [ ! -L "$LIVE" ]
}
status() {
  board
  current="$(sha "$LIVE" || :)"
  if [ "$current" = "$NEW_SHA" ]; then
    echo 'SMS_MIFI_DECODER_V151=installed'
  elif [ "$current" = "$OLD_SHA" ]; then
    echo 'SMS_MIFI_DECODER_V151=original_v15'
  else
    echo 'SMS_MIFI_DECODER_V151=unknown'
    printf 'CURRENT_CELLULAR_SHA256=%s\n' "$current"
  fi
  [ -f "$BACK" ] && echo 'SMS_MIFI_DECODER_BACKUP=present' ||
    echo 'SMS_MIFI_DECODER_BACKUP=absent'
  if [ -f /etc/veci-sms-feature ] && [ ! -L /etc/veci-sms-feature ]; then
    case "$(cat /etc/veci-sms-feature 2>/dev/null || :)" in
      1) echo 'SMS_FEATURE=ON' ;;
      0) echo 'SMS_FEATURE=OFF' ;;
      *) echo 'SMS_FEATURE=unknown' ;;
    esac
  fi
  echo 'MODEM_COMMANDS_EXECUTED=false'
}
restore_file() {
  [ "$(sha "$BACK")" = "$OLD_SHA" ] || return 1
  temporary="$LIVE.rollback.$$"
  cp "$BACK" "$temporary" && chmod 644 "$temporary" &&
    mv -f "$temporary" "$LIVE" && [ "$(sha "$LIVE")" = "$OLD_SHA" ]
}
apply() {
  board
  valid_live || fail missing_or_symlink_live_ui
  for cmd in wget sha256sum grep ubus; do
    command -v "$cmd" >/dev/null 2>&1 || fail missing_dependency
  done
  ubus -S list 2>/dev/null | grep -qx 'veci.sms' || fail mifi_sms_not_registered
  [ -f /etc/veci-sms-feature ] && [ ! -L /etc/veci-sms-feature ] ||
    fail v15_sms_setting_missing
  state="$(cat /etc/veci-sms-feature 2>/dev/null || :)"
  [ "$state" = 0 ] || [ "$state" = 1 ] || fail invalid_sms_setting
  current="$(sha "$LIVE")"
  if [ "$current" = "$NEW_SHA" ]; then
    echo 'SMS_MIFI_DECODER_V151_ALREADY_LIVE_PASS'
    status
    return 0
  fi
  [ "$current" = "$OLD_SHA" ] || {
    printf 'CURRENT_CELLULAR_SHA256=%s\n' "$current" >&2
    fail unsupported_live_ui_version
  }
  [ -d /root/veci-sms-mifi-v15-rollback ] ||
    fail v15_backup_directory_missing
  [ ! -e "$BACK" ] && [ ! -L "$BACK" ] || fail backup_already_exists

  work="$(mktemp -d /tmp/veci-sms-decoder.XXXXXX)" || fail staging_unavailable
  touched=0; completed=0
  cleanup() {
    code=$?
    trap - EXIT
    if [ "$touched" = 1 ] && [ "$completed" != 1 ]; then
      echo 'SMS_MIFI_DECODER_AUTO_ROLLBACK=started' >&2
      restore_file && echo 'SMS_MIFI_DECODER_AUTO_ROLLBACK=PASS' >&2 ||
        echo 'SMS_MIFI_DECODER_AUTO_ROLLBACK=manual_recovery_required' >&2
    fi
    rm -rf "$work"
    exit "$code"
  }
  trap cleanup EXIT
  trap 'exit 130' INT TERM
  wget -qO "$work/new.js" "$URL/$PIN/$SRC" || fail download_failed
  [ "$(sha "$work/new.js")" = "$NEW_SHA" ] || fail downloaded_sha_mismatch
  grep -Fq 'Alpha sender length' "$work/new.js" || fail missing_alpha_fix
  grep -Fq 'SMS format' "$work/new.js" || : # UI intentionally only generic diagnostic strings

  [ "$(sha "$LIVE")" = "$OLD_SHA" ] || fail concurrent_ui_change
  cp -p "$LIVE" "$BACK" || fail backup_failed
  chmod 600 "$BACK" || fail backup_permissions
  [ "$(sha "$BACK")" = "$OLD_SHA" ] || fail backup_sha_mismatch
  cp "$work/new.js" "$LIVE.newdecoder.$$" || fail stage_failed
  chmod 644 "$LIVE.newdecoder.$$" || fail stage_chmod_failed
  [ "$(sha "$LIVE")" = "$OLD_SHA" ] || fail concurrent_change
  mv -f "$LIVE.newdecoder.$$" "$LIVE" || fail switch_failed
  touched=1
  [ "$(sha "$LIVE")" = "$NEW_SHA" ] || fail installed_sha_mismatch
  completed=1
  echo 'SMS_MIFI_V151_DECODER_LIVE_PASS'
  echo 'SMS_MIFI_V15_BACKEND_UNCHANGED=true'
  echo 'NO_SMS_MODEM_COMMAND_DURING_HOTFIX=true'
  echo 'NO_RPCD_OR_LTE_RESTART=true'
  status
}
rollback() {
  board
  valid_live || fail missing_or_symlink_live_ui
  [ "$(sha "$LIVE")" = "$NEW_SHA" ] || fail unknown_live_ui
  restore_file || fail restore_failed
  echo 'SMS_MIFI_DECODER_V151_ROLLBACK_PASS'
  status
}
[ "$#" -eq 1 ] || fail usage_apply_status_rollback
case "$1" in apply) apply ;; status) status ;; rollback) rollback ;;
  *) fail invalid_action ;;
esac
