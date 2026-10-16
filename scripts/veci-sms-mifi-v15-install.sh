#!/bin/sh
# WE5927 VeCI v1.5: replace overcomplicated v1.4 SMS with MiFi Inbox + ON/OFF.
# No flash, no LTE restart, no modem command during install, one rpcd restart.
set -eu
umask 077
LC_ALL=C; export LC_ALL
PIN=f057a7853f25bb7aea81ab2131f452b5b3de2a98
URL=https://raw.githubusercontent.com/aicoach-alpha/zbt-we5927-openwrt
SRC=scripts/veci-sms-mifi-v15-staged
UI=/www/veci/js/pages/cellular.js
RPC=/usr/libexec/rpcd/veci.sms
META=/usr/libexec/veci-sms-inbox-index
META_ACL=/usr/share/rpcd/acl.d/veci-sms-inbox-we5927.json
PRIVATE=/usr/libexec/veci-sms-private-read
PRIVATE_UC=/usr/share/rpcd/ucode/veci-sms-private-consent.uc
PRIVATE_ACL=/usr/share/rpcd/acl.d/veci-sms-private-owner.json
MIFI=/usr/libexec/veci-sms-mifi-inbox
FLAG=/etc/veci-sms-feature
BACK=/root/veci-sms-mifi-v15-rollback
OLD_UI=76c8354c4db32188851f1c4af93555ba3d4ddbba29e1e256e259cbbeb58902dc
OLD_RPC=24102a1919856de11a2eb207c57e56b78f85612a50bf71628ff1959edf856a2e
OLD_META=ff11a42144181de131f1e595db163bd718a9e63cdf594e4fe2d7ec
OLD_META_ACL=8bfe87008b20d8060f07e6ee7058cea1873bc7f39c99a5c58ea22c76b2fd1fa4
OLD_PRIVATE=33fdeeaeaf991733e461825c6439ba76eff404c89a24f3435250e764f89e2b72
OLD_PRIVATE_UC=b5d8a10c04c305e9e5b493e299342f66858eb7468b831f9c7c50702eb2b48e2c
OLD_PRIVATE_ACL=891e2643f44262adcaf6a3bc9d76865c58003967784c3015bb2feffc8fde7f29
NEW_RPC=fca9c3d16537d2ab2bcba6ecff973913a3d56261940d20f0e19d1396df301a82
NEW_MIFI=99aa086fba307b4a6070345eea73f8acb9268c5ba51d3776f7290b6baed52186
NEW_UI=5ecd42fbb1b0e94db30a3590b9cba9e2fd4b8d6f2175c16ce97a755a2fff63dd
NEW_ACL=c41849a66f4f3f53ca84def2db3b58486c40899bac51896258f1a5c6296327d0
fail() { printf 'SMS_MIFI_V15_ERROR=%s\n' "$1" >&2; exit 1; }
sha() { sha256sum "$1" 2>/dev/null | awk '{print $1}'; }
board() {
    [ "$(id -u)" = 0 ] || fail root_required
    [ "$(cat /tmp/sysinfo/board_name 2>/dev/null || :)" = zbtlink,zbt-we5927 ] || fail wrong_router
}
# A current v1.4 may have had an independent hotfix. Refuse symlinks and
# unfamiliar modules, but preserve actual bytes rather than obsolete hashes.
check_old() {
    for f in "$UI" "$RPC" "$META" "$META_ACL" "$PRIVATE" "$PRIVATE_UC" "$PRIVATE_ACL"; do
        [ -f "$f" ] && [ ! -L "$f" ] && [ -s "$f" ] || return 1
    done
    grep -Fq 'cellular-sms-private-panel' "$UI" &&
    grep -Fq "api.call('veci.sms.private', 'readSlot'" "$UI" &&
    grep -Fq 'listIndex' "$RPC" &&
    grep -Fq 'AT+CMGL=4' "$META" &&
    grep -Fq '"veci.sms"' "$META_ACL" &&
    grep -Fq 'veci.sms.private' "$PRIVATE_UC" &&
    grep -Fq '"veci.sms.private"' "$PRIVATE_ACL" &&
    sh -n "$RPC" &&
    sh -n "$META" &&
    sh -n "$PRIVATE"
}
legacy_sha() {
    # Only hashes, no message content, secrets, session IDs or modem I/O.
    for f in "$UI" "$RPC" "$META" "$META_ACL" "$PRIVATE" "$PRIVATE_UC" "$PRIVATE_ACL"; do
        sha "$f" || return 1
    done
}
check_new() {
    [ "$(sha "$UI")" = "$NEW_UI" ] &&
    [ "$(sha "$RPC")" = "$NEW_RPC" ] &&
    [ "$(sha "$MIFI")" = "$NEW_MIFI" ] &&
    [ "$(sha "$META_ACL")" = "$NEW_ACL" ] &&
    [ -f "$BACK/meta" ] &&
    [ "$(sha "$META")" = "$(sha "$BACK/meta")" ] &&
    [ ! -e "$PRIVATE" ] && [ ! -e "$PRIVATE_UC" ] &&
    [ ! -e "$PRIVATE_ACL" ]
}
registered() {
    ubus -S list 2>/dev/null | grep -qx 'veci.sms' &&
    ubus -S list 2>/dev/null | grep -qx 'veci.cellular' &&
    ! ubus -S list 2>/dev/null | grep -qx 'veci.sms.private'
}
restart_rpc() {
    /etc/init.d/rpcd restart >/dev/null 2>&1 || return 1
    count=0
    while [ "$count" -lt 12 ]; do
        if registered; then return 0; fi
        count=$((count+1))
        sleep 1
    done
    return 1
}
anonymous_denied() {
    for method in listMessages setEnabled; do
        response="$(ubus call session access "{\"ubus_rpc_session\":\"00000000000000000000000000000000\",\"scope\":\"ubus\",\"object\":\"veci.sms\",\"function\":\"$method\"}" 2>/dev/null)" || return 1
        access="$(printf '%s' "$response" | jsonfilter -e '@.access' 2>/dev/null || :)"
        [ "$access" = 0 ] || [ "$access" = false ] || return 1
    done
}
status() {
    board
    if check_new; then echo 'SMS_MIFI_V15_FILES=installed'; else echo 'SMS_MIFI_V15_FILES=other_version'; fi
    if [ -f "$FLAG" ] && [ ! -L "$FLAG" ]; then
        case "$(cat "$FLAG" 2>/dev/null || :)" in
            1) echo 'SMS_FEATURE=ON' ;;
            0) echo 'SMS_FEATURE=OFF' ;;
            *) echo 'SMS_FEATURE=invalid' ;;
        esac
    else echo 'SMS_FEATURE=not_set'; fi
    if registered; then echo 'SMS_MIFI_V15_RPC=registered'; else echo 'SMS_MIFI_V15_RPC=not_ready'; fi
    [ -f "$BACK/ui" ] && echo 'SMS_MIFI_V15_BACKUP=present' || echo 'SMS_MIFI_V15_BACKUP=absent'
    echo 'INSTALL_MODEM_COMMANDS=false'
}
atomic_copy() {
    from="$1"; to="$2"; mode="$3"
    tmp="$to.newv15.$$"
    cp "$from" "$tmp" || return 1
    chmod "$mode" "$tmp" || return 1
    mv -f "$tmp" "$to" || return 1
}
restore() {
    [ -f "$BACK/SHA256SUMS" ] || return 1
    (cd "$BACK" && sha256sum -c SHA256SUMS >/dev/null 2>&1) || return 1
    # Metadata worker is not modified by the installer; avoid undoing a
    # concurrent change silently.
    [ "$(sha "$META")" = "$(sha "$BACK/meta")" ] || return 1
    atomic_copy "$BACK/ui" "$UI" 644 || return 1
    atomic_copy "$BACK/rpc" "$RPC" 755 || return 1
    atomic_copy "$BACK/meta-acl" "$META_ACL" 644 || return 1
    atomic_copy "$BACK/private" "$PRIVATE" 700 || return 1
    atomic_copy "$BACK/private-uc" "$PRIVATE_UC" 644 || return 1
    atomic_copy "$BACK/private-acl" "$PRIVATE_ACL" 644 || return 1
    rm -f "$MIFI" "$FLAG" || return 1
    [ "$(sha "$UI")" = "$(sha "$BACK/ui")" ] &&
    [ "$(sha "$RPC")" = "$(sha "$BACK/rpc")" ]
}
apply() {
    board
    for tool in wget sha256sum awk grep ubus jsonfilter flock uci; do
        command -v "$tool" >/dev/null 2>&1 || fail missing_tools
    done
    [ -x /etc/init.d/rpcd ] || fail rpcd_missing
    check_old || {
        echo 'SMS_MIFI_V15_BASELINE=unrecognized_v14_files' >&2
        # Diagnostics contain only file fingerprints, never SMS contents.
        for pair in "ui:$UI" "rpc:$RPC" "metadata:$META" "acl:$META_ACL" "worker:$PRIVATE" "ucode:$PRIVATE_UC" "private_acl:$PRIVATE_ACL"; do
            name="${pair%%:*}"; file="${pair#*:}"
            printf 'SMS_BASELINE_%s=%s\n' "$name" "$(sha "$file" || echo absent)" >&2
        done
        fail unrecognized_live_v14_files
    }
    [ ! -e "$MIFI" ] && [ ! -L "$MIFI" ] || fail mifi_worker_exists
    [ ! -e "$FLAG" ] && [ ! -L "$FLAG" ] || fail existing_setting_not_overwritten
    [ ! -e "$BACK" ] || fail backup_already_exists
    ubus -S list 2>/dev/null | grep -qx 'veci.sms.private' || fail old_private_rpc_missing
    ubus -S list 2>/dev/null | grep -qx 'veci.sms' || fail existing_sms_rpc_missing
    free="$(df -k /overlay | awk 'NR==2{print $4}')"
    case "$free" in ''|*[!0-9]*) fail unknown_overlay_space ;; esac
    [ "$free" -ge 200 ] || fail insufficient_space
    baseline="$(legacy_sha)" || fail baseline_unavailable
    # The already-live uhttpd must keep ubus ACL authentication enabled.
    uci -q show uhttpd >/dev/null 2>&1 || fail uhttpd_status_unavailable
    if uci -q show uhttpd | awk -F= '$1 ~ /\.no_ubusauth$/ {
        v=$2;gsub(/[^[:alnum:]]/,"",v);
        if(v=="1"||v=="yes"||v=="true")bad=1
    } END{exit !bad}'; then fail uhttpd_auth_disabled; fi
    pids="$(pidof uhttpd 2>/dev/null || :)"
    [ -n "$pids" ] || fail uhttpd_not_running
    for pid in $pids; do
        [ -r "/proc/$pid/cmdline" ] || fail uhttpd_status_unknown
        if tr '\000' '\n' < "/proc/$pid/cmdline" | grep -qx -- '-a'; then
            fail uhttpd_auth_disabled
        fi
    done
    work="$(mktemp -d /tmp/sms-mifi-v15.XXXXXX)" || fail staging_failed
    touched=0; success=0; backup_created=0
    cleanup() {
        code=$?
        trap - EXIT
        if [ "$touched" = 1 ] && [ "$success" != 1 ]; then
            echo 'SMS_MIFI_V15_AUTO_ROLLBACK=started' >&2
            if restore && /etc/init.d/rpcd restart >/dev/null 2>&1; then
                echo 'SMS_MIFI_V15_AUTO_ROLLBACK=PASS' >&2
            else
                echo 'SMS_MIFI_V15_AUTO_ROLLBACK=manual_recovery_required' >&2
            fi
        fi
        if [ "$backup_created" = 1 ] && [ "$touched" != 1 ] &&
           [ -d "$BACK" ] && [ ! -L "$BACK" ]; then
            rm -rf "$BACK"
        fi
        rm -rf "$work"
        exit "$code"
    }
    trap cleanup EXIT
    trap 'exit 130' INT TERM
    wget -qO "$work/rpc" "$URL/$PIN/$SRC/rpcd-veci.sms" || fail rpc_download
    wget -qO "$work/mifi" "$URL/$PIN/$SRC/veci-sms-mifi-inbox" || fail worker_download
    wget -qO "$work/ui" "$URL/$PIN/$SRC/cellular.js" || fail ui_download
    wget -qO "$work/acl" "$URL/$PIN/$SRC/acl.json" || fail acl_download
    [ "$(sha "$work/rpc")" = "$NEW_RPC" ] || fail rpc_hash
    [ "$(sha "$work/mifi")" = "$NEW_MIFI" ] || fail worker_hash
    [ "$(sha "$work/ui")" = "$NEW_UI" ] || fail ui_hash
    [ "$(sha "$work/acl")" = "$NEW_ACL" ] || fail acl_hash
    sh -n "$work/rpc" && sh -n "$work/mifi" || fail syntax_error
    grep -Fq '"listMessages"' "$work/acl" || fail acl_contract
    grep -Fq 'getConfig' "$work/rpc" || fail rpc_contract
    # No assumptions about older hotfix SHAs: ensure no one touched the
    # device files while the four new assets were being downloaded.
    [ "$(legacy_sha)" = "$baseline" ] || fail concurrent_change
    check_old || fail concurrent_change
    mkdir "$BACK" || fail backup_creation
    backup_created=1
    cp -p "$UI" "$BACK/ui" || fail backup_ui
    cp -p "$RPC" "$BACK/rpc" || fail backup_rpc
    cp -p "$META" "$BACK/meta" || fail backup_metadata
    cp -p "$META_ACL" "$BACK/meta-acl" || fail backup_acl
    cp -p "$PRIVATE" "$BACK/private" || fail backup_private
    cp -p "$PRIVATE_UC" "$BACK/private-uc" || fail backup_private_uc
    cp -p "$PRIVATE_ACL" "$BACK/private-acl" || fail backup_private_acl
    (cd "$BACK" && sha256sum ui rpc meta meta-acl private private-uc private-acl > SHA256SUMS) || fail backup_manifest
    (cd "$BACK" && sha256sum -c SHA256SUMS >/dev/null 2>&1) || fail backup_integrity
    touched=1
    atomic_copy "$work/mifi" "$MIFI" 700 || fail worker_install
    atomic_copy "$work/rpc" "$RPC" 755 || fail rpc_install
    atomic_copy "$work/acl" "$META_ACL" 644 || fail acl_install
    atomic_copy "$work/ui" "$UI" 644 || fail ui_install
    (umask 077; printf '1\n' > "$FLAG") || fail setting_creation
    chmod 600 "$FLAG" || fail setting_permissions
    # Retire v1.4 authorization+worker so SMS OFF cannot be bypassed.
    rm -f "$PRIVATE" "$PRIVATE_UC" "$PRIVATE_ACL" || fail retiring_old_private_failed
    check_new || fail integrity
    restart_rpc || fail rpc_registration
    anonymous_denied || fail anonymous_access_not_denied
    success=1
    echo 'SMS_MIFI_V15_LIVE_BACKEND_PASS'
    echo 'SMS_MIFI_V15_SWITCH_DEFAULT_ON_PASS'
    echo 'SMS_MIFI_V15_PRIVATE_V14_RETIRED_PASS'
    echo 'SMS_MIFI_V15_ANONYMOUS_DENIED_PASS'
    echo 'SMS_MIFI_V15_METADATA_PRESERVED_PASS'
    echo 'NO_SMS_MODEM_COMMAND_DURING_INSTALL=true'
    status
}
rollback() {
    board
    [ -f "$BACK/ui" ] && [ -f "$BACK/SHA256SUMS" ] || fail backup_missing
    check_new || fail unexpected_live_files
    restore || fail rollback_files
    /etc/init.d/rpcd restart >/dev/null 2>&1 || fail rpcd_restart
    echo 'SMS_MIFI_V15_ROLLBACK_PASS'
    echo 'NO_SMS_MODEM_COMMAND_DURING_ROLLBACK=true'
}
[ "$#" -eq 1 ] || fail usage_apply_status_rollback
case "$1" in
    apply) apply ;;
    status) status ;;
    rollback) rollback ;;
    *) fail unknown_action ;;
esac
