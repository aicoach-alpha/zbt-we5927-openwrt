#!/bin/sh
# VeCI-only Cellular quota UI 0.2.0 -> 0.2.1 signed core package upgrade.
# The separate veci.quota backend MUST already be live and is NEVER replaced.
# For WE5927 OpenWrt 25.12.5 via OFFICE laptop only.
# Uses verified APKv3, temporary trust, offline package transaction, rollback.
# NO LuCI features, firmware flash, APN, SMS/USSD, SIM or modem commands.
set -eu
umask 077
LC_ALL=C
PATH=/usr/sbin:/usr/bin:/sbin:/bin
export LC_ALL PATH

TAG=veci-native-quota-core-pair-9cbf71fcb12f
BASE="https://github.com/aicoach-alpha/zbt-we5927-openwrt/releases/download/$TAG"
NEW=veci-0.2.1-r1.apk
OLD=veci-0.2.0-r1.apk
KEY=veci-core.pem
NEW_SHA=fe19f1f1c7c433512cf9c51778877b988a51bdc3b6ef7ab5eebad66eed317b19
OLD_SHA=5822cd96a04bf4a856d1d0abe3ec2065811f712808ca3eaa223ddec933effbcf
KEY_SHA=7c62736c912bed2e08dabb89dfaa05e7ed9a362672a902d119cc7ced4c1f5432
OLD_CELL=e569794565fd2d59d4badeae9bcc086ab931b1200cafec5f4b247954f29485b4
NEW_CELL=2f043f5e45c0839de3caba0f7ee832e1ba30adae7549afe17014d7e96ef9b818
HELPER_SHA=fb3e078c2e65a39c3d0e852f5364f2fd433cbfd547df21b480b1cfd514104a9d

LOCK=/tmp/veci-cellular-core-deploy.lock
WORK=
APPLIED=0
FINISHED=0
PRESERVE=0

