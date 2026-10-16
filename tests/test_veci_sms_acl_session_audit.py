"""Offline mock of the WE5927 read-only SMS ACL/session inventory. No router I/O."""
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/"scripts/veci-sms-acl-session-audit-20261013.sh"


class MockAclAudit(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.dir=Path(self.tmp.name)
        self.bin=self.dir/"bin"
        self.bin.mkdir()
        self.board=self.dir/"board_name"
        self.board.write_text("zbtlink,zbt-we5927\n")
        self.acl=self.dir/"veci-sms-inbox-we5927.json"
        self.acl.write_text('{"veci-sms-inbox-we5927":{"write":{"ubus":{"veci.sms":["listIndex"]}}}}\n')
        self.mock_log=self.dir/"command-log"
        commands={
            "uci": '''#!/bin/sh
echo "uci:$*" >> LOGFILE
case "$*" in
  "-q get rpcd.@login[0]") echo login ;;
  "-q get rpcd.@login[1]") echo login ;;
  "-q get rpcd.@login[2]") echo login ;;
  "-q get rpcd.@login[3]") exit 1 ;;
  "-q get rpcd.@login[0].write") echo '*' ;;
  "-q get rpcd.@login[1].write") echo 'veci' ;;
  "-q get rpcd.@login[2].write") echo 'veci-sms-inbox-we5927' ;;
  "-q get rpcd.@login["*"].read") echo 'veci' ;;
  *) exit 1 ;;
esac
''',
            "ubus": '''#!/bin/sh
echo "ubus:$*" >> LOGFILE
case "$1:$2:$3" in
 "list:veci.sms:") echo veci.sms ;;
 "call:session:access") echo '{"access":false}' ;;
 *) exit 1 ;;
esac
''',
            "jsonfilter": '''#!/bin/sh
if [ "$1" = "-e" ] && [ "$2" = "@.access" ]; then
  python3 -c 'import json,sys; print(str(json.load(sys.stdin)["access"]).lower())'
  exit $?
fi
if [ "$1" = "-i" ]; then echo listIndex; exit 0; fi
exit 1
'''
        }
        for name,body in commands.items():
            p=self.bin/name
            p.write_text(body.replace("LOGFILE",str(self.mock_log)))
            p.chmod(0o755)
        source=SCRIPT.read_text()
        source=source.replace("/tmp/sysinfo/board_name",str(self.board))
        source=source.replace("/usr/share/rpcd/acl.d/veci-sms-inbox-we5927.json",str(self.acl))
        self.script=self.dir/"run-audit.sh"
        self.script.write_text(source)
        self.env={**os.environ,"PATH":str(self.bin)+os.pathsep+os.environ.get("PATH","")}

    def run_audit(self):
        return subprocess.run(["sh",str(self.script)],capture_output=True,text=True,
                              timeout=4,env=self.env)

    def test_shell_syntax(self):
        p=subprocess.run(["sh","-n",str(SCRIPT)],capture_output=True,text=True)
        self.assertEqual(p.returncode,0,p.stderr)

    def test_wildcard_explicit_and_restricted_login_class(self):
        p=self.run_audit()
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertIn("LOGIN_0_WRITE_GRANT_CLASS=wildcard",p.stdout)
        self.assertIn("LOGIN_1_WRITE_GRANT_CLASS=restricted",p.stdout)
        self.assertIn("LOGIN_2_WRITE_GRANT_CLASS=explicit_sms_write",p.stdout)
        self.assertIn("LOGIN_COUNT=3",p.stdout)
        self.assertIn("ANONYMOUS_SMS_LIST_ACCESS=denied",p.stdout)
        self.assertIn("NON_ADMIN_SESSION_TEST=not_performed",p.stdout)

    def test_never_calls_sms_list_or_prints_password_or_tokens(self):
        p=self.run_audit()
        self.assertEqual(p.returncode,0,p.stderr)
        commands=self.mock_log.read_text()
        self.assertIn("ubus:call session access",commands)
        self.assertNotIn("listIndex {",commands)
        self.assertNotIn("veci.sms listIndex",commands)
        self.assertNotIn(".password",commands)
        self.assertNotIn(".username",commands)
        self.assertNotIn("rpcd.@login[0].password",commands)
        self.assertNotIn("00000000000000000000000000000000",p.stdout)
        self.assertIn("NO_SMS_MODEM_COMMAND_SENT=true",p.stdout)
        self.assertIn("NO_CREDENTIALS_OR_SESSION_TOKENS_EXPORTED=true",p.stdout)
        raw=SCRIPT.read_text()
        for unsafe in ("we5927-at", "AT+CMGL", "AT+CMGR", "AT+CUSD",
                       "ubus call veci.sms", "rpcd restart", "uci set",
                       "ubus call session login", "ubus call session grant", "ubus call session create",
                       "logger ", "sysupgrade "):
            self.assertNotIn(unsafe,raw)

    def test_anonymous_access_security_failure_flagged(self):
        p=self.bin/"ubus"
        p.write_text('#!/bin/sh\n'
                     'case "$1:$2:$3" in\n'
                     ' "list:veci.sms:") echo veci.sms ;;\n'
                     ' "call:session:access") echo \'{"access":true}\' ;;\n'
                     'esac\n')
        p.chmod(0o755)
        result=self.run_audit()
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn("ANONYMOUS_SMS_LIST_ACCESS=ALLOWED_SECURITY_FAILURE",result.stdout)

    def test_unknown_group_requires_review(self):
        p=self.bin/"uci"
        p.write_text('#!/bin/sh\n'
                     'case "$*" in\n'
                     ' "-q get rpcd.@login[0]") echo login ;;\n'
                     ' "-q get rpcd.@login[1]") exit 1 ;;\n'
                     ' "-q get rpcd.@login[0].write") echo "veci-*" ;;\n'
                     ' *) exit 1 ;;\n'
                     'esac\n')
        p.chmod(0o755)
        result=self.run_audit()
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn("LOGIN_0_WRITE_GRANT_CLASS=needs_manual_review",result.stdout)

    def test_wrong_board_fail_closed(self):
        self.board.write_text("other,router\n")
        p=self.run_audit()
        self.assertNotEqual(p.returncode,0)
        self.assertIn("SMS_ACL_AUDIT_ERROR=wrong_board",p.stdout)


if __name__=="__main__":
    unittest.main()
