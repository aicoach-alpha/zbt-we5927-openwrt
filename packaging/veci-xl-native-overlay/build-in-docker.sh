#!/bin/sh
# Runs INSIDE Docker Alpine apk-tools v3. Does not access router.
set -eu
umask 077
SOURCE=/work/files
OUTPUT=/work/dist/veci-xl-native-overlay-1.0.0-r1-mipsel_24kc.apk
SIGN=/work/keys/veci-meter-r2-rsa.key
PUB=/work/keys/veci-meter-r2-rsa.pem
STAGE=/tmp/veci-xl-package-root
die(){ echo "XL_APK_BUILD=$1"; exit 1; }
[ -f "$SIGN" ] && [ -f "$PUB" ] || die local_signing_key_missing
for f in veci-xl-connection-status.js veci-xl-quota-session-gate veci-xl-authorized-config-import; do
 [ -s "$SOURCE/$f" ] || die source_missing
done
# apk mkpkg is apk-tools v3: NEVER create a v2 package.
apk --version | grep -Eq 'apk-tools 3[.]' || die apk_tools_v3_required
mkdir -p "$STAGE/www/veci/js/lib" "$STAGE/usr/libexec" /work/dist
cp "$SOURCE/veci-xl-connection-status.js" "$STAGE/www/veci/js/lib/veci-xl-connection-status.js"
cp "$SOURCE/veci-xl-quota-session-gate" "$STAGE/usr/libexec/veci-xl-quota-session-gate"
cp "$SOURCE/veci-xl-authorized-config-import" "$STAGE/usr/libexec/veci-xl-authorized-config-import"
chmod 755 "$STAGE" "$STAGE/www" "$STAGE/www/veci" "$STAGE/www/veci/js" "$STAGE/www/veci/js/lib" "$STAGE/usr" "$STAGE/usr/libexec"
chmod 644 "$STAGE/www/veci/js/lib/veci-xl-connection-status.js"
chmod 700 "$STAGE/usr/libexec/veci-xl-quota-session-gate" "$STAGE/usr/libexec/veci-xl-authorized-config-import"
sh -n "$STAGE/usr/libexec/veci-xl-quota-session-gate" || die invalid_quota_gate
sh -n "$STAGE/usr/libexec/veci-xl-authorized-config-import" || die invalid_provision_import
[ ! -e "$OUTPUT" ] || die apk_already_exists
apk mkpkg --files "$STAGE" \
 --info name:veci-xl-native-overlay \
 --info version:1.0.0-r1 \
 --info arch:mipsel_24kc \
 --info origin:veci-xl-native-overlay \
 --info license:GPL-2.0-only \
 --info description:VeCI-XL-native-owner-auth-and-quota-helpers \
 --info depends:"veci-telco-xl-native rpcd jsonfilter" \
 --sign-key "$SIGN" --output "$OUTPUT" || die mkpkg_failed
apk --keys-dir /work/keys verify "$OUTPUT" || die signature_check_failed
# Print only metadata and artifact checksum; no credentials.
echo XL_APK_BUILD=pass
echo XL_APK_SIGNATURE=pass
sha256sum "$OUTPUT"
