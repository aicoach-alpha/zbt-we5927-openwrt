#!/bin/sh
# Install VeCI native XL offline provisioning utility, read-only status check.
# Does not request OTP, alter accounts, or create operator configuration.
set -eu
umask 077
TARGET=/usr/libexec/veci-xl-authorized-config-import
TMP=/usr/libexec/.veci-xl-authorized-config-import.$$
URL=https://raw.githubusercontent.com/aicoach-alpha/zbt-we5927-openwrt/9ad1a5224c2c7c322054f37b7fb00ca2a20b4936/scripts/veci-xl-authorized-config-import-v10-20261020.sh
fail(){ echo "XL_V10=$1"; exit 1; }
trap 'rm -f "$TMP"' EXIT
[ "$(id -u)" = 0 ] || fail root_required
[ ! -e "$TARGET" ] && [ ! -L "$TARGET" ] || fail already_installed
[ ! -e "$TMP" ] && [ ! -L "$TMP" ] || fail temporary_path_in_use
[ -x /usr/libexec/rpcd/veci.xl ] || fail xl_backend_missing
wget -qO "$TMP" "$URL" || fail download_failed
sh -n "$TMP" || fail invalid_shell_syntax
grep -Fq 'safe_file "$SRC/$name"' "$TMP" || fail bundle_guard_missing
grep -Fq '[ "$(file_size "$SRC/xdata_key")" -eq 32 ]' "$TMP" || fail key_length_guard_missing
grep -Fq 'installed_operator_auth_not_verified' "$TMP" || fail unverified_state_guard_missing
chmod 700 "$TMP" || fail chmod_failed
mv -f "$TMP" "$TARGET" || fail activate_failed
STATUS="$("$TARGET" --status 2>/dev/null)" || {
 rm -f "$TARGET"
 fail status_integrity_failed
}
case "$STATUS" in
 XL_PROVISION=awaiting_authorized_config|XL_PROVISION=locally_configured_operator_access_unverified) ;;
 *) rm -f "$TARGET"; fail unexpected_status ;;
esac
echo XL_V10=installed
echo XL_V10_INTEGRITY=pass
echo "$STATUS"
echo XL_V10_OTP=not_triggered
echo XL_V10_LTE_SMS=unchanged
