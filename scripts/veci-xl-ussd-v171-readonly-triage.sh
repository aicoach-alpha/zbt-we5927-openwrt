#!/bin/sh
# VeCI XL USSD v1.7.1 read-only physical preflight (no modem command).
# No SMS/USSD, state modifications, restarts, credentials or raw status dump.
set -eu
LC_ALL=C;export LC_ALL
check_exec() {
  if [ -x "$2" ] && [ ! -L "$2" ];then
    printf '%s=present_executable\n' "$1"
  elif [ -L "$2" ];then
    printf '%s=unexpected_symlink\n' "$1"
  elif [ -e "$2" ];then
    printf '%s=not_executable\n' "$1"
  else
    printf '%s=missing\n' "$1"
  fi
}
check_command() {
  if command -v "$2" >/dev/null 2>&1;then
    printf '%s=present\n' "$1"
  else
    printf '%s=missing\n' "$1"
  fi
}
check_exec VECI_USSD_RPC /usr/libexec/rpcd/veci.ussd
check_exec VECI_USSD_WORKER /usr/libexec/veci-xl-ussd
check_exec VECI_USSD_NATIVE /usr/libexec/veci-xl-ussd-once
check_exec MODEM_MANAGER /usr/sbin/we5927-lte
check_exec QUOTA_CACHE /usr/libexec/veci-xl-quota-cache
check_command DEP_FLOCK flock
check_command DEP_JSONFILTER jsonfilter
check_command DEP_OD od
check_command DEP_TR tr
check_command DEP_DATE date
check_command DEP_HEAD head
check_command DEP_SHA256SUM sha256sum
check_command DEP_READLINK readlink
check_command DEP_SED sed
check_command DEP_AWK awk
printf 'USSD_WORKER_SYNTAX='
if sh -n /usr/libexec/veci-xl-ussd 2>/dev/null;then echo pass;else echo fail;fi
printf 'RPC_PLUGIN_SYNTAX='
if sh -n /usr/libexec/rpcd/veci.ussd 2>/dev/null;then echo pass;else echo fail;fi
printf 'CURRENT_ID_ROOT='
if [ "$(id -u)" = 0 ];then echo yes;else echo no;fi
printf 'BOARD_MATCH='
if [ "$(cat /tmp/sysinfo/board_name 2>/dev/null || :)" = zbtlink,zbt-we5927 ];then echo yes;else echo no;fi
printf 'MODEM_TTY_CHARDEV='
if [ -c /dev/ttyUSB2 ];then echo yes;else echo no;fi
printf 'MODEM_TTY_USB_INTERFACE='
dev="$(readlink -f /sys/class/tty/ttyUSB2/device 2>/dev/null || :)"
case "$dev" in /sys/devices/*:1.4/ttyUSB2) echo interface_1_4;; *) echo unrecognized;; esac
printf 'RPC_REGISTERED='
if ubus -S list veci.ussd >/dev/null 2>&1;then echo yes;else echo no;fi
printf 'SMS_RPC_REGISTERED='
if ubus -S list veci.sms >/dev/null 2>&1;then echo yes;else echo no;fi
printf 'QUOTA_SNAPSHOT='
if ubus call veci.ussd quotaStatus '{}' >/dev/null 2>&1;then echo reachable;else echo not_reachable;fi
printf 'MODEM_QUERIED=false\nSMS_READ_OR_SENT=false\nUSSD_DIALED=false\nCONFIG_CHANGED=false\n'
