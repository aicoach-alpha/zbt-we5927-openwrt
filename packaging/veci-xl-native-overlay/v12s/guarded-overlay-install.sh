#!/bin/sh
# VeCI XL v12s — single-package owner-overlay cutover and one integrity check.
# All artifacts staged by office laptop under /tmp. No firmware/modem/service restart.
set -eu
umask 077
STAGE=/tmp/veci-xl-v12s-20261021
NEW="$STAGE/veci-xl-native-overlay-1.0.3-r1-mipsel_24kc.apk"
OLD="$STAGE/veci-xl-native-overlay-1.0.2-r1-mipsel_24kc.apk"
PUB="$STAGE/veci-meter-r2-rsa.pem"
UI=/www/veci/js/lib/veci-xl-connection-status.js
GATE=/usr/libexec/veci-xl-quota-session-gate
IMPORT=/usr/libexec/veci-xl-authorized-config-import
PKG=veci-xl-native-overlay
KEYDIR=
fail(){ echo "XL_V12S_ERROR=$1"; exit 1; }
cleanup(){ [ -z "$KEYDIR" ] || rm -rf "$KEYDIR"; }
trap cleanup EXIT
[ "$#" -eq 7 ] && [ "$1" = apply ] || fail invalid_args
shift
BEFORE_UI="$1"; AFTER_UI="$2"; H_GATE="$3"; H_IMPORT="$4"; H_OLD="$5"; H_NEW="$6"
for hash in "$BEFORE_UI" "$AFTER_UI" "$H_GATE" "$H_IMPORT" "$H_OLD" "$H_NEW"; do
  printf '%s\n' "$hash" | grep -Eq '^[0-9a-f]{64}$' || fail invalid_sha256_parameter
done
[ "$(id -u)" -eq 0 ] || fail root_required
[ -d "$STAGE" ] && [ ! -L "$STAGE" ] || fail staging_unsafe
for file in "$NEW" "$OLD" "$PUB" "$UI" "$GATE" "$IMPORT"; do
 [ -s "$file" ] && [ -f "$file" ] && [ ! -L "$file" ] || fail required_file_missing_or_symlink
done
sha(){ sha256sum "$1" | cut -d ' ' -f1; }
[ "$(sha "$NEW")" = "$H_NEW" ] && [ "$(sha "$OLD")" = "$H_OLD" ] || fail staged_apk_digest_mismatch
apk list -I 2>/dev/null | grep -Fq "$PKG-1.0.2-r1 " || fail overlay_version_changed
[ "$(sha "$UI")" = "$BEFORE_UI" ] || fail original_ui_changed
[ "$(sha "$GATE")" = "$H_GATE" ] || fail existing_gate_changed
[ "$(sha "$IMPORT")" = "$H_IMPORT" ] || fail existing_importer_changed
[ ! -e "$STAGE/backup" ] && [ ! -L "$STAGE/backup" ] || fail prior_backup_exists
space="$(df -k /overlay | tail -n 1 | awk '{print $4}')"
case "$space" in ''|*[!0-9]*) fail overlay_space_invalid ;; esac
[ "$space" -ge 256 ] || fail overlay_space_insufficient
KEYDIR="$(mktemp -d /tmp/veci-xl-v12s-trust.XXXXXX)" || fail temp_trust_failed
chmod 700 "$KEYDIR"
cp "$PUB" "$KEYDIR/veci-meter-r2-rsa.pem"; chmod 600 "$KEYDIR/veci-meter-r2-rsa.pem"
apk --no-network --keys-dir "$KEYDIR" verify "$NEW" >/dev/null || fail new_signature_invalid
apk --no-network --keys-dir "$KEYDIR" verify "$OLD" >/dev/null || fail rollback_signature_invalid
echo XL_V12S_SIGNATURE=pass
if ! apk --no-network --keys-dir "$KEYDIR" add --simulate "$NEW" > "$STAGE/plan.log" 2>&1; then
 cat "$STAGE/plan.log"; fail solver_failed
fi
cat "$STAGE/plan.log"
[ "$(grep -Ec '^\([0-9]+/[0-9]+\) ' "$STAGE/plan.log")" -eq 1 ] || fail unexpected_solver_scope
grep -Fq 'Upgrading veci-xl-native-overlay (1.0.2-r1 -> 1.0.3-r1)' "$STAGE/plan.log" ||
 fail unexpected_upgrade_plan
grep -q '^OK: ' "$STAGE/plan.log" || fail solver_receipt_missing
echo XL_V12S_SIMULATION=one_overlay_upgrade
mkdir -m 700 "$STAGE/backup"
cp -p /etc/apk/world "$STAGE/backup/world"
cp -p "$UI" "$STAGE/backup/ui"
cp -p "$GATE" "$STAGE/backup/gate"
cp -p "$IMPORT" "$STAGE/backup/import"
apk list -I 2>/dev/null | awk '$NF=="[installed]" && index($1,"veci-xl-native-overlay-")!=1 {print $1}' | sort > "$STAGE/backup/others"
grep -v '^veci-xl-native-overlay' "$STAGE/backup/world" > "$STAGE/backup/world-others"
echo XL_V12S_PREFLIGHT=pass
rollback(){
 echo XL_V12S_ROLLBACK=attempted
 if apk --no-network --keys-dir "$KEYDIR" add "$OLD" >/dev/null &&
    apk list -I 2>/dev/null | grep -Fq "$PKG-1.0.2-r1 " &&
    [ "$(sha "$UI")" = "$BEFORE_UI" ] &&
    [ "$(sha "$GATE")" = "$H_GATE" ] &&
    [ "$(sha "$IMPORT")" = "$H_IMPORT" ]; then
    cp -p "$STAGE/backup/world" /etc/apk/world ||
      { echo XL_V12S_ROLLBACK=world_restore_failed; return 1; }
    echo XL_V12S_ROLLBACK=original_version_files_restored
 else
    echo XL_V12S_ROLLBACK=failed_manual_recovery_required
    return 1
 fi
}
echo XL_V12S_ACTION=upgrade_overlay_only
if ! apk --no-network --keys-dir "$KEYDIR" add "$NEW"; then
 rollback || :
 fail apk_upgrade_failed
fi
apk list -I 2>/dev/null | grep -Fq "$PKG-1.0.3-r1 " || { rollback || :; fail version_integrity_failed; }
if [ "$(sha "$UI")" != "$AFTER_UI" ] ||
   [ "$(sha "$GATE")" != "$H_GATE" ] ||
   [ "$(sha "$IMPORT")" != "$H_IMPORT" ] ||
   ! apk list -I 2>/dev/null | awk '$NF=="[installed]" && index($1,"veci-xl-native-overlay-")!=1 {print $1}' | sort | cmp -s "$STAGE/backup/others" - ||
   ! grep -v '^veci-xl-native-overlay' /etc/apk/world | cmp -s "$STAGE/backup/world-others" -; then
 rollback || :
 fail integrity_failed
fi
echo XL_V12S_RELEASE=installed
echo XL_V12S_INTEGRITY=pass
echo XL_V12S_PACKAGE=veci-xl-native-overlay-1.0.3-r1
echo XL_V12S_HELPERS=unchanged
echo XL_V12S_OTHER_PACKAGES=unchanged
echo XL_V12S_ROLLBACK=original_v12r_signed_apk_and_tmp_backup
echo XL_V12S_OPERATOR_QUOTA=unchanged_by_this_release
