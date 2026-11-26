#!/bin/sh
# Assemble existing OEM adapters. No second telemetry service, no vendor collector.
set -ef
umask 077
exec 9>/var/lock/oem-home.lock
flock -n 9 || exit 1
adapter=/usr/libexec/oem-updated/read-only-adapter
# The only JSON accepted here originates from our fixed allowlisted adapters.
# An absent source is not reported as healthy, and its UI receives a safe shape.
collect() {
    value="$(timeout 5 "$adapter" "$1" 2>/dev/null)" || value=""
    if [ "$(printf '%s' "$value" | jsonfilter -e '@.code' 2>/dev/null || true)" = 1 ]; then
        printf '%s' "$value"
    else
        printf '%s' "$2"
    fi
}
lan="$(collect get_lan_config '{"code":"-4","data":{}}')"
wan="$(collect get_wan_config '{"code":"-4","data":{}}')"
topology="$(collect get_network_topology '{"code":"-4","port":[],"internet":"unknown","wifi2":"","wifi5":"0"}')"
system="$(collect get_system_status '{"code":"-4","cpu_usage":"","memory_usage":"","uptime":"","load_avg":"","online_user_num":""}')"
traffic="$(collect app_home '{"code":"-4","rx":"","tx":"","internet_status":"unknown"}')"
wifi="$(collect getWiFi2 '{"code":"-4"}')"
lte="$(collect get_module_signal '{"code":"-4","data":[]}')"
sta="$(collect get_wifi_apclient_config '{"code":"-4","enabled":"","apclient_wifiname":""}')"
printf '{"home":{"get_lan_config":%s,"get_wan_config":%s,"get_network_topology":%s,"get_system_status":%s,"get_wan_traffic":%s,"getWiFi2":%s,"getWiFi5":{"supported":false,"wifi5_enabled":"0"},"get_module_signal":%s,"get_wifi_apclient_config":%s}}\n' "$lan" "$wan" "$topology" "$system" "$traffic" "$wifi" "$lte" "$sta"
