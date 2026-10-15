#!/bin/sh
# One-purpose VeCI-only native quota overlay for the ACTUAL 2026-10-15 WE5927 snapshot.
# Does NOT upgrade the 0.2.0 package or replace the existing 58KB SMS/USSD page.
# Source/payload pinned by SHA256; preserves persistent rollback copy before mutation.
# No LuCI, modem, SMS, USSD, APN, package DB, service restart or firmware changes.
set -eu
umask 077
LC_ALL=C
PATH=/usr/sbin:/usr/bin:/sbin:/bin
export LC_ALL PATH

PAGE=/www/veci/js/pages/cellular.js
LIB=/www/veci/js/lib/native-quota.js
BACKUP=/root/veci-native-quota-rollback-20261015
ORIGINAL_SHA=8f9219c21ca49b44ea5d5a2705fccdde77315249c53c21715974df384d4adef6
PATCHED_SHA=eef7b3453ebb2ba876b35e34f61fdf36ba1301aeb993d109a24af4cbf005caab
MODULE_SHA=5c1f66b5a5aa292be202897ef538f67ed7933e857ff3e11bcaabb075b75c692d
MODULE_URL=https://raw.githubusercontent.com/aicoach-alpha/zbt-we5927-openwrt/e2f8bc86ef6c214d813a1b3fc021acb8955577bc/scripts/veci-native-quota-overlay/native-quota.js
LOCK=/tmp/veci-native-quota-overlay.lock
WORK=
APPLIED=0
DONE=0

fail() { printf 'VECI_QUOTA_OVERLAY=blocked\nVECI_QUOTA_REASON=%s\n' "$1"; exit 1; }
sha() { sha256sum "$1" | awk '{print $1}'; }
check() { [ -f "$1" ] && [ ! -L "$1" ] && [ "$(sha "$1")" = "$2" ]; }
board_gate() {
    [ "$(id -u)" = 0 ] || fail root_required
    [ "$(cat /tmp/sysinfo/board_name 2>/dev/null || :)" = zbtlink,zbt-we5927 ] || fail wrong_router
    grep -q "^DISTRIB_RELEASE='25.12.5'$" /etc/openwrt_release || fail unsupported_openwrt
    for bin in awk apk cat chmod cp df grep id mkdir mktemp mv rmdir rm sha256sum ubus wget; do
        command -v "$bin" >/dev/null 2>&1 || fail system_tool_missing
    done
}
backup_ok() { [ -d "$BACKUP" ] && [ ! -L "$BACKUP" ] && check "$BACKUP/cellular.js" "$ORIGINAL_SHA"; }
restore() {
    backup_ok || return 1
    cp "$BACKUP/cellular.js" "$PAGE.rollback.$$" || return 1
    chmod 644 "$PAGE.rollback.$$" || return 1
    mv -f "$PAGE.rollback.$$" "$PAGE" || return 1
    check "$PAGE" "$ORIGINAL_SHA" || return 1
    if [ -e "$LIB" ] || [ -L "$LIB" ]; then
        check "$LIB" "$MODULE_SHA" || return 1
        rm -f "$LIB" || return 1
    fi
    [ ! -e "$LIB" ] && [ ! -L "$LIB" ]
}
finish() {
    rc="$1"
    trap - EXIT INT TERM
    if [ "$APPLIED" = 1 ] && [ "$DONE" = 0 ]; then
        if restore; then echo VECI_QUOTA_AUTOROLLBACK=pass
        else echo VECI_QUOTA_AUTOROLLBACK=needs_attention; fi
    fi
    [ -z "$WORK" ] || rm -rf "$WORK"
    rm -f "$PAGE.staging.$$" "$PAGE.rollback.$$" "$LIB.staging.$$"
    rmdir "$LOCK" 2>/dev/null || :
    exit "$rc"
}

[ "$#" = 1 ] || fail usage
case "$1" in --status|--install|--rollback) MODE="$1" ;; *) fail unknown_mode ;; esac
board_gate

if [ "$MODE" = --status ]; then
    if check "$PAGE" "$PATCHED_SHA" && check "$LIB" "$MODULE_SHA"; then
        echo VECI_QUOTA_OVERLAY=installed
    elif check "$PAGE" "$ORIGINAL_SHA" && [ ! -e "$LIB" ] && [ ! -L "$LIB" ]; then
        echo VECI_QUOTA_OVERLAY=original
    else
        echo VECI_QUOTA_OVERLAY=unknown
    fi
    printf 'VECI_QUOTA_CELLULAR_SHA256='
    if [ -f "$PAGE" ] && [ ! -L "$PAGE" ]; then sha "$PAGE"; else echo missing_or_symlink; fi
    if backup_ok; then echo VECI_QUOTA_ROLLBACK=available
    else echo VECI_QUOTA_ROLLBACK=not_verified; fi
    if ubus -S call veci.quota status >/dev/null 2>&1; then echo VECI_QUOTA_BACKEND=pass
    else echo VECI_QUOTA_BACKEND=unavailable; fi
    echo VECI_QUOTA_MODE=read_only
    exit 0
