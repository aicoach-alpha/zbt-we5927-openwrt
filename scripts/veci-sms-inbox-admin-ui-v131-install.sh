#!/bin/sh
# WE5927 optional SMS metadata index v1.3. Not a firmware flash.
# WARNING: User-initiated listing can mark unread SMS read. INSTALL itself
# NEVER accesses modem AT, SMS, OTP, USSD, SIM or LTE.
set -eu
umask 077
LC_ALL=C; export LC_ALL
REPO=https://raw.githubusercontent.com/aicoach-alpha/zbt-we5927-openwrt
PIN=cecfe43e99a1bf9b4c7c9c1158432acd44099de5
SRC=source/veci-sms-inbox-we5927/files
BASE=/www/veci/js/pages/cellular.js
RPC=/usr/libexec/rpcd/veci.sms
WORKER=/usr/libexec/veci-sms-inbox-index
ACL=/usr/share/rpcd/acl.d/veci-sms-inbox-we5927.json
BACKUP=/root/veci-sms-inbox-v131-rollback
V12_SHA=2deb013e6ccf433b9c3abc3d7f02aafb33739dd1b5b5f222d4de501865314d40
V131_SHA=5f34ca2320a77f0f91d1bda524e84f18c79af1d589ddeb2bf9392c2cd30af6ca
RPC_SHA=24102a1919856de11a2eb207c57e56b78f85612a50bf71628ff1959edf856a2e
WORKER_SHA=ff11a42144181de131f1e595db163bd6f8ce7b3dd718a9e63cdf594e4fe2d7ec
ACL_SHA=8bfe87008b20d8060f07e6ee7058cea1873bc7f39c99a5c58ea22c76b2fd1fa4

