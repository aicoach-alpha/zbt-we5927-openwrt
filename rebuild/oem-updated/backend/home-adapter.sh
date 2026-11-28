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
# Two concurrent readers at most: preserve a small memory footprint.
tmp=$(mktemp -d /tmp/oem-home.XXXXXX) || exit 1
trap 'rm -rf "$tmp"' EXIT
trap 'exit 1' HUP INT TERM
pair() {
    collect "$1" "$2" > "$tmp/$1" & first=$!
    collect "$3" "$4" > "$tmp/$3" & second=$!
    wait "$first" || exit 1
    wait "$second" || exit 1
}
pair get_lan_config '{"code":"-4","data":{}}' get_wan_config '{"code":"-4","data":{}}'
pair get_network_topology '{"code":"-4","port":[],"internet":"unknown","wifi2":"","wifi5":"0"}' get_system_status '{"code":"-4","cpu_usage":"","memory_usage":"","uptime":"","load_avg":"","online_user_num":""}'
pair app_home '{"code":"-4","rx":"","tx":"","internet_status":"unknown"}' getWiFi2 '{"code":"-4"}'
pair get_module_signal '{"code":"-4","data":[]}' get_wifi_apclient_config '{"code":"-4","enabled":"","apclient_wifiname":""}'
lan=$(cat "$tmp/get_lan_config"); wan=$(cat "$tmp/get_wan_config")
topology=$(cat "$tmp/get_network_topology"); system=$(cat "$tmp/get_system_status")
traffic=$(cat "$tmp/app_home"); wifi=$(cat "$tmp/getWiFi2")
lte=$(cat "$tmp/get_module_signal"); sta=$(cat "$tmp/get_wifi_apclient_config")
printf '{"home":{"get_lan_config":%s,"get_wan_config":%s,"get_network_topology":%s,"get_system_status":%s,"get_wan_traffic":%s,"getWiFi2":%s,"getWiFi5":{"supported":false,"wifi5_enabled":"0"},"get_module_signal":%s,"get_wifi_apclient_config":%s}}\n' "$lan" "$wan" "$topology" "$system" "$traffic" "$wifi" "$lte" "$sta"
