#!/bin/sh
# VeCI v13 — one local ubus session.login timing check, without credentials.
# Read-only. Do not restart rpcd, ubusd, uhttpd or the modem.
set -eu
PATH=/usr/sbin:/usr/bin:/sbin:/bin; export PATH
echo VECI_LOGIN_BACKEND_PROBE=begin
if command -v ubus >/dev/null 2>&1; then
  if ubus -S list session 2>/dev/null | grep -qx session; then
    echo VECI_LOGIN_SESSION_OBJECT=registered
  else
    echo VECI_LOGIN_SESSION_OBJECT=not_registered
  fi
fi
# Local status only; avoid printing sessions, credentials and ACLs.
for service in rpcd uhttpd ubusd; do
  if pidof "$service" >/dev/null 2>&1; then
    echo "VECI_LOGIN_PROCESS_${service}=running"
  else
    echo "VECI_LOGIN_PROCESS_${service}=absent"
  fi
done
if command -v ps >/dev/null 2>&1; then
  echo '=== authentication process indicators (no arguments) ==='
  ps | awk 'NR==1 || /[r]pcd|[u]busd|[p]am|[l]ogin/ {print $1, $2, $3}'
fi
echo '=== recent rpcd errors (sanitized) ==='
logread 2>/dev/null | grep -Ei 'rpcd|ubus|session|login|shadow|crypt|pam' | tail -n 18 |
 sed -E 's/([Pp]assword|[Tt]oken|[Ss]ecret|[Ss]ession[ _-]*id)[=: ]+[^ ,;]+/\1=[REDACTED]/g' || :
echo VECI_LOGIN_BACKEND_PROBE=read_only_complete