fail() { echo "INBOX_V131_ERROR: $*" >&2; exit 1; }
sha() { sha256sum "$1" 2>/dev/null | awk '{print $1}'; }
board() {
  [ "$(id -u)" = 0 ] || fail root_required
  [ "$(cat /tmp/sysinfo/board_name 2>/dev/null || :)" = zbtlink,zbt-we5927 ] ||
    fail wrong_device
}
status() {
  board
  echo "CURRENT_CELLULAR_SHA=$(sha "$BASE" || echo absent)"
  echo "EXPECTED_V12_SHA=$V12_SHA"
  echo "EXPECTED_V131_SHA=$V131_SHA"
  [ -f "$RPC" ] && echo "INBOX_RPC_SHA=$(sha "$RPC")" || echo "INBOX_RPC=absent"
  [ -f "$WORKER" ] && echo "INBOX_WORKER_SHA=$(sha "$WORKER")" || echo "INBOX_WORKER=absent"
  [ -f "$ACL" ] && echo "INBOX_ACL_SHA=$(sha "$ACL")" || echo "INBOX_ACL=absent"
  [ -d "$BACKUP" ] && echo "BACKUP=$BACKUP" || echo "BACKUP=none"
  df -h /overlay
}
atomic_copy() {
  src="$1"; dest="$2"; perm="$3"
  [ -s "$src" ] || return 1
  tmp="$dest.newv131.$$"
  cp "$src" "$tmp" || return 1
  chmod "$perm" "$tmp" || { rm -f "$tmp"; return 1; }
  mv -f "$tmp" "$dest" || { rm -f "$tmp"; return 1; }
}
restore() {
  [ "$(sha "$BACKUP/cellular-v12.js")" = "$V12_SHA" ] || return 1
  atomic_copy "$BACKUP/cellular-v12.js" "$BASE" 644 || return 1
  rm -f "$RPC" "$WORKER" "$ACL" || return 1
  [ "$(sha "$BASE")" = "$V12_SHA" ]
}
apply() {
  board
  [ -f "$BASE" ] && [ ! -L "$BASE" ] || fail bad_cellular_asset
  [ "$(sha "$BASE")" = "$V12_SHA" ] || fail current_cellular_not_live_v12
  [ ! -e "$RPC" ] && [ ! -L "$RPC" ] || fail existing_sms_rpc_do_not_overwrite
  [ ! -e "$WORKER" ] && [ ! -L "$WORKER" ] || fail existing_worker_do_not_overwrite
  [ ! -e "$ACL" ] && [ ! -L "$ACL" ] || fail existing_acl_do_not_overwrite
  [ ! -e "$BACKUP" ] || fail backup_already_exists
  [ -x /etc/init.d/rpcd ] || fail rpcd_service_missing
  # The already-live v1.2 plugin must be present BEFORE making changes.
  ubus list veci.cellular 2>/dev/null | grep -qx 'veci.cellular' ||
    fail existing_cellular_rpc_missing
  for cmd in wget sha256sum grep awk cmp ubus; do
    command -v "$cmd" >/dev/null 2>&1 || fail missing_dependency
  done
  space="$(df -k /overlay | awk 'NR==2 {print $4}')"
  case "$space" in ''|*[!0-9]*) fail unknown_overlay_space ;; esac
  [ "$space" -ge 160 ] || fail insufficient_overlay_space
  work="$(mktemp -d /tmp/veci-inbox-v131.XXXXXX)" || fail staging_failed
  touched=0; done_ok=0
  cleanup() {
    code=$?
    trap - EXIT
    if [ "$touched" = 1 ] && [ "$done_ok" != 1 ]; then
      echo "INBOX_V131_AUTOMATIC_ROLLBACK_STARTED" >&2
      restore_ok=0
      restore && restore_ok=1 ||
        echo "INBOX_V131_MANUAL_RECOVERY_REQUIRED=$BACKUP" >&2
      /etc/init.d/rpcd restart >/dev/null 2>&1 ||
        echo "INBOX_V131_RPCD_RESTART_REQUIRED" >&2
      if [ "$restore_ok" = 1 ] &&
         [ "$(sha "$BASE")" = "$V12_SHA" ] &&
         [ ! -e "$RPC" ] && [ ! -e "$WORKER" ] && [ ! -e "$ACL" ]; then
         echo "INBOX_V131_ROLLBACK_FILES_PASS" >&2
      else
         echo "INBOX_V131_MANUAL_RECOVERY_REQUIRED=$BACKUP" >&2
      fi
    fi
    rm -rf "$work"
    exit "$code"
  }
  trap cleanup EXIT
  trap 'exit 130' INT TERM
  wget -q -O "$work/ui.js" "$REPO/$PIN/scripts/veci-sms-inbox-ui-staged-20261013/cellular.js" ||
    fail ui_download_failed
  wget -q -O "$work/rpc" "$REPO/$PIN/$SRC/usr/libexec/rpcd/veci.sms" ||
    fail rpc_download_failed
  wget -q -O "$work/worker" "$REPO/$PIN/$SRC/usr/libexec/veci-sms-inbox-index" ||
    fail worker_download_failed
  wget -q -O "$work/acl" "$REPO/$PIN/$SRC/usr/share/rpcd/acl.d/veci-sms-inbox-we5927.json" ||
    fail acl_download_failed
  [ "$(sha "$work/ui.js")" = "$V131_SHA" ] || fail ui_hash_mismatch
  [ "$(sha "$work/rpc")" = "$RPC_SHA" ] || fail rpc_hash_mismatch
  [ "$(sha "$work/worker")" = "$WORKER_SHA" ] || fail worker_hash_mismatch
  [ "$(sha "$work/acl")" = "$ACL_SHA" ] || fail acl_hash_mismatch
  # Diagnose executable signature BEFORE any write/restart. Never call
  # listIndex: that would invoke CMGL and could mark SMS as read.
  sh -n "$work/rpc" || fail rpc_shell_syntax_invalid
  signature="$(sh "$work/rpc" list 2>/dev/null)" || fail rpc_signature_unavailable
  command -v jsonfilter >/dev/null 2>&1 || fail jsonfilter_missing
  signature_scope="$(jsonfilter -s "$signature" -e '@.listIndex.scope' 2>/dev/null)" ||
    fail rpc_signature_invalid
  signature_ack="$(jsonfilter -s "$signature" -e '@.listIndex.ack_unread_status' 2>/dev/null)" ||
    fail rpc_signature_invalid
  [ "$signature_scope" = str ] && [ "$signature_ack" = str ] ||
    fail rpc_signature_unexpected
  unset signature signature_scope signature_ack
  grep -Fq 'I_ACCEPT_UNREAD_TO_READ' "$work/ui.js" || fail ui_missing_consent
  grep -Fq '"veci.sms"' "$work/acl" || fail acl_missing_isolation
  grep -Fq "flock -n -x 9" "$work/worker" || fail missing_modem_lock
  # Even after network download, refuse if another change was installed.
  [ "$(sha "$BASE")" = "$V12_SHA" ] || fail ui_changed_during_download
  mkdir "$BACKUP" || fail backup_creation_failed
  cp -p "$BASE" "$BACKUP/cellular-v12.js" || fail ui_backup_failed
  [ "$(sha "$BACKUP/cellular-v12.js")" = "$V12_SHA" ] || fail backup_not_verified
  printf '%s\n' "$PIN" > "$BACKUP/pinned-payload"
  touched=1
  atomic_copy "$work/worker" "$WORKER" 700 || fail worker_install_failed
  atomic_copy "$work/rpc" "$RPC" 755 || fail rpc_install_failed
  atomic_copy "$work/acl" "$ACL" 644 || fail acl_install_failed
  atomic_copy "$work/ui.js" "$BASE" 644 || fail ui_install_failed
  [ "$(sha "$BASE")" = "$V131_SHA" ] &&
  [ "$(sha "$RPC")" = "$RPC_SHA" ] &&
  [ "$(sha "$WORKER")" = "$WORKER_SHA" ] &&
  [ "$(sha "$ACL")" = "$ACL_SHA" ] || fail final_integrity_mismatch
  # Refresh only rpcd registration; LTE and uhttpd services stay untouched.
  /etc/init.d/rpcd restart >/dev/null 2>&1 || fail rpcd_restart_failed
  # procd/rpcd registration is asynchronous on some devices. Allow 12s
  # for the new object AND previously-live cellular before giving up.
  # No additional restarts or modem queries while waiting.
  registered=0
  probe=0
  while [ "$probe" -lt 12 ]; do
    if ubus list veci.sms 2>/dev/null | grep -qx 'veci.sms' &&
       ubus list veci.cellular 2>/dev/null | grep -qx 'veci.cellular'; then
      registered=1
      break
    fi
    probe=$((probe + 1))
    sleep 1
  done
  [ "$registered" = 1 ] || fail rpc_registration_not_visible_after_grace
  done_ok=1
  echo "VECI_INBOX_V131_ASSETS_PASS"
  echo "MODEM_SMS_NOT_ACCESSED_BY_INSTALLER"
  echo "BACKUP=$BACKUP"
  echo "Re-login to VeCI if rpcd restart invalidated the prior session."
  echo "Hard-refresh Cellular. Metadata listing requires checkbox and a second confirmation."
  status
}
rollback() {
  board
  [ -f "$BACKUP/cellular-v12.js" ] || fail no_v131_backup
  [ "$(sha "$BACKUP/cellular-v12.js")" = "$V12_SHA" ] || fail invalid_backup
  current="$(sha "$BASE")"
  [ "$current" = "$V131_SHA" ] || [ "$current" = "$V12_SHA" ] ||
    fail newer_ui_change_do_not_overwrite
  for pair in "$RPC:$RPC_SHA" "$WORKER:$WORKER_SHA" "$ACL:$ACL_SHA"; do
    file="$(printf '%s\n' "$pair" | cut -d: -f1)"
    value="$(printf '%s\n' "$pair" | cut -d: -f2)"
    if [ -f "$file" ]; then
      [ "$(sha "$file")" = "$value" ] || fail newer_backend_change_do_not_overwrite
    fi
  done
  restore || fail restore_failed
  /etc/init.d/rpcd restart >/dev/null 2>&1 || fail rpcd_restart_failed
  echo "VECI_INBOX_V131_ROLLBACK_PASS"
  status
}
[ "$#" -eq 1 ] || fail usage_status_apply_rollback
case "$1" in
  status) status ;;
  apply) apply ;;
  rollback) rollback ;;
  *) fail unknown_action ;;
esac
