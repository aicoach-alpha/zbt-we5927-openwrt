#!/bin/sh
# VeCI XL quota v7: one targeted backend change, backup + rollback.
set -eu
umask 077
RPC=/usr/libexec/rpcd/veci.quota
GATE=/usr/libexec/veci-xl-quota-session-gate
BACKUP=/tmp/veci-quota-rpc-before-v7-20261019.sh
TMP=/tmp/veci-xl-gate-v7.$$
NEW=/tmp/veci-quota-rpc-v7.$$
URL=https://raw.githubusercontent.com/aicoach-alpha/zbt-we5927-openwrt/f24ca6bf2b7b1ed6b927cf7c5667bad2a1dbac4f/scripts/veci-xl-quota-session-gate-v7-20261019.sh
fail(){ echo "XL_V7=$1"; exit 1; }
trap 'rm -f "$TMP" "$NEW"' EXIT
[ "$(id -u)" = 0 ] || fail root_required
[ -f "$RPC" ] && [ ! -L "$RPC" ] && [ -x "$RPC" ] || fail rpc_missing
[ ! -e "$GATE" ] && [ ! -L "$GATE" ] || fail already_installed
ANCHOR='/usr/libexec/veci-quota-cache status /tmp/veci-telco/quota-xl.json'
[ "$(grep -Fc "$ANCHOR" "$RPC")" -eq 1 ] || fail rpc_anchor_missing
wget -qO "$TMP" "$URL" || fail download_failed
sh -n "$TMP" || fail gate_syntax_failed
grep -Fq 'safe_root_file "$ROOT/$name"' "$TMP" || fail session_guard_missing
grep -Fq '[ "$(field source)" = operator ]' "$TMP" || fail origin_guard_missing
sed 's@/usr/libexec/veci-quota-cache status /tmp/veci-telco/quota-xl.json@/usr/libexec/veci-xl-quota-session-gate --status@' "$RPC" > "$NEW"
sh -n "$NEW" || fail rpc_syntax_failed
grep -Fq "$GATE --status" "$NEW" || fail rpc_patch_failed
cp -p "$RPC" "$BACKUP" || fail backup_failed
rollback(){
 cp "$BACKUP" "$RPC" && chmod 755 "$RPC" || :
 rm -f "$GATE"
 /etc/init.d/rpcd restart >/dev/null 2>&1 || :
}
if ! {
 cp "$TMP" "$GATE" && chmod 700 "$GATE" &&
 cp "$NEW" "$RPC" && chmod 755 "$RPC" &&
 /etc/init.d/rpcd restart >/dev/null 2>&1
}; then
 rollback
 fail apply_failed_rolled_back
fi
sleep 5
RESP="$(ubus -S call veci.quota status 2>/dev/null)" || {
 rollback
 fail integrity_rpc_failed_rolled_back
}
if ! printf '%s\n' "$RESP" | grep -Fq '"remaining_bytes":null'; then
 rollback
 fail integrity_balance_guard_failed_rolled_back
fi
if ! printf '%s\n' "$RESP" | grep -Fq '"buckets":[]'; then
 rollback
 fail integrity_buckets_guard_failed_rolled_back
fi
echo XL_V7=installed
echo XL_V7_INTEGRITY=pass
echo XL_V7_BACKUP="$BACKUP"
