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
PKG_RELEASE:=4
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
	$(INSTALL_BIN) ./files/usr/libexec/oem-updated/shared-verify $(1)/usr/libexec/oem-updated/shared-verify
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
        shared = HERE.parent / "veci-v2/packages/veci-v2-ui/files/www"
        # Reuse native controls, not the complete VeCI frontend or a second backend.
        tools = files / "www/oem-tools"
        tools.mkdir()
        for name in ("sms-codec.js", "sms-center.js", "backup.js", "dns-settings.js"):
            shutil.copyfile(shared / "veci2" / name, tools / name)
        # Existing client module has three comma-expression loops; use arrays.
        sms = tools / "sms-center.js"
        sms_code = sms.read_text()
        old = "of ('sms-inbox-open','sms-sent-open','sms-drafts-open','sms-compose-open')"
        if sms_code.count(old) != 2:
            raise ValueError("SMS frontend loop anchor changed")
        short = "of ('sms-sent-open','sms-drafts-open','sms-compose-open')"
        if sms_code.count(short) != 1:
            raise ValueError("SMS frontend actions anchor changed")
        sms.write_text(sms_code.replace(old, "of ['sms-inbox-open','sms-sent-open','sms-drafts-open','sms-compose-open']")
                                .replace(short, "of ['sms-sent-open','sms-drafts-open','sms-compose-open']"))
        for name in ("tools.js", "tools.css"):
            shutil.copyfile(HERE / "frontend" / name, tools / name)
        # Extract only the reviewed panels and keep the OEM root landing intact.
        native_html = (shared / "veci2/index.html").read_text()
        def panel(marker):
            start = native_html.index(marker)
            begin = native_html.rindex("<article ", 0, start)
            end = native_html.index("</article>", start) + len("</article>")
            return native_html[begin:end]
        sms_panel = panel('id="sms-status"')
        backup_panel = panel('id="backup-export"')
        dns_panel = panel('id="dns-form"')
        (tools / "index.html").write_text(
            '<!doctype html><html lang="id"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>OEM Updated — Services</title><link rel="stylesheet" href="tools.css"><body>'
            '<header><h1>OEM Updated — Services</h1><a href="/">Kembali ke OEM</a></header>'
            '<form id="login"><h2>Login router</h2><p>Login ulang untuk kontrol privat.</p>'
            '<label>Username<input id="username" autocomplete="username" required></label>'
            '<label>Password<input id="password" type="password" autocomplete="current-password" required></label>'
            '<button id="login-button">Login</button><p id="login-result" role="status"></p></form>'
            '<main id="tools" hidden><button id="logout">Logout</button>'
            '<button id="sms-refresh">Refresh SMS status</button><button id="dns-refresh">Refresh DNS</button>'
            + sms_panel + dns_panel +
            '<article><h2>DHCP LAN</h2><p>Rentang menggunakan offset alamat dari subnet LAN, akhir eksklusif.</p>'
            '<button id="dhcp-refresh" type="button">Baca konfigurasi</button><form id="dhcp-form">'
            '<label>DHCP<select id="dhcp-enabled"><option value="1">Aktif</option><option value="0">Nonaktif</option></select></label>'
            '<label>Offset awal<input id="dhcp-start" type="number" min="1" max="99999" required></label>'
            '<label>Offset akhir eksklusif<input id="dhcp-end" type="number" min="2" max="99999" required></label>'
            '<label>Masa sewa<input id="dhcp-lease" maxlength="12" placeholder="12h" required></label>'
            '<button id="dhcp-save" disabled>Simpan dan terapkan</button></form><p id="dhcp-result" role="status"></p></article>'
            '<article><h2>Traffic lokal — 24 jam terakhir</h2><p>Hanya interval yang terukur, data di RAM; reset saat reboot. Bukan kuota operator.</p>'
            '<button id="traffic-refresh" type="button">Baca traffic terukur</button><pre id="traffic-result" class="result" role="status"></pre></article>'
            '<article><h2>Guest Wi-Fi (opsional)</h2><p>Nonaktif secara default. Hanya diaktifkan manual setelah addon dan profil terisolasi siap. Perubahan berlaku pada reboot manual; tidak ada restart otomatis.</p>'
            '<button id="guest-refresh" type="button">Baca status</button>'
            '<button id="guest-enable" type="button" disabled>Aktifkan saat boot berikutnya</button>'
            '<button id="guest-disable" type="button" disabled>Nonaktifkan saat boot berikutnya</button>'
            '<p id="guest-result" role="status"></p></article>'
            + backup_panel +
            '<article><h2>Firmware verification (no install)</h2><form id="firmware-form">'
            '<label>Firmware BIN<input id="firmware-image" type="file" accept=".bin" required></label>'
            '<label>Expected SHA-256<input id="firmware-sha" maxlength="64" required></label>'
            '<button id="firmware-submit">Verify only</button></form><p id="firmware-result" role="status"></p></article></main>'
            '<script src="sms-codec.js"></script><script src="sms-center.js"></script>'
            '<script src="dns-settings.js"></script><script src="tools.js"></script><script src="backup.js"></script></body></html>')
        landing = files / "www/index.html"
        html = landing.read_text()
        if html.count("</body>") != 1:
            raise ValueError("OEM landing link anchor changed")
        landing.write_text(html.replace("</body>", '<a href="/oem-tools/" style="position:fixed;right:12px;bottom:12px;z-index:9999;background:#2468a5;color:white;padding:8px;border-radius:4px">SMS / DNS / Backup</a></body>'))
        (cgi.parent / "veci2-backup").write_text("#!/bin/sh\nexec /usr/libexec/oem-updated/shared-backup\n")
        (cgi.parent / "veci2-backup").chmod(0o755)
        shutil.copyfile(shared / "cgi-bin/veci2-restore", cgi.parent / "veci2-restore")
        (cgi.parent / "veci2-restore").chmod(0o755)
        verify = adapter.parent / "shared-verify"
        shutil.copyfile(shared / "cgi-bin/veci2-verify", verify)
        verify.chmod(0o755)
        verify_gate = cgi.parent / "oem-verify"
        shutil.copyfile(HERE / "backend/verify-only.sh", verify_gate)
        verify_gate.chmod(0o755)
        for script in (cgi, adapter, writer, diagnostics, backup, verify, verify_gate, cgi.parent / "veci2-backup", cgi.parent / "veci2-restore"):
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
