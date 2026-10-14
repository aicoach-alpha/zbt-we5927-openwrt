#!/bin/sh
# WE5927 Delivery Report routing-capability check.
# Strictly read-only: AT+CNMI=? and AT+CPMS=? only. No SMS body, phone,
# OTP, PDU, session, or raw reply is ever printed.
set -eu
umask 077
LC_ALL=C;export LC_ALL
fail(){ printf 'SMS_DELIVERY_ROUTING_PREFLIGHT_ERROR=%s\n' "$1" >&2;exit 1; }
[ "$#" -eq 0 ] || fail args
[ "$(id -u)" = 0 ] || fail root_required
[ "$(cat /tmp/sysinfo/board_name 2>/dev/null || :)" = zbtlink,zbt-we5927 ] || fail wrong_router
[ -x /usr/sbin/we5927-at ] && [ -c /dev/ttyUSB2 ] || fail no_modem_transport
for c in flock awk grep readlink dirname tr head wc;do
 command -v "$c" >/dev/null 2>&1 || fail dependency_missing
done
tty="$(readlink -f /sys/class/tty/ttyUSB2/device 2>/dev/null || :)"
case "$tty" in /sys/devices/*:1.4/ttyUSB2);;*)fail device_identity;;esac
parent="$(dirname "$(dirname "$tty")")"
[ "$(cat "$parent/idVendor" 2>/dev/null || :)" = 05c6 ] || fail vendor
[ "$(cat "$parent/idProduct" 2>/dev/null || :)" = 902e ] || fail product
probe(){
 cmd="$1";expected="$2"
 reply="$(/usr/sbin/we5927-at /dev/ttyUSB2 "$cmd" 2500 2>/dev/null)" || return 1
 [ "$(printf %s "$reply"|wc -c)" -le 480 ] || return 1
 printf '%s\n' "$reply" | awk -v cmd="$cmd" -v pref="$expected" '
 {gsub(/\r/,"",$0)}
 $0==cmd{next}
 $0=="OK"{ok++;next}
 index($0,pref ":")==1{found++;next}
 $0==""{next}
 {bad=1}
 END{exit !(ok==1 && found==1 && !bad)}' || return 1
 printf '%s\n' "$reply" | tr -d '\r' | grep -F "$expected:" | head -n 1
}
echo 'VECI_SMS_DELIVERY_ROUTING_PREFLIGHT=read_only'
(
 flock -n -x 9 || fail modem_busy
 if cnmi="$(probe 'AT+CNMI=?' '+CNMI')";then
  # AT+CNMI test response has five parameter groups, fourth is <ds>.
  # Example: +CNMI: (0-3),(0-3),(0-2),(0-2),(0-1)
  # Treat malformed/atypical responses as UNKNOWN (not supported).
  ds="$(printf '%s\n' "$cnmi" | awk -F '[()]' '
    /^\+CNMI:/ && NF>=10 {gsub(/ /,"",$8);print $8}')"
  if [ -n "$ds" ];then
   printf '%s\n' "$ds" | awk -F ',' '
   function has(x, spec, n,a,b,i,parts) {
      n=split(spec,parts,",");
      for(i=1;i<=n;i++){
       if(parts[i]==x)return 1;
       if(parts[i] ~ /^[0-9]+-[0-9]+$/){
        split(parts[i],a,"-");
        if(a[1]+0<=x && a[2]+0>=x)return 1;
       }
      }
      return 0
   }
   {
    printf "STATUS_REPORT_DIRECT_URC_SUPPORTED=%s\n",has(1,$0)?"yes":"no";
    printf "STATUS_REPORT_STORED_INDICATION_SUPPORTED=%s\n",has(2,$0)?"yes":"no";
   }'
  else
   echo 'STATUS_REPORT_DIRECT_URC_SUPPORTED=unknown'
   echo 'STATUS_REPORT_STORED_INDICATION_SUPPORTED=unknown'
  fi
 else
  echo 'STATUS_REPORT_DIRECT_URC_SUPPORTED=unknown'
  echo 'STATUS_REPORT_STORED_INDICATION_SUPPORTED=unknown'
 fi
 if cpms="$(probe 'AT+CPMS=?' '+CPMS')";then
  # Supported memory names only (never counts or message contents).
  case "$cpms" in *'"SM"'*)echo 'SMS_STORAGE_SM_SUPPORTED=yes';;
   *)echo 'SMS_STORAGE_SM_SUPPORTED=unknown';;esac
  case "$cpms" in *'"ME"'*)echo 'SMS_STORAGE_ME_SUPPORTED=yes';;
   *)echo 'SMS_STORAGE_ME_SUPPORTED=unknown';;esac
 else
  echo 'SMS_STORAGE_SM_SUPPORTED=unknown'
  echo 'SMS_STORAGE_ME_SUPPORTED=unknown'
 fi
) 9>/var/lock/we5927-at.lock
echo 'ROUTING_CONFIGURATION_CHANGED=false'
echo 'MODEM_COMMANDS=capability_queries_only'
echo 'SMS_SENT_READ_DELETED=false'
echo 'MODEM_OR_SERVICE_RESTART=false'
echo 'RAW_MODEM_RESPONSES_EXPORTED=false'
