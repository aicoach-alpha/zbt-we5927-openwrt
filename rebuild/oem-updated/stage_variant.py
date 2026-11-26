#!/usr/bin/env python3
"""Produce a separate, incomplete OEM Updated package staging tree.

No flash, signing, installation or deployment. Only verified static OEM assets
and reviewed modern adapter code enter the package. A local vendor image is
required; never consume a router dump or publish vendor files in Git.
"""
import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from stage_oem_ui import STATIC, API, SQ_OFFSET, prepare, OEM_SHA, OPENWRT_BASE

PUBLIC_SHA = "80529b8e9c31d686eb7f63a1517d6dbcf781f26cb4aceb7b8b1ff27c2d51d1f9"
ASSET_DIGEST = "d0d7c7c3b81557398f56ad5802f9113d2b0512722c10de4a76e0bdc97bef7c58"
HERE = Path(__file__).resolve().parent
APP = "www/assets/js/app.d4300432.js"
REPLACEMENTS = (
    ('function i(e){return Object(l["a"])({url:"/webapi?op=login",method:"get",params:e})}',
     'function i(e){return fetch("/ubus",{method:"POST",headers:{"Content-Type":"application/json"},cache:"no-store",body:JSON.stringify({jsonrpc:"2.0",id:1,method:"call",params:["00000000000000000000000000000000","session","login",{username:e.username,password:e.password,timeout:300}]})}).then(function(r){if(!r.ok)throw Error("Login failed");return r.json()}).then(function(r){if(!r.result||r.result[0]!==0||!r.result[1]||!/^[a-f0-9]{32}$/.test(r.result[1].ubus_rpc_session))throw Error("Login failed");return {code:"1",reason:"success",access_token:r.result[1].ubus_rpc_session,wifi_type:"2"}})}'),
    ('a={access_token:t,t:new Date};return e.params?Object.assign(e.params,a):e.params=a,e',
     'a={t:new Date};return e.headers=e.headers||{},t&&(e.headers["X-OEM-Session"]=t),e.params?Object.assign(e.params,a):e.params=a,e'),
    ('url:"/webapi/login?op=logout",method:"get"', 'url:"/webapi?op=logout",method:"post"'),
    ('method:"get",params:{token:e}', 'method:"get"'),
)
MAKEFILE = """include $(TOPDIR)/rules.mk
PKG_NAME:=oem-updated-ui-dev
PKG_VERSION:=0.1
PKG_RELEASE:=3
include $(INCLUDE_DIR)/package.mk
define Package/oem-updated-ui-dev
  SECTION:=admin
  CATEGORY:=Administration
  TITLE:=ZBT OEM Updated UI development package
  DEPENDS:=+uhttpd +uhttpd-mod-ubus +rpcd +libubox +libustream-mbedtls +px5g-mbedtls +veci-v2-runtime
endef
define Build/Compile
endef
define Package/oem-updated-ui-dev/install
	$(INSTALL_DIR) $(1)/www
	$(CP) ./files/www/. $(1)/www/
	$(INSTALL_DIR) $(1)/usr/libexec/oem-updated $(1)/usr/share/rpcd/acl.d
	$(INSTALL_BIN) ./files/usr/libexec/oem-updated/read-only-adapter $(1)/usr/libexec/oem-updated/read-only-adapter
	$(INSTALL_BIN) ./files/usr/libexec/oem-updated/write-adapter $(1)/usr/libexec/oem-updated/write-adapter
	$(INSTALL_BIN) ./files/usr/libexec/oem-updated/diagnostics-adapter $(1)/usr/libexec/oem-updated/diagnostics-adapter
	$(INSTALL_BIN) ./files/usr/libexec/oem-updated/shared-backup $(1)/usr/libexec/oem-updated/shared-backup
	$(INSTALL_DATA) ./files/usr/share/rpcd/acl.d/oem-updated.json $(1)/usr/share/rpcd/acl.d/oem-updated.json
	$(INSTALL_BIN) ./files/www/cgi-bin/webapi $(1)/www/cgi-bin/webapi
	$(INSTALL_DIR) $(1)/etc/uci-defaults
	$(INSTALL_BIN) ./files/etc/uci-defaults/97-oem-updated-https $(1)/etc/uci-defaults/97-oem-updated-https
endef
$(eval $(call BuildPackage,oem-updated-ui-dev))
"""
def sha(data):
    return hashlib.sha256(data).hexdigest()

def route_oem_cgi(www):
    """Route every known OEM CGI URL to the installed modern gateway."""
    count = 0
    for path in sorted(www.rglob("*")):
        if not path.is_file() or path.suffix not in (".js", ".html"):
            continue
        original = path.read_text()
        code = original
        for legacy in ('"/webapi/webapi?', '"/webapi/?', '"/webapi?',
                       "'/webapi/webapi?", "'/webapi/?", "'/webapi?"):
            count += code.count(legacy)
            code = code.replace(legacy, legacy[0] + "/cgi-bin/webapi?")
        if any(x in code for x in ('"/webapi', "'/webapi")):
            raise ValueError("unmapped OEM CGI URL: " + str(path))
        if code != original:
            path.write_text(code)
            if path.suffix == ".js":
                subprocess.run(["node", "--check", str(path)], check=True)
    return count

