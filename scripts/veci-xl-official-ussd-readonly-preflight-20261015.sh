#!/bin/sh
# Physical WE5927: read-only inspection of existing VeCI XL USSD route.
# NO calls to start/reply/cancel, no modem AT, SMS, CLI secrets, firmware changes.
set -eu
PATH=/usr/sbin:/usr/bin:/sbin:/bin
LC_ALL=C
export PATH LC_ALL
fail(){ printf 'VECI_XL_USSD_PREFLIGHT=blocked\nVECI_XL_USSD_REASON=%s\n' "$1"; exit 1; }
[ "$#" -eq 1 ] && [ "$1" = --status ] || fail invalid_mode
[ "$(id -u)" -eq 0 ] || fail root_required
[ "$(cat /tmp/sysinfo/board_name 2>/dev/null || :)" = 'zbtlink,zbt-we5927' ] || fail wrong_router
grep -qx "DISTRIB_RELEASE='25.12.5'" /etc/openwrt_release || fail firmware_mismatch
command -v ubus >/dev/null 2>&1 || fail ubus_missing
if ubus -S list veci.ussd 2>/dev/null | grep -qx 'veci.ussd'; then
 echo VECI_XL_USSD_RPC=registered
 methods="$(ubus -S -v list veci.ussd 2>/dev/null || :)"
 case "$methods" in
  *'"start"'*'"reply"'*'"cancel"'*) echo VECI_XL_USSD_INTERACTIVE_METHODS=present ;;
  *) echo VECI_XL_USSD_INTERACTIVE_METHODS=incomplete ;;
 esac
 case "$methods" in
  *'"quotaStatus"'*) echo VECI_XL_USSD_CACHED_QUOTA_METHOD=present ;;
  *) echo VECI_XL_USSD_CACHED_QUOTA_METHOD=missing ;;
 esac
else
 echo VECI_XL_USSD_RPC=not_registered
 echo VECI_XL_USSD_INTERACTIVE_METHODS=unavailable
 echo VECI_XL_USSD_CACHED_QUOTA_METHOD=unavailable
fi
if [ -x /usr/libexec/veci-xl-ussd-once ]; then
 echo VECI_XL_USSD_NATIVE=installed
else
 echo VECI_XL_USSD_NATIVE=not_installed
fi
if [ -x /usr/libexec/veci-xl-quota-cache ]; then
 echo VECI_XL_USSD_CACHE=installed
else
 echo VECI_XL_USSD_CACHE=not_installed
fi
if [ -f /usr/share/rpcd/acl.d/veci-xl-ussd.json ] &&
   [ ! -L /usr/share/rpcd/acl.d/veci-xl-ussd.json ]; then
 echo VECI_XL_USSD_ACL=present
else
 echo VECI_XL_USSD_ACL=not_installed
fi
if ubus -S list veci.xl 2>/dev/null | grep -qx 'veci.xl'; then
 echo VECI_XL_037_RPC=registered
else
 echo VECI_XL_037_RPC=not_registered
fi
if [ -z "$(uci -q get uhttpd.main.listen_http 2>/dev/null || :)" ] &&
 [ -n "$(uci -q get uhttpd.main.listen_https 2>/dev/null || :)" ]; then
 echo VECI_HTTPS_ONLY=pass
else
 echo VECI_HTTPS_ONLY=not_confirmed
fi
echo VECI_XL_USSD_OPERATOR_REQUEST_SENT=false
echo VECI_XL_USSD_MODEM_SMS_CHANGED=false
echo VECI_XL_USSD_PREFLIGHT=pass
