"""Field failure recurrence: DHCP DNS must not default to forced public DNS."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
DEFAULTS=ROOT/"source/we5927-lte/files/etc/uci-defaults/99-we5927-lte"
PATCH=ROOT/"source/openwrt-zbt-we5927-current.patch"

class LtePeerDnsDefaults(unittest.TestCase):
    def test_source_and_pin_patch_keep_same_peer_dns_default(self):
        source=DEFAULTS.read_text()
        patch=PATCH.read_text()
        subprocess.run(["sh","-n",str(DEFAULTS)],check=True)
        for line in (
            "set network.lte.peerdns='1'",
            "# Follow the operator/modem DHCP DNS by default.",
            'if [ "$(uci -q get network.lte)" != "interface" ]; then',
        ):
            self.assertIn(line,source)
            self.assertIn("+"+line,patch)
        self.assertNotIn("set network.lte.peerdns='0'",source)
        self.assertNotIn("add_list network.lte.dns=",source)
        self.assertNotIn("+add_list network.lte.dns=",patch)
        self.assertNotIn("+set network.lte.peerdns='0'",patch)

    def execute_defaults(self, existing: bool):
        with tempfile.TemporaryDirectory() as tmp:
            log=Path(tmp)/"calls.log"
            content=str(DEFAULTS)
            cmd=r"""
uci() {
  case "$*" in
    "-q get network.lte") [ "$EXISTING" = 1 ] && { echo interface; return 0; }; return 1 ;;
    "-q get network.wan") return 1 ;;
    "-q show firewall") return 0 ;;
    "-q get we5927_lte.main."*) return 1 ;;
    "-q set "*|"-q commit "*) echo "UCI_CALL:$*" >> "$LOGFILE"; return 0 ;;
    "-q batch")
      echo "UCI_BATCH_BEGIN" >> "$LOGFILE"
      cat >> "$LOGFILE"
      echo "UCI_BATCH_END" >> "$LOGFILE"
      return 0 ;;
    *) echo "UNEXPECTED_UCI:$*" >> "$LOGFILE"; return 1 ;;
  esac
}
. "$DEFAULTS_FILE"
"""
            env=dict(os.environ,EXISTING="1" if existing else "0",
                     LOGFILE=str(log),DEFAULTS_FILE=content)
            result=subprocess.run(["sh","-c",cmd],text=True,capture_output=True,env=env,timeout=5)
            self.assertEqual(result.returncode,0,result.stderr)
            return log.read_text()
    def test_first_install_uses_modem_dhcp_dns_not_static_adguard(self):
        out=self.execute_defaults(False)
        self.assertIn("set network.lte.proto='dhcp'",out)
        self.assertIn("set network.lte.peerdns='1'",out)
        self.assertNotIn("94.140.14.14",out)
        self.assertNotIn("94.140.15.15",out)
        self.assertIn("UCI_CALL:-q commit network",out)
    def test_existing_custom_dns_configuration_is_preserved(self):
        out=self.execute_defaults(True)
        self.assertNotIn("UCI_BATCH_BEGIN",out)
        self.assertNotIn("UCI_CALL:-q commit network",out)
        self.assertNotIn("network.lte.peerdns",out)

if __name__=="__main__":
    unittest.main()
