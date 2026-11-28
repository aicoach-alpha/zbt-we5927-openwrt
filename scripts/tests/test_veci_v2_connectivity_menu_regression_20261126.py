"""Source-level integration gates for failures observed on the only physical WE5927.
Never call these offline PASSes physical LTE, Wi-Fi client or 72h UAT.
"""
from html.parser import HTMLParser
from pathlib import Path
import json, re, subprocess, tempfile, unittest

ROOT=Path(__file__).resolve().parents[2]
PKG=ROOT/"rebuild/veci-v2/packages"
UI=PKG/"veci-v2-ui/files/www/veci2"
RUNTIME=PKG/"veci-v2-runtime"
LTE=ROOT/"source/we5927-lte/files/usr/sbin/we5927-lte"

class IdInventory(HTMLParser):
 def __init__(self):super().__init__();self.ids=set();self.duplicates=[]
 def handle_starttag(self,tag,attrs):
  val=dict(attrs).get("id")
  if val:
   if val in self.ids:self.duplicates.append(val)
   self.ids.add(val)

class ConnectivityMenuRegressions(unittest.TestCase):
 def test_wifi_gui_control_ids_all_exist(self):
  html=IdInventory();html.feed((UI/"index.html").read_text())
  self.assertEqual(html.duplicates,[])
  for f in UI.glob("*.js"):
   ids=set(re.findall(r"""(?:el|\$|getElementById)\(['"]([A-Za-z0-9_-]+)['"]\)""",f.read_text()))
   self.assertEqual(ids-html.ids,set(),f.name)
  v=(UI/"index.html").read_text()
  wifi=v.split('<article class="panel wifi-primary-panel" data-group="wifi">',1)[1].split('</article>',1)[0]
  for token in ("wifi-name-form","wifi-visibility-change","wifi-activate-ap","wifi-auth"):
   if token=="wifi-auth":
    self.assertIn(token,v.split('data-group="wifi"',2)[-1])
   else:self.assertIn(token,wifi)
 def test_backend_rpc_discovery_matches_frontend_static_methods(self):
  providers={}
  for make in PKG.glob("*/Makefile"):
   for src,obj in re.findall(r"\$\(INSTALL_BIN\)\s+\./(\S+)\s+\$\(1\)/usr/libexec/rpcd/(\S+)",make.read_text()):
    providers[obj]=make.parent/src
  # SMS package is staged from the canonical (non-LuCI) VeCI SMS source.
  providers["veci.sms"]=ROOT/"source/veci-cellular-we5927/files/usr/libexec/rpcd/veci.sms"
  methods={}
  for name,path in providers.items():
   if not path.is_file(): continue
   result=subprocess.run(["sh",str(path),"list"],capture_output=True,text=True,timeout=4)
   self.assertEqual(result.returncode,0,name+":"+result.stderr)
   methods[name]=set(json.loads(result.stdout))
  self.assertIn("veci.v2.wifi",methods)
  self.assertIn("veci.v2.addon",methods)
  for file in UI.glob("*.js"):
   for obj,method in re.findall(r"""(?:\brpc|\bcall)\(\s*['"]([^'"]+)['"]\s*,\s*['"]([^'"]+)['"]""",file.read_text()):
    if not obj.startswith("veci."): continue
    self.assertIn(obj,methods,file.name+":"+obj)
    self.assertIn(method,methods[obj],file.name+":"+obj+"."+method)
  # Dynamic method routing (not visible to regex) must use correct provider.
  service=(UI/"services.js").read_text()
  self.assertIn("rpc('veci.v2.services', change ? 'save' : 'status'",service)
  self.assertNotIn("getElementById('addon-read')",service)
  self.assertNotIn("veci.v2.addon",service.replace("veci.v2.addon;",""))
  addon=(UI/"addon-profiles.js").read_text()
  self.assertIn("rpc('veci.v2.addon','status'",addon)
  self.assertTrue({"status","setVpnStartup","setPortalStartup"}<=methods["veci.v2.addon"])
 def test_activation_has_acl_and_one_shot_fail_closed(self):
  rpc=(RUNTIME/"veci2-wifi").read_text()
  helper=(RUNTIME/"veci2-wifi-activate").read_text()
  acl=json.loads((RUNTIME/"veci2-status-acl.json").read_text())["veci-v2-wifi"]
  self.assertIn("activationStatus",acl["read"]["ubus"]["veci.v2.wifi"])
  self.assertIn("activateAp",acl["write"]["ubus"]["veci.v2.wifi"])
  self.assertIn("PREPARE_WPA2_AP_NEXT_BOOT",rpc)
  self.assertIn("previous_activation_failed_manual_review_required",rpc)
  self.assertIn('wireless.default_radio0.encryption',helper)
  self.assertIn('wpa2_required',helper)
  self.assertIn('mt76_prior_error',helper)
  self.assertIn('record prepared_next_reboot',helper)
  self.assertIn('cp -p "$backup" /etc/config/wireless',helper)
  self.assertIn("config_restore_unverified",helper)
  self.assertNotIn("call network reload",helper.split("# This helper NEVER",1)[0])
  self.assertNotIn("ubus -S -t 12 call network reload",helper)
  self.assertNotIn("wifi up",helper.split("# This helper NEVER",1)[0])
  self.assertNotIn("sleep 75",helper)
  self.assertIn("enabled_unverified",rpc)
  self.assertIn("prepared_next_reboot",rpc)
  for forbidden in ("ifdown lte","ifup lte","AT+CFUN","sim 2","sysupgrade -",
                    "mtd write","/sbin/wifi up","/sbin/reboot"):
   self.assertNotIn(forbidden,"\n".join(x for x in helper.splitlines() if not x.strip().startswith("#")))
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp)
   q=helper.replace("/tmp/veci2-wifi-activate.state",str(root/"state"))
   q=q.replace("/tmp/veci2-wifi-activation.lock",str(root/"lock"))
   q=q.replace("/tmp/sysinfo/board_name",str(root/"non_router_board"))
   script=root/"activate.sh";script.write_text(q)
   res=subprocess.run(["sh",str(script)],capture_output=True,text=True,timeout=5)
   self.assertNotEqual(res.returncode,0)
   self.assertEqual((root/"state").read_text().strip(),"failed:wrong_board")
 def test_wifi_name_status_not_depend_optional_hexdump(self):
  src=(RUNTIME/"veci2-wifi").read_text()
  self.assertIn("ssid_value()",src)
  self.assertIn('json_add_string ssid "$configured"',src)
  self.assertNotIn("$(ssid_hex)",src)
  self.assertNotIn("| hexdump",src)
  self.assertIn("set +u\n. /usr/share/libubox/jshn.sh",src)
  js=(UI/"app.js").read_text()
  self.assertIn("typeof data.ssid === 'string'",js)
  self.assertIn("typeof data.ssid_hex === 'string'",js)
 def test_sim_readiness_before_apn_and_restore_only_once(self):
  source=LTE.read_text()
  other=(ROOT/"files/usr/sbin/we5927-lte").read_text()
  self.assertEqual(source,other)
  switch=source.rsplit("\ncase \"$1\" in",1)[1]
  self.assertIn("start_selected_sim require_ready",switch)
  handler=(RUNTIME/"veci2-sim-manual").read_text()
  self.assertIn("sim_switch_failed_previous_slot_restored",handler)
  self.assertIn("sim_switch_failed_rollback_unverified",handler)
 def test_source_syntax(self):
  files=[RUNTIME/"veci2-wifi",RUNTIME/"veci2-wifi-activate",
         RUNTIME/"veci2-sim-manual",LTE]
  for f in files:
   r=subprocess.run(["sh","-n",str(f)],capture_output=True,text=True,timeout=4)
   self.assertEqual(r.returncode,0,f.name+":"+r.stderr)
  for f in UI.glob("*.js"):
   r=subprocess.run(["node","--check",str(f)],capture_output=True,text=True,timeout=4)
   self.assertEqual(r.returncode,0,f.name+":"+r.stderr)

if __name__=="__main__":unittest.main()
