#!/bin/sh
# ZBT-WE5927 MT7628 LAN diagnosis, READ ONLY; no router config or flash writes.
# To run manually from an authenticated Wi-Fi SSH session:
#   sh /tmp/veci-lan-phy-readonly.sh
# Do NOT run swconfig set/apply or /etc/init.d/network restart.
set -u
export LC_ALL=C
PATH=/usr/sbin:/usr/bin:/sbin:/bin
export PATH

readsys() {
    if [ -r "$1" ]; then
        head -n1 "$1" 2>/dev/null | tr -cd '[:alnum:]_-'
    else
        printf 'unavailable'
    fi
}
getuci() {
    value="$(uci -q get "$1" 2>/dev/null || :)"
    # No secret UCI fields are queried: only interface names, VLAN IDs/ports.
    printf '%s' "$value" | tr -cd '[:alnum:]_./:@ -'
}
printf 'epoch_s=%s\n' "$(date +%s)"
printf 'uptime_s=%s\n' "$(awk '{printf "%.0f", $1}' /proc/uptime 2>/dev/null)"
printf 'board=%s\n' "$(readsys /tmp/sysinfo/board_name)"
printf 'lan_interface_type=%s\n' "$(getuci network.lan.proto)"
printf 'lan_device=%s\n' "$(getuci network.lan.device)"
printf 'lan_ifname=%s\n' "$(getuci network.lan.ifname)"
printf 'lan_switch_vlan1_ports=%s\n' "$(getuci 'network.@switch_vlan[0].ports')"
printf 'lan_switch_vlan2_ports=%s\n' "$(getuci 'network.@switch_vlan[1].ports')"

# eth0 on the MT7628 is the CPU-facing switch connection: it may report
# carrier even while EVERY external RJ45 port is physically disconnected.
for dev in eth0 eth0.1 eth0.2 br-lan; do
    [ -d "/sys/class/net/$dev" ] || continue
    printf '%s_carrier=%s\n' "$dev" "$(readsys "/sys/class/net/$dev/carrier")"
    printf '%s_operstate=%s\n' "$dev" "$(readsys "/sys/class/net/$dev/operstate")"
done

# The integrated rt3050-esw is a swconfig device, not a DSA 'lan1' port.
# Link states here are the main evidence that copper PHY has negotiated.
if command -v swconfig >/dev/null 2>&1; then
    if command -v timeout >/dev/null 2>&1; then
        port_state="$(timeout 3 swconfig dev switch0 show 2>/dev/null || :)"
    else
        port_state="$(swconfig dev switch0 show 2>/dev/null || :)"
    fi
    if [ -n "$port_state" ]; then
        printf '%s\n' "$port_state" |
            sed -n 's/.*port:\([0-9][0-9]*\) link:\(up\|down\).*/switch_port_\1_link=\2/p'
    else
        printf 'switch_port_status=unavailable\n'
    fi
else
    printf 'swconfig=unavailable\n'
fi

if command -v ubus >/dev/null 2>&1 && command -v jsonfilter >/dev/null 2>&1; then
    interface="$(ubus -S -t 2 call network.interface.lan status '{}' 2>/dev/null || :)"
    if [ -n "$interface" ]; then
        printf 'netifd_lan_up=%s\n' "$(printf '%s' "$interface" | jsonfilter -e '@.up' 2>/dev/null)"
    else
        printf 'netifd_lan_up=unavailable\n'
    fi
fi

# Ring-buffer observations are NOT monotonic since the ring can rotate.
if command -v logread >/dev/null 2>&1; then
    printf 'switch_link_events_in_ring=%s\n' "$(
        logread 2>/dev/null |
        grep -Eic '(rt3050-esw|mt7628.*esw).*port [0-9]+ link (up|down)' || :
    )"
fi
echo 'diagnostic_mode=read_only'
