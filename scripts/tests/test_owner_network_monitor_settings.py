"""One existing LTE monitor, configurable interval, no modem reset from VeCI."""
import json
from pathlib import Path
import subprocess, unittest
ROOT=Path(__file__).resolve().parents[2]
R=ROOT/'rebuild/veci-v2/packages/veci-v2-runtime'
UI=ROOT/'rebuild/veci-v2/packages/veci-v2-ui/files/www/veci2'
class NetworkMonitor(unittest.TestCase):
    def test_monitor_reuses_existing_modem_and_validates(self):
        p=R/'veci2-lte-policy'
        text=p.read_text()
        self.assertIn('setMonitor',text)
        self.assertIn('ping_interval',text)
        self.assertIn('stale_interval',text)
        self.assertIn('monitor_interval',text)
        self.assertIn('uci -q -t "$tmp" commit we5927_lte',text)
        for value in ("modprobe", "AT+CFUN", "gpio", "ifdown", "wifi reload", "reboot"):
            self.assertNotIn(value,text)
        subprocess.run(['sh','-n',str(p)],check=True)
    def test_rpc_and_panel_wired(self):
        acl=json.loads((R/'veci2-status-acl.json').read_text())
        self.assertIn('setMonitor',json.dumps(acl))
        html=(UI/'index.html').read_text()
        self.assertIn('monitor-settings.js',html)
        self.assertIn('id="monitor-save"',html)
        subprocess.run(['node','--check',str(UI/'monitor-settings.js')],check=True)
        output=subprocess.check_output(['sh',str(R/'veci2-lte-policy'),'list'],text=True)
        self.assertIn('setMonitor',output)
if __name__=='__main__':unittest.main()
