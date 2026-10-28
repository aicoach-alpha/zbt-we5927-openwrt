#!/bin/sh
# One-off read-only audit of exact old v13u/v13v processes; no kills/restarts.
set -eu
PATH=/usr/sbin:/usr/bin:/sbin:/bin
export PATH
echo VECI_V13_PROCESS_AUDIT=started
[ "$(id -u)" = 0 ] || { echo VECI_V13_PROCESS_AUDIT=root_required; exit 1; }
matches=0
for proc in /proc/[0-9]*; do
 [ -d "$proc" ] && [ -r "$proc/cmdline" ] && [ -r "$proc/status" ] || continue
 pid="$(basename "$proc")"
 [ "$pid" = "$$" ] && continue
 label=''
 if tr '\000' '\n' <"$proc/cmdline" 2>/dev/null |
    grep -Fqx '/tmp/veci-v13u-lan-http-login-20261028.sh'; then
  label=v13u
 elif tr '\000' '\n' <"$proc/cmdline" 2>/dev/null |
      grep -Fqx '/tmp/veci-v13v-http-no-auth-blocker-20261028.sh'; then
  label=v13v
 fi
 [ -n "$label" ] || continue
 state="$(awk '$1=="State:"{print $2;exit}' "$proc/status" 2>/dev/null || :)"
 parent="$(awk '$1=="PPid:"{print $2;exit}' "$proc/status" 2>/dev/null || :)"
 channel="$(cat "$proc/wchan" 2>/dev/null || echo unavailable)"
 echo "VECI_V13_OLD_PROCESS=$label;pid=$pid;ppid=$parent;state=$state;wchan=$channel"
 matches=$((matches+1))
done
echo "VECI_V13_OLD_EXACT_PROCESS_COUNT=$matches"
for kind in v13u v13v v13w; do
 case "$kind" in
  v13u) backup=/etc/config/uhttpd.veci-v13u-before-http-20261028 ;;
  v13v) backup=/etc/config/uhttpd.veci-v13v-before-http-20261028 ;;
  v13w) backup=/etc/config/uhttpd.veci-v13w-before-http-20261028 ;;
 esac
 if [ -s "$backup" ] && [ -f "$backup" ] && [ ! -L "$backup" ]; then
  echo "VECI_V13_BACKUP_$kind=present"
 elif [ -e "$backup" ] || [ -L "$backup" ]; then
  echo "VECI_V13_BACKUP_$kind=unexpected"
 else
  echo "VECI_V13_BACKUP_$kind=absent"
 fi
done
echo '=== /etc/config/uhttpd HTTP directives (no secret contents) ==='
awk '
 $1=="option" && ($2=="redirect_https" || $2=="ubus_prefix") { print $2"="$3 }
 $1=="list" && ($2=="listen_http" || $2=="listen_https") { print $2"="$3 }
' /etc/config/uhttpd 2>/dev/null || :
echo VECI_V13_PROCESS_AUDIT=read_only_complete
echo VECI_V13_PRODUCTION=unchanged