fail() {
    printf 'VECI_CELLULAR_UI_DEPLOY=blocked\n'
    printf 'VECI_CELLULAR_UI_REASON=%s\n' "$1"
    exit 1
}
sha() { sha256sum "$1" | awk '{print $1}'; }
check() { [ "$(sha "$1")" = "$2" ]; }
installed() { apk list -I 2>/dev/null | grep -q "^veci-$1-r1"; }
board_gate() {
    [ "$(id -u)" = 0 ] || fail root_required
    [ "$(cat /tmp/sysinfo/board_name 2>/dev/null || :)" = zbtlink,zbt-we5927 ] ||
        fail wrong_device
    grep -q "^DISTRIB_RELEASE='25.12.5'$" /etc/openwrt_release ||
        fail openwrt_mismatch
    for cmd in apk wget sha256sum awk grep df wc mktemp tar cp sort cmp ubus id sleep; do
        command -v "$cmd" >/dev/null 2>&1 || fail missing_system_tool
    done
}
quota_backend_gate() {
    # VeCI package post-upgrade restarts rpcd. Give ubus object registration
    # time to complete, rather than triggering a false rollback immediately.
    attempt=0
    while [ "$attempt" -lt 12 ]; do
        if ubus -S call veci.quota status > "$WORK/quota-rpc.json" 2>/dev/null; then
            return 0
        fi
        attempt=$((attempt + 1))
        sleep 1
    done
    fail existing_quota_backend_unavailable
}
temporary_keys() {
    mkdir "$WORK/keys"
    for src in /etc/apk/keys/*; do
        [ -f "$src" ] && [ ! -L "$src" ] || continue
        cp "$src" "$WORK/keys/" || fail temp_trust_copy_failed
    done
}
download_signed_pair() {
    for name in "$NEW" "$OLD" "$KEY"; do
        wget -qO "$WORK/$name" "$BASE/$name" || fail pinned_asset_download_failed
    done
    check "$WORK/$NEW" "$NEW_SHA" || fail target_integrity_failed
    check "$WORK/$OLD" "$OLD_SHA" || fail rollback_integrity_failed
    check "$WORK/$KEY" "$KEY_SHA" || fail trust_key_integrity_failed
    [ "$(wc -c < "$WORK/$NEW" | tr -d '[:space:]')" = 52686 ] ||
        fail target_size_failed
    [ "$(wc -c < "$WORK/$OLD" | tr -d '[:space:]')" = 52098 ] ||
        fail rollback_size_failed
    cp "$WORK/$KEY" "$WORK/keys/$KEY"
    for name in "$NEW" "$OLD"; do
        apk --keys-dir "$WORK/keys" verify "$WORK/$name" > "$WORK/verify-$name.log" 2>&1 ||
            fail signed_apk_rejected
    done
    printf 'VECI_CELLULAR_UI_PAIRED_SIGNATURES=pass\n'
}
do_rollback() {
    # Exact original signed APK. No removal of VeCI, no mass package changes.
    if apk --no-network --keys-dir "$WORK/keys" add "$WORK/$OLD" > "$WORK/rollback.log" 2>&1 &&
       installed 0.2.0 &&
       check /www/veci/js/pages/cellular.js "$OLD_CELL"; then
        printf 'VECI_CELLULAR_UI_ROLLBACK=pass\n'
        return 0
    fi
    printf 'VECI_CELLULAR_UI_ROLLBACK=needs_attention\n'
    return 1
}
finish() {
    rc="$1"
    trap - EXIT INT TERM
    if [ "$APPLIED" = 1 ] && [ "$FINISHED" = 0 ]; then
        do_rollback || PRESERVE=1
    fi
    if [ "$PRESERVE" = 0 ] && [ -n "$WORK" ] && [ -d "$WORK" ]; then
        rm -rf "$WORK"
    fi
    rmdir "$LOCK" 2>/dev/null || :
    exit "$rc"
}
[ "$#" -eq 1 ] || fail usage
case "$1" in --install|--rollback|--status) MODE="$1" ;; *) fail unknown_mode ;; esac
board_gate
mkdir "$LOCK" 2>/dev/null || fail installation_already_in_progress
trap 'finish $?' EXIT
trap 'exit 130' INT TERM
WORK="$(mktemp -d /tmp/veci-cellular-core.XXXXXX)" || fail tmp_unavailable

if [ "$MODE" = --status ]; then
    if installed 0.2.1; then
        printf 'VECI_CELLULAR_UI_PACKAGE=0.2.1\n'
    elif installed 0.2.0; then
        printf 'VECI_CELLULAR_UI_PACKAGE=0.2.0\n'
    else
        printf 'VECI_CELLULAR_UI_PACKAGE=unknown\n'
    fi
    if [ -f /www/veci/js/pages/cellular.js ]; then
        printf 'VECI_CELLULAR_UI_CELLULAR_SHA256=%s\n' "$(sha /www/veci/js/pages/cellular.js)"
    else
        printf 'VECI_CELLULAR_UI_CELLULAR_SHA256=missing\n'
    fi
    quota_backend_gate
    printf 'VECI_CELLULAR_UI_BACKEND=pass\nVECI_CELLULAR_UI_STATUS=read_only\n'
    exit 0
fi

quota_backend_gate
[ -f /www/veci/js/pages/cellular.js ] && [ ! -L /www/veci/js/pages/cellular.js ] ||
    fail cellular_source_missing
[ -f /www/veci/js/lib/quota.js ] && [ ! -L /www/veci/js/lib/quota.js ] ||
    fail quota_helper_missing
check /www/veci/js/lib/quota.js "$HELPER_SHA" || fail quota_helper_mismatch

if [ "$MODE" = --install ]; then
    if installed 0.2.1 && check /www/veci/js/pages/cellular.js "$NEW_CELL"; then
        printf 'VECI_CELLULAR_UI_DEPLOY=already_installed\n'
        exit 0
    fi
    installed 0.2.0 || fail existing_core_version_not_0_2_0
    check /www/veci/js/pages/cellular.js "$OLD_CELL" || fail existing_core_source_drift
else
    installed 0.2.1 || fail rollback_only_from_version_0_2_1
    check /www/veci/js/pages/cellular.js "$NEW_CELL" || fail rollback_source_drift
fi

free="$(df -k /overlay 2>/dev/null | awk 'NR==2 {print $4}')"
case "$free" in ''|*[!0-9]*) fail overlay_space_unreadable ;; esac
[ "$free" -ge 768 ] || fail insufficient_overlay_for_core_upgrade

temporary_keys
download_signed_pair
# APKv3 transaction planner must not change dependencies unrelated to VeCI.
if [ "$MODE" = --install ]; then
    apk --no-network --keys-dir "$WORK/keys" --simulate add "$WORK/$NEW" > "$WORK/plan.log" 2>&1 ||
        fail install_dependency_plan_failed
else
    apk --no-network --keys-dir "$WORK/keys" --simulate add "$WORK/$OLD" > "$WORK/plan.log" 2>&1 ||
        fail rollback_dependency_plan_failed
fi
if grep -Eiq '(^|[[:space:]])(Installing|Removing|Purging)[[:space:]]' "$WORK/plan.log"; then
    fail transaction_changes_other_packages
fi
apk list -I > "$WORK/packages-before.txt" || fail inventory_failed
grep -v '^veci-0[.]2[.]' "$WORK/packages-before.txt" | sort > "$WORK/non-veci-before.txt"
tar -cf "$WORK/config-and-ui-before.tar" -C / \
    etc/config/veci www/veci/js/pages/cellular.js www/veci/js/lib/quota.js \
    >/dev/null 2>&1 || fail volatile_backup_failed
printf 'VECI_CELLULAR_UI_PREINSTALL_GATES=pass\n'
APPLIED=1
if [ "$MODE" = --install ]; then
    apk --no-network --keys-dir "$WORK/keys" add "$WORK/$NEW" > "$WORK/upgrade.log" 2>&1 ||
        fail core_upgrade_failed
    installed 0.2.1 || fail updated_core_not_registered
    check /www/veci/js/pages/cellular.js "$NEW_CELL" ||
        fail updated_cellular_source_mismatch
else
    do_rollback || fail explicit_rollback_failed
fi
check /www/veci/js/lib/quota.js "$HELPER_SHA" || fail quota_helper_modified
quota_backend_gate
apk list -I > "$WORK/packages-after.txt" || fail inventory_after_failed
grep -v '^veci-0[.]2[.]' "$WORK/packages-after.txt" | sort > "$WORK/non-veci-after.txt"
cmp -s "$WORK/non-veci-before.txt" "$WORK/non-veci-after.txt" ||
    fail unrelated_packages_modified
FINISHED=1
if [ "$MODE" = --install ]; then
    printf 'VECI_CELLULAR_UI_CORE_APK_INSTALL=pass\n'
    printf 'VECI_CELLULAR_UI_NATIVE_QUOTA_SOURCE=pass\n'
    printf 'VECI_CELLULAR_UI_BACKEND=pass\n'
    printf 'VECI_CELLULAR_UI_ROLLBACK_AVAILABLE=true\n'
    printf 'VECI_CELLULAR_UI_BROWSER_UAT=pending\n'
    printf 'VECI_CARRIER_QUOTA=not_verified\n'
else
    printf 'VECI_CELLULAR_UI_EXPLICIT_ROLLBACK=pass\n'
fi
printf 'VECI_LUCI_UI_MODIFIED=false\n'
printf 'VECI_MODEM_SMS_UNCHANGED=true\n'
