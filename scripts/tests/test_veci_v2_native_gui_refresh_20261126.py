"""Native GUI redesign: correct navigation and no new router backend."""
from html.parser import HTMLParser
from pathlib import Path
import re
import subprocess
import unittest
ROOT=Path(__file__).resolve().parents[2]
UI=ROOT/"rebuild/veci-v2/packages/veci-v2-ui/files/www/veci2"
INDEX=(UI/"index.html").read_text()
APP=(UI/"app.js").read_text()
CSS=(UI/"veci-design.css").read_text()
MAKE=(ROOT/"rebuild/veci-v2/packages/veci-v2-ui/Makefile").read_text()
class Elements(HTMLParser):
 def __init__(self):
  super().__init__(convert_charrefs=True)
  self.elements=[]
  self.ids=set()
 def handle_starttag(self,tag,attrs):
  a=dict(attrs)
  self.elements.append((tag,a))
  if "id" in a:
   if a["id"] in self.ids: raise AssertionError("Duplicate ID "+a["id"])
   self.ids.add(a["id"])
class NativeUiRefresh(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.html=Elements()
  cls.html.feed(INDEX)
 def test_shortcuts_target_existing_panels(self):
  scopes={}
  for scope in ("overview","network","sms","settings"):
   part=INDEX.split('<section id="'+scope+'"',1)[1].split("</nav>",1)[0]
   scopes[scope]=set(re.findall(r'<button[^>]*class="subtab[^"]*"[^>]*data-group="([^"]+)"',part))
  links=[(a.get("data-target-page"),a.get("data-target-group"))
         for tag,a in self.html.elements if a.get("data-target-page")]
  self.assertGreaterEqual(len(links),13)
  for page,group in links:
   with self.subTest(page=page,group=group):
    self.assertIn(page,scopes)
    self.assertIn(group,scopes[page])
  self.assertEqual({x[0] for x in links},set(scopes))
 def test_no_new_external_dependencies_or_router_writes(self):
  self.assertIn('/veci2/veci-design.css',INDEX)
  self.assertIn('veci-design.css $(1)/www/veci2/veci-design.css',MAKE)
  self.assertNotIn('@import', CSS); self.assertNotIn('url(', CSS); self.assertNotIn('http://', CSS); self.assertNotIn('https://', CSS); self.assertNotIn('@font-face', CSS)
  shortcut=APP.split('function navigateShortcut',1)[1].split('function showWorkspace',1)[0]
  for forbidden in ('innerHTML','rpc(','fetch(','wifi up','uci '):
   self.assertNotIn(forbidden,shortcut)
  self.assertIn('if (!sid) return;',shortcut)
  for route in ('sim','wifi','lan','lte','network','security','firmware','health'):
   self.assertIn('data-target-group="'+route+'"',INDEX)
 def test_live_status_not_claiming_beacon_or_clients(self):
  for eid in ('shell-lte-status','shell-wifi-status','shell-router-status',
              'mobile-nav-toggle','mobile-nav-dismiss','mobile-nav-backdrop'):
   self.assertIn(eid,self.html.ids)
  self.assertIn('updateShellStatus',APP)
  self.assertIn("data.wifi_ap_enabled === true",APP)
  self.assertIn("AP aktif · klien belum diuji",APP)
  self.assertIn("Online · HTTPS & DNS PASS",APP)
  self.assertIn("if (sid !== session) return;",APP)
 def test_mobile_a11y(self):
  for marker in ('aria-controls="veci-primary-nav"','aria-expanded="false"',
                 'aria-label="Tutup menu navigasi"'):
   self.assertIn(marker,INDEX)
  self.assertIn("event.key === 'Escape'",APP)
  self.assertIn("closeMobileNav()",APP)
  self.assertIn('prefers-reduced-motion:reduce',CSS)
  self.assertIn(':focus-visible',CSS)
  self.assertIn('body.veci-nav-open',CSS)
 def test_javascript_syntax(self):
  for js in UI.glob("*.js"):
   result=subprocess.run(["node","--check",str(js)],capture_output=True,text=True,timeout=5)
   self.assertEqual(result.returncode,0,js.name+" "+result.stderr)
if __name__=="__main__":unittest.main()
