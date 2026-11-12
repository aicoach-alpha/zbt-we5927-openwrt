#!/bin/sh
set -eu
PROJECT="$(CDPATH='' cd "$(dirname "$0")/../.." && pwd)"
SCRIPT="$PROJECT/scripts/veci-ipv6-factory-image-only.sh"
sh -n "$SCRIPT"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT HUP INT TERM
ROOT="$TMP/staged-rootfs"
mkdir -p "$ROOT/etc/config" "$TMP/bin"
printf '%s\n' 'config interface lan' > "$ROOT/etc/config/network"
printf '%s\n' 'config dhcp lan' > "$ROOT/etc/config/dhcp"
cat > "$TMP/bin/uci" <<'MOCK'
#!/bin/sh
[ "$1" = -c ] || exit 99
shift 2
[ "$1" = -q ] && shift
cmd="$1"; shift
if [ "$cmd" = get ]; then
  case "$1" in
    network.lan|network.wan|network.lte|network.wan6) printf '%s\n' interface;;
    dhcp.lan) printf '%s\n' dhcp;;
    network.wan.proto|network.lte.proto) printf '%s\n' "${MOCK_PROTO:-dhcp}";;
    network.wan6.proto) printf '%s\n' dhcpv6;;
    *) exit 1;;
  esac
  exit 0
fi
printf '%s %s\n' "$cmd" "$*" >> "$MOCK_UCI_LOG"
MOCK
chmod +x "$TMP/bin/uci"
export MOCK_UCI_LOG="$TMP/uci.log"
export PATH="$TMP/bin:$PATH"
# No marker -> absolutely no mutation.
if sh "$SCRIPT" "$ROOT" >/dev/null 2>&1; then echo "unexpected_factory_without_marker" >&2; exit 1; fi
[ ! -e "$MOCK_UCI_LOG" ] || { echo "mutated_without_marker" >&2; exit 1; }
: > "$ROOT/.veci-factory-image-root"
# IPv6-dependent transport -> fail closed, with zero config changes.
export MOCK_PROTO=464xlat
if sh "$SCRIPT" "$ROOT" >/dev/null 2>&1; then echo "unexpected_clat_accept" >&2; exit 1; fi
[ ! -e "$MOCK_UCI_LOG" ] || { echo "mutated_on_clat" >&2; exit 1; }
unset MOCK_PROTO
sh "$SCRIPT" "$ROOT" | grep -q 'factory_ipv6_policy=off_staged_only'
grep -q '^set network.wan6.disabled=1$' "$MOCK_UCI_LOG"
grep -q '^set network.wan.ipv6=0$' "$MOCK_UCI_LOG"
grep -q '^set network.lte.ipv6=0$' "$MOCK_UCI_LOG"
grep -q '^set dhcp.lan.ra=disabled$' "$MOCK_UCI_LOG"
grep -q '^set dhcp.lan.dhcpv6=disabled$' "$MOCK_UCI_LOG"
grep -q '^commit network$' "$MOCK_UCI_LOG"
grep -q '^commit dhcp$' "$MOCK_UCI_LOG"
if grep -Eiq 'reboot|ifdown|ifup|wifi|service|network reload|kill' "$MOCK_UCI_LOG"; then
 echo "disruptive_operation_in_factory_policy" >&2; exit 1
fi
echo 'veci_ipv6_factory_off_tests=PASS'
