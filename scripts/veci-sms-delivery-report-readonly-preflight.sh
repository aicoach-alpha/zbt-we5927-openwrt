#!/bin/sh
# VeCI WE5927 SMS Delivery Report capability check.
# Only AT+CMGF?, AT+CSMS?, AT+CNMI?, AT+CNMI=?, AT+CPMS?, AT+CPMS=? queries under modem lock.
# No SMS text/number/PDU, session, tokens or raw AT replies are printed.
# Does NOT enable routing, change CNMI, read or delete SMS, reboot LTE, or send SMS.
set -eu
umask 077
LC_ALL=C;export LC_ALL
fail(){ printf 'VECI_SMS_DELIVERY_PREFLIGHT_ERROR=%s\n' "$1" >&2;exit 1; }
[ "$#" -eq 0 ] || fail unexpected_args
[ "$(id -u)" = 0 ] || fail root_required
[ "$(cat /tmp/sysinfo/board_name 2>/dev/null || :)" = zbtlink,zbt-we5927 ] || fail wrong_device
[ -x /usr/sbin/we5927-at ] && [ -c /dev/ttyUSB2 ] || fail modem_or_transport_missing
[ -f /etc/veci-sms-feature ] && [ ! -L /etc/veci-sms-feature ] || fail sms_config_missing
for c in flock awk grep readlink dirname head tr wc;do
 command -v "$c" >/dev/null 2>&1 || fail dependency_missing
done
target="$(readlink -f /sys/class/tty/ttyUSB2/device 2>/dev/null || :)"
case "$target" in /sys/devices/*:1.4/ttyUSB2);;*)fail modem_identity_mismatch;;esac
parent="$(dirname "$(dirname "$target")")"
[ "$(cat "$parent/idVendor" 2>/dev/null || :)" = 05c6 ] || fail vendor_mismatch
[ "$(cat "$parent/idProduct" 2>/dev/null || :)" = 902e ] || fail product_mismatch
probe(){
 cmd="$1";label="$2"
 output="$(/usr/sbin/we5927-at /dev/ttyUSB2 "$cmd" 2500 2>/dev/null)" || return 1
 [ "$(printf '%s' "$output"|wc -c)" -le 500 ] || return 1
 printf '%s\n' "$output" | awk -v label="$label" -v command="$cmd" '
 {gsub(/\r/,"",$0)}
 $0==command{next}
 $0=="OK"{ok=1;next}
 index($0,label ":")==1 {found++;next}
 $0==""{next}
 {bad=1}
 END{exit !(ok && found==1 && !bad)}
 ' || return 1
 printf '%s\n' "$output" | tr -d '\r' | grep -F "$label:" | head -n 1
}
echo 'VECI_SMS_DELIVERY_PREFLIGHT=read_only'
(
 flock -n -x 9 || fail modem_busy_retry_later
 if mode="$(probe 'AT+CMGF?' '+CMGF')";then
   case "$mode" in '+CMGF: 0')echo 'MODEM_SMS_MODE=PDU';;
    *)echo 'MODEM_SMS_MODE=unknown_or_not_pdu';;esac
 else echo 'MODEM_SMS_MODE=unavailable';fi
 if csms="$(probe 'AT+CSMS?' '+CSMS')";then
   capabilities="$(printf '%s\n' "$csms"|awk -F'[:, ]+' '
     /^\+CSMS:/ && $2 ~ /^[0-9]+$/ && $3 ~ /^[0-9]+$/ && $4 ~ /^[0-9]+$/ {
       print $2 "," $3 "," $4
     }')"
   if [ -n "$capabilities" ];then
     echo 'SMS_SERVICE_STATUS=reported'
   else echo 'SMS_SERVICE_STATUS=unknown';fi
 else echo 'SMS_SERVICE_STATUS=unavailable';fi
 if cnmi="$(probe 'AT+CNMI?' '+CNMI')";then
   ds="$(printf '%s\n' "$cnmi" | awk -F'[:, ]+' '
     /^\+CNMI:/ && NF>=6 && $5 ~ /^[0-9]+$/ {print $5}
   ')"
   case "$ds" in
     0)echo 'STATUS_REPORT_ROUTING=disabled';;
     1)echo 'STATUS_REPORT_ROUTING=direct_urc_likely_uncollected';;
     2)echo 'STATUS_REPORT_ROUTING=storage_indication_possible';;
     *)echo 'STATUS_REPORT_ROUTING=unknown';;
   esac
 else echo 'STATUS_REPORT_ROUTING=unavailable';fi
 # Capability-query forms are strictly read-only; do not alter CNMI/CPMS.
 if cnmicap="$(probe 'AT+CNMI=?' '+CNMI')";then
   # The modem can advertise <ds> capability set but we never print raw
   # modem responses. Values must be reviewed before any configuration.
   echo 'CNMI_SUPPORTED_VALUES_QUERY=responded'
 else echo 'CNMI_SUPPORTED_VALUES_QUERY=unavailable';fi
 if cpmscap="$(probe 'AT+CPMS=?' '+CPMS')";then
   echo 'CPMS_SUPPORTED_STORES_QUERY=responded'
 else echo 'CPMS_SUPPORTED_STORES_QUERY=unavailable';fi
 if cpms="$(probe 'AT+CPMS?' '+CPMS')";then
   echo 'SMS_STORAGE_QUERY=responded'
 else echo 'SMS_STORAGE_QUERY=unavailable';fi
) 9>/var/lock/we5927-at.lock
echo 'STATUS_REPORT_CAPTURE=not_yet_verified'
echo 'MODEM_COMMANDS=read_only_queries_only'
echo 'SMS_SENT=false'
echo 'SMS_READ_OR_DELETED=false'
echo 'MODEM_OR_SERVICE_RESTART=false'
echo 'RAW_MODEM_RESPONSES_EXPORTED=false'
