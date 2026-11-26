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
PKG_RELEASE:=5
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
	$(INSTALL_BIN) ./files/usr/libexec/oem-updated/home-adapter $(1)/usr/libexec/oem-updated/home-adapter
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
        # Language is a browser preference, not a privileged router mutation.
        language_old = 'setLang:function(e){var t=this;this.$req.get("webapi?op=language_set&language="+e).then((function(a){t.$i18n.locale=e,localStorage.removeItem("lang"),localStorage.setItem("lang",e),localStorage.setItem("numberSum","1"),window.location.reload()}))}'
        language_new = 'setLang:function(e){if(["zh","en","fr","id","vi","th","de","kr","ru"].indexOf(e)<0)return;this.$i18n.locale=e;localStorage.setItem("lang",e);localStorage.setItem("numberSum","1");window.location.reload()}'
        lang_get = 'this.$req.get("/webapi?op=language_get").then((function(t){if(t.language&&""!=t.language)'
        lang_local = 'Promise.resolve({language:(["zh","en","fr","id","vi","th","de","kr","ru"].indexOf(localStorage.getItem("lang"))>=0?localStorage.getItem("lang"):"")}).then((function(t){if(t.language&&""!=t.language)'
        for old,new in ((language_old,language_new),(lang_get,lang_local),('localStorage.setItem("en","en")','localStorage.setItem("lang","en")')):
            if code.count(old)!=1:
                raise ValueError("OEM language preference anchor changed")
            code=code.replace(old,new)
        app.write_text(code)
        # Fix the vendor dashboard's random suppression of high CPU usage,
        # disable overlapping polls, and preserve unknown samples as gaps.
        home = files / "www/assets/js/home.5db31f8c.js"
        dashboard = home.read_text()
        edits = (
            ('if(console.log("拓扑",r),console.log("wan",s),console.log("lan",o),e.topology=r,t&&t(r),e.wan_conf=s,e.lan_conf=o,a.cpu_usage>80){var u=Math.random(100);u<80&&(a.cpu_usage=Math.floor(a.cpu_usage/(1.5+Math.random())))}',
             'e.topology=r,t&&t(r),e.wan_conf=s,e.lan_conf=o;'),
            ('get_home_info:function(t){var e=this;this.$req.get',
             'get_home_info:function(t){var e=this;if(e._oemPolling)return;e._oemPolling=true;this.$req.get'),
            ('console.log("获取wifi2",e.wifi2),e.wifi5=c,console.log("获取wifi5",e.wifi5)}))}',
             'e.wifi5=c})).catch(function(){e.resp.device="";e.traffic={rx:"",tx:""};e.topology={port:[],internet:"unknown"};e.status4g=""}).finally(function(){e._oemPolling=false})}'),
            ('t.get_home_info()}),3e3)', 't.get_home_info()}),1e4)'),
            ('n=Number(t.traffic.tx),o=Number(t.traffic.rx)', 'n=t.traffic.tx===""||t.traffic.tx==null?null:Number(t.traffic.tx),o=t.traffic.rx===""||t.traffic.rx==null?null:Number(t.traffic.rx)'),
            ('console.log("shirt",i);',''),
        )
        for old,new in edits:
            if dashboard.count(old) != 1:
                raise ValueError("OEM dashboard patch anchor changed: " + old[:80])
            dashboard = dashboard.replace(old,new)
        home.write_text(dashboard)
        subprocess.run(["node","--check",str(home)],check=True)
        # Wire the original OEM connected-client action to the same native MAC
        # block list, with explicit confirmation and stale-revision protection.
        client = files / "www/assets/js/chunk-2d0c8fa4.ea2af3a8.js"
        client_code = client.read_text()
        old = 'operate:function(t){var e=this;console.log(t.operation);var i="REJECT"==t.operation?"ACCEPT":"REJECT";this.proxy_req("post","/webapi?op=set_wifi_client",{macaddr:t.macaddr,operation:i},(function(t){e.get_wifi_client()}),!0)}'
        new = 'operate:function(t){var e=this;if(!/^[0-9a-f]{64}$/.test(t.revision||"")||["ACCEPT","REJECT"].indexOf(t.operation)<0)return;var i="REJECT"==t.operation?"ACCEPT":"REJECT";if(!window.confirm(i==="REJECT"?"Block this client from WAN? Software flow offload will be disabled.":"Remove this client from the WAN block list?"))return;this.$req.post("/webapi?op=set_wifi_client",{macaddr:t.macaddr,operation:i,revision:t.revision,confirmation:i==="REJECT"?"BLOCK_CLIENT":"UNBLOCK_CLIENT"}).then(function(r){if(!r||r.code!=="1")throw Error("Client policy rejected");e.get_wifi_client()}).catch(function(){e.$message.error("Client policy unavailable or changed; refresh.");e.get_wifi_client()})}'
        if client_code.count(old)!=1:
            raise ValueError("OEM client policy anchor changed")
        client.write_text(client_code.replace(old,new))
        subprocess.run(["node","--check",str(client)],check=True)
        # Replace the vendor's state-changing GET calls with authenticated
        # POST, confirmation, and the current native network revision.
        wan = files / "www/assets/js/chunk-4f3e33ae.e79f6535.js"
        wan_code = wan.read_text()
        for op,action,label in (("pppoe_disconnect","DISCONNECT_ETHERNET_PPPOE","disconnect"),("pppoe_reconnect","RECONNECT_ETHERNET_PPPOE","reconnect")):
            old = 'this.proxy_req("get","/webapi?op='+op+'",{'+label+':"'+label+'"},(function('+("e" if label=="disconnect" else "t")+'){console.log('+("e,t._throttle" if label=="disconnect" else "t")+')}),!0)'
            new = 'if(!window.confirm("'+label.capitalize()+' Ethernet WAN PPPoE?"))return;this.$req.get("/webapi?op=get_pppoe_status").then(function(x){if(!x||x.code!=="1"||!/^[0-9a-f]{64}$/.test(x.revision||""))throw Error("PPPoE state unavailable");return t.$req.post("/webapi?op='+op+'",{revision:x.revision,confirmation:"'+action+'"})}).then(function(x){if(!x||x.code!=="1")throw Error("PPPoE request rejected");t.$message.success("Requested; check connection status.")}).catch(function(){t.$message.error("PPPoE request failed; refresh status.")})'
            if wan_code.count(old)!=1:
                raise ValueError("OEM PPPoE action anchor changed: "+op)
            wan_code=wan_code.replace(old,new)
        old=r'this.proxy_req("get","/webapi?op=pppoe_detection",{pppoe_detection:"pppoe_detection"},(function(e){console.log(e),t.detectionList=e.data.pppoe_detection.split("\n")}),!0)'
        new=r'if(!window.confirm("Discover Ethernet PPPoE access concentrators?"))return;this.$req.post("/webapi?op=pppoe_detection",{confirmation:"DISCOVER_ETHERNET_PPPOE"}).then(function(x){if(!x||x.code!=="1"||!x.data)throw Error("Discovery unavailable");t.detectionList=["Exit code: "+x.data.exit_code].concat(x.data.pppoe_detection.split("\n"))}).catch(function(){t.$message.error("Ethernet discovery unavailable.")})'
        if wan_code.count(old)!=1:
            raise ValueError("OEM PPPoE discovery anchor changed")
        wan.write_text(wan_code.replace(old,new))
        subprocess.run(["node","--check",str(wan)],check=True)
        # Keep the original OEM forms; save against the revision actually shown
        # to the user, never fetch a newer revision just before overwriting it.
        def edit_chunk(name, edits):
            path = files / "www/assets/js" / name
            value = path.read_text()
            for old,new in edits:
                if value.count(old)!=1:
                    raise ValueError("OEM network form anchor changed: "+name+" "+old[:70])
                value=value.replace(old,new)
            path.write_text(value)
            subprocess.run(["node","--check",str(path)],check=True)
        edit_chunk("chunk-2d224d12.c4bda38e.js", [
            ('this.proxy_req("post","/webapi?op=get_ddns_log"',
             'this.proxy_req("get","/webapi?op=get_ddns_log"'),
        ])
        edit_chunk("chunk-2d225296.9ea3b9f6.js", [
            ('console.log(t),e.values=e.obj_to_arr(t,["enabled","remote","port","ca","cert","key"]),console.log(e.values)',
             'e.values=e.obj_to_arr(t,["enabled","remote","port","ca","cert","key"])'),
            ('var e=this.arr_to_obj(this.values,["enabled","remote","port","ca","cert","key"]);console.log(e),this.proxy_req("post","/webapi?op=set_openvpn",e,this.get_openvpn,!0)',
             'this.$message.warning("OpenVPN configuration is read-only in this version.")'),
        ])
        lan_name="chunk-2d22c110.8a7728fb.js"
        lan_source=(files / "www/assets/js" / lan_name).read_text()
        lan_start=lan_source.index("set_lan_config:function()")
        lan_end=lan_source.index(",created:function()",lan_start)
        edit_chunk(lan_name, (
            ('get_lan_config:function(){var t=this;this.$req.get','get_lan_config:function(){var t=this;return this.$req.get'),
            ('var s=a.data;t.ipaddr=s.ipaddr,t.netmask=s.netmask,t.lan_config=a.data',
             'if(!a||a.code!=="1"||!a.data)throw Error("LAN unavailable");t._lanRevision=a.revision;var s=a.data;t.ipaddr=s.ipaddr,t.netmask=s.netmask,t.lan_config=a.data'),
            (lan_source[lan_start:lan_end],
             'set_lan_config:function(){var t=this;if(t._lanBusy||!t.isValidIP(t.ipaddr,t.netmask)||!/^[0-9a-f]{64}$/.test(t._lanRevision||""))return;if(!window.confirm("Save LAN configuration for next manual activation? Record the new IP address."))return;t._lanBusy=true;var a={ipaddr:t.ipaddr,netmask:t.netmask,revision:t._lanRevision,confirmation:"SAVE_NETWORK"};t._lanRevision="";t.$req.post("/webapi?op=set_lan_config",a).then(function(r){if(!r||r.code!=="1")throw Error("Save rejected");t.$message.success("Saved for next manual activation; no redirect or automatic restart.");return t.get_lan_config()}).catch(function(){t.$message.error("LAN save not confirmed; refresh configuration.")}).finally(function(){t._lanBusy=false})}}'),
            ('this.timer=setInterval(this.get_lan_config,3e3)','this.timer=setInterval(this.get_lan_status,3e3)'),
        ))
        wan_name="chunk-4f3e33ae.e79f6535.js"
        wan_source=(files / "www/assets/js" / wan_name).read_text()
        wan_start=wan_source.index("handleSave:function()")
        wan_end=wan_source.index(",create_pppoe_interval:function()",wan_start)
        edit_chunk(wan_name, (
            ('var i=e.data;console.log(e.data),t.selected_protocol=i.proto',
             'if(!e||e.code!=="1"||!e.data)throw Error("WAN unavailable");t._wanRevision=e.revision;var i=e.data;t.selected_protocol=i.proto'),
            (wan_source[wan_start:wan_end],
             'handleSave:function(){var t=this;if(t._wanBusy||!/^[0-9a-f]{64}$/.test(t._wanRevision||""))return;var p=t.selected_protocol;if(p!=="dhcp"&&p!=="static"){t.$message.error("PPPoE profile creation is not available yet.");return}var a={proto:p,revision:t._wanRevision,confirmation:"SAVE_NETWORK"};if(p==="static"){Object.assign(a,{ipaddr:t.value_static[0],netmask:t.value_static[1],gateway:t.value_static[2],dns_primary:t.value_static[3]||"",dns_secondary:t.value_static[4]||""})}else Object.assign(a,{dns_primary:t.value_dhcp[0]||"",dns_secondary:t.value_dhcp[1]||""});if(!window.confirm("Save Ethernet WAN configuration for next manual activation?"))return;t._wanBusy=true;t._wanRevision="";t.$req.post("/webapi?op=set_wan_config",a).then(function(r){if(!r||r.code!=="1")throw Error("Save rejected");t.$message.success("Saved for next manual activation.");return t.get_wan_config()}).catch(function(){t.$message.error("WAN save not confirmed; refresh. Use native DNS settings for DNS changes.")}).finally(function(){t._wanBusy=false})}'),
        ))
        dhcp_name="chunk-003dfc75.536cfc93.js"
        edit_chunk(dhcp_name, (
            ('get_dhcp_config:function(){var t=this;this.$req.get','get_dhcp_config:function(){var t=this;return this.$req.get'),
            ('get_static_dhcp:function(){var t=this;this.$req.get','get_static_dhcp:function(){var t=this;return this.$req.get'),
            ('console.log(e.data),t.prefix=e.data.dhcp_head','if(!e||e.code!=="1"||!e.data)throw Error("DHCP unavailable");t._dhcpRevision=e.revision;t.prefix=e.data.dhcp_head'),
            ('var a=parseInt(e.data.dhcp_lease),i=Math.floor(a/3600),s=Math.floor(a/60%60);i>0?(t.$set(t.dhcp_state,3,i),t.$set(t.dhcp_state,4,"h")):(t.$set(t.dhcp_state,3,s),t.$set(t.dhcp_state,4,"m"))',
             'var m=/^([0-9]+)([smhd]?)$/.exec(String(e.data.dhcp_lease));if(!m)throw Error("Unsupported lease format");var a=Number(m[1])*({"":1,s:1,m:60,h:3600,d:86400}[m[2]]);if(a%60!==0)throw Error("Lease not a whole minute");a%3600===0?(t.$set(t.dhcp_state,3,a/3600),t.$set(t.dhcp_state,4,"h")):(t.$set(t.dhcp_state,3,a/60),t.$set(t.dhcp_state,4,"m"))'),
            ('this.proxy_req("get","/webapi?op=set_dhcp_config",s,(function(t){"1"==t.code&&e.get_dhcp_config()}),!0,this.$t("network.dhcp.resultMap"))',
             'if(e._dhcpBusy||!/^[0-9a-f]{64}$/.test(e._dhcpRevision||"")||!window.confirm("Apply DHCP pool settings? Client service may briefly restart."))return;e._dhcpBusy=true;Object.assign(s,{revision:e._dhcpRevision,confirmation:"SAVE_DHCP_POOL"});e._dhcpRevision="";e.$req.post("/webapi?op=set_dhcp_config",s).then(function(r){if(!r||r.code!=="1")throw Error("DHCP rejected");return e.get_dhcp_config()}).catch(function(){e.$message.error("DHCP save not confirmed; refresh.")}).finally(function(){e._dhcpBusy=false})'),
            ('"SL"==t.corporation&&e.arp_mac_list.forEach','if(!e||e.code!=="1"||!Array.isArray(e.data))throw Error("Reservation list unavailable");t._reservationRevision=e.revision;"SL"==t.corporation&&e.arp_mac_list.forEach'),
            ('console.log(e),this.proxy_req("post","/webapi?op=delete_static_dhcp",e,(function(t){"1"==t.code&&a.get_static_dhcp()}),!0)',
             'if(e.maclist.length!==1){a.$message.error("Select one reservation at a time.");return}if(!/^[0-9a-f]{64}$/.test(a._reservationRevision||"")){a.$message.error("Refresh reservation list.");return}window.confirm("Delete selected DHCP reservation?")&&(e.revision=a._reservationRevision,e.confirmation="DELETE_RESERVATION",a._reservationRevision="",a.$req.post("/webapi?op=delete_static_dhcp",e).then(function(r){if(!r||r.code!=="1")throw Error("Delete rejected");return a.get_static_dhcp()}).catch(function(){a.$message.error("Delete not confirmed; refresh. Select one reservation at a time.")}))'),
        ))
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
        home_adapter = adapter.parent / "home-adapter"
        shutil.copyfile(HERE / "backend/home-adapter.sh", home_adapter)
        home_adapter.chmod(0o755)
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
            '<article><h2>Firewall &amp; NAT</h2><p>WAN management remains blocked. Software offload only.</p>'
            '<button id="fw-refresh" type="button">Baca konfigurasi</button>'
            '<form id="fw-form"><label><input id="fw-drop" type="checkbox">Drop invalid packets</label>'
            '<label><input id="fw-syn" type="checkbox">SYN flood protection</label>'
            '<button id="fw-save" disabled>Simpan firewall</button></form>'
            '<form id="offload-form"><label><input id="fw-offload" type="checkbox">Software flow offload</label>'
            '<button id="offload-save" disabled>Simpan NAT offload</button></form>'
            '<p id="fw-result" role="status"></p></article>'
            '<article><h2>MAC access control (LAN to WAN)</h2><p>Blocks forwarded LAN traffic to WAN; router management remains available. Software offload is disabled when a block list is configured.</p>'
            '<button id="mac-refresh" type="button">Baca daftar</button><form id="mac-form">'
            '<label>MAC address, satu per baris<textarea id="mac-list" rows="5" maxlength="288"></textarea></label>'
            '<button id="mac-save" disabled>Simpan daftar</button></form><p id="mac-result" role="status"></p></article>'
            '<article><h2>Wi-Fi transmit power</h2><p>Power dBm, or auto. Manual setting must be within the current regulatory limit. No live radio restart.</p>'
            '<button id="power-refresh" type="button">Baca power</button><form id="power-form">'
            '<label>Power (auto atau dBm)<input id="power-value" required maxlength="4"></label>'
            '<button id="power-save" disabled>Simpan untuk boot berikutnya</button></form><p id="power-result" role="status"></p></article>'
            '<article><h2>Scheduled reboot (optional)</h2><p>Disabled by default. Enabling this schedule will interrupt connections at the selected time.</p>'
            '<button id="schedule-refresh" type="button">Baca jadwal</button><form id="schedule-form">'
            '<label><input id="schedule-enabled" type="checkbox">Enable scheduled reboot</label>'
            '<label>Hour<input id="schedule-hour" type="number" min="0" max="23" required></label>'
            '<label>Minute<input id="schedule-minute" type="number" min="0" max="59" required></label>'
            '<label>Days (0 Sunday to 6 Saturday, comma separated)<input id="schedule-days" required maxlength="13"></label>'
            '<button id="schedule-save" disabled>Simpan jadwal</button></form><p id="schedule-result" role="status"></p></article>'
            '<article><h2>Optional services: DDNS / SQM</h2><p>Requires an installed compatible addon and configured profile. Settings are saved for next boot; no automatic restart. SQM requires offload disabled.</p>'
            '<button id="optional-refresh" type="button">Baca status addon</button>'
            '<p id="ddns-result" role="status"></p><button id="ddns-toggle" disabled>Toggle DDNS</button>'
            '<button id="ddns-check" disabled>Check DNS lookup</button><pre id="ddns-lookup-result" class="result"></pre>'
            '<p id="sqm-result" role="status"></p><button id="sqm-toggle" disabled>Toggle SQM</button></article>'
            '<article><h2>IPv4 forwarding TTL (optional)</h2><p>Default disabled. Scope: LAN to WAN forwarding only, not locally originated traffic. Flow offload must be disabled.</p>'
            '<button id="ttl-refresh" type="button">Baca TTL</button><form id="ttl-form">'
            '<label><input id="ttl-enabled" type="checkbox">Enable forwarding TTL policy</label>'
            '<label>TTL (1–255)<input id="ttl-value" type="number" min="1" max="255" required value="64"></label>'
            '<button id="ttl-save" disabled>Simpan TTL</button></form><p id="ttl-result" role="status"></p></article>'
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
        for script in (cgi, adapter, writer, diagnostics, home_adapter, backup, verify, verify_gate, cgi.parent / "veci2-backup", cgi.parent / "veci2-restore"):
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
