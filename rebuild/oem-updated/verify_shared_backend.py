"""Reject unreviewed divergence from the pinned shared VeCI backend snapshot."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
manifest = json.loads((ROOT / "rebuild/oem-updated/shared-backend.json").read_text())
assert manifest["schema"] == 1
for name, digest in manifest["files"].items():
    p = ROOT / name
    if not p.is_file() or p.is_symlink() or hashlib.sha256(p.read_bytes()).hexdigest() != digest:
        raise SystemExit("SHARED_BACKEND_DIVERGENCE: " + name)
print("SHARED_BACKEND_SOURCE_PARITY=PASS files=%d commit=%s" %
      (len(manifest["files"]), manifest["upstream_commit"]))
