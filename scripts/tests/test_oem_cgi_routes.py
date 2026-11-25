"""Offline regression of OEM frontend CGI transport; no router mutation."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "rebuild/oem-updated"))
from stage_variant import route_oem_cgi

class OemCgiRouteTests(unittest.TestCase):
    def test_all_known_forms_and_lazy_chunks(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "assets").mkdir()
            main = root / "assets" / "app.js"
            chunk = root / "assets" / "chunk.js"
            main.write_text('const a="/webapi?op=get_web_msg",b="/webapi/?op=get_wan_info";')
            chunk.write_text("const a='/webapi/webapi?op=getWiFi2',b='/ubus';")
            self.assertEqual(route_oem_cgi(root), 3)
            self.assertIn('"/cgi-bin/webapi?op=get_web_msg"', main.read_text())
            self.assertIn('"/cgi-bin/webapi?op=get_wan_info"', main.read_text())
            self.assertIn("'/cgi-bin/webapi?op=getWiFi2'", chunk.read_text())
            self.assertIn("'/ubus'", chunk.read_text())
            self.assertEqual(route_oem_cgi(root), 0)

    def test_unknown_route_fails_closed(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "bad.js").write_text('const a="/webapi/unknown";')
            with self.assertRaises(ValueError):
                route_oem_cgi(root)
