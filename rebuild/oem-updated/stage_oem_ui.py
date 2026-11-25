#!/usr/bin/env python3
"""Stage original ZBT web assets for OEM Updated development, not a flash image.

Use the exact original OEM image, never a router dump. Do not deploy the
preview to a live router: its original CGI contract needs a modern backend.
"""
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

OEM_SHA = "b3545ba964fe12c794da927574cb792b4c18a4e4a0de9b9cca71ca8341692095"
VECI_BASE = "d8faaeff420bdc44e03fc756a5e0527c886cdc27"
OPENWRT_BASE = "64900e756efa667774214f9c6b17c113222e01f7"
SQ_OFFSET = 0x121404
STATIC = ("www/assets", "www/index.html", "www/favicon.ico",
          "www/manifest.json", "www/menu_conf.json", "www/menu_conf1.json",
          "www/robots.txt")
API = "www/cgi-bin/webapi"
ALLOWED_SUFFIX = {".js", ".css", ".png", ".svg", ".gif", ".woff", ".ttf",
                  ".eot", ".ico", ".html", ".json", ".txt"}

def sha(data):
    return hashlib.sha256(data).hexdigest()

def validate_image(image):
    data = image.read_bytes()
    if len(data) != 7536644 or sha(data) != OEM_SHA:
        raise ValueError("wrong OEM reference; raw router dumps are not accepted")
    if data[SQ_OFFSET:SQ_OFFSET+4] != b"hsqs":
        raise ValueError("invalid SquashFS offset")
    return data

def prepare(root, dest):
    """Copy only static files, inventory operation names, never copy vendor CGI."""
    root = root.resolve()
    if dest.exists():
        raise ValueError("destination must not exist")
    paths = []
    for name in STATIC:
        path = root / name
        if path.is_symlink() or not path.exists():
            raise ValueError("invalid source: " + name)
        paths.extend(path.rglob("*") if path.is_dir() else [path])
    if any(p.is_symlink() or not (p.is_file() or p.is_dir()) for p in paths):
        raise ValueError("non-regular source entry")
    files = sorted(p for p in paths if p.is_file())
    if any(p.suffix.lower() not in ALLOWED_SUFFIX for p in files):
        raise ValueError("unexpected asset extension")
    if any(p.read_bytes().startswith(b"\x7fELF") for p in files):
        raise ValueError("ELF assets refused")
    api = root / API
    if api.is_symlink() or not api.is_file():
        raise ValueError("invalid CGI reference")
    ops = sorted(set(re.findall(r'\[\s*"\$op"\s*==\s*"([A-Za-z0-9_]+)"',
                                api.read_text(encoding="utf-8"))))
    if len(ops) != 158 or len(files) != 85:
        raise ValueError("unexpected OEM contract")
    menu = json.loads((root / "www/menu_conf1.json").read_text())
    if sum(sum(v.values()) for v in menu.values()) != 20:
        raise ValueError("unexpected OEM menu")
    dest.mkdir(parents=True)
    try:
        entries = []
        for p in files:
            rel = p.relative_to(root)
            out = dest / "preview" / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            data = p.read_bytes()
            out.write_bytes(data)
            entries.append({"path": str(rel), "bytes": len(data), "sha256": sha(data)})
        manifest = {
            "variant": "OEM Updated", "veci_base": VECI_BASE,
            "openwrt_base": OPENWRT_BASE, "oem_sha256": OEM_SHA,
            "assets": entries, "asset_bytes": sum(x["bytes"] for x in entries),
            "menu": menu, "operations": {op: "UNIMPLEMENTED" for op in ops},
            "backend_ready": False, "flash_allowed": False,
            "excluded": ["vendor CGI", "vendor executables", "vendor kernel modules",
                         "device overlay", "credentials", "service worker cache"],
        }
        (dest / "manifest.json").write_text(json.dumps(manifest, indent=2)+"\n")
    except Exception:
        shutil.rmtree(dest)
        raise
    return manifest

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("oem_image", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    validate_image(args.oem_image)
    if args.output.exists():
        raise ValueError("output already exists")
    with tempfile.TemporaryDirectory(prefix="zbt-oem-ui-") as tmp:
        root = Path(tmp) / "root"
        subprocess.run(["unsquashfs", "-no-progress", "-offset", str(SQ_OFFSET),
                        "-d", str(root), str(args.oem_image.resolve()),
                        *STATIC, API], check=True)
        result = prepare(root, args.output)
    print("OEM_STATIC_ASSETS_STAGED=" + str(len(result["assets"])))
    print("OEM_CGI_CONTRACT_OPERATIONS=" + str(len(result["operations"])))
    print("BACKEND_READY=NO")
    print("FLASH_ALLOWED=NO")

if __name__ == "__main__":
    main()
