#!/bin/sh
# Read-only WE5927 usb0 modem-gateway vs public-IP LTE check; no network changes.
set -u
board="$(cat /tmp/sysinfo/board_name 2>/dev/null || :)"
if [ "$board" != zbtlink,zbt-we5927 ]; then echo TRIAGE_ABORT=WRONG_BOARD; exit 3; fi
echo TRIAGE_START=LTE_GATEWAY_VS_INTERNET
echo ===IP_AND_DEFAULT_ROUTE===
ip -4 addr show dev usb0 2>/dev/null
ip -4 route show default 2>/dev/null
echo ===MODEM_GATEWAY_NEIGHBOR===
ip -4 neigh show to 192.168.7.1 dev usb0 2>/dev/null
echo ===MODEM_GATEWAY_PING===
ping -I usb0 -c 1 -W 2 192.168.7.1 >/dev/null 2>&1
echo MODEM_PING_EXIT=$?
echo ===MODEM_GATEWAY_HTTP===
curl --disable --ipv4 --noproxy '*' --interface 'if!usb0' --connect-timeout 2 --max-time 5 --silent --output /dev/null --write-out 'MODEM_HTTP_CODE=%{http_code}\n' http://192.168.7.1/
echo MODEM_HTTP_EXIT=$?
echo ===PUBLIC_IP_HTTPS_NO_DNS===
curl --disable --ipv4 --insecure --noproxy '*' --interface 'if!usb0' --connect-timeout 3 --max-time 8 --silent --output /dev/null --write-out 'PUBLIC_TLS_IP_HTTP_CODE=%{http_code}\n' https://1.1.1.1/
echo PUBLIC_TLS_IP_EXIT=$?
echo ===LTE_RESOLVERS===
if [ -f /tmp/resolv.conf.d/resolv.conf.auto ]; then grep '^nameserver ' /tmp/resolv.conf.d/resolv.conf.auto || :; else echo RESOLV_AUTO=absent; fi
echo TRIAGE_END=OK
