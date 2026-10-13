#!/bin/sh
# Source-only VeCI uhttpd/rpcd effective auth preflight for office WE5927.
# Read-only: no modem, network call, session dump, package install or restart.
# Never treat this check as a proof of browser-to-native principal binding.
set -eu
PROC_ROOT=/proc

if ! command -v uci >/dev/null 2>&1 || ! command -v ubus >/dev/null 2>&1; then
    echo 'VECI_AUTH_EFFECTIVE_PREFLIGHT=unavailable'
    exit 1
fi

# UCI show is consumed only by grep/awk. No original config values are output.
uci_available=unknown
if uci -q show uhttpd >/dev/null 2>&1; then uci_available=yes; fi
uci_enabled() {
    [ "$uci_available" = yes ] || return 1
    uci -q show uhttpd 2>/dev/null | awk -F= -v key="$1" '
       $1 ~ ("\\." key "$") {
          v=$2
          gsub(/[^[:alnum:]]/, "", v)
          if (v=="1" || v=="yes" || v=="true") found=1
       }
       END { exit (found ? 0 : 1) }'
}

auth_config=unknown
cors_config=unknown
if [ "$uci_available" = yes ]; then
    # IMPORTANT: actual OpenWrt init script uses "no_ubusauth" -> -a.
    # "ubus_noauth" is NOT the effective UCI option.
    auth_config=not_enabled
    cors_config=not_enabled
    if uci_enabled no_ubusauth; then auth_config=enabled_NO_GO; fi
    if uci_enabled ubus_cors; then cors_config=enabled_REVIEW; fi
fi

if [ -f /usr/lib/uhttpd_ubus.so ]; then
    module=present
else
    module=absent
fi
if [ -f /usr/lib/rpcd/ucode.so ]; then
    rpcd_ucode=present
else
    rpcd_ucode=absent
fi
if command -v ucode >/dev/null 2>&1; then
    ucode_bin=present
else
    ucode_bin=absent
fi

runtime=unknown
cors_runtime=unknown
loaded=unknown
if command -v pidof >/dev/null 2>&1; then
    pids="$(pidof uhttpd 2>/dev/null || :)"
    if [ -z "$pids" ]; then
        runtime=no_uhttpd_process
        loaded=no_uhttpd_process
        cors_runtime=no_uhttpd_process
    else
        runtime=not_enabled
        cors_runtime=not_enabled
        loaded=not_observed
        for pid in $pids; do
            case "$pid" in
                *[!0-9]*|'') runtime=unknown; loaded=unknown; cors_runtime=unknown; continue ;;
            esac
            cmd="$PROC_ROOT/$pid/cmdline"
            maps="$PROC_ROOT/$pid/maps"
            if [ ! -r "$cmd" ]; then
                runtime=unknown
                cors_runtime=unknown
            else
                if tr '\000' '\n' < "$cmd" | awk '$0=="-a"{yes=1} END{exit !yes}'; then
                    runtime=enabled_NO_GO
                fi
                if tr '\000' '\n' < "$cmd" | awk '$0=="-X"{yes=1} END{exit !yes}'; then
                    cors_runtime=enabled_REVIEW
                fi
            fi
            if [ ! -r "$maps" ]; then
                loaded=unknown
            elif grep -q '/uhttpd_ubus\.so' "$maps"; then
                loaded=present
            fi
        done
    fi
fi

private_api=not_registered
if ubus -S list 2>/dev/null | grep -q '^veci\.sms\.private$'; then
    private_api=registered_UNEXPECTED
fi

gate=needs_review
if [ "$auth_config" = enabled_NO_GO ] || [ "$runtime" = enabled_NO_GO ]; then
    gate=NO_GO_auth_disabled
elif [ "$auth_config" = not_enabled ] && [ "$runtime" = not_enabled ] &&
     [ "$module" = present ] && [ "$loaded" = present ] &&
     [ "$ucode_bin" = present ] && [ "$rpcd_ucode" = present ] &&
     [ "$private_api" = not_registered ]; then
    gate=backend_ready_session_binding_unverified
fi

printf 'VECI_AUTH_EFFECTIVE_PREFLIGHT=read_only\n'
printf 'UHTTPD_NO_UBUSAUTH_UCI=%s\n' "$auth_config"
printf 'UHTTPD_NO_UBUSAUTH_RUNTIME=%s\n' "$runtime"
printf 'UHTTPD_UBUS_CORS_UCI=%s\n' "$cors_config"
printf 'UHTTPD_UBUS_CORS_RUNTIME=%s\n' "$cors_runtime"
printf 'UHTTPD_UBUS_MODULE_FILE=%s\n' "$module"
printf 'UHTTPD_UBUS_MODULE_LOADED=%s\n' "$loaded"
printf 'UCODE_BINARY=%s\n' "$ucode_bin"
printf 'RPCD_UCODE_PLUGIN=%s\n' "$rpcd_ucode"
printf 'VECI_PRIVATE_SMS_API=%s\n' "$private_api"
printf 'AUTH_BACKEND_GATE=%s\n' "$gate"
printf 'BROWSER_SESSION_BINDING=unverified\n'
printf 'SMS_MODEM_COMMAND_SENT=false\n'
printf 'SESSIONS_OR_CREDENTIALS_EXPORTED=false\n'
