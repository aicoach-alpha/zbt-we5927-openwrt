#!/bin/sh
# VeCI XL release module rollup. Reconciles UI and helpers already integrated in RPC.
# Only this compact release set; no OTP, operator network I/O, or service restart.
set -eu
umask 077
UI=/www/veci/js/lib/veci-xl-connection-status.js
GATE=/usr/libexec/veci-xl-quota-session-gate
IMPORT=/usr/libexec/veci-xl-authorized-config-import
RPC_XL=/usr/libexec/rpcd/veci.xl
RPC_Q=/usr/libexec/rpcd/veci.quota
CLEAR=/usr/libexec/veci-xl-session-clear
BACKUP=/tmp/veci-xl-release-before-20261020
URL_BASE=https://raw.githubusercontent.com/aicoach-alpha/zbt-we5927-openwrt
fail(){ echo "XL_RELEASE=$1"; exit 1; }
[ "$(id -u)" = 0 ] || fail root_required
for f in "$UI" "$GATE" "$IMPORT" "$RPC_XL" "$RPC_Q" "$CLEAR"; do
 [ -f "$f" ] && [ ! -L "$f" ] || fail prerequisite_missing
done
grep -Fq '/usr/libexec/veci-xl-quota-session-gate --status' "$RPC_Q" || fail quota_rpc_incompatible
grep -Fq 'logout) logout_local ;;' "$RPC_XL" || fail xl_rpc_incompatible
grep -Fq 'export async function mountXlConnection' "$UI" || fail ui_incompatible
[ ! -L "$BACKUP" ] || fail backup_symlink
[ ! -e "$BACKUP" ] || fail backup_already_exists
WORK="$(mktemp -d /tmp/veci-xl-release.XXXXXX)" || fail staging_failed
trap 'rm -rf "$WORK"' EXIT
chmod 700 "$WORK" || fail staging_permission_failed
wget -qO "$WORK/ui" "$URL_BASE/1e836e7ba124b03318819776808b9b0d2af7bbc6/web/veci-xl-auth-panel-release-20261020.js" || fail ui_download_failed
wget -qO "$WORK/gate" "$URL_BASE/addaa6f3d53ace2812fe6528c4aa8bd9a19b6d9e/scripts/veci-xl-quota-session-gate-v8-20261019.sh" || fail gate_download_failed
wget -qO "$WORK/import" "$URL_BASE/9ad1a5224c2c7c322054f37b7fb00ca2a20b4936/scripts/veci-xl-authorized-config-import-v10-20261020.sh" || fail import_download_failed
sh -n "$WORK/gate" && sh -n "$WORK/import" || fail helper_syntax_failed
grep -Fq "official.href = 'https://www.xl.co.id/id/myxl'" "$WORK/ui" || fail official_link_missing
grep -Fq "void action('submitOtp', { otp })" "$WORK/ui" || fail otp_flow_missing
grep -Fq "q.source !== 'operator'" "$WORK/ui" || fail origin_guard_missing
grep -Fq '[ "$modified" -ge "$epoch" ] || unavailable stale' "$WORK/gate" || fail cache_order_guard_missing
grep -Fq 'installed_operator_auth_not_verified' "$WORK/import" || fail unverified_config_guard_missing
# Idempotent: do not touch installed files if byte-for-byte identical.
if cmp -s "$WORK/ui" "$UI" && cmp -s "$WORK/gate" "$GATE" &&
   cmp -s "$WORK/import" "$IMPORT"; then
 echo XL_RELEASE=already_current
 echo XL_RELEASE_INTEGRITY=pass
 exit 0
fi
mkdir -m 700 "$BACKUP" || fail backup_create_failed
if ! cp -p "$UI" "$BACKUP/ui" ||
   ! cp -p "$GATE" "$BACKUP/gate" ||
   ! cp -p "$IMPORT" "$BACKUP/import"; then
 rm -rf "$BACKUP"
 fail backup_failed
fi
restore(){
 cp -p "$BACKUP/ui" "$UI" || :
 cp -p "$BACKUP/gate" "$GATE" || :
 cp -p "$BACKUP/import" "$IMPORT" || :
}
apply_file(){
 cp "$WORK/$1" "$2.next.$$" || return 1
 chmod "$3" "$2.next.$$" || return 1
 mv -f "$2.next.$$" "$2" || return 1
}
if ! apply_file ui "$UI" 644 ||
   ! apply_file gate "$GATE" 700 ||
   ! apply_file import "$IMPORT" 700; then
 restore
 fail install_failed_rolled_back
fi
# One bounded integrity gate, no separate end-to-end UAT.
if ! cmp -s "$WORK/ui" "$UI" ||
   ! cmp -s "$WORK/gate" "$GATE" ||
   ! cmp -s "$WORK/import" "$IMPORT"; then
 restore
 fail integrity_failed_rolled_back
fi
echo XL_RELEASE=installed
echo XL_RELEASE_INTEGRITY=pass
echo XL_RELEASE_MYXL_FALLBACK=official
echo XL_RELEASE_NATIVE_AUTH=operator_config_required
echo XL_RELEASE_BACKUP="$BACKUP"
