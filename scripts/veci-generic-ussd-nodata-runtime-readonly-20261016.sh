#!/bin/sh
# Read-only sanitized runtime check for valid-start ubus NO_DATA on physical WE5927.
# Does NOT access modem, send USSD, restart services or print raw logs.
set -eu
LC_ALL=C
PATH=/usr/sbin:/usr/bin:/sbin:/bin
export LC_ALL PATH
fail(){ echo VECI_USSD_RUNTIME_DIAG=blocked; echo "VECI_USSD_RUNTIME_REASON=$1"; exit 1; }
[ "$#" -eq 1 ] && [ "$1" = --status ] || fail invalid_mode
[ "$(id -u)" -eq 0 ] || fail root_required
[ "$(cat /tmp/sysinfo/board_name 2>/dev/null || :)" = zbtlink,zbt-we5927 ] || fail wrong_router
grep -qx "DISTRIB_RELEASE='25.12.5'" /etc/openwrt_release || fail wrong_firmware
if ubus -S list veci.dialer 2>/dev/null | grep -qx veci.dialer; then
 echo VECI_USSD_RUNTIME_RPC=registered
else
 echo VECI_USSD_RUNTIME_RPC=not_registered
fi
if [ -f /tmp/veci-xl-ussd.session ] && [ ! -L /tmp/veci-xl-ussd.session ]; then
 echo VECI_USSD_RUNTIME_INTERACTIVE_SESSION=present
else
 echo VECI_USSD_RUNTIME_INTERACTIVE_SESSION=absent
fi
# Obtain only the configured -t number; never print complete process command lines.
timeout_value=default_or_unknown
if command -v pidof >/dev/null 2>&1; then
 for pid in $(pidof rpcd 2>/dev/null || :); do
  [ -r "/proc/$pid/cmdline" ] || continue
  timeout_arg=no
  while IFS= read -r arg; do
   if [ "$timeout_arg" = yes ]; then
    case "$arg" in
     ''|*[!0-9]*) timeout_value=invalid; ;;
     *) timeout_value="$arg"; ;;
    esac
    timeout_arg=no
   elif [ "$arg" = -t ]; then timeout_arg=yes
   fi
  done <<EOF
$(tr '\000' '\n' < "/proc/$pid/cmdline")
EOF
  break
 done
fi
case "$timeout_value" in
 default_or_unknown) echo VECI_USSD_RUNTIME_RPCD_TIMEOUT=default_or_unknown ;;
 invalid) echo VECI_USSD_RUNTIME_RPCD_TIMEOUT=invalid ;;
 *) echo "VECI_USSD_RUNTIME_RPCD_TIMEOUT_SECONDS=$timeout_value" ;;
esac
mem="$(awk '/^MemAvailable:/ {print $2;exit}' /proc/meminfo)"
case "$mem" in ''|*[!0-9]*) echo VECI_USSD_RUNTIME_MEMAVAILABLE_KB=unavailable ;;
 *) echo "VECI_USSD_RUNTIME_MEMAVAILABLE_KB=$mem" ;;
esac
if command -v dmesg >/dev/null 2>&1; then
 if dmesg 2>/dev/null | grep -Eiq 'out of memory|oom-kill|oom killer|killed process .*rpcd|killed process .*veci|killed process .*sh'; then
  echo VECI_USSD_RUNTIME_KERNEL_OOM_EVENTS=present
 else
  echo VECI_USSD_RUNTIME_KERNEL_OOM_EVENTS=not_detected
 fi
else
 echo VECI_USSD_RUNTIME_KERNEL_OOM_EVENTS=unavailable
fi
if command -v ps >/dev/null 2>&1; then
 if ps 2>/dev/null | grep -E '[v]eci-ussd-dialer(-once)?([[:space:]]|$)' >/dev/null 2>&1; then
  echo VECI_USSD_RUNTIME_WORKER_PROCESS=present
 else
  echo VECI_USSD_RUNTIME_WORKER_PROCESS=not_running
 fi
else
 echo VECI_USSD_RUNTIME_WORKER_PROCESS=unknown
fi
if [ -z "$(uci -q get uhttpd.main.listen_http 2>/dev/null || :)" ]; then
 echo VECI_USSD_RUNTIME_HTTPS_ONLY=pass
else
 echo VECI_USSD_RUNTIME_HTTPS_ONLY=not_confirmed
fi
echo VECI_USSD_RUNTIME_MODEM_COMMANDS=false
echo VECI_USSD_RUNTIME_SERVICES_CHANGED=false
echo VECI_USSD_RUNTIME_DIAG=pass
