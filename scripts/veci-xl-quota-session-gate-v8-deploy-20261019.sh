#!/bin/sh
# VeCI XL v8: upgrade only the existing backend session gate.
# No rpcd restart, modem change, SMS, USSD, LuCI, or OTP.
set -eu
umask 077
GATE=/usr/libexec/veci-xl-quota-session-gate
RPC=/usr/libexec/rpcd/veci.quota
BACKUP=/tmp/veci-xl-gate-before-v8-20261019.sh
TMP=/tmp/veci-xl-gate-v8.$$
NEXT=/usr/libexec/veci-xl-quota-session-gate.next.$$
URL=https://raw.githubusercontent.com/aicoach-alpha/zbt-we5927-openwrt/addaa6f3d53ace2812fe6528c4aa8bd9a19b6d9e/scripts/veci-xl-quota-session-gate-v8-20261019.sh
fail(){ echo "XL_V8=$1"; exit 1; }
trap 'rm -f "$TMP" "$NEXT"' EXIT
[ "$(id -u)" = 0 ] || fail root_required
[ -f "$GATE" ] && [ ! -L "$GATE" ] && [ -x "$GATE" ] || fail v7_gate_missing
[ -f "$RPC" ] && [ ! -L "$RPC" ] || fail rpc_missing
grep -Fq '/usr/libexec/veci-xl-quota-session-gate --status' "$RPC" || fail rpc_not_using_gate
grep -Fq '[ $((now-modified)) -le 1800 ] || unavailable stale' "$GATE" || fail unexpected_v7_baseline
wget -qO "$TMP" "$URL" || fail download_failed
sh -n "$TMP" || fail syntax_failed
grep -Fq '[ "$modified" -ge "$epoch" ] || unavailable stale' "$TMP" || fail session_order_guard_missing
grep -Fq '[ "$(field source)" = operator ]' "$TMP" || fail carrier_source_guard_missing
cp -p "$GATE" "$BACKUP" || fail backup_failed
cp "$TMP" "$NEXT" && chmod 700 "$NEXT" || fail prepare_failed
mv -f "$NEXT" "$GATE" || fail activate_failed
RESP="$(ubus -S call veci.quota status 2>/dev/null)" || {
 cp -p "$BACKUP" "$GATE" || :
 fail integrity_failed_rolled_back
}
if ! printf '%s\n' "$RESP" | grep -Fq '"remaining_bytes":null'; then
 cp -p "$BACKUP" "$GATE" || :
 fail balance_guard_failed_rolled_back
fi
if ! printf '%s\n' "$RESP" | grep -Fq '"buckets":[]'; then
 cp -p "$BACKUP" "$GATE" || :
 fail buckets_guard_failed_rolled_back
fi
echo XL_V8=installed
echo XL_V8_INTEGRITY=pass
echo XL_V8_CACHE_SESSION_ORDER=enabled
echo XL_V8_BACKUP="$BACKUP"
