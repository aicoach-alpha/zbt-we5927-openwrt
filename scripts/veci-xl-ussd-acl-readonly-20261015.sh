#!/bin/sh
# WE5927 VeCI USSD ACL diagnosis. Read only. NO USSD/OTP/modem requests.
set -eu
LC_ALL=C; PATH=/usr/sbin:/usr/bin:/sbin:/bin; export LC_ALL PATH
[ "$#" = 1 ] && [ "$1" = --status ] || exit 2
[ "$(id -u)" = 0 ] || exit 2
[ "$(cat /tmp/sysinfo/board_name 2>/dev/null || :)" = zbtlink,zbt-we5927 ] || exit 2
f=/usr/share/rpcd/acl.d/veci-xl-ussd.json
if [ -f "$f" ] && [ ! -L "$f" ]; then
 echo VECI_USSD_ACL_FILE=present
 if grep -q '"veci.ussd"' "$f" && grep -q '"start"' "$f"; then
  echo VECI_USSD_ACL_START_DECLARED=yes
 else echo VECI_USSD_ACL_START_DECLARED=no; fi
 if grep -q '"quotaStatus"' "$f"; then
  echo VECI_USSD_ACL_QUOTA_DECLARED=yes
 else echo VECI_USSD_ACL_QUOTA_DECLARED=no; fi
else echo VECI_USSD_ACL_FILE=missing; fi
# The following checks inspect only ACL declarations, NOT session tokens.
for f in /usr/share/rpcd/acl.d/*.json; do
 [ -f "$f" ] && [ ! -L "$f" ] || continue
 if grep -q '"veci.ussd"' "$f"; then
  echo VECI_USSD_ACL_SOURCE="$(basename "$f")"
 fi
done
if ubus -S list session 2>/dev/null | grep -qx 'session'; then
 echo VECI_UBUS_SESSION_OBJECT=registered
else echo VECI_UBUS_SESSION_OBJECT=not_found; fi
if ubus -S list veci.ussd 2>/dev/null | grep -qx 'veci.ussd'; then
 echo VECI_USSD_RPC=registered
else echo VECI_USSD_RPC=not_registered; fi
echo VECI_USSD_REQUEST_SENT=false
echo VECI_MODEM_CHANGED=false
echo VECI_USSD_ACL_READONLY=pass
