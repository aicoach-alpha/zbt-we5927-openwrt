#!/bin/sh
# Read-only VeCI XL core source export on the authorized WE5927.
# Excludes credentials, private session state and subscriber data.
set -eu
umask 077
OUT=/tmp/veci-xl-core-source-20261020.tar.gz
XL=usr/libexec/rpcd/veci.xl
QUOTA=usr/libexec/rpcd/veci.quota
ACL=usr/share/rpcd/acl.d/veci-xl-owner.json
CLEAR=usr/libexec/veci-xl-session-clear
fail(){ echo "XL_CORE_EXPORT=$1"; exit 1; }
[ "$(id -u)" = 0 ] || fail root_required
[ ! -e "$OUT" ] && [ ! -L "$OUT" ] || fail archive_already_exists
for item in "$XL" "$QUOTA" "$ACL" "$CLEAR"; do
 [ -f "/$item" ] && [ ! -L "/$item" ] || fail prerequisite_missing
done
grep -Fq 'logout) logout_local ;;' "/$XL" || fail logout_handler_missing
grep -Fq '/usr/libexec/veci-xl-quota-session-gate --status' "/$QUOTA" || fail quota_gate_missing
grep -Fq '"logout"' "/$ACL" || fail owner_acl_missing
[ -x /usr/bin/jsonfilter ] || fail jsonfilter_missing
/usr/bin/jsonfilter -i "/$ACL" -e '@' >/dev/null || fail invalid_owner_acl_json
# No sessions, provider app secrets, customer numbers, OTPs, caches or keys.
tar -czf "$OUT" -C / "$XL" "$QUOTA" "$ACL" "$CLEAR" || {
 rm -f "$OUT"
 fail archive_failed
}
chmod 600 "$OUT" || {
 rm -f "$OUT"
 fail chmod_failed
}
size="$(wc -c < "$OUT" | tr -d '[:space:]')"
case "$size" in ''|*[!0-9]*) rm -f "$OUT"; fail size_invalid ;; esac
[ "$size" -gt 200 ] && [ "$size" -le 131072 ] || {
 rm -f "$OUT"
 fail archive_size_out_of_bounds
}
echo XL_CORE_EXPORT=ready
echo XL_CORE_ARCHIVE="$OUT"
echo XL_CORE_SHA256="$(sha256sum "$OUT" | cut -d ' ' -f 1)"
echo XL_CORE_BYTES="$size"
echo XL_CORE_CONTENT=rpc_xl_rpc_quota_owner_acl_local_logout
echo XL_CORE_CUSTOMER_DATA=excluded