fi

mkdir "$LOCK" 2>/dev/null || fail another_operation_in_progress
trap 'finish $?' EXIT
trap 'exit 130' INT TERM
WORK="$(mktemp -d /tmp/veci-native-quota.XXXXXX)" || fail temp_storage_unavailable

if [ "$MODE" = --rollback ]; then
    check "$PAGE" "$PATCHED_SHA" || fail patched_page_changed
    check "$LIB" "$MODULE_SHA" || fail quota_module_changed
    restore || fail rollback_failed
    DONE=1
    echo VECI_QUOTA_ROLLBACK=pass
    echo VECI_SMS_LTE_MODIFIED=false
    exit 0
fi

# Validate precise owner-provided router snapshot. DO NOT disable these gates.
if check "$PAGE" "$PATCHED_SHA" && check "$LIB" "$MODULE_SHA"; then
    echo VECI_QUOTA_OVERLAY=already_installed
    exit 0
fi
check "$PAGE" "$ORIGINAL_SHA" || fail existing_core_source_drift
[ ! -e "$LIB" ] && [ ! -L "$LIB" ] || fail target_module_exists
apk list -I 2>/dev/null | grep -q '^veci-0[.]2[.]0-r1' || fail existing_core_version_not_0_2_0
ubus -S call veci.quota status > "$WORK/backend.json" 2>/dev/null || fail quota_backend_unavailable
free="$(df -k /overlay | awk 'NR==2 {print $4}')"
case "$free" in ''|*[!0-9]*) fail overlay_space_unreadable ;; esac
[ "$free" -ge 512 ] || fail insufficient_overlay_space

wget -qO "$WORK/native-quota.js" "$MODULE_URL" || fail module_download_failed
check "$WORK/native-quota.js" "$MODULE_SHA" || fail module_integrity_failed

# BusyBox awk patches the EXACT old source in RAM; preserves every existing
# SMS Inbox / Sent / Draft / PDU / USSD function and every existing event handler.
awk '
  /^[[:space:]]*if \(online\) \{$/ {
    print "\t\tmountOperatorQuota({ api, root });"; mounts++
  }
  { print }
  /^import \{ badge, escapeHtml, setBusy \} from / {
    print "import { mountOperatorQuota } from '\''../lib/native-quota.js?v=20261015'\'';"; imports++
  }
  END { if (imports != 1 || mounts != 1) exit 19 }
' "$PAGE" > "$WORK/cellular.js" || fail patch_anchor_mismatch
check "$WORK/cellular.js" "$PATCHED_SHA" || fail patched_source_hash_mismatch

if [ -e "$BACKUP" ] || [ -L "$BACKUP" ]; then
    backup_ok || fail existing_backup_drift
else
    mkdir "$BACKUP" || fail backup_directory_failed
    chmod 700 "$BACKUP" || fail backup_permissions_failed
    cp "$PAGE" "$BACKUP/cellular.js" || fail persistent_backup_failed
    chmod 600 "$BACKUP/cellular.js" || fail backup_permissions_failed
    backup_ok || fail backup_integrity_failed
fi

# Stage both files on target filesystem before switching import visibility.
cp "$WORK/native-quota.js" "$LIB.staging.$$" || fail module_stage_failed
cp "$WORK/cellular.js" "$PAGE.staging.$$" || fail page_stage_failed
chmod 644 "$LIB.staging.$$" "$PAGE.staging.$$" || fail staging_permissions_failed
check "$LIB.staging.$$" "$MODULE_SHA" || fail module_staging_integrity_failed
check "$PAGE.staging.$$" "$PATCHED_SHA" || fail page_staging_integrity_failed
APPLIED=1
mv -f "$LIB.staging.$$" "$LIB" || fail module_commit_failed
mv -f "$PAGE.staging.$$" "$PAGE" || fail page_commit_failed
check "$PAGE" "$PATCHED_SHA" && check "$LIB" "$MODULE_SHA" || fail postinstall_integrity_failed
ubus -S call veci.quota status >/dev/null 2>&1 || fail quota_backend_postinstall_failed
DONE=1
echo VECI_QUOTA_OVERLAY=installed
echo VECI_QUOTA_PATCHED_SOURCE=pass
echo VECI_QUOTA_READONLY_BACKEND=pass
echo VECI_QUOTA_ROLLBACK=available
echo VECI_QUOTA_BROWSER_UAT=pending
echo VECI_OPERATOR_AUTHENTICATED_QUOTA=not_verified
echo VECI_SMS_LTE_MODIFIED=false
echo VECI_LUCI_UI_MODIFIED=false
