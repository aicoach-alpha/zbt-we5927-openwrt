#!/bin/sh
# VeCI XL v12q: sign 1.0.1-r1 and reconstructed rollback 1.0.0-r1.
# Offline Alpine apk-tools v3, no router changes.
set -eu
umask 077
SOURCE=/source
DIST=/dist
KEY=/keys/veci-meter-r2-rsa.key
die(){ echo "XL_V12Q_BUILD=$1"; exit 1; }
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
for state in before after; do
 if [ "$state" = before ]; then version=1.0.0-r1; else version=1.0.1-r1; fi
 stage="$(mktemp -d /tmp/veci-xl-v12q.XXXXXX)" || die temp_stage_failed
 mkdir -p "$stage/www/veci/js/lib" "$stage/usr/libexec"
 cp "$SOURCE/$state/veci-xl-connection-status.js" "$stage/www/veci/js/lib/veci-xl-connection-status.js"
 cp "$SOURCE/$state/veci-xl-quota-session-gate" "$stage/usr/libexec/veci-xl-quota-session-gate"
 cp "$SOURCE/$state/veci-xl-authorized-config-import" "$stage/usr/libexec/veci-xl-authorized-config-import"
 chmod 644 "$stage/www/veci/js/lib/veci-xl-connection-status.js"
 chmod 700 "$stage/usr/libexec/veci-xl-quota-session-gate" "$stage/usr/libexec/veci-xl-authorized-config-import"
 file="$DIST/veci-xl-native-overlay-$version-mipsel_24kc.apk"
 [ ! -e "$file" ] || die output_already_exists
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
 echo "XL_V12Q_$state-SHA256=$(sha256sum "$file" | cut -d ' ' -f1)"
 rm -rf "$stage"
done
echo XL_V12Q_BUILD=pass
echo XL_V12Q_SIGNATURE=pass
echo XL_V12Q_HELPERS=unchanged
echo XL_V12Q_ROUTER=unchanged
