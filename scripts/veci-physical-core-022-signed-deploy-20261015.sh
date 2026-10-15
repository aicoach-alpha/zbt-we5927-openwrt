#!/bin/sh
# VeCI-only, exact-snapshot core 0.2.0 -> 0.2.2 signed upgrade.
# OFFICE LAPTOP -> WE5927 only. NO LuCI, SMS/USSD, modem, SIM, APN, firmware flash.
# Existing active native quota UI and complete SMS Center code are preserved.
set -eu
umask 077
LC_ALL=C
PATH=/usr/sbin:/usr/bin:/sbin:/bin
export LC_ALL PATH

TAG=veci-physical-core-022-c76cb7f13f06
BASE="https://github.com/aicoach-alpha/zbt-we5927-openwrt/releases/download/$TAG"
NEW=veci-0.2.2-r1.apk
OLD=veci-0.2.0-r1.apk
KEY=veci-physical-022.pem
NEW_SHA=e06ad0b5f57f29630f20ff4bdaa06665261c09cbaef21a17a5a5504c092ff168
OLD_SHA=2b18a8c1e230314837068649023c097e1c354b9b8bdd77a4a148692fb7f3fd9a
KEY_SHA=c9915940535bdc8f9f388af8a924f329e77cc20217cb3b3d8fbc495f80628fcc
CELL_SHA=b075a4852d3eeb5f717e4db568a0929fc732b225f025a154beb24961a3f85379
MODULE_SHA=5c1f66b5a5aa292be202897ef538f67ed7933e857ff3e11bcaabb075b75c692d
RPCD_SHA=d08edadd38f0d9b992fc54d879eabf9f797bf54df83fa8c8cf7b59e55b9e99ce
ACL_SHA=d655406fd94214c22cf047bf5fc49e66876365634958be9d25171e6100e6a171
CSS_SHA=fd3b3540109d815d9b3cb5151298af04ef865e55557d8a8a91d9c30f1548fdb2
CONFIG_SHA=95927da8bad40be6ac0eb14d8c92d13fa82ffc1594a8f608d59a06680275caae
PAGE=/www/veci/js/pages/cellular.js
MODULE=/www/veci/js/lib/native-quota.js
RPCD=/usr/libexec/rpcd/veci
ACL=/usr/share/rpcd/acl.d/veci.json
CSS=/www/veci/sms-center.css
CONF=/etc/config/veci
BACKUP=/root/veci-core-022-live-backup
LOCK=/tmp/veci-core-022-deploy.lock
WORK=
APPLIED=0
FINISHED=0
KEEP_WORK=0

