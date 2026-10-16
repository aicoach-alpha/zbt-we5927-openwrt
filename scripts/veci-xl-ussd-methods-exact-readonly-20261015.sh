#!/bin/sh
# Read-only, order-independent XL USSD rpcd method inspection on owner's WE5927.
# This file does not call any USSD method or modem and does not print account data.
set -eu
LC_ALL=C
PATH=/usr/sbin:/usr/bin:/sbin:/bin
export LC_ALL PATH
fail(){ printf 'VECI_XL_USSD_METHODS=blocked\nVECI_XL_USSD_REASON=%s\n' "$1"; exit 1; }
[ "$#" -eq 1 ] && [ "$1" = --status ] || fail invalid_mode
[ "$(id -u)" -eq 0 ] || fail root_required
[ "$(cat /tmp/sysinfo/board_name 2>/dev/null || :)" = zbtlink,zbt-we5927 ] || fail wrong_router
grep -qx "DISTRIB_RELEASE='25.12.5'" /etc/openwrt_release || fail wrong_firmware
command -v ubus >/dev/null 2>&1 || fail ubus_missing
if ! ubus -S list veci.ussd 2>/dev/null | grep -qx 'veci.ussd'; then
 echo VECI_XL_USSD_RPC=not_registered
 echo VECI_XL_USSD_METHODS=unavailable
 exit 0
fi
echo VECI_XL_USSD_RPC=registered
# ubus -v method serialization and method order may vary among versions.
# Read the locally installed rpcd plugin's declarative "list" action only.
plugin=/usr/libexec/rpcd/veci.ussd
[ -f "$plugin" ] && [ ! -L "$plugin" ] && [ -x "$plugin" ] ||
 fail rpc_exec_missing_or_unsafe
methods="$( "$plugin" list 2>/dev/null || : )"
[ "$(printf '%s' "$methods" | wc -c)" -le 1400 ] && [ -n "$methods" ] || fail rpc_method_manifest_invalid
case "$methods" in
 '{'*'}') ;;
 *) fail rpc_method_manifest_invalid ;;
esac
ok=1
for method in start reply cancel quotaStatus; do
 case "$methods" in
  *"\"$method\""*)
   printf 'VECI_XL_USSD_METHOD_%s=present\n' "$method" ;;
  *)
   printf 'VECI_XL_USSD_METHOD_%s=missing\n' "$method"
   ok=0 ;;
 esac
done
if [ "$ok" = 1 ]; then
 echo VECI_XL_USSD_METHODS=pass
else
 echo VECI_XL_USSD_METHODS=incomplete
fi
echo VECI_XL_USSD_OPERATOR_REQUEST_SENT=false
echo VECI_XL_USSD_MODEM_UNCHANGED=true
