#!/bin/sh
# VeCI XL v9: opt-in OTP UI for existing HTTPS-only account RPC.
# UI-only install: no changes to modem, SMS, LTE, rpcd, or LuCI.
set -eu
umask 077
TARGET=/www/veci/js/lib/veci-xl-connection-status.js
PAGE=/www/veci/js/pages/cellular.js
BACKUP=/tmp/veci-xl-ui-before-v9-20261019.js
TMP=/www/veci/js/lib/.veci-xl-v9.$$
URL=https://raw.githubusercontent.com/aicoach-alpha/zbt-we5927-openwrt/3052cc7e4e737939d658162cd275dfab7e83722a/web/veci-xl-auth-panel-v9-20261019.js
fail(){ echo "XL_V9=$1"; exit 1; }
trap 'rm -f "$TMP"' EXIT
[ "$(id -u)" = 0 ] || fail root_required
[ -f "$TARGET" ] && [ ! -L "$TARGET" ] || fail target_missing
[ -f "$PAGE" ] && [ ! -L "$PAGE" ] || fail cellular_missing
grep -Fq 'mountXlConnection(root, api)' "$PAGE" || fail ui_anchor_missing
[ ! -e "$TMP" ] && [ ! -L "$TMP" ] || fail temp_conflict
wget -qO "$TMP" "$URL" || fail download_failed
[ "$(wc -c < "$TMP" | tr -d '[:space:]')" -le 15000 ] || fail module_too_large
grep -Fq 'export async function mountXlConnection' "$TMP" || fail module_export_missing
grep -Fq "void action('requestOtp', { number })" "$TMP" || fail request_otp_missing
grep -Fq "void action('submitOtp', { otp })" "$TMP" || fail submit_otp_missing
grep -Fq "void action('refreshQuota', {})" "$TMP" || fail quota_refresh_missing
grep -Fq "api.call('veci.xl', 'logout'" "$TMP" || fail logout_missing
grep -Fq "q.source !== 'operator'" "$TMP" || fail operator_guard_missing
grep -Fq "s.operator_configured" "$TMP" || fail config_guard_missing
cp -p "$TARGET" "$BACKUP" || fail backup_failed
chmod 644 "$TMP" || fail chmod_failed
mv -f "$TMP" "$TARGET" || fail install_failed
if ! grep -Fq "void action('submitOtp', { otp })" "$TARGET"; then
 cp -p "$BACKUP" "$TARGET" || :
 fail integrity_failed_rolled_back
fi
echo XL_V9=installed
echo XL_V9_INTEGRITY=pass
echo XL_V9_AUTH=owner_initiated_only
echo XL_V9_BACKUP="$BACKUP"
