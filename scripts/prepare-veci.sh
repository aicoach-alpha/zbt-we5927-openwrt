#!/bin/sh
set -eu

# Edition is selected explicitly at build time; never from any remote
# service and never silently changes an existing General image.
VECI_EDITION="${VECI_EDITION:-general}"
case "$VECI_EDITION" in
	general|indonesia) ;;
	*) echo "error: unsupported VeCI edition: $VECI_EDITION" >&2; exit 2 ;;
esac

OPENWRT_ROOT="${1:-}"
[ -n "$OPENWRT_ROOT" ] || {
	echo "usage: $0 /path/to/openwrt" >&2
	exit 2
}

[ -d "$OPENWRT_ROOT/package" ] || {
	echo "error: $OPENWRT_ROOT does not look like an OpenWrt source tree" >&2
	exit 1
}

SELF_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
PIN="$(tr -d '[:space:]' < "$SELF_DIR/source/veci.commit")"
REPO="${VECI_REPO_URL:-https://github.com/aicoach-alpha/veci.git}"
DEST="$OPENWRT_ROOT/package/veci"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT INT TERM

case "$PIN" in
	????????????????????????????????????????) ;;
	*) echo "error: invalid VeCI commit pin: $PIN" >&2; exit 1 ;;
esac

mkdir -p "$TMP/tree"

if [ -n "${VECI_SOURCE_DIR:-}" ]; then
	git -C "$VECI_SOURCE_DIR" cat-file -e "$PIN^{commit}" 2>/dev/null || {
		echo "error: pinned VeCI commit $PIN is not present in $VECI_SOURCE_DIR" >&2
		exit 1
	}
	git -C "$VECI_SOURCE_DIR" archive "$PIN" | tar -x -C "$TMP/tree"
else
	git -C "$TMP" init -q repo
	git -C "$TMP/repo" remote add origin "$REPO"
	git -C "$TMP/repo" fetch -q --depth 1 origin "$PIN"
	git -C "$TMP/repo" checkout -q --detach FETCH_HEAD
	git -C "$TMP/repo" archive HEAD | tar -x -C "$TMP/tree"
fi

grep -qx 'PKG_NAME:=veci' "$TMP/tree/Makefile" || {
	echo "error: pinned source is not a VeCI OpenWrt package" >&2
	exit 1
}

rm -rf "$DEST"
mkdir -p "$DEST"
cp -a "$TMP/tree/." "$DEST/"

# The OpenWrt board patch provides a bootstrap we5927-lte package, but the
# audited package in source/we5927-lte MUST replace it on both editions.
# Otherwise a stale modem manager could be embedded in a green build.
for package in we5927-lte veci-default-ui veci-cellular-we5927 veci-app-catalog-we5927 veci-app-guest veci-app-sqm veci-app-ddns veci-app-wireguard veci-app-voucher veci-update-we5927; do
	rm -rf "$OPENWRT_ROOT/package/$package"
	cp -a "$SELF_DIR/source/$package" "$OPENWRT_ROOT/package/$package"
done

# One source tree, two clearly separated build profiles. The optional
# carrier package has no effect on General firmware staging.
if [ "$VECI_EDITION" = "indonesia" ]; then
	rm -rf "$OPENWRT_ROOT/package/veci-telco-indonesia"
	cp -a "$SELF_DIR/source/veci-telco-indonesia" "$OPENWRT_ROOT/package/veci-telco-indonesia"
else
	rm -rf "$OPENWRT_ROOT/package/veci-telco-indonesia"
fi

BUILD_ID="$(git -C "$SELF_DIR" rev-parse HEAD)"
if git -C "$OPENWRT_ROOT" rev-parse HEAD >/dev/null 2>&1; then
	OPENWRT_PIN="$(git -C "$OPENWRT_ROOT" rev-parse HEAD)"
else
	# Minimal CI package-staging harnesses are not full OpenWrt Git trees.
	OPENWRT_PIN="$(tr -d '[:space:]' < "$SELF_DIR/source/openwrt-source-commit.txt")"
