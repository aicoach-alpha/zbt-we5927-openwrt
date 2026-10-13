#!/bin/sh
# VeCI WE5927 private SMS read v1.4: explicit install + rollback.
# NO modem calls during installation. No sysupgrade. No LTE restart.
set -eu
umask 077
LC_ALL=C; export LC_ALL
PIN=bde4ec2c608c5b03f7bab2a010de5b9b67f379bb
REPO=https://raw.githubusercontent.com/aicoach-alpha/zbt-we5927-openwrt
BASE=/www/veci/js/pages/cellular.js
WORKER=/usr/libexec/veci-sms-private-read
UC=/usr/share/rpcd/ucode/veci-sms-private-consent.uc
ACL=/usr/share/rpcd/acl.d/veci-sms-private-owner.json
BACK=/root/veci-sms-private-v14-rollback
PRIOR_SHA=5f34ca2320a77f0f91d1bda524e84f18c79af1d589ddeb2bf9392c2cd30af6ca
NEW_UI_SHA=29360941a951ca5bbf72e9ffb005db9e13d3d038c876ada9c993a9f6035bb9d4
WORKER_SHA=33fdeeaeaf991733e461825c6439ba76eff404c89a24f3435250e764f89e2b72
UC_SHA=4510fde262d70a98f5f4e570c406a878df33ea497f538cd40cbab20725a5160e
ACL_SHA=891e2643f44262adcaf6a3bc9d76865c58003967784c3015bb2feffc8fde7f29
SRC_WORKER=source/veci-sms-private-we5927/files/usr/libexec/veci-sms-private-read
SRC_UC=source/we5927-lte/src/veci-sms-private-consent.uc
SRC_ACL=source/we5927-lte/src/veci-sms-private-acl.json
SRC_UI=scripts/veci-sms-private-ui-staged-20261013/cellular.js
fail() { echo "VECI_SMS_V14_ERROR=$1" >&2; exit 1; }
sha() { sha256sum "$1" 2>/dev/null | awk '{print $1}'; }
board() {
    [ "$(id -u)" = 0 ] || fail root_required
    [ "$(cat /tmp/sysinfo/board_name 2>/dev/null || :)" = zbtlink,zbt-we5927 ] || fail wrong_router
}
installed() {
    [ "$(sha "$BASE")" = "$NEW_UI_SHA" ] &&
    [ "$(sha "$WORKER")" = "$WORKER_SHA" ] &&
    [ "$(sha "$UC")" = "$UC_SHA" ] &&
    [ "$(sha "$ACL")" = "$ACL_SHA" ]
}
status() {
    board
    if installed; then echo "SMS_PRIVATE_V14_FILES=installed"; else echo "SMS_PRIVATE_V14_FILES=not_complete"; fi
    if ubus -S list 2>/dev/null | grep -qx 'veci.sms.private'; then
        echo "SMS_PRIVATE_RPC=registered"
    else
        echo "SMS_PRIVATE_RPC=not_registered"
    fi
    if ubus -S list 2>/dev/null | grep -qx 'veci.sms'; then
        echo "SMS_METADATA_V131=registered"
    else
        echo "SMS_METADATA_V131=missing"
    fi
    [ -f "$BACK/cellular-v131.js" ] && echo "SMS_PRIVATE_BACKUP=present" || echo "SMS_PRIVATE_BACKUP=absent"
    echo "NO_MODEM_COMMAND_DURING_INSTALL=true"
}
atomic_copy() {
    src="$1"; dest="$2"; mode="$3"
    temp="$dest.newveci.$$"
    [ -s "$src" ] || return 1
    cp "$src" "$temp" || return 1
    chmod "$mode" "$temp" || { rm -f "$temp"; return 1; }
    mv -f "$temp" "$dest" || { rm -f "$temp"; return 1; }
}
restore() {
    [ "$(sha "$BACK/cellular-v131.js")" = "$PRIOR_SHA" ] || return 1
    atomic_copy "$BACK/cellular-v131.js" "$BASE" 644 || return 1
    rm -f "$UC" "$ACL" "$WORKER" || return 1
    [ "$(sha "$BASE")" = "$PRIOR_SHA" ]
}
apply() {
    board
    for binary in wget sha256sum awk grep ucode jsonfilter ubus flock; do
        command -v "$binary" >/dev/null 2>&1 || fail missing_dependency
    done
    [ -f "$BASE" ] && [ ! -L "$BASE" ] || fail missing_ui
    [ "$(sha "$BASE")" = "$PRIOR_SHA" ] || fail wrong_live_ui_version
    [ ! -e "$WORKER" ] && [ ! -L "$WORKER" ] || fail existing_private_worker
    [ ! -e "$UC" ] && [ ! -L "$UC" ] || fail existing_private_ucode
    [ ! -e "$ACL" ] && [ ! -L "$ACL" ] || fail existing_private_acl
    [ ! -e "$BACK" ] || fail backup_exists
    ubus -S list 2>/dev/null | grep -qx 'veci.cellular' || fail no_cellular_rpc
    ubus -S list 2>/dev/null | grep -qx 'veci.sms' || fail no_sms_metadata_rpc
    ubus -S list 2>/dev/null | grep -qx 'veci.sms.private' && fail private_rpc_already_present
    # Never activate private RPC when uhttpd authentication is disabled.
    if uci -q show uhttpd 2>/dev/null | awk -F= '$1 ~ /\.no_ubusauth$/ {v=$2; gsub(/[^[:alnum:]]/,"",v); if(v=="1"||v=="yes"||v=="true")bad=1} END{exit !bad}'; then
        fail uhttpd_unauthenticated
    fi
    pids="$(pidof uhttpd 2>/dev/null || :)"
    [ -n "$pids" ] || fail uhttpd_process_missing
    for pid in $pids; do
        [ -r "/proc/$pid/cmdline" ] || fail uhttpd_runtime_unknown
        if tr '\000' '\n' < "/proc/$pid/cmdline" | grep -qx -- '-a'; then
            fail uhttpd_unauthenticated
        fi
    done
    [ -f /usr/lib/uhttpd_ubus.so ] || fail no_uhttpd_ubus
    [ -f /usr/lib/rpcd/ucode.so ] || fail no_rpcd_ucode
    ucode -e "require('fs');" >/dev/null 2>&1 || fail no_ucode_fs
    [ -x /etc/init.d/rpcd ] || fail no_rpcd_service
    free="$(df -k /overlay | awk 'NR==2{print $4}')"
    case "$free" in ''|*[!0-9]*) fail unknown_overlay_space ;; esac
    [ "$free" -ge 150 ] || fail overlay_full

    work="$(mktemp -d /tmp/veci-private-v14.XXXXXX)" || fail staging_failed
    touched=0
    done_ok=0
    cleanup() {
        code=$?
        trap - EXIT
        if [ "$touched" = 1 ] && [ "$done_ok" != 1 ]; then
            echo "SMS_PRIVATE_V14_AUTOMATIC_ROLLBACK=started" >&2
            if restore; then
                echo "SMS_PRIVATE_V14_AUTOMATIC_ROLLBACK=files_restored" >&2
            else
                echo "SMS_PRIVATE_V14_AUTOMATIC_ROLLBACK=manual_recovery_required" >&2
            fi
            /etc/init.d/rpcd restart >/dev/null 2>&1 || echo "SMS_PRIVATE_V14_RESTART_REVIEW=needed" >&2
        fi
        rm -rf "$work"
        exit "$code"
    }
    trap cleanup EXIT
    trap 'exit 130' INT TERM
    wget -qO "$work/ui" "$REPO/$PIN/$SRC_UI" || fail ui_download
    wget -qO "$work/worker" "$REPO/$PIN/$SRC_WORKER" || fail worker_download
    wget -qO "$work/uc" "$REPO/$PIN/$SRC_UC" || fail ucode_download
    wget -qO "$work/acl" "$REPO/$PIN/$SRC_ACL" || fail acl_download
    [ "$(sha "$work/ui")" = "$NEW_UI_SHA" ] || fail ui_sha_mismatch
    [ "$(sha "$work/worker")" = "$WORKER_SHA" ] || fail worker_sha_mismatch
    [ "$(sha "$work/uc")" = "$UC_SHA" ] || fail uc_sha_mismatch
    [ "$(sha "$work/acl")" = "$ACL_SHA" ] || fail acl_sha_mismatch
    sh -n "$work/worker" || fail worker_syntax
    ucode -c -o "$work/bytecode" "$work/uc" >/dev/null 2>&1 || fail ucode_syntax
    grep -Fq '"veci.sms.private"' "$work/acl" || fail private_acl_invalid
    grep -Fq 'I_CONFIRM_READ_THIS_ONE_SMS' "$work/ui" || fail missing_consent
    # All validation done before overlay modification.
    [ "$(sha "$BASE")" = "$PRIOR_SHA" ] || fail concurrent_ui_change
    mkdir "$BACK" || fail backup_creation
    cp -p "$BASE" "$BACK/cellular-v131.js" || fail backup_failed
    [ "$(sha "$BACK/cellular-v131.js")" = "$PRIOR_SHA" ] || fail backup_corrupt
    touched=1
    mkdir -p /usr/share/rpcd/ucode
    atomic_copy "$work/worker" "$WORKER" 700 || fail worker_install
    atomic_copy "$work/uc" "$UC" 644 || fail uc_install
    atomic_copy "$work/acl" "$ACL" 644 || fail acl_install
    atomic_copy "$work/ui" "$BASE" 644 || fail ui_install
    installed || fail installed_integrity
    /etc/init.d/rpcd restart >/dev/null 2>&1 || fail rpcd_restart
    ready=0; loops=0
    while [ "$loops" -lt 12 ]; do
        if ubus -S list 2>/dev/null | grep -qx 'veci.sms.private' &&
           ubus -S list 2>/dev/null | grep -qx 'veci.sms' &&
           ubus -S list 2>/dev/null | grep -qx 'veci.cellular'; then
            ready=1; break
        fi
        loops=$((loops+1))
        sleep 1
    done
    [ "$ready" = 1 ] || fail rpc_registration
    anonymous='00000000000000000000000000000000'
    response="$(ubus call session access "{\"ubus_rpc_session\":\"$anonymous\",\"scope\":\"ubus\",\"object\":\"veci.sms.private\",\"function\":\"readSlot\"}" 2>/dev/null)" || fail acl_probe_unavailable
    granted="$(printf '%s' "$response" | jsonfilter -e '@.access' 2>/dev/null || :)"
    [ "$granted" = false ] || [ "$granted" = 0 ] || fail anonymous_access_not_denied
    done_ok=1
    echo "VECI_SMS_PRIVATE_V14_LIVE_BACKEND_PASS"
    echo "VECI_SMS_PRIVATE_V14_ANONYMOUS_DENIED_PASS"
    echo "VECI_SMS_METADATA_V131_PRESERVED_PASS"
    echo "NO_MODEM_COMMAND_DURING_INSTALL=true"
    echo "SMS_READ_ACTUAL_MESSAGE=requires_explicit_user_click"
    status
}
rollback() {
    board
    [ -f "$BACK/cellular-v131.js" ] || fail backup_missing
    [ "$(sha "$BACK/cellular-v131.js")" = "$PRIOR_SHA" ] || fail backup_corrupt
    current="$(sha "$BASE")"
    [ "$current" = "$NEW_UI_SHA" ] || [ "$current" = "$PRIOR_SHA" ] || fail unknown_ui_change
    for pair in "$WORKER:$WORKER_SHA" "$UC:$UC_SHA" "$ACL:$ACL_SHA"; do
        file="$(printf '%s' "$pair" | cut -d: -f1)"
        expected="$(printf '%s' "$pair" | cut -d: -f2)"
        if [ -f "$file" ] && [ "$(sha "$file")" != "$expected" ]; then
            fail modified_private_component
        fi
    done
    restore || fail restore_failed
    /etc/init.d/rpcd restart >/dev/null 2>&1 || fail rpcd_restart
    echo "VECI_SMS_PRIVATE_V14_ROLLBACK_PASS"
    status
}
[ "$#" -eq 1 ] || fail usage_apply_status_rollback
case "$1" in
    apply) apply ;;
    status) status ;;
    rollback) rollback ;;
    *) fail unknown_action ;;
esac
