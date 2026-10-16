#!/bin/sh
# VeCI XL compact dynamic runtime — physical MIPS ABI one-shot, 2026-10-15.
# Only volatile /tmp, synthetic PUBLIC crypto/quota data, no operator request.
# Does not install into flash, read OTP, touch the modem, reboot or change LTE.
set -eu
umask 077
LC_ALL=C; export LC_ALL
[ "$#" -eq 1 ] && [ "$1" = "--verify" ] || exit 2
fail(){ printf 'VECI_XL_COMPACT_UAT_ERROR=%s\n' "$1" >&2;exit 1; }
[ "$(cat /tmp/sysinfo/board_name 2>/dev/null || :)" = "zbtlink,zbt-we5927" ] || fail wrong_router
for command_name in wget sha256sum awk mktemp chmod cmp grep; do
  command -v "$command_name" >/dev/null 2>&1 || fail missing_tool
done
dir="$(mktemp -d /tmp/veci-xl-compact.XXXXXX)" || fail ram_unavailable
trap 'rm -rf "$dir"' EXIT
trap 'exit 130' INT TERM
base="https://github.com/aicoach-alpha/zbt-we5927-openwrt/releases/download/veci-xl-runtime-compact-24653c5bc779"
crypto="$dir/veci-xl-crypto"
parser="$dir/veci-xl-parser"
http="$dir/veci-xl-http"
wget -qO "$crypto" "$base/veci-xl-crypto-dynamic-mipsel" || fail crypto_download
wget -qO "$parser" "$base/veci-xl-quota-normalize-dynamic-mipsel" || fail parser_download
wget -qO "$http" "$base/veci-xl-quota-http-dynamic-mipsel" || fail http_download
[ "$(sha256sum "$crypto" | awk '{print $1}')" = "4bb8f2cb62d18aa7da34bf84aba25a2681cc0dc1ef75d5d984dd0fd68b44d931" ] || fail crypto_sha256
[ "$(sha256sum "$parser" | awk '{print $1}')" = "756daba7b1db1dbede615cf6154ed1ca767e66f42118aee947b515a9cdee1015" ] || fail parser_sha256
[ "$(sha256sum "$http" | awk '{print $1}')" = "64c140562ddbc4fd1bb35597ef3a69022e392227a7a89d04ca1bea0c5ca4401b" ] || fail http_sha256
chmod 700 "$crypto" "$parser" "$http"
printf 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa' > "$dir/key"
chmod 600 "$dir/key"
printf '%s' '{"status":"SUCCESS","data":{"quotas":[{"benefits":[{"data_type":"DATA","remaining":512,"total":1024}]}]}}' > "$dir/public-data"
"$crypto" xdata 1791987600000 "$dir/key" < "$dir/public-data" > "$dir/encoded" 2>/dev/null || fail dynamic_crypto_unavailable
"$crypto" decrypt 1791987600000 "$dir/key" < "$dir/encoded" > "$dir/decoded" 2>/dev/null || fail dynamic_decrypt_unavailable
cmp -s "$dir/public-data" "$dir/decoded" || fail crypto_roundtrip
actual="$("$parser" < "$dir/decoded" 2>/dev/null)" || fail dynamic_parser_unavailable
[ "$actual" = '{"ok":true,"parsed_only":true,"provider":"xl","remaining_bytes":512,"total_bytes":1024}' ] || fail parser_mismatch
# Supply INVALID command to the HTTPS binary to test its shared library loader.
# The quota command is NEVER invoked: no accidental operator connection or token access.
if "$http" --invalid-no-network > "$dir/http.out" 2> "$dir/http.err"; then
  fail http_must_reject_invalid_command
fi
grep -qx 'usage: veci-xl-quota-http quota' "$dir/http.err" || fail dynamic_http_loader_unavailable
[ ! -s "$dir/http.out" ] || fail unexpected_http_output
printf 'VECI_XL_COMPACT_RUNTIME_MIPS_ABI=pass\n'
printf 'VECI_XL_COMPACT_RUNTIME_SHA256=pass\n'
printf 'VECI_XL_COMPACT_CRYPTO_ROUNDTRIP=pass\n'
printf 'VECI_XL_COMPACT_QUOTA_PARSER=pass\n'
printf 'VECI_XL_COMPACT_HTTP_LOADER=pass\n'
printf 'VECI_REAL_OPERATOR_LOGIN=not_attempted\n'
printf 'VECI_OPERATOR_QUOTA=not_verified\n'
printf 'VECI_MODEM_AND_SMS_UNCHANGED=true\n'
printf 'VECI_FLASH_WRITES=none\n'
