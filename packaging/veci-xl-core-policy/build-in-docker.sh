#!/bin/sh
# Build a signed APKv3 using the exact office-captured Core XL source.
# Executes only inside Docker; no SSH and no changes to router production.
set -eu
umask 077
SRC=/work/source/usr
STAGE=/tmp/veci-xl-core-policy-root
DIST=/work/dist
KEY=/work/keys/veci-meter-r2-rsa.key
OUT=$DIST/veci-xl-core-policy-0.1.0-r1-mipsel_24kc.apk
fail(){ echo "XL_CORE_APK=$1"; exit 1; }
[ -s "$KEY" ] || fail local_signing_key_missing
[ -s /work/keys/veci-meter-r2-rsa.pem ] || fail signing_public_key_missing
apk --version | grep -Eq 'apk-tools 3[.]' || fail apk_tools_v3_required
for f in "$SRC/libexec/rpcd/veci.xl" "$SRC/libexec/rpcd/veci.quota" \
 "$SRC/share/rpcd/acl.d/veci-xl-owner.json" "$SRC/libexec/veci-xl-session-clear"; do
 [ -s "$f" ] || fail source_missing
done
for f in "$SRC/libexec/rpcd/veci.xl" "$SRC/libexec/rpcd/veci.quota" \
 "$SRC/libexec/veci-xl-session-clear"; do
 sh -n "$f" || fail shell_syntax_invalid
done
mkdir -p "$STAGE/usr/libexec/rpcd" "$STAGE/usr/share/rpcd/acl.d" "$DIST"
cp "$SRC/libexec/rpcd/veci.xl" "$STAGE/usr/libexec/rpcd/veci.xl"
cp "$SRC/libexec/rpcd/veci.quota" "$STAGE/usr/libexec/rpcd/veci.quota"
cp "$SRC/libexec/veci-xl-session-clear" "$STAGE/usr/libexec/veci-xl-session-clear"
cp "$SRC/share/rpcd/acl.d/veci-xl-owner.json" "$STAGE/usr/share/rpcd/acl.d/veci-xl-owner.json"
chmod 755 "$STAGE/usr/libexec/rpcd/veci.xl" "$STAGE/usr/libexec/rpcd/veci.quota"
chmod 700 "$STAGE/usr/libexec/veci-xl-session-clear"
chmod 644 "$STAGE/usr/share/rpcd/acl.d/veci-xl-owner.json"
[ ! -e "$OUT" ] || fail output_already_exists
apk mkpkg --files "$STAGE" \
 --info name:veci-xl-core-policy \
 --info version:0.1.0-r1 \
 --info arch:mipsel_24kc \
 --info origin:veci-xl-core-policy \
 --info license:GPL-2.0-only \
 --info description:VeCI-XL-account-RPC-owner-ACL-and-quota-gate-dispatch \
 --info depends:"veci-telco-xl-native veci-xl-native-overlay rpcd jsonfilter" \
 --sign-key "$KEY" --output "$OUT" || fail mkpkg_failed
apk --keys-dir /work/keys verify "$OUT" || fail signature_failed
echo XL_CORE_APK=pass
echo XL_CORE_SIGNATURE=pass
sha256sum "$OUT"
