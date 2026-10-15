#!/bin/sh
# Read-only failed XL *808# root-cause preflight; does NOT transmit a USSD.
set -eu
LC_ALL=C
PATH=/usr/sbin:/usr/bin:/sbin:/bin
export LC_ALL PATH
fail(){ printf 'VECI_XL_USSD_DIAG=blocked\nVECI_XL_USSD_DIAG_REASON=%s\n' "$1"; exit 1; }
[ "$#" -eq 1 ] && [ "$1" = --status ] || fail invalid_mode
[ "$(id -u)" -eq 0 ] || fail root_required
[ "$(cat /tmp/sysinfo/board_name 2>/dev/null || :)" = 'zbtlink,zbt-we5927' ] || fail wrong_router
grep -qx "DISTRIB_RELEASE='25.12.5'" /etc/openwrt_release || fail wrong_firmware
if ubus -S list veci.ussd 2>/dev/null | grep -qx 'veci.ussd'; then
 echo VECI_XL_USSD_RPC=registered
else
 echo VECI_XL_USSD_RPC=not_registered
fi
plugin=/usr/libexec/rpcd/veci.ussd
worker=/usr/libexec/veci-xl-ussd
native=/usr/libexec/veci-xl-ussd-once
for item in "$plugin" "$worker" "$native"; do
 name=RPC
 [ "$item" = "$worker" ] && name=WORKER
 [ "$item" = "$native" ] && name=NATIVE
 if [ -f "$item" ] && [ ! -L "$item" ] && [ -x "$item" ]; then
  printf 'VECI_XL_USSD_%s_EXECUTABLE=pass\n' "$name"
 else
  printf 'VECI_XL_USSD_%s_EXECUTABLE=missing\n' "$name"
 fi
done
if [ -x "$plugin" ]; then
 methods="$("$plugin" list 2>/dev/null || :)"
 for method in start reply cancel quotaStatus; do
  case "$methods" in
   *"\"$method\""*) printf 'VECI_XL_USSD_METHOD_%s=present\n' "$method" ;;
   *) printf 'VECI_XL_USSD_METHOD_%s=missing\n' "$method" ;;
  esac
 done
fi
for item in flock jsonfilter sha256sum readlink dirname head date; do
 if command -v "$item" >/dev/null 2>&1; then
  printf 'VECI_XL_USSD_DEP_%s=present\n' "$item"
 else
  printf 'VECI_XL_USSD_DEP_%s=missing\n' "$item"
 fi
done
if [ -c /dev/ttyUSB2 ]; then
 echo VECI_XL_USSD_SERIAL=present
else
 echo VECI_XL_USSD_SERIAL=missing
fi
port="$(readlink -f /sys/class/tty/ttyUSB2/device 2>/dev/null || :)"
case "$port" in
 /sys/devices/*:1.4/ttyUSB2) echo VECI_XL_USSD_PORT_PATH=expected ;;
 '') echo VECI_XL_USSD_PORT_PATH=unavailable ;;
 *) echo VECI_XL_USSD_PORT_PATH=not_matching_current_guard ;;
esac
if [ -n "$port" ]; then
 parent="$(dirname "$(dirname "$port")")"
 vid="$(cat "$parent/idVendor" 2>/dev/null || :)"
 pid="$(cat "$parent/idProduct" 2>/dev/null || :)"
 if [ "$vid" = 05c6 ] && [ "$pid" = 902e ]; then
  echo VECI_XL_USSD_USB_ID=expected
 else
  echo VECI_XL_USSD_USB_ID=not_matching_current_guard
 fi
fi
if [ -x /usr/sbin/we5927-lte ] && command -v jsonfilter >/dev/null 2>&1; then
 info="$(/usr/sbin/we5927-lte status-fast 2>/dev/null || :)"
 if [ -n "$info" ] && [ "$(printf %s "$info" | wc -c)" -le 2500 ]; then
  sim="$(printf %s "$info" | jsonfilter -e '@.sim' 2>/dev/null || :)"
  op="$(printf %s "$info" | jsonfilter -e '@.operator' 2>/dev/null || :)"
  case "$sim" in 1|2) echo VECI_XL_USSD_SIM=valid ;;
    *) echo VECI_XL_USSD_SIM=missing_or_invalid ;; esac
  case "$op" in
   XL|XL\ *|*XL\ Axiata*|*XL\ SMART*|*XL\ AXIATA*)
    echo VECI_XL_USSD_OPERATOR_GUARD=pass ;;
   '') echo VECI_XL_USSD_OPERATOR_GUARD=empty ;;
   *) echo VECI_XL_USSD_OPERATOR_GUARD=rejects_current_label ;;
  esac
 else
  echo VECI_XL_USSD_LTE_STATUS=unavailable
 fi
else
 echo VECI_XL_USSD_LTE_STATUS=unavailable
fi
if [ -f /tmp/veci-xl-ussd.session ]; then
 echo VECI_XL_USSD_PRIOR_SESSION=present
else
 echo VECI_XL_USSD_PRIOR_SESSION=absent
fi
echo VECI_XL_USSD_OPERATOR_REQUEST_SENT=false
echo VECI_XL_USSD_MODEM_CHANGED=false
echo VECI_XL_USSD_DIAG=pass
