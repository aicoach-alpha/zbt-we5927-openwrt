#!/bin/sh
set -eu

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

for package in veci-default-ui veci-cellular-we5927 veci-app-catalog-we5927 veci-app-guest veci-app-sqm veci-app-ddns veci-app-wireguard veci-app-voucher veci-update-we5927; do
	rm -rf "$OPENWRT_ROOT/package/$package"
	cp -a "$SELF_DIR/source/$package" "$OPENWRT_ROOT/package/$package"
done

BUILD_ID="$(git -C "$SELF_DIR" rev-parse HEAD)"
OPENWRT_PIN="$(tr -d '[:space:]' < "$SELF_DIR/source/openwrt-source-commit.txt")"
case "$BUILD_ID:$OPENWRT_PIN" in
	????????????????????????????????????????:????????????????????????????????????????) ;;
	*) echo "error: invalid firmware release identity" >&2; exit 1 ;;
esac

mkdir -p "$OPENWRT_ROOT/package/veci-default-ui/files/etc"
cat > "$OPENWRT_ROOT/package/veci-default-ui/files/etc/veci-release.json" <<EOF
{
	"schema": 1,
	"build_id": "$BUILD_ID",
	"veci_commit": "$PIN",
	"openwrt_commit": "$OPENWRT_PIN"
}
EOF

echo "Prepared VeCI $PIN"
echo "  core:      $DEST"
echo "  default:   $OPENWRT_ROOT/package/veci-default-ui"
echo "  cellular:  $OPENWRT_ROOT/package/veci-cellular-we5927"
echo "  app catalog: $OPENWRT_ROOT/package/veci-app-catalog-we5927"
echo "  app wrappers: guest sqm ddns wireguard voucher"
echo "  update profile: $OPENWRT_ROOT/package/veci-update-we5927"
