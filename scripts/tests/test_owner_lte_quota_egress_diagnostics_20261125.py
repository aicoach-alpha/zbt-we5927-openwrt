"""Operator quota may be depleted while modem 192.168.7.1 stays connected.

All probes are read-only, bounded and do not assert that quota is exhausted.
"""
import json
from pathlib import Path
import os
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
BACKEND=ROOT/"rebuild/veci-v2/packages/veci-v2-runtime/veci2-status"
FRONTEND=ROOT/"rebuild/veci-v2/packages/veci-v2-ui/files/www/veci2/app.js"


class QuotaEgressTruth(unittest.TestCase):
    def source_case(self):
        s=BACKEND.read_text()
        self.assertIn("    call:internetCheck)",s)
        chunk=s.split("    call:internetCheck)",1)[1].split("    call:smsDiagnostics)",1)[0]
        # Replace only the netdev presence guard in a hermetic shell test.
        self.assertIn('if [ ! -d /sys/class/net/usb0 ]; then',chunk)
        chunk=chunk.replace("if [ ! -d /sys/class/net/usb0 ]; then",
                            'if [ ! -d "$TEST_NETDEV" ]; then')
        return chunk

    def simulate(self, primary_exit, primary_http, direct_exit, direct_http,
                 modem_exit, modem_http, dev=True):
        with tempfile.TemporaryDirectory() as d:
            devpath=Path(d)/"usb0"
            if dev: devpath.mkdir()
            chunk=self.source_case()
            body=r"""
curl() {
  case " $* " in
    *"https://www.cloudflare.com/cdn-cgi/trace"*)
       printf '%s' "$PRIMARY_HTTP"; return "$PRIMARY_EXIT" ;;
    *"https://one.one.one.one/"*)
       printf '%s' "$DIRECT_HTTP"; return "$DIRECT_EXIT" ;;
    *"http://192.168.7.1/"*)
       printf '%s' "$MODEM_HTTP"; return "$MODEM_EXIT" ;;
    *) echo "UNEXPECTED_PROBE" >&2; return 99 ;;
  esac
}
case call:internetCheck in
    call:internetCheck)""" + chunk + """
esac
"""
            env=dict(os.environ,TEST_NETDEV=str(devpath),
                     PRIMARY_EXIT=str(primary_exit),PRIMARY_HTTP=str(primary_http),
                     DIRECT_EXIT=str(direct_exit),DIRECT_HTTP=str(direct_http),
                     MODEM_EXIT=str(modem_exit),MODEM_HTTP=str(modem_http))
            r=subprocess.run(["sh","-c",body],capture_output=True,text=True,env=env,timeout=6)
            self.assertEqual(r.returncode,0,r.stderr)
            return json.loads(r.stdout.strip())

    def test_quota_exhaustion_pattern_does_not_claim_quota_is_certain(self):
        s=self.simulate(28,"000",35,"000",0,"200")
        self.assertFalse(s["verified"])
        self.assertTrue(s["modem_http_verified"])
        self.assertEqual(s["reason"],"modem_connected_public_unavailable_check_quota")
        self.assertEqual(s["source"],"usb0_https")
        self.assertNotIn("quota_exhausted",s)

    def test_public_https_without_dns_keeps_dns_unverified(self):
        s=self.simulate(28,"000",0,"200",0,"200")
        self.assertFalse(s["verified"])
        self.assertTrue(s["public_https_verified"])
        self.assertFalse(s["dns_verified"])
        self.assertEqual(s["reason"],"hostname_dns_or_endpoint_unavailable")

    def test_verified_public_dns_and_https_pass(self):
        s=self.simulate(0,"200",99,"000",99,"000")
        self.assertTrue(s["verified"])
        self.assertTrue(s["dns_verified"])
        self.assertEqual(s["reason"],"verified_public_https_and_dns")

    def test_modem_down_is_not_labelled_quota(self):
        s=self.simulate(28,"000",28,"000",28,"000")
        self.assertFalse(s["verified"])
        self.assertFalse(s["modem_http_verified"])
        self.assertEqual(s["reason"],"public_and_modem_unavailable")

    def test_no_interface_shortcircuits_without_probes(self):
        s=self.simulate(28,"000",28,"000",0,"200",dev=False)
        self.assertFalse(s["verified"])
        self.assertEqual(s["reason"],"lte_interface_unavailable")

    def test_read_only_bounded_probes_preserve_tls_verification(self):
        s=self.source_case()
        subprocess.run(["sh","-n",str(BACKEND)],check=True)
        self.assertEqual(s.count("curl --disable --ipv4"),3)
        self.assertEqual(s.count("--interface 'if!usb0'"),3)
        self.assertEqual(s.count("--max-time"),3)
        self.assertIn("--resolve 'one.one.one.one:443:1.1.1.1'",s)
        for action in ("--insecure"," -k ","kill ","pkill","killall","reboot",
                       "sysupgrade","uci ","ifdown","ifup","/etc/init.d/network"):
            self.assertNotIn(action,s,action)

    def test_gui_distinguishes_modem_registration_from_data_plan(self):
        s=FRONTEND.read_text()
        subprocess.run(["node","--check",str(FRONTEND)],check=True)
        for expected in ("modem_connected_public_unavailable_check_quota",
                         "hostname_dns_or_endpoint_unavailable",
                         "Periksa kuota/paket data atau gangguan operator",
                         "Modem aktif, internet publik gagal",
                         "HTTPS publik tanpa DNS berhasil"):
            self.assertIn(expected,s,expected)
        self.assertNotIn("kuota pasti habis",s.lower())

if __name__=="__main__":unittest.main()
