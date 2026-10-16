#!/bin/sh
# WE5927 SMS storage-count-only v2 hotfix; operator-run ONLY.
# Does not flash firmware, change LTE/SIM/network, read SMS/OTP or run AT.
# A separately authorized ubus method may later call read-only AT+CPMS?.
set -eu
umask 077
LC_ALL=C
export LC_ALL
SOURCE_SHA=a880417be79c5a1e156c6c39023e6a905216f5fd
SOURCE=https://raw.githubusercontent.com/aicoach-alpha/zbt-we5927-openwrt
PAYLOAD=scripts/veci-live-storage-v2
RPC=/usr/libexec/rpcd/veci.cellular
HELPER=/usr/libexec/veci-modem-capabilities
ACL=/usr/share/rpcd/acl.d/veci-cellular-we5927.json
BACKUP=/root/veci-storage-hotfix-rollback
RPC_OLD=2fde4bb0200f1319a2d63688e5be1422b68b5c3efa7f2dca117cf7f8c0eafada
ACL_OLD=b39a09cd65e264e46373f3e4fd674021a9a6a04622f1c5b6108b981ca3d382c1
HELPER_OLD=d0191d99ccfdab5554baf3f2084ce81e1735550e51e64a219ffeb4e3abbdb85c
RPC_NEW=6751641e8342a2974362b5876c5e0a84275e89774b8d98b40b2b5f1fd0191fcc
ACL_NEW=9a6aa475093427b6618ffedaaa31c62d87decf2c684286fd577be62e7c8b1289
HELPER_NEW=f90e6ad98774b47293d43ec682cf253eafd5ab21cce7b27ced051fa072afe053

