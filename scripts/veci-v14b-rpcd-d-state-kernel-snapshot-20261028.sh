#!/bin/sh
# VeCI v14b: ONE read-only kernel wait snapshot for verified D-state rpcd.
# No auth requests, SIGKILL, sysrq triggers, USB rebind or service restart.
set -u
PATH=/usr/sbin:/usr/bin:/sbin:/bin
export PATH
echo VECI_V14B_STAGE=started
[ "$(id -u)" -eq 0 ] || { echo VECI_V14B_ERROR=root_required; exit 1; }
[ "$(cat /tmp/sysinfo/board_name 2>/dev/null)" = zbtlink,zbt-we5927 ] ||
 { echo VECI_V14B_ERROR=wrong_router; exit 1; }
grep -Fqx "DISTRIB_RELEASE='25.12.5'" /etc/openwrt_release ||
 { echo VECI_V14B_ERROR=wrong_firmware; exit 1; }
PID=1017
[ -f "/proc/$PID/status" ] || { echo VECI_V14B_ERROR=rpcd_pid_absent; exit 0; }
[ "$(cat "/proc/$PID/comm" 2>/dev/null)" = rpcd ] ||
 { echo VECI_V14B_ERROR=pid_reused_or_not_rpcd; exit 0; }
echo VECI_V14B_PROCESS=rpcd_1017_verified
awk '
 $1=="State:" {print "VECI_V14B_RPCD_STATE="$2}
 $1=="PPid:" {print "VECI_V14B_RPCD_PARENT="$2}
 $1=="Threads:" {print "VECI_V14B_RPCD_THREADS="$2}
 $1=="VmRSS:" {print "VECI_V14B_RPCD_RSS_KIB="$2}
' "/proc/$PID/status"
state="$(awk '$1=="State:"{print $2;exit}' "/proc/$PID/status")"
if [ "$state" != D ]; then
 echo VECI_V14B_NOTE=rpcd_no_longer_in_D
 echo VECI_V14B_PRODUCTION=unchanged
 exit 0
fi
echo VECI_V14B_STAGE=kernel_wait_location
echo '=== /proc/1017/stack (up to 28 frames; may be unsupported) ==='
if [ -r "/proc/$PID/stack" ]; then
 sed -n '1,28p' "/proc/$PID/stack" 2>&1 || echo VECI_V14B_STACK=read_failed
else
 echo VECI_V14B_STACK=not_available
fi
echo '=== /proc/1017/wchan ==='
if [ -r "/proc/$PID/wchan" ]; then
 head -c 128 "/proc/$PID/wchan" 2>/dev/null || :
 echo
else
 echo VECI_V14B_WCHAN=not_available
fi
echo '=== /proc/1017/syscall (numeric, may be unsupported) ==='
if [ -r "/proc/$PID/syscall" ]; then
 head -c 240 "/proc/$PID/syscall" 2>/dev/null || :
 echo
else
 echo VECI_V14B_SYSCALL=not_available
fi
echo '=== opened modem serial devices, if any ==='
count_serial=0
for fd in /proc/1017/fd/*; do
 [ -L "$fd" ] || continue
 dest="$(readlink "$fd" 2>/dev/null || :)"
 case "$dest" in
  /dev/ttyUSB*|/dev/ttyACM*)
   echo "VECI_V14B_RPCD_SERIAL_FD=$(basename "$fd"):$dest"
   count_serial=$((count_serial+1))
   ;;
 esac
done
echo "VECI_V14B_RPCD_SERIAL_FD_COUNT=$count_serial"
echo VECI_V14B_STAGE=kernel_related_messages
# Kernel logs only, bounded to 24 relevant lines; no auth or session data.
if command -v dmesg >/dev/null 2>&1; then
 dmesg 2>/dev/null |
 grep -Ei 'blocked for more than|hung task|I/O error|usb.*(reset|disconnect|error|stall)|ttyUSB|jffs2|ubifs|mtd.*error|mmc.*error|kernel BUG|watchdog.*lockup' |
 tail -n 24 || :
else
 echo VECI_V14B_DMESG=unavailable
fi
echo VECI_V14B_STAGE=complete
echo VECI_V14B_NO_SERVICE_RESTART=true
echo VECI_V14B_NO_USB_RESET=true
echo VECI_V14B_NO_AUTH_REQUEST=true
echo VECI_V14B_PRODUCTION=unchanged
