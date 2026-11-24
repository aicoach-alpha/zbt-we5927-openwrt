"""Source-level authentication and ACL acceptance for VeCI on exact ZBT board.

Runs the real browser login/logout state machine using the existing VM fixture,
validates RPC ACL separation and rejects persistent credentials in the source.
Not a real-router HTTPS/hardware UAT.
"""
import json
from pathlib import Path
import re
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[2]
PACKAGES=ROOT/"rebuild/veci-v2/packages"
UI=(PACKAGES/"veci-v2-ui/files/www/veci2/app.js")
ACL=(PACKAGES/"veci-v2-runtime/veci2-status-acl.json")
FIXTURE=ROOT/"scripts/tests/fixtures/veci_ui_sessions.js"


class OwnerLoginAcceptance(unittest.TestCase):
    def test_real_login_logout_session_state_machine(self):
        proc=subprocess.run(["node",str(FIXTURE),str(UI)],
                            capture_output=True,text=True,timeout=16)
        self.assertEqual(proc.returncode,0,proc.stdout+"\n"+proc.stderr)
        # The VM fixture checks HTTPS-only login, invalid/zero SIDs,
        # duplicate submits, session status, password clearing, and logout.
        source=FIXTURE.read_text()
        for guard in ("location.protocol = 'https:'", "for (const bad of",
                      "assert.equal(calls.length, 4)",
                      "assert.deepEqual(calls[5]", "assert.equal(reloads, 1)",
                      "assert.equal(element('password').value, '')"):
            self.assertIn(guard,source)

    def test_session_token_scope_and_no_credential_persistence(self):
        src=UI.read_text()
        self.assertIn("location.protocol !== 'https:'",src)
        self.assertIn("location.hostname !== 'localhost'",src)
        self.assertIn("const ROOT_SID = '00000000000000000000000000000000'",src)
        self.assertIn("!/^[0-9a-f]{32}$/.test(token)",src)
        self.assertIn("sid = '';",src)
        self.assertIn("el('password').value = ''",src)
        self.assertIn("rpc('session', 'login', {username, password}, ROOT_SID)",src)
        self.assertNotIn("localStorage",src)
        self.assertNotIn("sessionStorage",src)
        self.assertNotIn("document.cookie",src)
        self.assertNotIn("eval(",src)
        self.assertRegex(src,r"rpc\('session', 'destroy', \{\}, old\)")

    def test_read_only_acl_and_write_scopes_are_separated(self):
        acl=json.loads(ACL.read_text())
        base=acl["veci-v2-runtime"]
        self.assertEqual(base["write"]["ubus"],{})
        self.assertEqual(base["read"]["ubus"]["session"],["destroy"])
        self.assertEqual(set(base["read"]["ubus"]["veci.v2"]),
                         {"status","capabilities","smsProvider","ethernetPorts", "traffic", "internetCheck", "smsDiagnostics", "networkHealth"})
        self.assertNotIn("unauthenticated",acl)
        protected={
            "veci.v2.firewall":"veci-v2-firewall",
            "veci.v2.dns":"veci-v2-dns",
            "veci.v2.lte":"veci-v2-lte",
        }
        for object_name,grant in protected.items():
            with self.subTest(grant=grant):
                self.assertIn(object_name,acl[grant]["write"]["ubus"])
                self.assertNotIn(object_name,base["write"]["ubus"])
        for grant,definition in acl.items():
            self.assertFalse("write" in definition and "ubus" in definition["write"] and
                             "session" in definition["write"]["ubus"] and
                             "login" in definition["write"]["ubus"]["session"],
                             "login should be explicitly handled through session at ubus")

    def test_rpc_uses_token_with_server_side_permission_checks(self):
        src=UI.read_text()
        self.assertIn("params: [session, object, method, args]",src)
        self.assertIn("credentials: 'same-origin'",src)
        self.assertIn("payload.result[0] !== 0",src)
        self.assertIn("request.abort()",src)
        # No changes to radio/modem unless a separately-authorized RPC write.
        self.assertNotIn("AT+CFUN",src)
        self.assertNotIn("gpio_set",src)

if __name__=="__main__":
    unittest.main()
