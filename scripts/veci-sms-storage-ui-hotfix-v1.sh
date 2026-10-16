#!/bin/sh
# Reversible, no-AT VeCI UI-only SMS storage overlay for physical WE5927.
# NO SMS listing, USSD, SIM/LTE/network writes, firmware flash or reboot.
set -eu
umask 077
LC_ALL=C
export LC_ALL
REPO=https://raw.githubusercontent.com/aicoach-alpha/veci
ORIGINAL_COMMIT=f19603b6172854dfeca3861826017d8f1aa1268c
UPDATED_COMMIT=88009f1fd394eeeb583f27839d29c714e31b91b6
PAGE=/www/veci/js/pages/cellular.js
UTIL=/www/veci/js/lib/messaging.js
BACKUP=/root/veci-sms-storage-ui-v1-rollback

fail() { echo "UI_ERROR: $*" >&2; exit 1; }
board() {
    [ "$(cat /tmp/sysinfo/board_name 2>/dev/null || :)" = zbtlink,zbt-we5927 ] ||
        fail "Wrong board"
}
status() {
    board
    [ -d "$BACKUP" ] && echo "UI_BACKUP=$BACKUP" || echo "UI_BACKUP=none"
    [ -f "$UTIL" ] && echo "Formatter present" || echo "Formatter absent"
    df -h /overlay
}
put() {
    temp="$2.ui.$$"
    cp "$1" "$temp" || return 1
    chmod 644 "$temp" || return 1
    mv -f "$temp" "$2"
}
restore() {
    [ -s "$BACKUP/old-cellular" ] || return 1
    put "$BACKUP/old-cellular" "$PAGE" || return 1
    if [ -e "$BACKUP/old-messaging-present" ]; then
        [ -s "$BACKUP/old-messaging" ] || return 1
        put "$BACKUP/old-messaging" "$UTIL" || return 1
    else
        rm -f "$UTIL"
    fi
}
rollback() {
    board
    [ -s "$BACKUP/old-cellular" ] || fail "Missing backup"
    [ -s "$BACKUP/old-cellular.sha256" ] || fail "Missing backup digest"
    want="$(cat "$BACKUP/old-cellular.sha256")"
    got="$(sha256sum "$BACKUP/old-cellular" | awk '{print $1}')"
    [ "$want" = "$got" ] || fail "Backup checksum mismatch"
    restore || fail "Restore failed"
    cmp -s "$PAGE" "$BACKUP/old-cellular" || fail "Restored file mismatch"
    echo "VECI_SMS_STORAGE_UI_ROLLBACK_PASS"
    status
}
apply() {
    [ "$(id -u)" = 0 ] || fail "Root required"
    board
    [ -f "$PAGE" ] && [ ! -L "$PAGE" ] || fail "Missing/symlinked Cellular page"
    [ ! -e "$UTIL" ] && [ ! -L "$UTIL" ] || fail "Formatter already exists, no overwrite"
    [ ! -e "$BACKUP" ] || fail "Backup directory exists, no overwrite"
    for x in wget cmp sha256sum awk; do
        command -v "$x" >/dev/null 2>&1 || fail "Required tool missing: $x"
    done
    free="$(df -k /overlay | awk 'NR==2{print $4}')"
    case "$free" in ''|*[!0-9]*) fail "Unknown overlay free space" ;; esac
    [ "$free" -ge 96 ] || fail "Overlay below 96 KiB free"
    work="$(mktemp -d /tmp/veci-ui.XXXXXX)" || fail "TMP staging failed"
    changed=0
    success=0
    cleanup() {
        rc=$?
        trap - EXIT
        if [ "$changed" = 1 ] && [ "$success" != 1 ]; then
            echo "VECI_UI_INSTALL_FAILED_RESTORING" >&2
            restore || echo "UI_MANUAL_RECOVERY_REQUIRED=$BACKUP" >&2
        fi
        rm -rf "$work"
        exit "$rc"
    }
    trap cleanup EXIT
    trap 'exit 130' INT TERM

    # Only compatible with byte-identical known-good firmware-pinned base.
    wget -q -O "$work/original" "$REPO/$ORIGINAL_COMMIT/veci/js/pages/cellular.js" ||
        fail "Unable to fetch immutable original source"
    cmp -s "$PAGE" "$work/original" ||
        fail "Installed Cellular differs from pinned base: untouched"
    wget -q -O "$work/new-page" "$REPO/$UPDATED_COMMIT/veci/js/pages/cellular.js" ||
        fail "Unable to fetch immutable new page"
    wget -q -O "$work/new-util" "$REPO/$UPDATED_COMMIT/veci/js/lib/messaging.js" ||
        fail "Unable to fetch immutable formatter"
    grep -Fq "import { smsStorageLabel }" "$work/new-page" ||
        fail "Missing strict formatter import"
    grep -Fq "'messagingStorage'" "$work/new-page" ||
        fail "Missing read-only v2 RPC call"
    grep -Fq "SMS Inbox is not enabled yet" "$work/new-page" ||
        fail "Missing inbox disabled warning"
    grep -Fq "Number.isSafeInteger" "$work/new-util" ||
        fail "Formatter does not validate numeric data"
    if grep -Eq 'AT\+CMGL=4|AT\+CUSD=1|sendSms|readSms' "$work/new-page"; then
        fail "Unexpected sensitive action"
    fi
    [ "$(wc -c < "$work/new-page")" -le 20000 ] || fail "Unexpected page size"
    [ "$(wc -c < "$work/new-util")" -le 3000 ] || fail "Unexpected util size"

    mkdir "$BACKUP" || fail "Cannot create backup directory"
    cp -p "$PAGE" "$BACKUP/old-cellular" || fail "Existing page backup failed"
    sha256sum "$BACKUP/old-cellular" | awk '{print $1}' > "$BACKUP/old-cellular.sha256"
    echo "$ORIGINAL_COMMIT" > "$BACKUP/original-commit"
    echo "$UPDATED_COMMIT" > "$BACKUP/new-commit"
    changed=1
    put "$work/new-util" "$UTIL" || fail "Metadata formatter write failed"
    put "$work/new-page" "$PAGE" || fail "Cellular page write failed"
    cmp -s "$UTIL" "$work/new-util" && cmp -s "$PAGE" "$work/new-page" ||
        fail "Installed payload mismatch"
    success=1
    echo "VECI_SMS_STORAGE_UI_LIVE_ASSETS_PASS"
    echo "NO_AT_COMMAND_SENT_BY_INSTALLER"
    echo "UI_BACKUP=$BACKUP"
    echo "Hard refresh VeCI Cellular after installing"
    status
}
[ "$#" -eq 1 ] || fail "Usage: sh ui-hotfix.sh status|apply|rollback"
case "$1" in
    status) status ;;
    apply) apply ;;
    rollback) rollback ;;
    *) fail "Unknown command" ;;
esac
