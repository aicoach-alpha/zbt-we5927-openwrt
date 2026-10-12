#!/bin/sh
# WE5927 operator-run partial overlay hotfix for capabilities only.
# NO firmware flash/reboot, NO LTE or network edit, NO AT/SMS/USSD during install.
# An explicit later messagingCapabilities call sends FOUR read-only AT test commands.
# Not an apk package upgrade. Source and SHA256 pinned to an immutable commit.
set -eu
umask 077
LC_ALL=C
export LC_ALL

SOURCE_SHA=216355e88f30276bec5783fdde0f399200365263
BASE=https://raw.githubusercontent.com/aicoach-alpha/zbt-we5927-openwrt
RPC=/usr/libexec/rpcd/veci.cellular
HELPER=/usr/libexec/veci-modem-capabilities
ACL=/usr/share/rpcd/acl.d/veci-cellular-we5927.json
BACKUP=/root/veci-capability-hotfix-rollback
RPC_SHA=2fde4bb0200f1319a2d63688e5be1422b68b5c3efa7f2dca117cf7f8c0eafada
HELPER_SHA=d0191d99ccfdab5554baf3f2084ce81e1735550e51e64a219ffeb4e3abbdb85c
ACL_SHA=b39a09cd65e264e46373f3e4fd674021a9a6a04622f1c5b6108b981ca3d382c1

