#!/bin/sh
# WE5927 VeCI SMS storage count UI: corrected Terser/minified overlay.
# No modem AT, SMS read, USSD, LTE, network change, rpcd or reboot.
set -eu
umask 077
LC_ALL=C
export LC_ALL
SOURCE_SHA=15f8a6afd4e16ff8f58bcfe5545f045fc3f943cf
SRC=https://raw.githubusercontent.com/aicoach-alpha/zbt-we5927-openwrt
PFX=scripts/veci-sms-storage-ui-built-v1
PAGE=/www/veci/js/pages/cellular.js
HELPER=/www/veci/js/lib/messaging.js
BACKUP=/root/veci-sms-storage-ui-v11-rollback
OLD_SHA=a2c62cbf42909951b73127a4ee1bfef60cf7d8654ee274f41e997001444a7aa4
NEW_SHA=ec74f3f575d35df073c7b839ab687103fba6557f2cf7e7136b7922a0150e7d65
HELPER_SHA=50d5aba460b8b5b20c256cdf72bd41e660444ab59e2c1f4e5094edd9bb5277ac

fail() { echo "UI_V11_ERROR: $*" >&2; exit 1; }
sha() { sha256sum "$1" 2>/dev/null | awk '{print $1}'; }
board() {
  [ "$(cat /tmp/sysinfo/board_name 2>/dev/null || :)" = zbtlink,zbt-we5927 ] ||
    fail wrong_board
}
show() {
  board
  echo "CURRENT_CELLULAR_SHA=$(sha "$PAGE" || echo unavailable)"
  echo "EXPECTED_MINIFIED_SHA=$OLD_SHA"
  echo "NEW_CELLULAR_SHA=$NEW_SHA"
  [ -f "$HELPER" ] && echo "HELPER_SHA=$(sha "$HELPER")" || echo "HELPER_SHA=absent"
  [ -d "$BACKUP" ] && echo "V11_BACKUP=$BACKUP" || echo "V11_BACKUP=none"
  df -h /overlay
}
atomic_write() {
  [ -s "$1" ] || return 1
  dst="$2"
  tmp="$dst.v11.$$"
  cp "$1" "$tmp" || return 1
  chmod 644 "$tmp" || { rm -f "$tmp"; return 1; }
  mv -f "$tmp" "$dst" || { rm -f "$tmp"; return 1; }
}
backup_ok() {
  [ -f "$BACKUP/original-page" ] &&
  [ -f "$BACKUP/original-sha" ] &&
  [ "$(cat "$BACKUP/original-sha")" = "$OLD_SHA" ] &&
  [ "$(sha "$BACKUP/original-page")" = "$OLD_SHA" ]
}
restore() {
  backup_ok || return 1
  atomic_write "$BACKUP/original-page" "$PAGE" || return 1
  rm -f "$HELPER" || return 1
  [ "$(sha "$PAGE")" = "$OLD_SHA" ]
}
rollback() {
  [ "$(id -u)" = 0 ] || fail root_required
  board
  backup_ok || fail missing_or_invalid_backup
  current="$(sha "$PAGE" || echo missing)"
  [ "$current" = "$OLD_SHA" ] || [ "$current" = "$NEW_SHA" ] ||
    fail current_page_was_modified_do_not_overwrite
  if [ -f "$HELPER" ]; then
    [ "$(sha "$HELPER")" = "$HELPER_SHA" ] ||
      fail current_formatter_was_modified_do_not_overwrite
  fi
  restore || fail rollback_failed
  echo "UI_V11_ROLLBACK_PASS"
  show
}
apply() {
  [ "$(id -u)" = 0 ] || fail root_required
  board
  [ -f "$PAGE" ] && [ ! -L "$PAGE" ] || fail missing_or_symlinked_page
  [ ! -e "$HELPER" ] && [ ! -L "$HELPER" ] || fail helper_exists
  [ ! -e "$BACKUP" ] || fail backup_exists
  for cmd in wget sha256sum awk cmp grep; do
    command -v "$cmd" >/dev/null 2>&1 || fail missing_dependency
  done
  available="$(df -k /overlay | awk 'NR==2{print $4}')"
  case "$available" in ''|*[!0-9]*) fail unknown_space ;; esac
  [ "$available" -ge 128 ] || fail low_overlay_space
  actual="$(sha "$PAGE")"
  if [ "$actual" != "$OLD_SHA" ]; then
    echo "CURRENT_CELLULAR_SHA=$actual" >&2
    echo "EXPECTED_MINIFIED_SHA=$OLD_SHA" >&2
    echo "CURRENT_CELLULAR_BYTES=$(wc -c < "$PAGE")" >&2
    fail installed_asset_not_verified_untouched
  fi
  work="$(mktemp -d /tmp/veci-ui-v11.XXXXXX)" || fail tmp_staging
  changed=0
  success=0
  cleanup() {
    result=$?
    trap - EXIT
    if [ "$changed" = 1 ] && [ "$success" != 1 ]; then
      echo "UI_V11_INSTALL_FAILED_RECOVERING" >&2
      restore || echo "UI_V11_MANUAL_ROLLBACK_BACKUP=$BACKUP" >&2
    fi
    rm -rf "$work"
    exit "$result"
  }
  trap cleanup EXIT
  trap 'exit 130' INT TERM
  wget -q -O "$work/old" "$SRC/$SOURCE_SHA/$PFX/expected-cellular.js" ||
    fail old_asset_download
  wget -q -O "$work/new" "$SRC/$SOURCE_SHA/$PFX/new-cellular.js" ||
    fail new_asset_download
  wget -q -O "$work/helper" "$SRC/$SOURCE_SHA/$PFX/new-messaging.js" ||
    fail helper_asset_download
  [ "$(sha "$work/old")" = "$OLD_SHA" ] || fail old_asset_hash_mismatch
  [ "$(sha "$work/new")" = "$NEW_SHA" ] || fail new_asset_hash_mismatch
  [ "$(sha "$work/helper")" = "$HELPER_SHA" ] || fail helper_hash_mismatch
  cmp -s "$PAGE" "$work/old" || fail unexpected_local_page
  grep -Fq "messagingStorage" "$work/new" || fail missing_metadata_rpc
  grep -Fq "smsStorageLabel" "$work/new" || fail missing_sanitizer_import
  grep -Fq "Number.isSafeInteger" "$work/helper" || fail missing_validation
  if grep -Eq 'AT\+CMGL=4|AT\+CUSD=1|sendSms|readSms' "$work/new"; then
    fail sensitive_api_not_allowed
  fi
  mkdir "$BACKUP" || fail cannot_reserve_backup
  cp -p "$PAGE" "$BACKUP/original-page" || fail cannot_backup_page
  printf '%s\n' "$OLD_SHA" > "$BACKUP/original-sha"
  printf '%s\n' "$SOURCE_SHA" > "$BACKUP/payload-sha"
  backup_ok || fail invalid_backup
  changed=1
  atomic_write "$work/helper" "$HELPER" || fail helper_install
  atomic_write "$work/new" "$PAGE" || fail cellular_install
  [ "$(sha "$PAGE")" = "$NEW_SHA" ] &&
  [ "$(sha "$HELPER")" = "$HELPER_SHA" ] || fail installed_checksum
  success=1
  echo "UI_V11_LIVE_ASSETS_PASS"
  echo "NO_AT_COMMAND_SENT_BY_INSTALLER"
  echo "UI_BACKUP=$BACKUP"
  echo "Browser hard refresh required to see the SMS count button"
  show
}
[ "$#" -eq 1 ] || fail "usage: status|apply|rollback"
case "$1" in
  status) show ;;
  apply) apply ;;
  rollback) rollback ;;
  *) fail invalid_action ;;
esac
