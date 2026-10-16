"""Source-only UCI/runtime auth check must fail closed without dumping secrets."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "scripts/veci-sms-auth-effective-preflight-20261013.sh"

class EffectiveAuthPreflight(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        (self.base / "bin").mkdir()
        (self.base / "proc/111").mkdir(parents=True)
        (self.base / "proc/111/cmdline").write_bytes(b"/usr/sbin/uhttpd\0-f\0-p\0:80\0")
        (self.base / "proc/111/maps").write_text("aaa /usr/lib/uhttpd_ubus.so\n")
        uci = self.base / "bin/uci"
        uci.write_text("#!/bin/sh\n[ \"$1\" = -q ] || exit 3\n"
            "echo \"uhttpd.main=uhttpd\"\n"
            "echo \"uhttpd.main.no_ubusauth='0'\"\n"
            "echo \"uhttpd.main.ubus_noauth='1'\"\n"  # old WRONG option
            "echo \"uhttpd.main.ubus_cors='0'\"\n"
            "echo \"uhttpd.main.password='SENSITIVE_NOT_FOR_OUTPUT'\"\n")
        uci.chmod(0o755)
        ubus = self.base / "bin/ubus"
        ubus.write_text("#!/bin/sh\nif [ \"$1\" = -S ]; then echo veci.sms; fi\n")
        ubus.chmod(0o755)
        pidof = self.base / "bin/pidof"
        pidof.write_text("#!/bin/sh\n[ \"$1\" = uhttpd ] && echo 111\n")
        pidof.chmod(0o755)
        self.env = {**os.environ, "PATH": str(self.base/"bin")+":"+os.environ["PATH"]}
        self.path = self.base/"check.sh"
        source = SRC.read_text().replace("PROC_ROOT=/proc",f"PROC_ROOT={self.base}/proc")
        # Only redirect fixture path; never write real /proc.
        source = source.replace("/usr/lib/uhttpd_ubus.so",str(self.base/"module/uhttpd_ubus.so"))
        source = source.replace("/usr/lib/rpcd/ucode.so",str(self.base/"module/ucode.so"))
        (self.base/"module").mkdir()
        (self.base/"module/uhttpd_ubus.so").write_text("")
        (self.base/"module/ucode.so").write_text("")
        self.path.write_text(source)

    def run_check(self):
        p = subprocess.run(["sh",str(self.path)],env=self.env,text=True,
                           capture_output=True,timeout=6)
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertNotIn("SENSITIVE_NOT_FOR_OUTPUT",p.stdout+p.stderr)
        self.assertIn("SMS_MODEM_COMMAND_SENT=false",p.stdout)
        self.assertIn("BROWSER_SESSION_BINDING=unverified",p.stdout)
        return p.stdout

    def test_invalid_legacy_option_is_not_mistaken_for_real_auth(self):
        out=self.run_check()
        self.assertIn("UHTTPD_NO_UBUSAUTH_UCI=not_enabled",out)
        self.assertIn("UHTTPD_NO_UBUSAUTH_RUNTIME=not_enabled",out)
        self.assertIn("UHTTPD_UBUS_MODULE_FILE=present",out)
        self.assertIn("UHTTPD_UBUS_MODULE_LOADED=present",out)

    def test_actual_no_ubusauth_uci_flag_is_red(self):
        p=self.base/"bin/uci"
        p.write_text(p.read_text().replace("no_ubusauth='0'","no_ubusauth='1'"))
        out=self.run_check()
        self.assertIn("UHTTPD_NO_UBUSAUTH_UCI=enabled_NO_GO",out)
        self.assertIn("AUTH_BACKEND_GATE=NO_GO_auth_disabled",out)

    def test_runtime_a_flag_is_red_even_with_safe_uci(self):
        (self.base/"proc/111/cmdline").write_bytes(b"/usr/sbin/uhttpd\0-a\0-f\0")
        out=self.run_check()
        self.assertIn("UHTTPD_NO_UBUSAUTH_RUNTIME=enabled_NO_GO",out)
        self.assertIn("AUTH_BACKEND_GATE=NO_GO_auth_disabled",out)

    def test_runtime_unreadable_cannot_claim_safe(self):
        (self.base/"proc/111/cmdline").unlink()
        out=self.run_check()
        self.assertIn("UHTTPD_NO_UBUSAUTH_RUNTIME=unknown",out)
        self.assertIn("AUTH_BACKEND_GATE=needs_review",out)

    def test_cors_flag_detected_but_no_credentials_dumped(self):
        p=self.base/"bin/uci"
        p.write_text(p.read_text().replace("ubus_cors='0'","ubus_cors='1'"))
        (self.base/"proc/111/cmdline").write_bytes(b"/usr/sbin/uhttpd\0-X\0")
        out=self.run_check()
        self.assertIn("UHTTPD_UBUS_CORS_UCI=enabled_REVIEW",out)
        self.assertIn("UHTTPD_UBUS_CORS_RUNTIME=enabled_REVIEW",out)

    def test_no_modem_or_mutation_in_source(self):
        s=SRC.read_text()
        for forbidden in ("AT+CMGR","AT+CMGL","AT+CUSD","uci set",
                          "ubus call","sysupgrade","reboot","opkg install",
                          "/etc/init.d/rpcd restart","/dev/ttyUSB"):
            self.assertNotIn(forbidden,s)
        self.assertEqual(subprocess.run(["sh","-n",str(SRC)]).returncode,0)
        self.assertNotIn("veci-sms-auth-effective-preflight", (ROOT/"source/we5927-lte/Makefile").read_text())

if __name__=="__main__":
    unittest.main()