fi
case "$BUILD_ID:$OPENWRT_PIN" in
	????????????????????????????????????????:????????????????????????????????????????) ;;
	*) echo "error: invalid firmware release identity" >&2; exit 1 ;;
esac

mkdir -p "$OPENWRT_ROOT/package/veci-default-ui/files/etc"
cat > "$OPENWRT_ROOT/package/veci-default-ui/files/etc/veci-release.json" <<EOF
{
	"schema": 1,
	"edition": "$VECI_EDITION",
	"build_id": "$BUILD_ID",
	"veci_commit": "$PIN",
	"openwrt_commit": "$OPENWRT_PIN"
}
EOF

if [ "${VECI_PUBLISHED_RELEASE:-0}" = "1" ]; then
	printf 'published\n' > "$OPENWRT_ROOT/package/veci-default-ui/files/etc/veci-release-channel"
else
	printf 'development\n' > "$OPENWRT_ROOT/package/veci-default-ui/files/etc/veci-release-channel"
fi

# Required SMS integration: reject fake frontend-only releases.
[ -s "$DEST/veci/sms-center.css" ] || {
    echo "error: VeCI SMS stylesheet missing from pinned Core" >&2; exit 1;
}
[ -s "$DEST/veci/js/pages/cellular.js" ] || {
    echo "error: Cellular page missing from pinned Core" >&2; exit 1;
}
[ -x "$OPENWRT_ROOT/package/veci-cellular-we5927/files/usr/libexec/rpcd/veci.sms" ] || {
    echo "error: veci.sms RPC backend missing" >&2; exit 1;
}
[ -x "$OPENWRT_ROOT/package/veci-cellular-we5927/files/usr/libexec/veci-sms-parse" ] || {
    echo "error: bounded SMS PDU parser missing" >&2; exit 1;
}
grep -q '"veci.sms"' "$OPENWRT_ROOT/package/veci-cellular-we5927/files/usr/share/rpcd/acl.d/veci-cellular-we5927.json" || {
    echo "error: SMS ubus ACL missing" >&2; exit 1;
}

# Full SMS release MUST include matching native transport, RPC, workers,
# ACL and v160 UI. A frontend-only candidate is forbidden.
for name in veci-sms-send-one veci-sms-delete-one veci-sms-sent-history veci-sms-drafts; do
  [ -x "$OPENWRT_ROOT/package/veci-cellular-we5927/files/usr/libexec/$name" ] || {
    echo "error: missing SMS worker $name" >&2
    exit 1
  }
done
[ -s "$OPENWRT_ROOT/package/we5927-lte/src/veci-sms-cmgs.c" ] || {
  echo "error: missing native SMS submit source" >&2
  exit 1
}
grep -q 'veci-sms-cmgs' "$OPENWRT_ROOT/package/we5927-lte/Makefile" || {
  echo "error: missing native SMS packaging" >&2
  exit 1
}
grep -q 'deleteMessage' "$OPENWRT_ROOT/package/veci-cellular-we5927/files/usr/share/rpcd/acl.d/veci-cellular-we5927.json" || {
  echo "error: missing SMS mutation permissions" >&2
  exit 1
}
grep -q 'sendMessage' "$DEST/veci/js/pages/cellular.js" || {
  echo "error: full SMS UI contract unavailable" >&2
  exit 1
}

echo "Prepared VeCI $PIN (edition: $VECI_EDITION)"
echo "  core:      $DEST"
echo "  default:   $OPENWRT_ROOT/package/veci-default-ui"
echo "  cellular:  $OPENWRT_ROOT/package/veci-cellular-we5927"
echo "  app catalog: $OPENWRT_ROOT/package/veci-app-catalog-we5927"
echo "  app wrappers: guest sqm ddns wireguard voucher"
echo "  update profile: $OPENWRT_ROOT/package/veci-update-we5927"
