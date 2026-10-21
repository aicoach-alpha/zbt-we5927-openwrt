#!/bin/sh
# VeCI XL v12r: sign 1.0.2-r1; retain exact original installed 1.0.1-r1 APK for rollback.
# Offline Alpine apk-tools v3, no router changes.
set -eu
umask 077
SOURCE=/source
DIST=/dist
KEY=/keys/veci-meter-r2-rsa.key
die(){ echo "XL_V12R_BUILD=$1"; exit 1; }
apk --version | grep -Eq 'apk-tools 3[.]' || die apk_tools_3_required
[ -s "$KEY" ] && [ -s /keys/veci-meter-r2-rsa.pem ] || die signer_missing
for state in before after; do
 [ -s "$SOURCE/$state/veci-xl-connection-status.js" ] || die ui_source_missing
 [ -s "$SOURCE/$state/veci-xl-quota-session-gate" ] || die gate_source_missing
 [ -s "$SOURCE/$state/veci-xl-authorized-config-import" ] || die importer_source_missing
done
for item in veci-xl-quota-session-gate veci-xl-authorized-config-import; do
 cmp -s "$SOURCE/before/$item" "$SOURCE/after/$item" || die helper_changed
 sh -n "$SOURCE/after/$item" || die helper_syntax_invalid
done
cmp -s "$SOURCE/before/veci-xl-connection-status.js" "$SOURCE/after/veci-xl-connection-status.js" && die ui_unchanged
for state in after; do
 version=1.0.2-r1
 stage="$(mktemp -d /tmp/veci-xl-v12r.XXXXXX)" || die temp_stage_failed
 mkdir -p "$stage/www/veci/js/lib" "$stage/usr/libexec"
 cp "$SOURCE/$state/veci-xl-connection-status.js" "$stage/www/veci/js/lib/veci-xl-connection-status.js"
 cp "$SOURCE/$state/veci-xl-quota-session-gate" "$stage/usr/libexec/veci-xl-quota-session-gate"
 cp "$SOURCE/$state/veci-xl-authorized-config-import" "$stage/usr/libexec/veci-xl-authorized-config-import"
 # Match original overlay permissions; 0700 on /www would break the Web UI.
 chmod 755 "$stage" "$stage/www" "$stage/www/veci" "$stage/www/veci/js" "$stage/www/veci/js/lib" "$stage/usr" "$stage/usr/libexec"
 chmod 644 "$stage/www/veci/js/lib/veci-xl-connection-status.js"
 chmod 700 "$stage/usr/libexec/veci-xl-quota-session-gate" "$stage/usr/libexec/veci-xl-authorized-config-import"
 file="$DIST/veci-xl-native-overlay-$version-mipsel_24kc.apk"
 if [ -e "$file" ] || [ -L "$file" ]; then
  [ -s "$file" ] && [ -f "$file" ] && [ ! -L "$file" ] || die existing_archive_unsafe
  apk --keys-dir /keys verify "$file" >/dev/null || die existing_archive_signature_failed
  extracted="$(mktemp -d /tmp/veci-xl-v12r-verify.XXXXXX)" || die extraction_stage_failed
  apk --keys-dir /keys extract --no-chown --destination "$extracted" "$file" >/dev/null ||
    die existing_archive_extract_failed
  # Exact three-file, content and mode match; never trust archive filename alone.
  (cd "$stage" && find . -type f | sort) > /tmp/veci-xl-v12r.expected.$
  (cd "$extracted" && find . -type f | sort) > /tmp/veci-xl-v12r.actual.$
  cmp -s /tmp/veci-xl-v12r.expected.$ /tmp/veci-xl-v12r.actual.$ ||
    die existing_archive_manifest_mismatch
  rm -f /tmp/veci-xl-v12r.expected.$ /tmp/veci-xl-v12r.actual.$
  for relative in www/veci/js/lib/veci-xl-connection-status.js usr/libexec/veci-xl-quota-session-gate usr/libexec/veci-xl-authorized-config-import; do
   cmp -s "$stage/$relative" "$extracted/$relative" || die existing_archive_contents_mismatch
   [ "$(stat -c %a "$stage/$relative")" = "$(stat -c %a "$extracted/$relative")" ] ||
     die existing_archive_mode_mismatch
  done
  [ "$(stat -c %a "$extracted/www/veci/js/lib")" = 755 ] ||
    die existing_archive_web_dir_mode_mismatch
  rm -rf "$extracted"
  echo XL_V12R_BUILD=already_valid_signed_archive
 else
  apk mkpkg --files "$stage" \
   --info name:veci-xl-native-overlay \
   --info "version:$version" \
   --info arch:mipsel_24kc \
   --info origin:veci-xl-native-overlay \
   --info license:GPL-2.0-only \
   --info description:VeCI-XL-owner-panel-and-local-session-helpers \
   --info 'depends:veci-telco-xl-native rpcd jsonfilter' \
   --sign-key "$KEY" --output "$file" || die apk_build_failed
  apk --keys-dir /keys verify "$file" >/dev/null || die signed_apk_verify_failed
 fi
 echo "XL_V12R_$state-SHA256=$(sha256sum "$file" | cut -d ' ' -f1)"
 rm -rf "$stage"
done
echo XL_V12R_BUILD=pass
echo XL_V12R_SIGNATURE=pass
echo XL_V12R_HELPERS=unchanged
echo XL_V12R_ROLLBACK=reuse_exact_original_apk
echo XL_V12R_ROUTER=unchanged