def stage(image, out):
    data = image.read_bytes()
    digest = sha(data)
    if (digest, len(data)) not in {(OEM_SHA, 7536644), (PUBLIC_SHA, 7471108)}:
        raise ValueError("unverified OEM reference refused")
    if data[SQ_OFFSET:SQ_OFFSET+4] != b"hsqs" or out.exists():
        raise ValueError("invalid image or output exists")
    with tempfile.TemporaryDirectory(prefix="oem-updated-") as td:
        tmp = Path(td)
        root = tmp / "root"
        subprocess.run(["unsquashfs", "-no-progress", "-offset", str(SQ_OFFSET),
                        "-d", str(root), str(image.resolve()), *STATIC, API], check=True)
        m = prepare(root, tmp / "preview")
        asset_digest = sha("".join("/"+x["path"]+" "+x["sha256"]+"\n"
                                   for x in m["assets"]).encode())
        if asset_digest != ASSET_DIGEST:
            raise ValueError("reference assets differ")
        pkg = tmp / "oem-updated-ui-dev"
        files = pkg / "files"
        shutil.copytree(tmp / "preview/preview/www", files / "www")
        # Both OEM menu profiles and the login response constrain the UI to radio0.
        for profile in ("menu_conf.json", "menu_conf1.json"):
            wifi = json.loads((files / "www" / profile).read_text())["wifi"]
            if (wifi["wifi_2"], wifi["wifi_5"], wifi["wifi_60"]) != (1, 0, 0):
                raise ValueError("unexpected radio capabilities in " + profile)
        app = files / APP
        original = app.read_text()
        code = original
        for old, new in REPLACEMENTS:
            if code.count(old) != 1:
                raise ValueError("unexpected frontend transport anchor")
            code = code.replace(old, new)
        app.write_text(code)
        routed = route_oem_cgi(files / "www")
        if routed < 100:
            raise ValueError("incomplete OEM CGI route inventory")
        code = app.read_text()
        # JS syntax validation is mandatory at staging.
        subprocess.run(["node", "--check", str(app)], check=True)
        cgi = files / "www/cgi-bin/webapi"
        cgi.parent.mkdir()
        shutil.copyfile(HERE / "backend/webapi", cgi)
        cgi.chmod(0o755)
        adapter = files / "usr/libexec/oem-updated/read-only-adapter"
        adapter.parent.mkdir(parents=True)
        shutil.copyfile(HERE / "backend/read-only-adapter.sh", adapter)
        adapter.chmod(0o755)
        writer = adapter.parent / "write-adapter"
        shutil.copyfile(HERE / "backend/write-adapter.sh", writer)
        writer.chmod(0o755)
        diagnostics = adapter.parent / "diagnostics-adapter"
        shutil.copyfile(HERE / "backend/diagnostics-adapter.sh", diagnostics)
        diagnostics.chmod(0o755)
        backup = adapter.parent / "shared-backup"
        shutil.copyfile(HERE.parent / "veci-v2/packages/veci-v2-ui/files/www/cgi-bin/veci2-backup", backup)
        backup.chmod(0o755)
        for script in (cgi, adapter, writer, diagnostics, backup):
            subprocess.run(["sh", "-n", str(script)], check=True)
        acl = files / "usr/share/rpcd/acl.d/oem-updated.json"
        acl.parent.mkdir(parents=True)
        acl.write_text(json.dumps({"oem-updated-read": {
            "description": "Authenticated OEM read-only development API",
            "read": {"ubus": {"oem.updated": ["read"]}}},
            "oem-updated-write": {"description": "Authenticated OEM configuration API",
                "write": {"ubus": {"oem.updated": ["write"]}}}}, indent=2)+"\n")
        defaults = files / "etc/uci-defaults/97-oem-updated-https"
        defaults.parent.mkdir(parents=True)
        shutil.copyfile(HERE / "backend/97-oem-updated-https", defaults)
        defaults.chmod(0o755)
        subprocess.run(["sh", "-n", str(defaults)], check=True)
        (pkg / "Makefile").write_text(MAKEFILE)
        m.update({"reference_sha256":digest, "original_asset_digest":asset_digest,
                  "transport_patch": {"path":APP, "before":sha(original.encode()),
                                      "after":sha(code.encode()), "cgi_routes_rewritten":routed},
                  "backend_ready":False, "flash_allowed":False,
                  "openwrt_pin":OPENWRT_BASE})
        (pkg / "development-manifest.json").write_text(json.dumps(m, indent=2)+"\n")
        shutil.copytree(pkg, out)
    print("OEM_UPDATED_PACKAGE_STAGED=YES")
    print("OEM_UI_TRANSPORT_PATCH=PASS")
    print("FIRMWARE_BUILT=NO")
    print("FLASH_ALLOWED=NO")

if __name__ == "__main__":
    p=argparse.ArgumentParser()
    p.add_argument("image",type=Path)
    p.add_argument("out",type=Path)
    a=p.parse_args()
    stage(a.image,a.out)
