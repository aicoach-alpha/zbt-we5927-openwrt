#!/bin/sh
# VeCI v13 read-only frontend and rpcd/uhttpd health capture.
# Never logs in, restarts services, edits config, or reads /etc/shadow.
set -eu
umask 077
PATH=/usr/sbin:/usr/bin:/sbin:/bin
export PATH
WORK=/tmp/veci-v13-capture-20261028
ARCH=/tmp/veci-v13-ui-source-20261028.tar.gz
REPORT="$WORK/diagnostics.txt"
fail(){ echo "VECI_V13_CAPTURE=$1"; exit 1; }
[ "$(id -u)" = 0 ] || fail root_required
[ -d /www/veci ] && [ ! -L /www/veci ] || fail veci_web_root_missing
[ -f /etc/openwrt_release ] || fail not_openwrt
[ ! -L "$WORK" ] || fail unsafe_existing_workdir
if [ -e "$WORK" ]; then
 [ -d "$WORK" ] || fail unsafe_existing_workdir
else
 mkdir -m 700 "$WORK" || fail mkdir_failed
fi
[ ! -L "$ARCH" ] || fail unsafe_existing_archive
if [ -e "$ARCH" ]; then fail existing_archive_preserved; fi
{
 echo '=== VECI V13 READ-ONLY ROUTER AUDIT ==='
 echo "VECI_V13_BOARD=$(cat /tmp/sysinfo/board_name 2>/dev/null || echo unknown)"
 echo "VECI_V13_VERSION=$(grep DISTRIB_RELEASE /etc/openwrt_release | head -n1 | cut -d= -f2 | tr -d "'\"")"
 for service in rpcd uhttpd ubusd; do
  if pidof "$service" >/dev/null 2>&1; then echo "VECI_V13_PROCESS_$service=running"
  else echo "VECI_V13_PROCESS_$service=absent"; fi
 done
 if command -v timeout >/dev/null 2>&1; then
  if timeout 6 ubus -S list session >/dev/null 2>&1; then
    echo VECI_V13_SESSION_RPC=responding
  else
    echo VECI_V13_SESSION_RPC=unavailable_or_timeout
  fi
 else
  echo VECI_V13_SESSION_RPC=timeout_command_unavailable
 fi
 for service in veci.meter veci.ussd veci.quota veci.xl veci.sms; do
  if command -v timeout >/dev/null 2>&1 && timeout 3 ubus -S list "$service" >/dev/null 2>&1; then
   echo "VECI_V13_RPC_$service=registered"
  else
   echo "VECI_V13_RPC_$service=not_confirmed"
  fi
 done
 echo '=== PACKAGE OWNER NAMES (NO SECRETS) ==='
 apk list -I 2>/dev/null | awk '$NF=="[installed]" && ($1~/^veci-/ || $1~/^rpcd-/ || $1~/^uhttpd-/) {print $1}' | sort || :
 echo '=== FRONTEND FILE CANDIDATES (NO FILE CONTENT IN TERMINAL) ==='
 find /www/veci -type f \( -name '*.js' -o -name '*.css' -o -name '*.html' \) -print 2>/dev/null | sort | sed -n '1,120p'
 echo '=== FLASH ==='
 df -k /overlay | tail -n 1
 echo 'VECI_V13_NO_PASSWORD_READ=true'
 echo 'VECI_V13_NO_SERVICE_RESTART=true'
 echo 'VECI_V13_NO_MODEM_CHANGE=true'
} > "$REPORT"
# Whitelist only public, browser-delivered static source directories. Do not
# copy server configs, private files, secret/token files, cache or auth sessions.
set --
for part in index.html login.html app.html js css styles assets; do
 if [ -f "/www/veci/$part" ] || [ -d "/www/veci/$part" ]; then
  [ ! -L "/www/veci/$part" ] || fail web_source_symlink_disallowed
  set -- "$@" "veci/$part"
 fi
done
[ "$#" -gt 0 ] || fail ui_sources_not_found
tar -czf "$ARCH" -C /www "$@" || fail tar_failed
[ -s "$ARCH" ] || fail archive_empty
echo "VECI_V13_SOURCE_ARCHIVE_BYTES=$(wc -c < "$ARCH" | tr -d '[:space:]')"
# print only bounded sanitized operational report, never session.list payload.
cat "$REPORT"
echo VECI_V13_AUDIT=pass
echo VECI_V13_PRODUCTION=unchanged
echo VECI_V13_ARCHIVE=/tmp/veci-v13-ui-source-20261028.tar.gz
