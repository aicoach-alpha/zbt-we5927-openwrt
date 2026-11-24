"""Prevent repeating owner WE5927 Wi-Fi first-boot and router audit failures."""
from pathlib import Path
import hashlib
import re
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[2]
ROUTER=ROOT/"scripts/router"
FIRMWARE=ROOT/"source/we5927-lte/files/etc/uci-defaults/98-we5927-websafe"


class HardwareWifiGuard(unittest.TestCase):
    def test_readonly_audit_and_bounded_security(self):
        p=ROUTER/"veci-live-router-audit.sh"
        s=p.read_text()
        subprocess.run(["sh","-n",str(p)],check=True)
        self.assertIn("zbtlink,zbt-we5927",s)
        for area in ["WIFI_AP_DISABLED","WIFI_PHY0","WIFI_HOSTAPD_STATE",
                     "WIFI_KERNEL_MCU_FAULT_EVIDENCE","USB0_INTERFACE","LTE_BOUND_HTTPS",
                     "LAN_DHCP_PROCESS","FIREWALL4_EXEC","ROOT_PASSWORD_CONFIGURED",
                     "SMS_RPC_REGISTERED","TRUST_ANCHOR","STABILITY_72H"]:
            self.assertIn(area,s)
        for dangerous in ["uci -q set","uci -q commit","/etc/init.d/","sysupgrade -",
                          "wifi up","wifi reload","wifi down","reboot","AT+CFUN"]:
            self.assertNotIn(dangerous,s,dangerous)
        self.assertNotIn('printf %s "$(get wireless.default_radio0.key)"',s)
        self.assertIn("WIFI_AP_PSK_CONFIGURED",s)
        self.assertIn("ROOT_PASSWORD_CONFIGURED",s)
        self.assertIn("we5927_lte.main.sim",s)
        self.assertIn("WIFI_TIMEOUT_HELPER",s)
        self.assertIn("WIFI_RADIO_DISABLED",s)
        test=subprocess.run(["sh",str(p)],capture_output=True,text=True)
        self.assertNotEqual(test.returncode,0)
        self.assertIn("AUDIT_ABORT=wrong_board",test.stdout)

    def test_guarded_wifi_activation_has_backup_and_no_disruptive_network_actions(self):
        p=ROUTER/"veci-live-wifi-guarded-repair.sh"
        s=p.read_text()
        subprocess.run(["sh","-n",str(p)],check=True)
        for prereq in ["wrong_board","phy0_missing","lte_default_route_missing",
                       "prior_mt76_kernel_timeout_abort_to_preserve_router",
                       "pending_wireless_changes","WIFI_BACKUP=","cmp -s",
                       "wireless.default_radio0.encryption=psk2",
                       "wireless.radio0.disabled=0",
                       "wireless.default_radio0.disabled=0",
                       "network.wireless up","hostapd_ap_not_enabled_rollback",
                       "radio_up_but_ap_disabled_targeted_up_does_not_apply_uci",
                       "wireless.default_radio0.network=lan",
                       "sleep 75","success_flag","ubus -S -t 12",
                       "cp -p"]:
            self.assertIn(prereq,s,prereq)
        self.assertLess(s.index("radio_up_but_ap_disabled_targeted_up_does_not_apply_uci"),
                        s.index("backup_dir=/root/veci-router-uat"))
        commands="\n".join(line for line in s.splitlines() if not line.lstrip().startswith("#"))
        for dangerous in ["sysupgrade","reboot","ifdown","ifup","wifi reload",
                          "service network restart","/etc/init.d/network restart","network reload",
                          "AT+CFUN","mtd write","uci -q commit network"]:
            self.assertNotIn(dangerous,commands,dangerous)
        test=subprocess.run(["sh",str(p)],capture_output=True,text=True)
        self.assertNotEqual(test.returncode,0)
        self.assertTrue("WIFI_REPAIR_STOP=" in test.stdout)

    def test_kernel_uuid_keygen_branch_without_od_dependency(self):
        """Run the actual script branch (without UCI mutation or key disclosure)."""
        source=(ROUTER/"veci-live-wifi-guarded-repair.sh").read_text()
        self.assertNotIn(" | od ",source)
        self.assertIn("/proc/sys/kernel/random/uuid",source)
        self.assertIn('case "$key" in ????????????4*',source)
        code=source.split('if [ "$new_key" = yes ]; then',1)[1].split("\nfi",1)[0]
        program = """die() { exit 7; }
uci() { :; }
new_key=yes
if [ "$new_key" = yes ]; then
""" + code + """
fi
[ "$(printf %s "$key" | wc -c | tr -d ' ')" = 32 ] || exit 12
printf 'KEY_GENERATION_PASS\\n'
"""
        for _ in range(5):
            result=subprocess.run(["sh","-c",program],capture_output=True,
                                  text=True,timeout=5)
            self.assertEqual(result.returncode,0,result.stderr)
            self.assertEqual(result.stdout.strip(),"KEY_GENERATION_PASS")

    def test_windows_wrapper_validates_fingerprint_hash_and_redacts_wifi_password(self):
        s=(ROUTER/"VeCI-WE5927-Audit-and-Repair-WiFi.ps1").read_text()
        self.assertIn("StrictHostKeyChecking=yes",s)
        self.assertIn("SHA256:vTuQFuvd+br7jrfmqqNDN2FZxLtNNRYvOo3bDQ2Zlic",s)
        self.assertIn("Test-NetConnection",s)
        self.assertIn("InterfaceAlias",s)
        self.assertIn("Get-FileHash",s)
        self.assertIn("[REDACTED]",s)
        self.assertIn("NEW_WIFI_PASSWORD_PRIVATE_DO_NOT_SHARE=",s)
        for name in ["veci-live-router-audit.sh","veci-live-wifi-guarded-repair.sh"]:
            hash=hashlib.sha256((ROUTER/name).read_bytes()).hexdigest()
            self.assertIn(hash,s,name)
        self.assertNotIn("StrictHostKeyChecking=no",s)
        self.assertIn("$SavedPreference = $ErrorActionPreference",s)
        self.assertIn("$ErrorActionPreference = 'Continue'",s)
        self.assertIn("$ExitCode = $LASTEXITCODE",s)
        self.assertIn("AUDIT_END=OK",s)
        self.assertIn("WIFI_REPAIR_STATUS=AP_STARTED_CONFIGURATION_SAVED",s)
        self.assertIn("$SafePayload = $Text.TrimEnd([char[]]@([char]10,[char]13))",s)
        self.assertIn("'exit $?'",s)

    def test_terminal_cr_causes_127_and_append_exit_preserves_success(self):
        # Reproduces Windows PowerShell native stdin's terminal CR (ash sees
        # it as a command) and demonstrates the fail-closed transport fix.
        bad = subprocess.run(["sh","-s"],input="echo AUDIT_END=OK\n\r\n",
                             capture_output=True,text=True)
        self.assertEqual(bad.returncode,127)
        good = subprocess.run(["sh","-s"],input="echo AUDIT_END=OK\nexit $?\n\r\n",
                              capture_output=True,text=True)
        self.assertEqual(good.returncode,0)
        self.assertIn("AUDIT_END=OK",good.stdout)

    def test_first_boot_does_not_create_open_ap_and_wizard_still_required(self):
        s=FIRMWARE.read_text()
        self.assertIn("wireless.$radio.disabled=1",s)
        self.assertIn("wifi config",s)
        # Not a real-world UAT: this documents why an AP was inactive after -n flash.
        owner=(ROOT/"rebuild/veci-v2/contracts/owner-hardware-uat-20261124.json").read_text()
        self.assertIn("owner_decisions",owner)

if __name__=="__main__":
    unittest.main()
