#!/bin/sh
# VeCI XL overlay APKv3 installer. Intended for office-laptop SSH on the WE5927.
# Single bounded preflight + install + integrity. No firmware, LTE or RPC restart.
set -eu
umask 077
PKG=/tmp/veci-xl-native-overlay-1.0.0-r1-mipsel_24kc.apk
KEY=/tmp/veci-meter-r2-rsa.pem
NAME=veci-xl-native-overlay
SHA=5b418533be9ffdfced4b357bef933934496606f769d400c99df3921116dec486
UI=/www/veci/js/lib/veci-xl-connection-status.js
GATE=/usr/libexec/veci-xl-quota-session-gate
IMPORT=/usr/libexec/veci-xl-authorized-config-import
BACKUP=/tmp/veci-xl-apk-before-install-20261020
KEYDIR=
fail(){ echo "XL_APK_INSTALL=$1"; exit 1; }
cleanup(){ [ -z "$KEYDIR" ] || rm -rf "$KEYDIR"; }
trap cleanup EXIT
[ "$(id -u)" = 0 ] || fail root_required
[ -f "$PKG" ] && [ ! -L "$PKG" ] || fail apk_not_staged
[ -f "$KEY" ] && [ ! -L "$KEY" ] || fail public_key_not_staged
[ "$(sha256sum "$PKG" | cut -d ' ' -f 1)" = "$SHA" ] || fail sha256_mismatch
[ -x /usr/bin/apk ] || command -v apk >/dev/null 2>&1 || fail apk_unavailable
if apk info -e "$NAME" >/dev/null 2>&1; then
 echo XL_APK_INSTALL=already_installed
 exit 0
fi
for dep in veci-telco-xl-native rpcd jsonfilter; do
 apk info -e "$dep" >/dev/null 2>&1 || fail dependency_missing
done
[ -f /usr/libexec/rpcd/veci.xl ] && [ -f /usr/libexec/rpcd/veci.quota ] || fail rpc_prerequisite_missing
grep -Fq 'logout) logout_local ;;' /usr/libexec/rpcd/veci.xl || fail xl_rpc_incompatible
grep -Fq '/usr/libexec/veci-xl-quota-session-gate --status' /usr/libexec/rpcd/veci.quota || fail quota_rpc_incompatible
for f in "$UI" "$GATE" "$IMPORT"; do
 [ -f "$f" ] && [ ! -L "$f" ] || fail existing_file_missing
 # Do not steal files from another installed package.
 if apk info -W "$f" >/dev/null 2>&1; then fail package_ownership_conflict; fi
done
[ ! -e "$BACKUP" ] && [ ! -L "$BACKUP" ] || fail backup_path_exists
# The overlay must have 256 KiB free before any writes to the package database.
FREE="$(df -k /overlay | tail -n 1 | awk '{print $4}')" || fail df_failed
case "$FREE" in ''|*[!0-9]*) fail df_invalid ;; esac
[ "$FREE" -ge 256 ] || fail overlay_space_low
KEYDIR="$(mktemp -d /tmp/veci-xl-key.XXXXXX)" || fail keydir_failed
chmod 700 "$KEYDIR"
cp "$KEY" "$KEYDIR/veci-meter-r2-rsa.pem" || fail trust_key_copy_failed
chmod 600 "$KEYDIR/veci-meter-r2-rsa.pem"
apk --no-network --keys-dir "$KEYDIR" verify "$PKG" >/dev/null || fail signature_failed
# One package-resolution dry run, no broad regression suite.
apk --no-network --keys-dir "$KEYDIR" add --simulate "$PKG" >/dev/null || fail apk_solver_blocked
mkdir -m 700 "$BACKUP" || fail backup_failed
cp -p "$UI" "$BACKUP/ui" && cp -p "$GATE" "$BACKUP/gate" &&
 cp -p "$IMPORT" "$BACKUP/import" || fail backup_copy_failed
restore(){
 apk --no-network --keys-dir "$KEYDIR" del "$NAME" >/dev/null 2>&1 || :
 cp -p "$BACKUP/ui" "$UI" || :
 cp -p "$BACKUP/gate" "$GATE" || :
 cp -p "$BACKUP/import" "$IMPORT" || :
}
if ! apk --no-network --keys-dir "$KEYDIR" add "$PKG" >/dev/null; then
 restore
 fail apk_add_failed_rolled_back
fi
if ! apk info -e "$NAME" >/dev/null 2>&1 ||
   ! grep -Fq "official.href = 'https://www.xl.co.id/id/myxl'" "$UI" ||
   ! grep -Fq '[ "$modified" -ge "$epoch" ] || unavailable stale' "$GATE" ||
   ! grep -Fq 'installed_operator_auth_not_verified' "$IMPORT"; then
 restore
 fail integrity_failed_rolled_back
fi
echo XL_APK_INSTALL=installed
echo XL_APK_SIGNATURE=pass
echo XL_APK_INTEGRITY=pass
echo XL_APK_ARCH=mipsel_24kc
echo XL_APK_BACKUP="$BACKUP"
echo XL_APK_AUTH=operator_config_required