fail() {
    printf 'VECI_022_DEPLOY=blocked\nVECI_022_REASON=%s\n' "$1"
    exit 1
}
sha() { sha256sum "$1" | awk '{print $1}'; }
check() { [ -f "$1" ] && [ ! -L "$1" ] && [ "$(sha "$1")" = "$2" ]; }
installed() { apk list -I 2>/dev/null | grep -q "^veci-$1-r1"; }
health() {
    ubus -S call veci.quota status >/dev/null 2>&1 &&
    ubus -S call veci.cellular status >/dev/null 2>&1
}
live_checks() {
    check "$PAGE" "$CELL_SHA" || fail live_cellular_source_drift
    check "$MODULE" "$MODULE_SHA" || fail live_quota_module_drift
    check "$RPCD" "$RPCD_SHA" || fail live_core_rpcd_drift
    check "$ACL" "$ACL_SHA" || fail live_core_acl_drift
    check "$CSS" "$CSS_SHA" || fail live_sms_css_drift
    check "$CONF" "$CONFIG_SHA" || fail live_uci_config_drift
    health || fail existing_backend_unavailable
}
board_gate() {
    [ "$(id -u)" = 0 ] || fail root_required
    [ "$(cat /tmp/sysinfo/board_name 2>/dev/null || :)" = zbtlink,zbt-we5927 ] || fail wrong_device
    grep -q "^DISTRIB_RELEASE='25.12.5'$" /etc/openwrt_release || fail openwrt_mismatch
    for c in apk wget sha256sum awk grep df wc mktemp mkdir cp cmp sort tar id chmod mv rm rmdir ubus sleep; do
        command -v "$c" >/dev/null 2>&1 || fail missing_system_tool
    done
}
verify_assets() {
    mkdir "$WORK/keys" || fail temp_key_dir_failed
    for file in "$NEW" "$OLD" "$KEY"; do
        wget -qO "$WORK/$file" "$BASE/$file" || fail release_asset_download_failed
    done
    check "$WORK/$NEW" "$NEW_SHA" || fail signed_target_integrity_failed
    check "$WORK/$OLD" "$OLD_SHA" || fail signed_rollback_integrity_failed
    check "$WORK/$KEY" "$KEY_SHA" || fail release_public_key_integrity_failed
    [ "$(wc -c < "$WORK/$NEW" | tr -d '[:space:]')" = 55594 ] || fail target_size_failed
    [ "$(wc -c < "$WORK/$OLD" | tr -d '[:space:]')" = 55595 ] || fail rollback_size_failed
    for keyfile in /etc/apk/keys/*; do
        [ -f "$keyfile" ] && [ ! -L "$keyfile" ] || continue
        cp "$keyfile" "$WORK/keys/" || fail temporary_trust_failed
    done
    cp "$WORK/$KEY" "$WORK/keys/$KEY"
    for file in "$NEW" "$OLD"; do
        apk --keys-dir "$WORK/keys" verify "$WORK/$file" > "$WORK/verify-$file.log" 2>&1 ||
            fail apk_signature_rejected
    done
    echo VECI_022_PAIRED_SIGNATURES=pass
}
simulate() {
    candidate="$1"
    apk --no-network --keys-dir "$WORK/keys" --simulate add "$WORK/$candidate" > "$WORK/plan.log" 2>&1 ||
        fail transaction_simulation_failed
    # Reject unintended package changes. Rollback is a separate signed APK.
    if grep -Eiq '(^|[[:space:]])(Installing|Removing|Purging|Upgrading|Downgrading)[[:space:]]' "$WORK/plan.log"; then
        # A dependency change is never permitted.
        if grep -Ei '(^|[[:space:]])(Installing|Removing|Purging|Upgrading|Downgrading)[[:space:]]' "$WORK/plan.log" |
           grep -Ev '(^|[[:space:]])veci([ -]|$)' > /dev/null 2>&1; then
            fail unrelated_package_transaction
        fi
    fi
    echo VECI_022_TRANSACTION_SIMULATION=pass
}
backup_ok() {
    [ -d "$BACKUP" ] && [ ! -L "$BACKUP" ] &&
    check "$BACKUP/cellular.js" "$CELL_SHA" &&
    check "$BACKUP/native-quota.js" "$MODULE_SHA" &&
    check "$BACKUP/rpcd-veci" "$RPCD_SHA" &&
    check "$BACKUP/veci-acl.json" "$ACL_SHA" &&
    check "$BACKUP/veci.config" "$CONFIG_SHA" &&
    check "$BACKUP/sms-center.css" "$CSS_SHA"
}
create_backup() {
    if [ -e "$BACKUP" ] || [ -L "$BACKUP" ]; then
        backup_ok || fail existing_rollback_backup_drift
        return
    fi
    mkdir "$BACKUP" || fail rollback_directory_failed
    chmod 700 "$BACKUP" || fail rollback_permissions_failed
    cp "$PAGE" "$BACKUP/cellular.js" || fail backup_failed
    cp "$MODULE" "$BACKUP/native-quota.js" || fail backup_failed
    cp "$RPCD" "$BACKUP/rpcd-veci" || fail backup_failed
    cp "$ACL" "$BACKUP/veci-acl.json" || fail backup_failed
    cp "$CONF" "$BACKUP/veci.config" || fail backup_failed
    cp "$CSS" "$BACKUP/sms-center.css" || fail backup_failed
    chmod 600 "$BACKUP/"* || fail rollback_permissions_failed
    backup_ok || fail rollback_backup_integrity_failed
    echo VECI_022_PERSISTENT_BACKUP=pass
}
restore_files() {
    backup_ok || return 1
    cp "$BACKUP/veci.config" "$CONF" || return 1
    chmod 600 "$CONF" || return 1
    cp "$BACKUP/cellular.js" "$PAGE" || return 1
    cp "$BACKUP/native-quota.js" "$MODULE" || return 1
    cp "$BACKUP/rpcd-veci" "$RPCD" || return 1
    cp "$BACKUP/veci-acl.json" "$ACL" || return 1
    cp "$BACKUP/sms-center.css" "$CSS" || return 1
    # Backups are root-only 0600, but restored RPCD must remain executable.
    chmod 755 "$RPCD" || return 1
    chmod 644 "$PAGE" "$MODULE" "$ACL" "$CSS" || return 1
    check "$CONF" "$CONFIG_SHA" &&
    check "$PAGE" "$CELL_SHA" &&
    check "$MODULE" "$MODULE_SHA" &&
    check "$RPCD" "$RPCD_SHA" &&
    check "$ACL" "$ACL_SHA" &&
    check "$CSS" "$CSS_SHA"
}
rollback_to_live() {
    backup_ok || { echo VECI_022_ROLLBACK=needs_attention; return 1; }
    if ! apk --no-network --keys-dir "$WORK/keys" add "$WORK/$OLD" > "$WORK/rollback.log" 2>&1; then
        restore_files || :
        echo VECI_022_ROLLBACK=needs_attention
        return 1
    fi
    if ! restore_files || ! installed 0.2.0 || ! health; then
        echo VECI_022_ROLLBACK=needs_attention
        return 1
    fi
    echo VECI_022_ROLLBACK=pass
}
finish() {
    rc="$1"
    trap - EXIT INT TERM
    if [ "$APPLIED" = 1 ] && [ "$FINISHED" = 0 ]; then
        rollback_to_live || KEEP_WORK=1
    fi
    if [ "$KEEP_WORK" = 0 ] && [ -n "$WORK" ] && [ -d "$WORK" ]; then
        rm -rf "$WORK"
    fi
    rmdir "$LOCK" 2>/dev/null || :
    exit "$rc"
}
[ "$#" = 1 ] || fail usage
case "$1" in --status|--verify|--install|--rollback) MODE="$1" ;; *) fail unknown_mode ;; esac
board_gate

if [ "$MODE" = --status ]; then
    if installed 0.2.2; then echo VECI_022_INSTALLED_VERSION=0.2.2
    elif installed 0.2.0; then echo VECI_022_INSTALLED_VERSION=0.2.0
    else echo VECI_022_INSTALLED_VERSION=unknown; fi
    for file in "$PAGE" "$MODULE" "$RPCD" "$ACL" "$CSS" "$CONF"; do
        if [ -f "$file" ] && [ ! -L "$file" ]; then
            printf 'VECI_022_SHA256_%s=%s\n' "$(basename "$file")" "$(sha "$file")"
        else
            printf 'VECI_022_FILE_MISSING=%s\n' "$file"
        fi
    done
    if health; then echo VECI_022_BACKENDS=pass
    else echo VECI_022_BACKENDS=unavailable; fi
    if backup_ok; then echo VECI_022_LIVE_BACKUP=available
    else echo VECI_022_LIVE_BACKUP=not_created; fi
    echo VECI_022_STATUS=read_only
    exit 0
fi

mkdir "$LOCK" 2>/dev/null || fail operation_in_progress
trap 'finish $?' EXIT
trap 'exit 130' INT TERM
WORK="$(mktemp -d /tmp/veci-core022.XXXXXX)" || fail tmp_unavailable

if [ "$MODE" = --rollback ]; then
    installed 0.2.2 || fail rollback_requires_0_2_2
    live_checks
    backup_ok || fail rollback_backup_unavailable
    verify_assets
    simulate "$OLD"
    rollback_to_live || fail rollback_failed
    FINISHED=1
    echo VECI_022_EXPLICIT_ROLLBACK=pass
    exit 0
fi

if installed 0.2.2; then
    live_checks
    echo VECI_022_DEPLOY=already_installed
    exit 0
fi
installed 0.2.0 || fail existing_core_version_not_0_2_0
live_checks
free="$(df -k /overlay | awk 'NR==2 {print $4}')"
case "$free" in ''|*[!0-9]*) fail overlay_space_unreadable ;; esac
[ "$free" -ge 768 ] || fail insufficient_overlay_space
verify_assets
simulate "$NEW"
if [ "$MODE" = --verify ]; then
    echo VECI_022_PREFLIGHT=pass
    echo VECI_022_FLASH_WRITES=none
    echo VECI_022_PACKAGE_INSTALLED=false
    echo VECI_022_MODEM_SMS_UNCHANGED=true
    exit 0
fi

create_backup
apk list -I > "$WORK/packages-before.txt" || fail inventory_before_failed
grep -v '^veci-0[.]2[.]' "$WORK/packages-before.txt" | sort > "$WORK/unrelated-before.txt"
APPLIED=1
apk --no-network --keys-dir "$WORK/keys" add "$WORK/$NEW" > "$WORK/upgrade.log" 2>&1 ||
    fail signed_core_install_failed
installed 0.2.2 || fail target_version_not_registered
live_checks
apk list -I > "$WORK/packages-after.txt" || fail inventory_after_failed
grep -v '^veci-0[.]2[.]' "$WORK/packages-after.txt" | sort > "$WORK/unrelated-after.txt"
cmp -s "$WORK/unrelated-before.txt" "$WORK/unrelated-after.txt" ||
    fail unrelated_packages_modified
FINISHED=1
echo VECI_022_DEPLOY=pass
echo VECI_022_INSTALLED_VERSION=0.2.2
echo VECI_022_SMS_USSD_SOURCE_PRESERVED=pass
echo VECI_022_LIVE_CORE_RPCD_ACL_PRESERVED=pass
echo VECI_022_CONFIG_PRESERVED=pass
echo VECI_022_BACKENDS=pass
echo VECI_022_ROLLBACK_AVAILABLE=true
echo VECI_022_BROWSER_UAT=pending
echo VECI_CARRIER_QUOTA=not_verified
echo VECI_LUCI_UI_MODIFIED=false
echo VECI_MODEM_SMS_UNCHANGED=true
