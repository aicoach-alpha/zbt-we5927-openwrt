#!/bin/sh
# Read-only backend gate for the native XL quota cache.
# Rejects cached balances after logout, expiry, or invalid provenance.
set -eu
umask 077
ROOT=/tmp/veci-telco-private
CACHE=/tmp/veci-telco/quota-xl.json
PARSER=/usr/libexec/veci-quota-cache
JSONFILTER=/usr/bin/jsonfilter

unavailable() {
  # Intentionally never emit cached balances when no valid subscriber session.
  printf '{"schema":1,"provider":"xl","state":"%s","total_bytes":null,"remaining_bytes":null,"used_bytes":null,"expires_at":null,"fetched_at":null,"source":null,"buckets":[]}\n' "$1"
  exit 0
}
numeric() {
 case "$1" in ''|*[!0-9]*) return 1 ;; esac
 [ "${#1}" -le 13 ]
}
safe_root_dir() {
 [ -d "$1" ] && [ ! -L "$1" ] &&
 [ "$(ls -ldn "$1" | awk '{print $1 " " $3}')" = "drwx------ 0" ]
}
safe_root_file() {
 [ -f "$1" ] && [ ! -L "$1" ] &&
 [ "$(ls -ldn "$1" | awk '{print $1 " " $3}')" = "-rw------- 0" ]
}
[ "$#" -eq 1 ] && [ "$1" = --status ] || unavailable unavailable
[ "$(id -u)" -eq 0 ] || unavailable unavailable
safe_root_dir "$ROOT" || unavailable not_connected
for name in id_token access_token refresh_token verified_number verified_epoch; do
 safe_root_file "$ROOT/$name" || unavailable not_connected
done
epoch="$(cat "$ROOT/verified_epoch" 2>/dev/null)" || unavailable not_connected
now="$(date +%s)"
numeric "$epoch" && numeric "$now" || unavailable unavailable
[ "$now" -ge "$epoch" ] || unavailable unavailable
[ $((now-epoch)) -le 1800 ] || unavailable stale
safe_root_file "$CACHE" || unavailable unavailable
[ -x "$PARSER" ] && [ -x "$JSONFILTER" ] || unavailable unavailable
size="$(wc -c < "$CACHE" | tr -d '[:space:]')"
numeric "$size" && [ "$size" -gt 0 ] && [ "$size" -le 32768 ] || unavailable unavailable
modified="$(stat -c %Y "$CACHE" 2>/dev/null)" || unavailable unavailable
numeric "$modified" && [ "$now" -ge "$modified" ] || unavailable unavailable
[ $((now-modified)) -le 1800 ] || unavailable stale
payload="$("$PARSER" status "$CACHE" 2>/dev/null)" || unavailable unavailable
[ "${#payload}" -le 32768 ] || unavailable unavailable
field() { printf '%s\n' "$payload" | "$JSONFILTER" -e "@.$1" 2>/dev/null; }
[ "$(field provider)" = xl ] || unavailable unavailable
[ "$(field state)" = ok ] || unavailable unavailable
[ "$(field source)" = operator ] || unavailable unavailable
fetched="$(field fetched_at)" || unavailable unavailable
[ -n "$fetched" ] && [ "$fetched" != null ] || unavailable unavailable
remaining="$(field 'buckets[0].remaining_bytes')" || unavailable unavailable
numeric "$remaining" || unavailable unavailable
printf '%s\n' "$payload"
