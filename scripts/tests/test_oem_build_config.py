import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"rebuild/oem-updated"))
from check_build_config import check,REQUIRED,TARGET
class BuildConfig(unittest.TestCase):
 def test_resolved_config_contract(self):
  base="\n".join(sorted(k+"=y" for k in TARGET|{"CONFIG_PACKAGE_"+p for p in REQUIRED}))
  self.assertEqual(check(base),([],[]))
  self.assertIn("CONFIG_PACKAGE_coreutils-timeout",check(base.replace("CONFIG_PACKAGE_coreutils-timeout=y","CONFIG_PACKAGE_coreutils-timeout=m"))[0])
  self.assertIn("CONFIG_PACKAGE_luci-app-firewall",check(base+"\nCONFIG_PACKAGE_luci-app-firewall=y")[1])
  self.assertIn("CONFIG_PACKAGE_uspot",check(base+"\nCONFIG_PACKAGE_uspot=y")[1])
  self.assertIn("CONFIG_BUSYBOX_CONFIG_PING6",check(base+"\nCONFIG_BUSYBOX_CUSTOM=y")[0])
  with self.assertRaises(ValueError):check(base+"\nCONFIG_PACKAGE_coreutils-timeout=m")
