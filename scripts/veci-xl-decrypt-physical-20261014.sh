#!/bin/sh
# One physical regression check for NEW native XL decryption and payload parser.
# Synthetic PUBLIC DATA only; nothing is installed, logged or written to flash.
set -eu
umask 077
LC_ALL=C; export LC_ALL
fail(){ printf 'VECI_XL_DECRYPT_UAT_ERROR=%s\n' "$1" >&2;exit 1; }
[ "$#" -eq 1 ] && [ "$1" = "--verify" ] || fail usage
[ "$(cat /tmp/sysinfo/board_name 2>/dev/null || :)" = "zbtlink,zbt-we5927" ] || fail wrong_router
for x in wget sha256sum awk mktemp chmod cmp; do
 command -v "$x" >/dev/null 2>&1 || fail missing_dependency
done
work="$(mktemp -d /tmp/veci-xl-decrypt.XXXXXX)" || fail tmp_unavailable
trap 'rm -rf "$work"' EXIT
trap 'exit 130' INT TERM
crypto="$work/veci-xl-crypto"
parser="$work/veci-xl-normalizer"
wget -qO "$crypto" \
 "https://github.com/aicoach-alpha/zbt-we5927-openwrt/releases/download/veci-xl-crypto-3bcd7b516148/veci-xl-crypto-mipsel" || fail crypto_download
[ "$(sha256sum "$crypto" | awk '{print $1}')" = "6fb5f4ff793e576901f1e53e243be03f811265203d16eb4e9a40bf67bc35ad0b" ] || fail crypto_sha256
wget -qO "$parser" \
 "https://github.com/aicoach-alpha/zbt-we5927-openwrt/releases/download/veci-xl-quota-normalize-17e5e160caa2/veci-xl-quota-normalize-mipsel" || fail parser_download
[ "$(sha256sum "$parser" | awk '{print $1}')" = "2105dea88ef4f2990fd580a349fc563403b59564e3a8673b360f9b1f7c746284" ] || fail parser_sha256
chmod 700 "$crypto" "$parser"
printf '%s' 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa' > "$work/key"
chmod 600 "$work/key"
printf '%s' '{"status":"SUCCESS","data":{"quotas":[{"benefits":[{"data_type":"DATA","remaining":512,"total":1024}]}]}}' > "$work/public-fixture"
"$crypto" xdata 1791987600000 "$work/key" < "$work/public-fixture" > "$work/encrypted" || fail encrypt
"$crypto" decrypt 1791987600000 "$work/key" < "$work/encrypted" > "$work/decrypted" || fail decrypt
cmp -s "$work/public-fixture" "$work/decrypted" || fail decrypt_mismatch
[ "$("$parser" < "$work/decrypted")" = '{"ok":true,"parsed_only":true,"provider":"xl","remaining_bytes":512,"total_bytes":1024}' ] || fail parser
if printf '%s' 'corrupted@@@' | "$crypto" decrypt 1791987600000 "$work/key" >/dev/null 2>&1; then
 fail invalid_cipher_accepted
fi
printf 'VECI_XL_NATIVE_DECRYPT=pass\n'
printf 'VECI_XL_NATIVE_ENCRYPT_DECRYPT_ROUNDTRIP=pass\n'
printf 'VECI_XL_NATIVE_DECRYPT_QUOTA_PARSER=pass\n'
printf 'VECI_XL_RELEASE_SHA256=pass\n'
printf 'VECI_REAL_OPERATOR_LOGIN=not_attempted\n'
printf 'VECI_OPERATOR_QUOTA=not_verified\n'
printf 'VECI_MODEM_AND_SMS_UNCHANGED=true\n'
printf 'VECI_FLASH_WRITES=none\n'