die() { echo "V2_ERROR: $*" >&2; exit 1; }
sha_ok() {
    [ -s "$1" ] || return 1
    got="$(sha256sum "$1" 2>/dev/null | awk '{print $1}')" || return 1
    [ "$got" = "$2" ]
}
board() {
    [ "$(cat /tmp/sysinfo/board_name 2>/dev/null)" = "zbtlink,zbt-we5927" ] ||
        die "incorrect board; refusing installation"
}
methods_ok() {
    methods="$(ubus -v list veci.cellular 2>/dev/null)" || return 1
    for method in status reconnect switchSim messagingCapabilities; do
        printf '%s\n' "$methods" | grep -q "\"$method\":" || return 1
    done
    printf '%s\n' "$methods" | grep -Fq '"switchSim":{"sim":"String"}' || return 1
}
status_ok() {
    current="$(ubus call veci.cellular status 2>/dev/null)" || return 1
    printf '%s\n' "$current" | grep -q '"enabled"' || return 1
}
download() {
    wget -q -O "$2" "$SOURCE/$SOURCE_SHA/$PAYLOAD/$1" ||
        die "download failed: $1"
}
install_one() {
    temporary="$2.v2-tmp-$$"
    cp "$1" "$temporary" || return 1
    chmod "$3" "$temporary" || return 1
    mv -f "$temporary" "$2"
}
backup_valid() {
    sha_ok "$BACKUP/rpc" "$RPC_OLD" &&
    sha_ok "$BACKUP/acl" "$ACL_OLD" &&
    sha_ok "$BACKUP/helper" "$HELPER_OLD"
}
recover() {
    backup_valid || return 1
    install_one "$BACKUP/helper" "$HELPER" 755 || return 1
    install_one "$BACKUP/acl" "$ACL" 644 || return 1
    install_one "$BACKUP/rpc" "$RPC" 755 || return 1
    sha_ok "$RPC" "$RPC_OLD" && sha_ok "$ACL" "$ACL_OLD" &&
        sha_ok "$HELPER" "$HELPER_OLD"
}
show() {
    board
    ubus -v list veci.cellular || :
    df -h /overlay || :
    [ ! -d "$BACKUP" ] || echo "V2_BACKUP=$BACKUP"
}
rollback() {
    [ "$(id -u)" = 0 ] || die "requires root"
    board
    backup_valid || die "v1 backup absent/corrupt, refusing rollback"
    recover || die "file rollback failed: inspect $BACKUP"
    /etc/init.d/rpcd restart || die "RPCD restart failed during rollback"
    methods_ok || die "v1 RPC methods did not recover"
    status_ok || die "v1 LTE status did not recover"
    echo "V2_ROLLBACK_PASS: restored previous LIVE/PASS capability RPC"
    show
}
preflight() {
    [ "$(id -u)" = 0 ] || die "requires root"
    board
    [ -x /etc/init.d/rpcd ] && [ -x /usr/sbin/we5927-at ] ||
        die "missing rpcd/AT transport"
    [ -x /usr/sbin/we5927-lte ] || die "missing LTE manager"
    [ ! -e "$BACKUP" ] || die "v2 backup already exists, refusing overwrite"
    [ -s /root/veci-capability-hotfix-rollback/old-rpc ] ||
        die "v1 rollback backup not found; refusing to touch current LIVE deployment"
    for name in sha256sum wget flock awk jsonfilter ubus; do
        command -v "$name" >/dev/null 2>&1 ||
            die "missing command: $name"
    done
    for target in "$RPC" "$ACL" "$HELPER"; do
        [ -f "$target" ] && [ ! -L "$target" ] ||
            die "missing or symlinked target: $target"
    done
    sha_ok "$RPC" "$RPC_OLD" && sha_ok "$ACL" "$ACL_OLD" &&
        sha_ok "$HELPER" "$HELPER_OLD" ||
        die "unexpected installed version; fail closed without modification"
    methods_ok || die "baseline methods not registered"
    status_ok || die "baseline LTE status not healthy"
    capacity="$(df -k /overlay | awk 'NR==2 {print $4}')"
    case "$capacity" in ''|*[!0-9]*) die "overlay capacity unreadable";; esac
    [ "$capacity" -ge 160 ] || die "insufficient overlay free space"
}
apply() {
    preflight
    work="$(mktemp -d /tmp/veci-storage-v2.XXXXXX)" ||
        die "tmpfs staging failed"
    changed=0
    success=0
    finish() {
        result=$?
        trap - EXIT
        if [ "$changed" = 1 ] && [ "$success" != 1 ]; then
            echo "V2_INSTALL_FAILED: restoring previous working v1" >&2
            recover || echo "V2_RECOVERY_ERROR: check backup and invoke rollback" >&2
            /etc/init.d/rpcd restart || :
        fi
        rm -rf "$work"
        exit "$result"
    }
    trap finish EXIT
    trap 'exit 130' INT TERM
    download veci.cellular "$work/rpc"
    download veci-cellular-we5927.json "$work/acl"
    download veci-modem-capabilities "$work/helper"
    sha_ok "$work/rpc" "$RPC_NEW" || die "RPC payload SHA256 mismatch"
    sha_ok "$work/acl" "$ACL_NEW" || die "ACL payload SHA256 mismatch"
    sha_ok "$work/helper" "$HELPER_NEW" ||
        die "helper payload SHA256 mismatch"
    sh -n "$work/rpc" && sh -n "$work/helper" ||
        die "downloaded shell syntax invalid"
    grep -Fq '"messagingStorage": {}' "$work/rpc" ||
        die "RPC missing new method"
    grep -Fq 'AT+CPMS?' "$work/helper" ||
        die "helper missing read-only counter query"
    grep -Fq '"messagingStorage"' "$work/acl" ||
        die "ACL missing read-only storage permission"
    # A persistent *new* backup preserves already-live v1, separate from
    # the original capability hotfix rollback. Never overwrite either.
    mkdir "$BACKUP" || die "cannot create storage backup"
    cp -p "$RPC" "$BACKUP/rpc" || die "backup RPC failed"
    cp -p "$ACL" "$BACKUP/acl" || die "backup ACL failed"
    cp -p "$HELPER" "$BACKUP/helper" || die "backup helper failed"
    backup_valid || die "backed-up source fails SHA256 check"
    echo "$SOURCE_SHA" > "$BACKUP/payload-source-sha"
    changed=1
    install_one "$work/helper" "$HELPER" 755 || die "helper install failed"
    install_one "$work/acl" "$ACL" 644 || die "ACL install failed"
    install_one "$work/rpc" "$RPC" 755 || die "RPC install failed"
    sha_ok "$RPC" "$RPC_NEW" && sha_ok "$ACL" "$ACL_NEW" &&
        sha_ok "$HELPER" "$HELPER_NEW" || die "installed hash mismatch"
    /etc/init.d/rpcd restart || die "rpcd restart failed"
    attempt=0
    while [ "$attempt" -lt 10 ]; do
        if ubus -v list veci.cellular 2>/dev/null |
            grep -q '"messagingStorage":'; then break; fi
        sleep 1
        attempt=$((attempt+1))
    done
    methods_ok || die "legacy RPC method registration regressed"
    methods="$(ubus -v list veci.cellular 2>/dev/null)" ||
        die "ubus methods missing"
    printf '%s\n' "$methods" | grep -q '"messagingStorage":' ||
        die "new RPC method missing"
    status_ok || die "LTE status regressed after RPC restart"
    success=1
    echo "V2_LIVE_RPC_PASS: messagingStorage registered"
    echo "V2_STATUS_PASS: LTE status healthy"
    echo "NO_AT_COMMAND_SENT_BY_INSTALLER"
    echo "V2_ROLLBACK_BACKUP=$BACKUP"
    show
}
[ "$#" -eq 1 ] ||
    die "usage: sh veci-live-storage-hotfix-v2.sh status|apply|rollback"
case "$1" in
    status) show ;;
    apply) apply ;;
    rollback) rollback ;;
    *) die "unsupported operation";;
esac
