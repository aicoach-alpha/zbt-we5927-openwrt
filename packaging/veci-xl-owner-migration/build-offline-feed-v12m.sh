#!/bin/sh
# VeCI v12m: build signed offline index for already-signed native APKs.
# Runs only inside Alpine Docker. Never touches the router.
set -eu
KEY=/keys/veci-meter-r2-rsa.key
PUB=/keys/veci-meter-r2-rsa.pem
DIR=/repo
[ -s "$KEY" ] && [ -s "$PUB" ] || { echo XL_V12M=signing_key_missing; exit 1; }
apk --version | grep -Eq 'apk-tools 3[.]' || { echo XL_V12M=apk_v3_required; exit 1; }
cd "$DIR"
for pair in 'veci-telco-xl-native-0.3.8-r2.apk:801b421569f6cd18ade2bfc3a86c7e61e333e680dfc41e29edffd3cdd0793f37' 'veci-telco-indonesia-0.2.2-r2.apk:da3d5d9da1bdc684170d75773a03562f7dcca672a3d3d8dd1575969ad4d65866'; do
  file="${pair%%:*}"
  hash="${pair#*:}"
  [ -s "$file" ] && [ ! -L "$file" ] || { echo XL_V12M=package_missing; exit 1; }
  [ "$(sha256sum "$file" | cut -d ' ' -f1)" = "$hash" ] || { echo XL_V12M=package_hash_mismatch; exit 1; }
  apk --keys-dir /keys verify "$file" >/dev/null || { echo XL_V12M=package_signature_failed; exit 1; }
done
if [ -e Packages.adb ] || [ -L Packages.adb ]; then
  # Resume only a regular, previously signed index; never delete or overwrite it.
  [ -f Packages.adb ] && [ ! -L Packages.adb ] || { echo XL_V12M=index_path_unsafe; exit 1; }
  apk --keys-dir /keys verify Packages.adb || { echo XL_V12M=existing_index_signature_failed; exit 1; }
  echo XL_V12M_FEED_BUILD=already_valid
else
  apk mkndx --sign-key "$KEY" -o Packages.adb veci-telco-xl-native-0.3.8-r2.apk veci-telco-indonesia-0.2.2-r2.apk || { echo XL_V12M=mkndx_failed; exit 1; }
  apk --keys-dir /keys verify Packages.adb || { echo XL_V12M=index_signature_failed; exit 1; }
  echo XL_V12M_FEED_BUILD=pass
fi
echo XL_V12M_FEED_SIGNATURE=pass
echo "XL_V12M_INDEX_SHA256=$(sha256sum Packages.adb | cut -d ' ' -f1)"
echo XL_V12M_INSTALL=not_attempted
echo XL_V12M_ROUTER=unchanged
