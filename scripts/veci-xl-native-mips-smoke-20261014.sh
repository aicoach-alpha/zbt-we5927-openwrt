#!/bin/sh
# VeCI XL native MIPS 95-KiB smoke: execute from /tmp ONLY.
# No flash install, no modem, no SMS/OTP, no carrier login or HTTPS requests.
set -eu
umask 077
LC_ALL=C;export LC_ALL
SHA=87c2c863edf62add04fa063d9bf5835947002d6aa27467b9c03471978474f123
URL=https://github.com/aicoach-alpha/zbt-we5927-openwrt/releases/download/veci-xl-crypto-d5413f5617ae/veci-xl-crypto-mipsel
EXPECTED=9521584dcb6abe89c25327a0bd22de3201631c27d9d4c175d7bb7bed89b8407833db09743a67679b39fe508d437bece624c4203a1c33e4ed4b11469b4ffc5697
fail(){ printf 'VECI_XL_MIPS_SMOKE_ERROR=%s\n' "$1" >&2;exit 1; }
[ "$#" -eq 1 ] && [ "$1" = --verify ] || fail usage
[ "$(cat /tmp/sysinfo/board_name 2>/dev/null || :)" = zbtlink,zbt-we5927 ] || fail wrong_router
for x in wget sha256sum awk mktemp chmod;do
 command -v "$x" >/dev/null 2>&1 || fail missing_dependency
done
work="$(mktemp -d /tmp/veci-xl-mips.XXXXXX)" || fail temp_unavailable
trap 'rm -rf "$work"' EXIT
trap 'exit 130' INT TERM
binary="$work/veci-xl-crypto"
wget -qO "$binary" "$URL" || fail download
[ "$(sha256sum "$binary"|awk '{print $1}')" = "$SHA" ] || fail checksum
chmod 700 "$binary" || fail permissions
# Only synthetic PUBLIC test data and a fixed PUBLIC deterministic HMAC.
printf '%s' 'veci-public-fixture-app-secret' > "$work/key"
printf '%s' 'veci-public-fixture-id-token' > "$work/token"
chmod 600 "$work/key" "$work/token"
actual="$("$binary" signature 1791987600 "$work/key" "$work/token" 2>/dev/null)" ||
 fail incompatible_native_binary
[ "$actual" = "$EXPECTED" ] || fail native_signature_mismatch
printf '%s' 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa' > "$work/aes"
chmod 600 "$work/aes"
encoded="$(printf '{"lang":"en"}' | "$binary" xdata 1791987600000 "$work/aes" 2>/dev/null)" ||
 fail native_aes_unavailable
[ "$(printf %s "$encoded" | wc -c)" -eq 24 ] ||
 fail unexpected_aes_ciphertext_size
# Second self-contained native MIPS executable, no operator API call.
PARSER_SHA=2105dea88ef4f2990fd580a349fc563403b59564e3a8673b360f9b1f7c746284
PARSER_URL=https://github.com/aicoach-alpha/zbt-we5927-openwrt/releases/download/veci-xl-quota-normalize-17e5e160caa2/veci-xl-quota-normalize-mipsel
parser="$work/veci-xl-quota-normalize"
wget -qO "$parser" "$PARSER_URL" || fail quota_parser_download
[ "$(sha256sum "$parser"|awk '{print $1}')" = "$PARSER_SHA" ] || fail quota_parser_checksum
chmod 700 "$parser" || fail quota_parser_permissions
sample='{"quotas":[{"benefits":[{"data_type":"DATA","remaining":512,"total":1024},{"data_type":"VOICE","remaining":999,"total":999}]}]}'
normalized="$(printf %s "$sample" | "$parser" 2>/dev/null)" ||
 fail quota_parser_incompatible
[ "$normalized" = '{"ok":true,"parsed_only":true,"provider":"xl","remaining_bytes":512,"total_bytes":1024}' ] ||
 fail quota_parser_wrong_data
if printf '%s' '{"status":"FAILED","quota_display":"Buy 10 GB"}' |
   "$parser" >/dev/null 2>&1;then fail quota_parser_false_positive;fi
printf 'VECI_XL_NATIVE_QUOTA_DATA_PARSER=pass\n'
printf 'VECI_XL_NATIVE_MIPS_SHA256=pass\n'
printf 'VECI_XL_NATIVE_MIPS_HMAC=pass\n'
printf 'VECI_XL_NATIVE_MIPS_AES=pass\n'
printf 'VECI_XL_NATIVE_MIPS_EXECUTABLE=pass\n'
printf 'VECI_REAL_OPERATOR_LOGIN=not_attempted\n'
printf 'VECI_OPERATOR_QUOTA=not_verified\n'
printf 'VECI_MODEM_AND_SMS_UNCHANGED=true\n'
printf 'VECI_FLASH_WRITES=none\n'
