#!/usr/bin/env bash
# Optional host-side sync on user-owned server; NO credentials on router.
set -euo pipefail
: "\${VECI_ROUTER_SSH:?Set VECI_ROUTER_SSH to a preapproved SSH destination}"
case "$VECI_ROUTER_SSH" in
  *[!A-Za-z0-9@._:-]*|'') echo "invalid SSH destination" >&2; exit 2 ;;
esac
BITSXL_BIN="\${BITSXL_BIN:-bitsxl}"
command -v "$BITSXL_BIN" >/dev/null || { echo "Missing host BITS-XL CLI" >&2; exit 2; }
ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
# No raw MyXL response or token is ever recorded by this sync script.
timeout 60s "$BITSXL_BIN" json quota 2>/dev/null |
  python3 "$ROOT/scripts/veci_xl_quota_normalize.py" |
  ssh -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=10 \
      -- "$VECI_ROUTER_SSH" /usr/sbin/veci-quota-import
