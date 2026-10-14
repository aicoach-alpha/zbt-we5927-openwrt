#!/bin/sh
# VeCI XL: one direct TLS identity probe from /tmp, NO login or quota.
# Install footprint = 0 bytes; no modem, SMS, OTP, token or flash writes.
set -eu
umask 077
LC_ALL=C
export LC_ALL
SHA="42e871e74329ca1ba6d0f5d58c8ebf6b5e0259d442387341b50d6271adb59ba6"
URL="https://github.com/aicoach-alpha/zbt-we5927-openwrt/releases/download/veci-xl-tls-probe-4dee809bd872/veci-xl-tls-probe-mipsel"
fail(){ printf 'VECI_XL_TLS_PROBE_ERROR=%s\n' "$1" >&2; exit 1; }
[ "$#" -eq 1 ] && [ "$1" = --probe-api ] || fail usage
[ "$(cat /tmp/sysinfo/board_name 2>/dev/null || :)" = "zbtlink,zbt-we5927" ] || fail wrong_router
for command_name in wget sha256sum awk mktemp chmod wc; do
  command -v "$command_name" >/dev/null 2>&1 || fail missing_dependency
done
work="$(mktemp -d /tmp/veci-xl-tls.XXXXXX)" || fail temp_unavailable
trap 'rm -rf "$work"' EXIT
trap 'exit 130' INT TERM
binary="$work/veci-xl-tls-probe"
wget -qO "$binary" "$URL" || fail download_failed
[ "$(wc -c < "$binary" | tr -d '[:space:]')" -eq 540588 ] || fail size_mismatch
[ "$(sha256sum "$binary" | awk '{print $1}')" = "$SHA" ] || fail sha256_mismatch
chmod 700 "$binary" || fail chmod_failed
"$binary" api || fail tls_identity_unverified
printf 'VECI_XL_NATIVE_TLS_MIPS_SHA256=pass\n'
printf 'VECI_XL_AUTHENTICATED_QUOTA_CLIENT=not_implemented\n'