die() { echo "HOTFIX_ERROR: $*" >&2; exit 1; }
check_sha() {
    [ -s "$1" ] || return 1
    got="$(sha256sum "$1" 2>/dev/null | awk '{print $1}')" || return 1
    [ "$got" = "$2" ]
}
fetch() {
    wget -q -O "$2" "$BASE/$SOURCE_SHA/$1" ||
        die "HTTPS download failed: $1"
}
board() {
    [ -r /tmp/sysinfo/board_name ] || die "board info missing"
    [ "$(cat /tmp/sysinfo/board_name)" = "zbtlink,zbt-we5927" ] ||
        die "wrong board: abort"
}
status() {
    echo "=== METHODS ==="
    ubus -v list veci.cellular || :
    echo "=== BACKUP ==="
    [ ! -d "$BACKUP" ] || echo "$BACKUP"
    df -h /overlay || :
}
recover_files() {
    cp "$BACKUP/old-rpc" "$RPC" || return 1
    cp "$BACKUP/old-acl" "$ACL" || return 1
    if [ -f "$BACKUP/had-helper" ]; then
        cp "$BACKUP/old-helper" "$HELPER" || return 1
    else
        rm -f "$HELPER" || return 1
    fi
    chmod 755 "$RPC"
    chmod 644 "$ACL"
    [ ! -f "$HELPER" ] || chmod 755 "$HELPER"
}
rollback() {
    board
    [ -s "$BACKUP/old-rpc" ] && [ -s "$BACKUP/old-acl" ] ||
        die "no complete backup; refusing rollback"
    recover_files || die "file restoration failed, check $BACKUP"
    /etc/init.d/rpcd restart || die "RPCD restart failed after rollback"
    echo "ROLLBACK_PASS: previous RPC and ACL restored"
    status
}
put() {
    tmp="$2.hotfix.$$"
    cp "$1" "$tmp" || return 1
    chmod "$3" "$tmp" || return 1
    mv -f "$tmp" "$2" || return 1
}
preflight() {
    [ "$(id -u)" = 0 ] || die "root required"
    board
    [ -x /etc/init.d/rpcd ] || die "rpcd absent"
    [ -x /usr/sbin/we5927-at ] || die "AT CLI absent"
    [ -x /usr/sbin/we5927-lte ] || die "LTE manager absent"
    [ -f "$RPC" ] && [ -f "$ACL" ] ||
        die "existing RPC/ACL missing"
    [ ! -L "$RPC" ] && [ ! -L "$ACL" ] && [ ! -L "$HELPER" ] ||
        die "target is a symlink"
    [ ! -e "$BACKUP" ] ||
        die "backup exists: use status or rollback; no overwrite"
    [ ! -e "$HELPER" ] ||
        die "helper already installed; refusing overwrite"
    for cmd in sha256sum wget flock awk jsonfilter ubus; do
        command -v "$cmd" >/dev/null 2>&1 ||
            die "required command missing: $cmd"
    done
    kb="$(df -k /overlay | awk 'NR==2 {print $4}')"
    case "$kb" in ''|*[!0-9]*) die "overlay capacity unknown";; esac
    [ "$kb" -ge 160 ] || die "overlay free space below 160 KiB"
}
apply() {
    preflight
    work="$(mktemp -d /tmp/veci-cap-hotfix.XXXXXX)" ||
        die "cannot create tmpfs staging"
    changed=0
    success=0
    cleanup() {
        code=$?
        trap - EXIT
        if [ "$changed" = 1 ] && [ "$success" != 1 ]; then
            echo "HOTFIX_FAILURE: RESTORING BACKUP" >&2
            recover_files || :
            /etc/init.d/rpcd restart || :
        fi
        rm -rf "$work"
        exit "$code"
    }
    trap cleanup EXIT

    fetch scripts/veci-live-minimal/veci.cellular "$work/rpc"
    fetch source/veci-cellular-we5927/files/usr/libexec/veci-modem-capabilities "$work/helper"
    fetch scripts/veci-live-minimal/veci-cellular-we5927.json "$work/acl"
    check_sha "$work/rpc" "$RPC_SHA" || die "RPC SHA256 mismatch"
    check_sha "$work/helper" "$HELPER_SHA" || die "helper SHA256 mismatch"
    check_sha "$work/acl" "$ACL_SHA" || die "ACL SHA256 mismatch"
    sh -n "$work/rpc" && sh -n "$work/helper" ||
        die "shell syntax invalid"
    for method in status reconnect switchSim messagingCapabilities; do
        grep -q "\"$method\":" "$work/rpc" ||
            die "RPC method missing: $method"
    done
    grep -Fq '"sim": "String"' "$work/rpc" ||
        die "legacy SIM method schema changed"
    if grep -q '"identityLive":' "$work/rpc" ||
       grep -q '"identity":' "$work/rpc"; then
        die "minimal hotfix unexpectedly exposes IMEI methods"
    fi
    if grep -q '"identityLive"' "$work/acl" ||
       grep -q '"identity"' "$work/acl"; then
        die "minimal hotfix ACL unexpectedly exposes IMEI methods"
    fi
    grep -Fq 'AT+CMGF=?' "$work/helper" ||
        die "capability-only AT command allowlist missing"
    grep -Fq 'AT+CUSD=?' "$work/helper" ||
        die "capability-only AT command allowlist missing"

    # Persistent rollback: never replace these backups on repeat invocation.
    mkdir "$BACKUP" || die "could not reserve backup"
    cp -p "$RPC" "$BACKUP/old-rpc" ||
        die "old RPC backup failed"
    cp -p "$ACL" "$BACKUP/old-acl" ||
        die "old ACL backup failed"
    if [ -e "$HELPER" ]; then
        touch "$BACKUP/had-helper"
        cp -p "$HELPER" "$BACKUP/old-helper" ||
            die "old helper backup failed"
    fi
    echo "$SOURCE_SHA" > "$BACKUP/source-commit"
    changed=1
    put "$work/helper" "$HELPER" 755 || die "helper install failed"
    put "$work/acl" "$ACL" 644 || die "ACL install failed"
    put "$work/rpc" "$RPC" 755 || die "RPC install failed"
    check_sha "$RPC" "$RPC_SHA" &&
    check_sha "$HELPER" "$HELPER_SHA" &&
    check_sha "$ACL" "$ACL_SHA" ||
        die "installed files did not match SHA256"
    /etc/init.d/rpcd restart ||
        die "RPCD restart failed"
    n=0
    while [ "$n" -lt 10 ]; do
        if ubus -v list veci.cellular 2>/dev/null |
            grep -q '"messagingCapabilities":'; then
            break
        fi
        n=$((n + 1))
        sleep 1
    done
    methods="$(ubus -v list veci.cellular)" ||
        die "RPCD failed to register"
    for method in status reconnect switchSim messagingCapabilities; do
        printf '%s\n' "$methods" | grep -q "\"$method\":" ||
            die "registered RPC missing: $method"
    done
    success=1
    echo "LIVE_RPC_REGISTRATION_PASS"
    echo "NO_AT_COMMAND_SENT_BY_INSTALLER"
    echo "BACKUP=$BACKUP"
    status
}
[ "$#" -eq 1 ] || {
    echo "usage: sh veci-live-capability-hotfix.sh status|apply|rollback" >&2
    exit 2
}
case "$1" in
    status) status ;;
    apply) apply ;;
    rollback) rollback ;;
    *) echo "unsupported operation" >&2; exit 2 ;;
esac
