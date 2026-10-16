#!/bin/sh
# Resume FINAL verification after veci-ussd-remove stopped at sms_lost.
# Never touches modem, LTE, SMS content, quota API, or apk database.
set -eu
umask 077
PATH=/usr/sbin:/usr/bin:/sbin:/bin
export PATH
fail(){ echo VECI_USSD_RECONCILE=blocked; echo "VECI_USSD_REASON=$1"; exit 1; }
[ "$#" -eq 1 ] || fail usage
case "$1" in --status|--recover) MODE="$1";; *)fail usage;; esac
[ "$(id -u)" -eq 0 ] || fail root_required
[ "$(cat /tmp/sysinfo/board_name 2>/dev/null || :)" = zbtlink,zbt-we5927 ] || fail wrong_board
grep -qx "DISTRIB_RELEASE='25.12.5'" /etc/openwrt_release || fail wrong_firmware
for prog in apk grep ubus sleep; do command -v "$prog" >/dev/null 2>&1 || fail missing_tool; done
registered(){ ubus -S list "$1" 2>/dev/null | grep -qx "$1"; }
pkg(){ apk list -I 2>/dev/null | grep -q '^veci-ussd-dialer-[0-9]'; }
status(){
 if registered veci.sms; then echo VECI_SMS_RPC=present; else echo VECI_SMS_RPC=missing; fi
 if registered veci.quota; then echo VECI_QUOTA_RPC=present; else echo VECI_QUOTA_RPC=missing; fi
 if registered veci.xl; then echo VECI_XL_RPC=present; else echo VECI_XL_RPC=missing; fi
 if registered veci.ussd; then echo VECI_USSD_RPC=present; else echo VECI_USSD_RPC=absent; fi
 if [ -x /usr/libexec/rpcd/veci.sms ]; then echo VECI_SMS_EXEC=present; else echo VECI_SMS_EXEC=missing; fi
 if [ -x /usr/libexec/rpcd/veci.quota ]; then echo VECI_QUOTA_EXEC=present; else echo VECI_QUOTA_EXEC=missing; fi
 if [ -x /usr/libexec/rpcd/veci.xl ]; then echo VECI_XL_EXEC=present; else echo VECI_XL_EXEC=missing; fi
 if pkg; then echo VECI_USSD_PACKAGE=installed; else echo VECI_USSD_PACKAGE=absent; fi
 if [ -e /usr/libexec/rpcd/veci.ussd ]; then echo VECI_USSD_RPC_FILE=present; else echo VECI_USSD_RPC_FILE=absent; fi
 if [ -e /www/veci/js/pages/cellular.js ] && grep -q 'veci.ussd' /www/veci/js/pages/cellular.js; then echo VECI_USSD_UI=present; else echo VECI_USSD_UI=absent; fi
 if [ -f /tmp/veci-ussd-removal-20261016/cellular.js ]; then echo VECI_USSD_BACKUP=present; else echo VECI_USSD_BACKUP=missing; fi
}
ready(){
 registered veci.sms && registered veci.quota && registered veci.xl && ! registered veci.ussd
}
[ "$MODE" = --status ] && { status; exit 0; }
# The previous --apply already changed only VeCI USSD assets. Do not rerun it.
[ -x /usr/libexec/rpcd/veci.sms ] || fail sms_executable_missing
[ -x /usr/libexec/rpcd/veci.quota ] || fail quota_executable_missing
[ -x /usr/libexec/rpcd/veci.xl ] || fail xl_executable_missing
[ -x /usr/sbin/we5927-lte ] || fail modem_control_missing
[ -f /www/veci/js/pages/cellular.js ] || fail veci_ui_missing
[ -f /tmp/veci-ussd-removal-20261016/cellular.js ] || fail backup_missing
[ ! -e /usr/libexec/rpcd/veci.ussd ] || fail ussd_rpc_file_present
[ ! -e /usr/libexec/veci-xl-ussd ] || fail ussd_worker_present
[ ! -e /usr/libexec/veci-xl-ussd-once ] || fail ussd_native_present
! pkg || fail ussd_package_installed
! grep -q 'veci.ussd' /www/veci/js/pages/cellular.js || fail ussd_ui_still_present
# rpcd exec registration is asynchronous following service restart.
attempt=0
while [ "$attempt" -lt 12 ]; do
 if ready; then
  echo VECI_USSD_RECONCILE=pass
  echo VECI_SMS_PRESERVED=true
  echo VECI_QUOTA_PRESERVED=true
  echo VECI_LTE_NOT_TOUCHED=true
  status
  exit 0
 fi
 sleep 1
 attempt=$((attempt+1))
done
# One bounded rpcd-only recovery, not a modem/network restart.
[ -x /etc/init.d/rpcd ] || fail rpcd_service_missing
echo VECI_RPCD_RECOVERY=restart_once
/etc/init.d/rpcd restart >/dev/null 2>&1 || fail rpcd_restart_failed
attempt=0
while [ "$attempt" -lt 20 ]; do
 if ready; then
  echo VECI_USSD_RECONCILE=pass
  echo VECI_SMS_PRESERVED=true
  echo VECI_QUOTA_PRESERVED=true
  echo VECI_LTE_NOT_TOUCHED=true
  status
  exit 0
 fi
 sleep 1
 attempt=$((attempt+1))
done
status
fail rpc_registration_not_recovered
