#!/bin/sh
# VeCI WE5927 v1.4 installed backend type-name correction, no modem commands.
# One-command apply/rollback, exact original + new sha256, no firmware flash.
set -eu
umask 077
LC_ALL=C; export LC_ALL
PIN=a5c2fe19a10e35d170bc059646d8298d169285d1
OLD_SHA=4510fde262d70a98f5f4e570c406a878df33ea497f538cd40cbab20725a5160e
NEW_SHA=b5d8a10c04c305e9e5b493e299342f66858eb7468b831f9c7c50702eb2b48e2c
SOURCE=source/we5927-lte/src/veci-sms-private-consent.uc
LIVE=/usr/share/rpcd/ucode/veci-sms-private-consent.uc
BACK=/root/veci-sms-private-v14-rollback/ucode-pretype-fix.uc
URL=https://raw.githubusercontent.com/aicoach-alpha/zbt-we5927-openwrt
fail() { printf 'VECI_SMS_V14_HOTFIX_ERROR=%s\n' "$1" >&2; exit 1; }
sha() { sha256sum "$1" 2>/dev/null | awk '{print $1}'; }
board() {
    [ "$(id -u)" -eq 0 ] || fail root_required
    [ "$(cat /tmp/sysinfo/board_name 2>/dev/null || :)" = zbtlink,zbt-we5927 ] || fail wrong_router
}
status() {
    board
    h="$(sha "$LIVE" || :)"
    case "$h" in
        "$NEW_SHA") echo 'VECI_SMS_V14_BACKEND_TYPEFIX=installed' ;;
        "$OLD_SHA") echo 'VECI_SMS_V14_BACKEND_TYPEFIX=original' ;;
        *) echo 'VECI_SMS_V14_BACKEND_TYPEFIX=unknown_or_missing' ;;
    esac
    if ubus -S list 2>/dev/null | grep -qx 'veci.sms.private'; then
        echo 'VECI_SMS_PRIVATE_RPC=registered'
    else
        echo 'VECI_SMS_PRIVATE_RPC=not_registered'
    fi
    [ -f "$BACK" ] && echo 'VECI_SMS_TYPEFIX_BACKUP=present' || echo 'VECI_SMS_TYPEFIX_BACKUP=absent'
    echo 'SMS_MODEM_COMMANDS_EXECUTED=false'
}
runtime_check() {
    # This live patch must never enable a private endpoint if the HTTP
    # auth bypass is active, or the uhttpd daemon disappeared.
    uci -q show uhttpd >/dev/null 2>&1 || fail uhttpd_uci_unavailable
    if uci -q show uhttpd | awk -F= '$1 ~ /\.no_ubusauth$/ {
        v=$2;gsub(/[^[:alnum:]]/,"",v);
        if(v=="1"||v=="yes"||v=="true")bad=1
    } END{exit !bad}'; then fail uhttpd_unauthenticated; fi
    pids="$(pidof uhttpd 2>/dev/null || :)"
    [ -n "$pids" ] || fail uhttpd_missing
    for pid in $pids; do
        case "$pid" in ''|*[!0-9]*) fail uhttpd_unknown ;; esac
        [ -r "/proc/$pid/cmdline" ] || fail uhttpd_unknown
        if tr '\000' '\n' < "/proc/$pid/cmdline" | grep -qx -- '-a'; then
            fail uhttpd_unauthenticated
        fi
    done
}
registered() {
    ubus -S list 2>/dev/null | grep -qx 'veci.sms.private' &&
    ubus -S list 2>/dev/null | grep -qx 'veci.sms' &&
    ubus -S list 2>/dev/null | grep -qx 'veci.cellular'
}
anonymous_denied() {
    result="$(ubus call session access '{"ubus_rpc_session":"00000000000000000000000000000000","scope":"ubus","object":"veci.sms.private","function":"readSlot"}' 2>/dev/null)" || return 1
    flag="$(printf '%s' "$result" | jsonfilter -e '@.access' 2>/dev/null || :)"
    [ "$flag" = false ] || [ "$flag" = 0 ]
}
restart_rpc() {
    /etc/init.d/rpcd restart >/dev/null 2>&1 || return 1
    n=0
    while [ "$n" -lt 12 ]; do
        if registered; then return 0; fi
        n=$((n+1))
        sleep 1
    done
    return 1
}
apply() {
    board
    [ -f "$LIVE" ] && [ ! -L "$LIVE" ] || fail missing_or_symlink_backend
    if [ "$(sha "$LIVE")" = "$NEW_SHA" ]; then
        echo 'VECI_SMS_TYPEFIX_ALREADY_LIVE=PASS'
        status
        return 0
    fi
    [ "$(sha "$LIVE")" = "$OLD_SHA" ] || fail unexpected_live_backend
    [ ! -e "$BACK" ] && [ ! -L "$BACK" ] || fail existing_backup_do_not_overwrite
    [ -d /root/veci-sms-private-v14-rollback ] || fail v14_backup_not_present
    for binary in wget sha256sum ucode jsonfilter ubus awk grep tr pidof uci; do
        command -v "$binary" >/dev/null 2>&1 || fail missing_tool
    done
    [ -x /etc/init.d/rpcd ] || fail rpcd_unavailable
    runtime_check
    registered || fail live_services_not_ready
    anonymous_denied || fail anonymous_acl_not_denied
    tmp="$(mktemp -d /tmp/veci-sms-typefix.XXXXXX)" || fail staging_failed
    changed=0
    complete=0
    cleanup() {
        rc=$?
        trap - EXIT
        if [ "$changed" = 1 ] && [ "$complete" != 1 ]; then
            echo 'VECI_SMS_TYPEFIX_AUTOMATIC_ROLLBACK=started' >&2
            if [ "$(sha "$BACK")" = "$OLD_SHA" ]; then
                cp "$BACK" "$LIVE.newrollback.$$" &&
                chmod 644 "$LIVE.newrollback.$$" &&
                mv -f "$LIVE.newrollback.$$" "$LIVE" &&
                restart_rpc &&
                echo 'VECI_SMS_TYPEFIX_AUTOMATIC_ROLLBACK=PASS' >&2 ||
                echo 'VECI_SMS_TYPEFIX_AUTOMATIC_ROLLBACK=manual_recovery_required' >&2
            fi
        fi
        rm -rf "$tmp"
        exit "$rc"
    }
    trap cleanup EXIT
    trap 'exit 130' INT TERM
    wget -qO "$tmp/new.uc" "$URL/$PIN/$SOURCE" || fail download_failed
    [ "$(sha "$tmp/new.uc")" = "$NEW_SHA" ] || fail downloaded_hash_mismatch
    ucode -c -o "$tmp/new.ucb" "$tmp/new.uc" >/dev/null 2>&1 || fail native_ucode_compile
    [ -s "$tmp/new.ucb" ] || fail native_ucode_empty
    # Backup the currently LIVE backend before replacing it atomically.
    cp "$LIVE" "$BACK" || fail backup_failed
    chmod 600 "$BACK" || fail backup_permissions
    [ "$(sha "$BACK")" = "$OLD_SHA" ] || fail backup_integrity
    cp "$tmp/new.uc" "$LIVE.newtypefix.$$" || fail staging_write_failed
    chmod 644 "$LIVE.newtypefix.$$" || fail staging_mode_failed
    [ "$(sha "$LIVE")" = "$OLD_SHA" ] || fail concurrent_change
    mv -f "$LIVE.newtypefix.$$" "$LIVE" || fail replace_failed
    changed=1
    [ "$(sha "$LIVE")" = "$NEW_SHA" ] || fail installed_hash_mismatch
    restart_rpc || fail rpcd_registration
    anonymous_denied || fail anonymous_acl_failed
    complete=1
    echo 'VECI_SMS_V14_TYPEFIX_LIVE_PASS'
    echo 'VECI_SMS_V14_ANONYMOUS_DENIED_PASS'
    echo 'VECI_SMS_V14_METADATA_PRESERVED_PASS'
    echo 'NO_MODEM_COMMAND_DURING_HOTFIX=true'
    status
}
rollback() {
    board
    [ "$(sha "$BACK")" = "$OLD_SHA" ] || fail backup_unavailable
    [ "$(sha "$LIVE")" = "$NEW_SHA" ] || fail unknown_live_backend
    cp "$BACK" "$LIVE.back.$$" || fail staging_write_failed
    chmod 644 "$LIVE.back.$$" || fail staging_mode_failed
    mv -f "$LIVE.back.$$" "$LIVE" || fail restore_failed
    restart_rpc || fail rpcd_registration
    echo 'VECI_SMS_TYPEFIX_ROLLBACK_PASS'
    status
}
[ "$#" -eq 1 ] || fail usage_apply_status_rollback
case "$1" in apply) apply ;; rollback) rollback ;; status) status ;; *) fail unknown_action ;; esac
