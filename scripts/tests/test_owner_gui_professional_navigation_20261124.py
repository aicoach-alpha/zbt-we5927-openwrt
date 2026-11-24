"""Professional 4-top-level native offline GUI, full nested routes and truthful graphs."""
from collections import Counter
from html.parser import HTMLParser
import re
import subprocess
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
WEB=ROOT/"rebuild/veci-v2/packages/veci-v2-ui/files/www/veci2"

class Document(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids=[]
        self.top=[]
        self.scopes=[]
        self.subtabs=[]
        self.panels=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if a.get("id"): self.ids.append(a["id"])
        if tag=="button" and "data-page" in a:self.top.append(a["data-page"])
        if tag=="nav" and "data-scope" in a:self.scopes.append(a["data-scope"])
        if tag=="button" and "subtab" in a.get("class",""):
            self.subtabs.append(a.get("data-group"))
        if tag=="article" and "data-group" in a:self.panels.append(a["data-group"])

class ProfessionalRouterGui(unittest.TestCase):
    def test_four_top_menu_and_submenu_routes(self):
        d=Document();d.feed((WEB/"index.html").read_text())
        self.assertEqual(d.top,["overview","network","sms","settings"])
        self.assertEqual(d.scopes,["overview","network","settings","sms"])
        self.assertEqual(len(d.ids),len(set(d.ids)),[x for x,n in Counter(d.ids).items() if n>1])
        for group in ("dashboard","health","sim","wifi","lan","lte","overview",
                      "system","network","security","firmware","messages","diagnostics"):
            self.assertIn(group,d.subtabs,group)
            self.assertIn(group,d.panels,group)
        for id in ("health-chart","traffic-chart","health-grid","status-grid",
                   "health-banner","internet-indicator","path-modem","path-router",
                   "path-clients","sms-diagnostics","session-permissions",
                   "firmware-check","wifi-extra","dns-form"):
            self.assertIn(id,d.ids)

    def test_css_is_offline_responsive_not_vendor_copy(self):
        css=(WEB/"app.css").read_text()
        for item in ("#workspace>.tabs", ".topology-strip", ".health-banner",
                     "@media(max-width:860px)", "@media(max-width:610px)",
                     "@media(prefers-reduced-motion:reduce)"):
            self.assertIn(item,css)
        for src in ("@import", "url(https:", "fonts.googleapis.com","font-awesome"):
            self.assertNotIn(src,css)

    def test_health_uses_authenticated_live_rpc_not_mocked_data(self):
        js=(WEB/"app.js").read_text()
        subprocess.run(["node","--check",str(WEB/"app.js")],check=True)
        for item in ("rpc('veci.v2','networkHealth'", "sampleTraffic",
                     "refreshHealth", "renderHealthChart", "unmanaged_netifd_count",
                     "memory_available_kb", "procd_netifd_owner_confirmed"):
            self.assertIn(item,js)
        self.assertNotIn("Math.random()",js)
        self.assertNotIn("localStorage",js)
        self.assertIn("setSubgroup(scope, groupButton.dataset.group)",js)
        self.assertIn("healthSeries.length < 2",js)
        self.assertIn("trafficSeries.length < 2",js)
if __name__=="__main__":
    unittest.main()
