#!/bin/sh
# VeCI XL v12o: sign an offline APKv3 index from two previously signed APK archives.
# Alpine apk-tools v3 only, no router or operator access.
set -eu
umask 077
LC_ALL=C; export LC_ALL
P=/release
KEY=/keys/veci-meter-r2-rsa.key
PUB=/keys/veci-meter-r2-rsa.pem
error() { printf 'XL_V12O_BUILD=%s\n' "$1"; exit 1; }
[ -f "$KEY" ] && [ -f "$PUB" ] || error signing_key_missing
apk --version | grep -Eq 'apk-tools 3[.]' || error apk_tools_3_required
[ -d "$P" ] && [ ! -L "$P" ] || error release_directory_missing
cd "$P"
[ -s release-files.txt ] && [ ! -L release-files.txt ] || error release_manifest_missing
[ "$(wc -l < release-files.txt | tr -d '[:space:]')" = 2 ] || error expected_two_packages
while IFS= read -r file; do
  case "$file" in
    veci-telco-xl-native-*.apk|veci-telco-indonesia-*.apk) ;;
    *) error package_name_invalid ;;
  esac
  [ -s "$file" ] && [ ! -L "$file" ] || error package_file_missing
  apk --keys-dir /keys verify "$file" >/dev/null || error package_signature_invalid
done < release-files.txt
set --
while IFS= read -r file; do set -- "$@" "$file"; done < release-files.txt
[ "$#" -eq 2 ] || error manifest_invalid
[ ! -e Packages.adb ] && [ ! -L Packages.adb ] || error index_exists
apk --keys-dir /keys mkndx --sign-key "$KEY" -o Packages.adb "$@" || error index_create_failed
apk --keys-dir /keys verify Packages.adb >/dev/null || error index_signature_invalid
printf 'XL_V12O_BUILD=pass\nXL_V12O_SIGNATURE=pass\nXL_V12O_ARCHIVES=2\nXL_V12O_INDEX_SHA256=%s\nXL_V12O_ROUTER=unchanged\n' "$(sha256sum Packages.adb | cut -d ' ' -f1)"
