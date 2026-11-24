"""Physical failure reproduction: refuse duplicate/unknown netifd; never auto-kill."""
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
SOURCE=ROOT/"source/we5927-lte/files/usr/sbin/we5927-lte"
MIRROR=ROOT/"files/usr/sbin/we5927-lte"

def func(name):
    m=re.search(rf"(?ms)^{name}\(\) \{{\n.*?^\}}\n",SOURCE.read_text())
    assert m,name
    return m.group()

class SingleOwnerGate(unittest.TestCase):
    def test_no_generic_ifup_or_global_network_reload_in_lte_source(self):
        s=SOURCE.read_text()
        self.assertEqual(SOURCE.read_bytes(),MIRROR.read_bytes())
        subprocess.run(["sh","-n",str(SOURCE)],check=True)
        executable="\n".join(x for x in s.splitlines() if not x.lstrip().startswith("#"))
        for forbidden in ("ifup lte", "ifdown lte", "killall netifd",
                          "pkill netifd", "/sbin/netifd &", "ubus call network reload",
                          "/etc/init.d/network reload", "/etc/init.d/network restart"):
            self.assertNotIn(forbidden,executable,forbidden)
        for phrase in ('network_manager_safe() {','lte_netifd_call() {',
                       'call network.interface.lte "$method"',
                       'stage=network_manager_anomaly',
                       'CFUN reconnect held: network manager conflict',
                       'Unexpected netifd ownership or duplicate'):
            if phrase == 'Unexpected netifd ownership or duplicate':
                phrase='Duplicate/unowned netifd detected'
            self.assertIn(phrase,s,phrase)

    def manager(self, pids, owner, exe='/sbin/netifd', ppid='1', state='S'):
        with tempfile.TemporaryDirectory() as d:
            base=Path(d)
            status=base/"proc"/"1366"/"status"
            status.parent.mkdir(parents=True)
            status.write_text(f"Name:\tnetifd\nPPid:\t{ppid}\nState:\t{state}\n")
            (status.parent/"exe").symlink_to(exe)
            function=func("network_manager_safe")
            function=function.replace('/proc/',str(base/"proc")+'/')
            stubs=f"""
pidof() {{ echo '{pids}'; }}
ubus() {{ echo owner_data; }}
jsonfilter() {{ echo '{owner}'; }}
"""
            script=stubs+function+"\nnetwork_manager_safe; echo MANAGER_RC=$?\n"
            r=subprocess.run(["sh","-c",script],capture_output=True,text=True,timeout=4)
            self.assertEqual(r.returncode,0,r.stderr)
            return int(r.stdout.strip().split('=')[-1])
    def test_sole_procd_managed_netifd_allowed(self):
        self.assertEqual(self.manager('1366','1366'),0)
    def test_duplicate_netifd_refuses_unsafe_recovery(self):
        self.assertNotEqual(self.manager('16862 1366','1366'),0)
    def test_unowned_or_reparented_process_refused(self):
        self.assertNotEqual(self.manager('1366',''),0)
        self.assertNotEqual(self.manager('1366','1366',ppid='16854'),0)
    def test_wrong_binary_refused(self):
        self.assertNotEqual(self.manager('1366','1366',exe='/bin/ash'),0)
    def test_lte_call_is_scoped_and_does_not_mutate_when_duplicate(self):
        stub="""
calls=0
network_manager_safe() { return 1; }
log() { :; }
ubus() { echo SHOULD_NOT_RUN; }
"""
        script=stub+func("lte_netifd_call")+"\nlte_netifd_call down; echo RC=$?\n"
        r=subprocess.run(["sh","-c",script],text=True,capture_output=True,timeout=4)
        self.assertEqual(r.stdout.strip(),"RC=3")
        self.assertNotIn("SHOULD_NOT_RUN",r.stdout)
    def test_good_single_owner_uses_only_lte_interface_method(self):
        stub="""
network_manager_safe() { return 0; }
log() { :; }
ubus() { case "$*" in *"network.interface.lte up"*) echo ONLY_LTE; return 0;; esac; return 2; }
"""
        # The reviewed function suppresses ubus stdout, so use exit code.
        script=stub+func("lte_netifd_call")+"\nlte_netifd_call up; echo RC=$?\n"
        r=subprocess.run(["sh","-c",script],text=True,capture_output=True,timeout=4)
        self.assertEqual(r.stdout.strip(),"RC=0")
if __name__=="__main__":
    unittest.main()
