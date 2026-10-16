#!/bin/sh
# Read-only HTTPS certificate diagnosis, physical WE5927 only.
# No certificate/private-key copying, no uhttpd restart and no config changes.
set -eu
umask 077
LC_ALL=C
PATH=/usr/sbin:/usr/bin:/sbin:/bin
export LC_ALL PATH
stop(){ echo VECI_HTTPS_CERT_AUDIT=blocked; printf 'VECI_HTTPS_CERT_REASON=%s\n' "$1"; exit 1; }
[ "$#" -eq 1 ] && [ "$1" = --status ] || stop invalid_mode
[ "$(id -u)" = 0 ] || stop root_required
[ "$(cat /tmp/sysinfo/board_name 2>/dev/null || :)" = 'zbtlink,zbt-we5927' ] || stop wrong_router
grep -qx "DISTRIB_RELEASE='25.12.5'" /etc/openwrt_release || stop wrong_firmware
[ -z "$(uci -q get uhttpd.main.listen_http 2>/dev/null || :)" ] || stop http_listener_enabled
https="$(uci -q get uhttpd.main.listen_https 2>/dev/null || :)"
[ -n "$https" ] || stop https_listener_missing
cert="$(uci -q get uhttpd.main.cert 2>/dev/null || :)"
key="$(uci -q get uhttpd.main.key 2>/dev/null || :)"
[ -n "$cert" ] && [ -n "$key" ] || stop tls_paths_missing
[ -f "$cert" ] && [ ! -L "$cert" ] && [ -r "$cert" ] || stop cert_not_readable
[ -f "$key" ] && [ ! -L "$key" ] || stop key_missing
echo VECI_HTTPS_LISTENER=https_only
echo VECI_HTTPS_CERT_FILE=present
echo VECI_HTTPS_KEY_FILE=present_not_exported
if command -v openssl >/dev/null 2>&1; then
  # Inspect public cert only. Accept either PEM or DER.
  format=PEM
  if ! openssl x509 -in "$cert" -noout >/dev/null 2>&1; then format=DER; fi
  if ! openssl x509 -inform "$format" -in "$cert" -noout >/dev/null 2>&1; then
    echo VECI_HTTPS_CERT_FORMAT=unrecognized
  else
    echo VECI_HTTPS_CERT_FORMAT="$format"
    if openssl x509 -inform "$format" -in "$cert" -noout -checkend 0 >/dev/null 2>&1; then
      echo VECI_HTTPS_CERT_DATE=currently_valid
    else
      echo VECI_HTTPS_CERT_DATE=expired_or_not_yet_valid
    fi
    if openssl x509 -inform "$format" -in "$cert" -noout -ext subjectAltName 2>/dev/null |
       grep -Eq 'IP Address:192[.]168[.]1[.]1([^0-9]|$)'; then
      echo VECI_HTTPS_CERT_SAN_PRIVATE_IP=present
    else
      echo VECI_HTTPS_CERT_SAN_PRIVATE_IP=not_found
    fi
    subject="$(openssl x509 -inform "$format" -in "$cert" -noout -subject -nameopt RFC2253 2>/dev/null | sed 's/^subject=//')"
    issuer="$(openssl x509 -inform "$format" -in "$cert" -noout -issuer -nameopt RFC2253 2>/dev/null | sed 's/^issuer=//')"
    if [ -n "$subject" ] && [ "$subject" = "$issuer" ]; then
      echo VECI_HTTPS_CERT_ISSUER=self_issued
    else
      echo VECI_HTTPS_CERT_ISSUER=external_or_unknown
    fi
  fi
else
  echo VECI_HTTPS_CERT_INSPECTION=openssl_unavailable
fi
echo VECI_HTTPS_BROWSER_TRUST=not_checked_from_router
echo VECI_HTTPS_PRIVATE_KEY_EXPORTED=false
echo VECI_HTTPS_CHANGES_MADE=false
echo VECI_HTTPS_CERT_AUDIT=pass
