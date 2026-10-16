#!/bin/sh
# VeCI WE5927 AUTH BACKEND READINESS - NO INSTALL / NO SMS / NO SESSION DUMP.
# Source-only diagnostic. Run locally only on actual office WE5927 if approved.
set -eu
if ! command -v uci >/dev/null 2>&1 || ! command -v ubus >/dev/null 2>&1; then
    echo 'VECI_AUTH_BACKEND_PREFLIGHT=unavailable'
    exit 1
fi
# Never emit the values of /etc/config/rpcd, /etc/shadow or ubus sessions.
# Only inspect explicit ubus_noauth and ubus_cors *flags*.
if uci -q show uhttpd 2>/dev/null | grep -Eq '\.ubus_noauth=(1|true|yes)([[:space:]]|$)'; then
    noauth=enabled
elif uci -q show uhttpd >/dev/null 2>&1; then
    noauth=not_enabled_in_uci
else
    noauth=unknown
fi
if uci -q show uhttpd 2>/dev/null | grep -Eq '\.ubus_cors=(1|true|yes)([[:space:]]|$)'; then
    cors=enabled
elif uci -q show uhttpd >/dev/null 2>&1; then
    cors=not_enabled_in_uci
else
    cors=unknown
fi
if command -v ucode >/dev/null 2>&1; then ucode_bin=present; else ucode_bin=absent; fi
if [ -f /usr/lib/rpcd/ucode.so ]; then rpcd_ucode=present; else rpcd_ucode=absent; fi
if [ -f /usr/lib/uhttpd/ubus.so ]; then http_ubus=present; else http_ubus=absent_or_alternate_path; fi
if ubus -S list 2>/dev/null | grep -q '^veci\.sms\.private$'; then
    private_api=registered_UNEXPECTED
else
    private_api=not_registered
fi
printf 'VECI_AUTH_BACKEND_PREFLIGHT=read_only\n'
printf 'UHTTPD_UBUS_NOAUTH=%s\n' "$noauth"
printf 'UHTTPD_UBUS_CORS=%s\n' "$cors"
printf 'UCODE_BINARY=%s\n' "$ucode_bin"
printf 'RPCD_UCODE_PLUGIN=%s\n' "$rpcd_ucode"
printf 'UHTTPD_UBUS_MODULE=%s\n' "$http_ubus"
printf 'VECI_PRIVATE_SMS_API=%s\n' "$private_api"
printf 'SMS_MODEM_COMMAND_SENT=false\n'
printf 'LOGIN_CREDENTIALS_EXPORTED=false\n'
printf 'SESSION_IDS_EXPORTED=false\n'
