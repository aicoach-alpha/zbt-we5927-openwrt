#!/bin/sh
# VeCI Indonesia native quota-engine feasibility probe.
# READ ONLY: no modem/AT, no SMS/OTP, no HTTPS call, no package installation.
# Prints no IMEI, ICCID, MSISDN, saved tokens or carrier responses.
set -eu
LC_ALL=C;export LC_ALL
[ "$#" -eq 1 ] && [ "$1" = --status ] || exit 2
if [ "$(cat /tmp/sysinfo/board_name 2>/dev/null || :)" != zbtlink,zbt-we5927 ];then
 echo 'VECI_TELCO_NATIVE_PREFLIGHT=unsupported_router';exit 1
fi
echo 'VECI_TELCO_NATIVE_PREFLIGHT=read_only'
if command -v uclient-fetch >/dev/null 2>&1;then
 echo 'VECI_DIRECT_HTTPS_CLIENT=uclient-fetch'
elif command -v wget >/dev/null 2>&1;then
 echo 'VECI_DIRECT_HTTPS_CLIENT=wget_capabilities_unverified'
else echo 'VECI_DIRECT_HTTPS_CLIENT=missing';fi
if [ -r /etc/ssl/certs/ca-certificates.crt ] || [ -r /etc/ssl/cert.pem ];then
 echo 'VECI_CA_TRUST_STORE=available'
else echo 'VECI_CA_TRUST_STORE=not_detected';fi
if ls /usr/lib/libmbedcrypto.so* >/dev/null 2>&1;then
 echo 'VECI_NATIVE_MBEDCRYPTO=available'
else echo 'VECI_NATIVE_MBEDCRYPTO=not_detected';fi
if ls /usr/lib/libcrypto.so* >/dev/null 2>&1;then
 echo 'VECI_NATIVE_OPENSSL_CRYPTO=available'
else echo 'VECI_NATIVE_OPENSSL_CRYPTO=not_detected';fi
if command -v apk >/dev/null 2>&1;then
 echo 'VECI_PACKAGE_MANAGER=apk'
else echo 'VECI_PACKAGE_MANAGER=not_detected';fi
if [ -r /proc/meminfo ];then
 awk '/^MemAvailable:/ {printf "VECI_AVAILABLE_RAM_KB=%d\n",$2;found=1;exit}
      END {if(!found)print "VECI_AVAILABLE_RAM_KB=unknown"}' /proc/meminfo
fi
if command -v df >/dev/null 2>&1;then
 df -k /overlay | awk 'NR==2 && $4 ~ /^[0-9]+$/ {
    printf "VECI_OVERLAY_FREE_KB=%s\n",$4
 }'
fi
echo 'VECI_NATIVE_QUOTA_PROVIDER_STATUS=not_authenticated'
echo 'VECI_OTP_AUTO_READ=false'
echo 'VECI_EXTERNAL_INTERMEDIARY=false'
echo 'VECI_USSD_USED=false'
echo 'VECI_SIM_OR_MODEM_COMMANDS=false'
