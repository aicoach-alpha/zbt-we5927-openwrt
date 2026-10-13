"""v1.4 standalone predeploy UI: never alter checked-in LIVE/V13 artifacts."""
from pathlib import Path
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[1]
UI=ROOT/"scripts/veci-sms-private-ui-staged-20261013/cellular.js"
OLDER=ROOT/"scripts/veci-sms-inbox-ui-staged-20261013/cellular.js"
class StageV14(unittest.TestCase):
    def test_node_syntax(self):
        r=subprocess.run(["node","--check",str(UI)],text=True,
                         capture_output=True,timeout=12)
        self.assertEqual(r.returncode,0,r.stderr)
    def test_select_only_from_explicit_metadata_and_no_auto_sms(self):
        c=UI.read_text()
        self.assertIn("updatePrivateSlots(rows)",c)
        self.assertIn("listedSlots.has(slot)",c)
        self.assertIn("api.call('veci.sms', 'listIndex'",c)
        self.assertIn("privatePanel.hidden = listedSlots.size === 0",c)
        self.assertIn("const consent = await confirm(",c)
        self.assertIn("if (!consent || !root.isConnected",c)
        self.assertLess(c.index("const consent = await confirm("),c.index("api.call('veci.sms.private', 'armRead'"))
        self.assertLess(c.index("api.call('veci.sms.private', 'armRead'"),c.index("api.call('veci.sms.private', 'readSlot'"))
    def test_private_data_in_textcontent_only_and_not_cached(self):
        c=UI.read_text()
        self.assertIn("message.textContent =",c)
        self.assertIn("decodePrivatePdu(result.pdu)",c)
        self.assertIn("TextDecoder('utf-16be'",c)
        self.assertIn("message.textContent = ''",c)
        self.assertIn("privateOutput.replaceChildren(message)",c)
        self.assertIn("setTimeout(() => {",c)
        self.assertNotIn("privateOutput.innerHTML",c)
        self.assertNotIn("localStorage.setItem",c)
        self.assertNotIn("sessionStorage.setItem",c)
        self.assertNotIn("console.log",c)
        self.assertNotIn("AT+CMGR=",c)
    def test_older_ui_untouched_and_v14_never_auto_published(self):
        c=UI.read_text()
        self.assertIn("I_CONFIRM_READ_THIS_ONE_SMS",c)
        self.assertNotIn("api.call('veci.sms.private'",OLDER.read_text())
        self.assertNotIn("veci-sms-private-ui-staged", (ROOT/"source/we5927-lte/Makefile").read_text())
        self.assertNotIn("veci-sms-private-ui-staged",(ROOT/"scripts/veci-sms-inbox-admin-ui-v131-install.sh").read_text())
if __name__=="__main__":
    unittest.main()
