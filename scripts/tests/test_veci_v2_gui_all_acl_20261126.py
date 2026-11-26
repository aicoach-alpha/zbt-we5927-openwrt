"""Every direct GUI RPC must exist and be exposed by a narrow ACL."""
import json
from pathlib import Path
import re
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[2]
UI=ROOT/"rebuild/veci-v2/packages/veci-v2-ui/files/www/veci2"
PKG=ROOT/"rebuild/veci-v2/packages"

class NativeGuiRpcAcl(unittest.TestCase):
 def test_every_direct_rpc_has_method_and_permission(self):
  providers={}
  for make in PKG.glob("*/Makefile"):
   for source,provider in re.findall(r"\$\(INSTALL_BIN\)\s+\./(\S+)\s+\$\(1\)/usr/libexec/rpcd/(\S+)",make.read_text()):
    path=make.parent/source
    if path.is_file():providers[provider]=path
  providers["veci.sms"]=ROOT/"source/veci-cellular-we5927/files/usr/libexec/rpcd/veci.sms"
  self.assertGreaterEqual(len(providers),20)
  methods={}
  for provider,path in providers.items():
   result=subprocess.run(["sh",str(path),"list"],capture_output=True,text=True,timeout=3)
   self.assertEqual(result.returncode,0,provider+":"+result.stderr)
   methods[provider]=set(json.loads(result.stdout))
  permissions={}
  for file in list(PKG.rglob("*.json"))+list((ROOT/"source").rglob("*.json")):
   if "/acl.d/" not in str(file) and "-acl.json" not in file.name:continue
   try: acl=json.loads(file.read_text())
   except ValueError:continue
   for group,rights in acl.items():
    for role in ("read","write"):
     for provider,names in rights.get(role,{}).get("ubus",{}).items():
      permissions.setdefault(provider,set()).update(names)
  calls=set()
  for file in UI.glob("*.js"):
   for provider,method in re.findall(r"""(?:\brpc|\bcall)\(\s*['"]([^'"]+)['"]\s*,\s*['"]([^'"]+)['"]""",file.read_text()):
    if provider.startswith("veci."):calls.add((provider,method,file.name))
  self.assertGreaterEqual(len(calls),35)
  for provider,method,file in sorted(calls):
   with self.subTest(module=file,provider=provider,method=method):
    self.assertIn(provider,methods)
    self.assertIn(method,methods[provider])
    self.assertTrue(method in permissions.get(provider,set()) or
                    "*" in permissions.get(provider,set()))
  services=(UI/"services.js").read_text()
  for name in ("status","save"):
   self.assertIn(name,methods["veci.v2.services"])
   self.assertIn(name,permissions.get("veci.v2.services",set()))
  addons=(UI/"addon-profiles.js").read_text()
  for name in ("status","setVpnStartup","setPortalStartup"):
   self.assertIn(name,methods["veci.v2.addon"])
   self.assertIn(name,permissions.get("veci.v2.addon",set()))
  self.assertIn("veci.v2.addon",addons)
  self.assertNotIn("rpc('veci.v2.addon'",services)

if __name__=="__main__":unittest.main()
