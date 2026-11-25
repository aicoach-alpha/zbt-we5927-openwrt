#!/bin/sh
# Internal read-only adapter prototype. NOT a CGI. Never expose under /www
# or rpcd until authenticated ACL integration is complete.
set -eu
. /usr/share/libubox/jshn.sh
get() { uci -q get "$1"; }
error() {
    json_init
    json_add_string code "-4"
    json_add_string reason "$1"
    json_dump
    exit 1
}
success() {
    json_init
    json_add_string code "1"
    json_add_string reason "$1"
}
[ "$#" -eq 1 ] || error "operation required"
case "$1" in
    get_sys_version)
        version="$(ubus call system board | jsonfilter -e '@.release.version')" || error "version unavailable"
        [ -n "$version" ] || error "version unavailable"
        success "get sysversion success"
        json_add_string sysversion "$version"
        ;;
    get_lan_config)
        proto="$(get network.lan.proto)" || error "LAN protocol unavailable"
        address="$(get network.lan.ipaddr)" || error "LAN address unavailable"
        case "$address" in
            *' '*) error "multiple LAN addresses not supported yet" ;;
            */*)
                prefix="${address##*/}"
                address="${address%/*}"
                case "$prefix" in ''|*[!0-9]*) error "invalid prefix";; esac
                [ "$prefix" -le 32 ] || error "invalid prefix"
                mask="$(awk -v p="$prefix" 'BEGIN {for(i=0;i<4;i++){n=p>8?8:p; if(n<0)n=0; printf "%s%d",i?".":"",256-2^(8-n);p-=n}}')"
                ;;
            *) mask="$(get network.lan.netmask)" || error "LAN netmask unavailable" ;;
        esac
        mac="$(cat /sys/class/net/br-lan/address | tr 'a-z' 'A-Z')" || error "LAN MAC unavailable"
        [ -n "$mac" ] && [ -n "$address" ] && [ -n "$mask" ] || error "LAN unavailable"
        success "get lan config success"
        json_add_object data
        json_add_string proto "$proto"
        json_add_string ipaddr "$address"
        json_add_string netmask "$mask"
        json_add_string macaddr "$mac"
        json_close_object
        ;;
    get_dhcp_config)
        ignore="$(get dhcp.lan.ignore || true)"
        case "$ignore" in 1) enabled=0;; ''|0) enabled=1;; *) error "invalid DHCP flag";; esac
        start="$(get dhcp.lan.start)" || error "DHCP start unavailable"
        limit="$(get dhcp.lan.limit)" || error "DHCP limit unavailable"
        case "$start:$limit" in *[!0-9:]*|:*|*:) error "invalid DHCP range";; esac
        lease="$(get dhcp.lan.leasetime)" || error "DHCP lease unavailable"
        address="$(get network.lan.ipaddr)" || error "LAN address unavailable"
        address="${address%/*}"
        head="${address%.*}"
        options="$(get dhcp.lan.dhcp_option || true)"
        success "get dhcp config success"
        json_add_object data
        json_add_string dhcp_enabled "$enabled"
        json_add_string dhcp_start "$start"
        # Preserve original OEM wire convention, not an inclusive pool end.
        json_add_string dhcp_end "$((start+limit))"
        json_add_string dhcp_lease "$lease"
        json_add_string dhcp_head "$head"
        json_add_string dhcp_option "$options"
        json_close_object
        ;;
    *) error "operation not implemented" ;;
esac
json_dump
