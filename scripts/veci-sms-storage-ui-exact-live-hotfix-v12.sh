#!/bin/sh
# WE5927 UI-only hotfix: EXACT operator-captured 6357B Cellular file.
# Does NOT invoke modem AT, SMS, USSD, LTE manager, rpcd or reboot.
set -eu
umask 077
LC_ALL=C
export LC_ALL

BOARD=zbtlink,zbt-we5927
ORIGINAL_SHA=0a4e78d5368806b31441612b8979ab7b2ac8f425890cfd89104f969accd8ee18
PATCHED_SHA=2deb013e6ccf433b9c3abc3d7f02aafb33739dd1b5b5f222d4de501865314d40
PATCH_COMMIT=9c5be87354cb08b93ef478fdd2dbd1b7e777fc7b
FILE=/www/veci/js/pages/cellular.js
BACKUP=/root/veci-sms-ui-exact-live-v12-backup
URL=https://raw.githubusercontent.com/aicoach-alpha/zbt-we5927-openwrt

die() { echo "V12_ERROR: $*" >&2; exit 1; }
sha() { sha256sum "$1" 2>/dev/null | awk '{print $1}'; }
check() {
    [ "$(id -u)" = 0 ] || die root_only
    [ "$(cat /tmp/sysinfo/board_name 2>/dev/null || :)" = "$BOARD" ] || die wrong_board
}
status() {
    check
    [ -f "$FILE" ] && [ ! -L "$FILE" ] || die cellular_file_unavailable
    echo "CURRENT_SHA=$(sha "$FILE")"
    echo "CURRENT_BYTES=$(wc -c < "$FILE")"
    echo "EXPECTED_ORIGINAL_SHA=$ORIGINAL_SHA"
    echo "EXPECTED_PATCHED_SHA=$PATCHED_SHA"
    [ -d "$BACKUP" ] && echo "BACKUP=$BACKUP" || echo "BACKUP=none"
    df -h /overlay
}
atomic_copy() {
    src="$1"
    dst="$2"
    temp="$dst.v12.$$"
    cp "$src" "$temp" || return 1
    chmod 644 "$temp" || { rm -f "$temp"; return 1; }
    mv -f "$temp" "$dst" || { rm -f "$temp"; return 1; }
}
restore() {
    [ "$(sha "$BACKUP/original.js")" = "$ORIGINAL_SHA" ] || return 1
    atomic_copy "$BACKUP/original.js" "$FILE" || return 1
    [ "$(sha "$FILE")" = "$ORIGINAL_SHA" ]
}
apply() {
    check
    [ -f "$FILE" ] && [ ! -L "$FILE" ] || die cellular_file_unavailable
    [ ! -e "$BACKUP" ] || die backup_exists_no_overwrite
    for bin in wget sha256sum awk cmp; do
        command -v "$bin" >/dev/null 2>&1 || die missing_dependency
    done
    # No blind overwrite. If local JS changes, stop before any backup.
    actual="$(sha "$FILE")"
    if [ "$actual" != "$ORIGINAL_SHA" ]; then
        echo "ACTUAL_SHA=$actual" >&2
        die unexpected_local_cellular_file_unchanged
    fi
    available="$(df -k /overlay | awk 'NR==2{print $4}')"
    case "$available" in ''|*[!0-9]*) die overlay_space_unknown ;; esac
    [ "$available" -ge 96 ] || die low_overlay_space
    stage="$(mktemp -d /tmp/veci-ui-v12.XXXXXX)" || die tmp_staging_failed
    applied=0
    finished=0
    tidy() {
        rc=$?
        trap - EXIT
        if [ "$applied" = 1 ] && [ "$finished" != 1 ]; then
            echo "V12_INSTALL_FAILED_RESTORING" >&2
            restore || echo "V12_RECOVERY_NEEDS_MANUAL_INSPECTION=$BACKUP" >&2
        fi
        rm -rf "$stage"
        exit "$rc"
    }
    trap tidy EXIT
    trap 'exit 130' INT TERM
    wget -q -O "$stage/patched.js" \
      "$URL/$PATCH_COMMIT/scripts/veci-sms-ui-live-captured-20261012/cellular.js" ||
        die patch_download_failed
    [ "$(sha "$stage/patched.js")" = "$PATCHED_SHA" ] || die patched_sha_mismatch
    grep -Fq "SMS Inbox is not enabled yet" "$stage/patched.js" || die missing_consent_notice
    grep -Fq "'messagingStorage'" "$stage/patched.js" || die missing_storage_rpc
    grep -Fq "Number.isSafeInteger" "$stage/patched.js" || die missing_metadata_validation
    if grep -Eq 'AT\+CMGL=4|AT\+CMGR=|AT\+CUSD=|AT\+CMGS=' "$stage/patched.js"; then
        die forbidden_sms_content_or_ussd
    fi
    # Check original again before installing, to avoid stomping local edits.
    [ "$(sha "$FILE")" = "$ORIGINAL_SHA" ] || die original_changed_during_preflight
    mkdir "$BACKUP" || die cannot_create_backup
    cp -p "$FILE" "$BACKUP/original.js" || die backup_copy_failed
    [ "$(sha "$BACKUP/original.js")" = "$ORIGINAL_SHA" ] || die backup_checksum_failed
    echo "$PATCH_COMMIT" > "$BACKUP/source-commit"
    applied=1
    atomic_copy "$stage/patched.js" "$FILE" || die patch_copy_failed
    [ "$(sha "$FILE")" = "$PATCHED_SHA" ] || die installed_checksum_failed
    finished=1
    echo "V12_UI_ASSETS_LIVE_PASS"
    echo "NO_MODEM_AT_COMMAND_SENT"
    echo "BACKUP=$BACKUP"
    echo "Browser hard refresh Cellular, then click Check stored SMS count"
    status
}
rollback() {
    check
    [ -f "$BACKUP/original.js" ] || die backup_not_found
    [ "$(sha "$BACKUP/original.js")" = "$ORIGINAL_SHA" ] || die backup_corrupt
    current="$(sha "$FILE")"
    [ "$current" = "$PATCHED_SHA" ] || [ "$current" = "$ORIGINAL_SHA" ] ||
        die newer_local_change_detected_no_overwrite
    restore || die rollback_failed
    echo "V12_UI_ROLLBACK_PASS"
    status
}
[ "$#" -eq 1 ] || die usage_status_apply_rollback
case "$1" in
    status) status ;;
    apply) apply ;;
    rollback) rollback ;;
    *) die unknown_operation ;;
esac
