#!/bin/sh
# WE5927 VeCI TLS certificate read-only inspection. Never exports private key.
set -eu
PATH=/usr/sbin:/usr/bin:/sbin:/bin; export PATH
fail(){ echo "VECI_TLS_AUDIT=blocked"; echo "VECI_TLS_REASON=$1"; exit 1; }
[ "${1:-}" = --status ] && [ "$#" -eq 1 ] || fail usage
[ "$(id -u)" = 0 ] || fail root_required
[ "$(cat /tmp/sysinfo/board_name 2>/dev/null || :)" = zbtlink,zbt-we5927 ] || fail wrong_router
[ -z "$(uci -q get uhttpd.main.listen_http 2>/dev/null || :)" ] || fail http_still_enabled
[ -n "$(uci -q get uhttpd.main.listen_https 2>/dev/null || :)" ] || fail https_missing
cert="$(uci -q get uhttpd.main.cert 2>/dev/null || :)"
key="$(uci -q get uhttpd.main.key 2>/dev/null || :)"
[ -n "$cert" ] && [ -n "$key" ] || fail tls_paths_missing
[ -f "$cert" ] && [ ! -L "$cert" ] && [ -s "$cert" ] || fail certificate_missing
[ -f "$key" ] && [ ! -L "$key" ] && [ -s "$key" ] || fail key_missing
echo VECI_TLS_HTTPS_ONLY=pass
if command -v openssl >/dev/null 2>&1; then
 echo VECI_TLS_OPENSSL=available
 openssl x509 -in "$cert" -noout -dates 2>/dev/null |
  sed 's/^notBefore=/VECI_TLS_NOT_BEFORE=/;s/^notAfter=/VECI_TLS_NOT_AFTER=/'
 if openssl x509 -in "$cert" -noout -ext subjectAltName >/tmp/veci-tls-san-check.$$ 2>/dev/null; then
  if grep -Eq 'IP Address:192\.168\.1\.1' /tmp/veci-tls-san-check.$$; then
   echo VECI_TLS_IP_SAN=present
  else
   echo VECI_TLS_IP_SAN=missing
  fi
 else echo VECI_TLS_IP_SAN=unknown; fi
 rm -f /tmp/veci-tls-san-check.$$
 if openssl verify -CAfile "$cert" "$cert" >/dev/null 2>&1; then
  echo VECI_TLS_SELF_SIGNED_OR_SELF_TRUSTED=possible
 else
  echo VECI_TLS_SELF_SIGNED_OR_SELF_TRUSTED=not_confirmed
 fi
else
 echo VECI_TLS_OPENSSL=unavailable
 echo VECI_TLS_IP_SAN=unknown
fi
echo VECI_TLS_PRIVATE_KEY_EXPORTED=false
echo VECI_TLS_CONFIG_CHANGED=false
echo VECI_TLS_AUDIT=pass
