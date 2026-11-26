#!/usr/bin/env python3
"""Source contract: modem controls must be discoverable and never fake PDP activation."""
import json
from pathlib import Path
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[2]
UI=ROOT/"rebuild/veci-v2/packages/veci-v2-ui/files/www/veci2"
RUNTIME=ROOT/"rebuild/veci-v2/packages/veci-v2-runtime"
CAP=ROOT/"source/veci-cellular-we5927/files/usr/libexec/veci-modem-capabilities"
class Controls(unittest.TestCase):
 def test_lte_controls_are_in_lte_tab_without_duplicate_ids(self):
  html=(UI/"index.html").read_text()
  block=html.split('<article class="panel lte-control-panel" data-group="sim">')[1].split("</article>",1)[0]
  for control in ("lte-connection-enable","lte-reconnect","lte-status-refresh","lte-apn-form","lte-policy-change"):
   self.assertIn('id="'+control+'"',block)
   self.assertEqual(html.count('id="'+control+'"'),1)
  self.assertIn('data-group="sim"',html)
  self.assertIn('data-group="dashboard"',html)
 def test_modem_reconnect_is_existing_backend_not_browser_http_guess(self):
  js=(UI/"app.js").read_text()
  self.assertIn("rpc('veci.cellular','reconnect',{},session",js)
  self.assertIn('result.queued!==true',js)
  self.assertIn('refreshLtePathStatus()',js)
  self.assertIn('data.connection_enabled',js)
  self.assertIn('window.confirm(',js)
  self.assertNotIn("AT+CGATT=1",js)
  self.assertNotIn("AT+CGACT=1",js)
  subprocess.run(["node","--check",str(UI/"app.js")],check=True)
 def test_connection_policy_method_is_guarded_and_does_not_fake_online(self):
  s=(RUNTIME/"veci2-lte-policy").read_text()
  self.assertIn('enableConnection',s)
  self.assertIn('ENABLE_CONNECTION',s)
  self.assertIn('activation_requested',s)
  self.assertIn('connection_enabled',s)
  for disallowed in ("AT+CFUN=1","AT+CGATT=1","AT+CGACT=1","ifdown","ifup","/sbin/reboot","power_cycle"):
   self.assertNotIn(disallowed,s)
  subprocess.run(["sh","-n",str(RUNTIME/"veci2-lte-policy")],check=True)
  acl=json.loads((RUNTIME/"veci2-status-acl.json").read_text())
  self.assertIn('enableConnection',acl["veci-v2-lte"]["write"]["ubus"]["veci.v2.lte"])
 def test_no_active_ussd_command_probe(self):
  self.assertNotIn('AT+CUSD',CAP.read_text())
  html=(UI/"index.html").read_text()
  self.assertNotIn('ussd',html.lower())
if __name__=="__main__":
 unittest.main()
