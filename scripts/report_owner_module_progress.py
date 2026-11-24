#!/usr/bin/env python3
"""Truthful 27-module source progress from canonical contract and evidence.

The 'partial' label means source files exist in the owner worktree. It never
means the feature works on hardware. The initial 27 are frozen by the owner
source-reuse manifest so completed modules cannot vanish from the denominator.
"""
import json
import hashlib
from pathlib import Path
import re
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "rebuild/veci-v2/contracts/veci-v2-rebuild-contract.json"
EVIDENCE = ROOT / "rebuild/veci-v2/contracts/owner-final-source-evidence.json"
BASELINE = ROOT / "docs/SOURCE_REUSE_27_MODULES.md"
RUNTIME = "rebuild/veci-v2/packages/veci-v2-runtime/"

# A 'partial' entry requires each listed implementation and test file to
# actually exist. Other modules stay pending, even if an unrelated test passes.
PARTIAL = {
    "interface_wan_lan": [RUNTIME + "veci2-interfaces", "scripts/tests/test_owner_reuse_existing_source.py"],
    "addon_enable_disable": [RUNTIME + "veci2-addon", "scripts/tests/test_owner_addon_profiles_source.py"],
    "firmware_network_watchdog": [RUNTIME + "veci2-lte-policy", "scripts/tests/test_owner_network_monitor_settings.py"],
    "system_update_policy": [RUNTIME + "veci2-update-policy", "scripts/tests/test_owner_verify_only_default.py"],
    "router_login_and_permissions": ["rebuild/veci-v2/packages/veci-v2-ui/files/www/veci2/app.js", "scripts/tests/test_veci_ui_sessions.py"],
    "lte_rndis_data": ["source/we5927-lte/files/usr/sbin/we5927-lte", "scripts/tests/test_lte_rndis_identity.py"],
    "firmware_gpio_hardware_watchdog": [RUNTIME + "veci2-gpio-watchdog", "scripts/tests/test_gpio_watchdog_registration.py"],
    "guest_wifi_isolation": [RUNTIME + "veci2-guest-check", "scripts/tests/test_guest_isolation_readonly.py"],
    "ipv6_ra_dhcpv6": ["rebuild/veci-v2/packages/veci-v2-ipv6/files/usr/libexec/rpcd/veci2-ra", "scripts/tests/test_parallel_network_source.py"],
    "wifi_ap_2g": [RUNTIME + "veci2-wifi-controls", "scripts/tests/test_parallel_radio_source.py"],
    "wifi_survey_channel": [RUNTIME + "veci2-wifi-controls", "scripts/tests/test_parallel_radio_source.py"],
    "wifi_clients_access_control": [RUNTIME + "veci2-wifi-controls", "scripts/tests/test_parallel_radio_source.py"],
    "system_cron_scheduler": [RUNTIME + "veci2-cron", "scripts/tests/test_parallel_system_source.py"],
    "system_services_startup": [RUNTIME + "veci2-services", "scripts/tests/test_parallel_system_source.py"],
    "system_backup_restore": ["rebuild/veci-v2/packages/veci-v2-ui/files/www/cgi-bin/veci2-backup", "scripts/tests/test_parallel_security_source.py"],
    "dhcp_dns_static_leases": [RUNTIME + "veci2-dns", RUNTIME + "veci2-static-leases", "scripts/tests/test_owner_static_leases_source.py"],
    "firewall_zones_nat": [RUNTIME + "veci2-firewall", "scripts/tests/test_owner_firewall_source.py"],
    "port_forward_dmz": [RUNTIME + "veci2-firewall", "scripts/tests/test_owner_firewall_source.py"],
    "static_routes_policy": [RUNTIME + "veci2-routes", "scripts/tests/test_owner_reuse_existing_source.py"],
    "lte_dual_sim_manual": [RUNTIME + "veci2-sim-manual", "scripts/tests/test_owner_manual_sim_source.py"],
    "lte_apn_pin_puk": [RUNTIME + "veci2-sim-lock", "scripts/tests/test_sim_unlock.py"],
    "system_logs_diagnostics": [RUNTIME + "veci2-system-admin", "scripts/tests/test_owner_system_admin_source.py"],
    "system_time_ntp": [RUNTIME + "veci2-system-admin", "scripts/tests/test_owner_system_admin_source.py"],
    "system_leds_buttons": [RUNTIME + "veci2-system-admin", "scripts/tests/test_owner_system_admin_source.py"],
    "system_access_ssh_https": [RUNTIME + "veci2-access", "scripts/tests/test_owner_reuse_existing_source.py"],
    "firmware_24x7_observability": [RUNTIME + "veci2-system-admin", "scripts/tests/test_owner_system_admin_source.py"],
}


def module_source_verified(entry, record, known_tests):
    """Match the strict source gate; never promote an unverified claim."""
    if entry.get("v2_state") != "source_verified" or record.get("status") != "pass":
        return False
    files = record.get("implementation_files")
    tests = record.get("test_ids")
    test_files = record.get("test_source_files")
    hashes = record.get("source_sha256")
    receipt = record.get("receipt")
    if (not isinstance(files,list) or not files or not isinstance(tests,list) or not tests
            or not isinstance(test_files,list) or not test_files
            or not isinstance(hashes,dict) or not isinstance(receipt,dict)
            or set(hashes) != set(files + test_files)):
        return False
    for rel in files + test_files:
        if not isinstance(rel,str) or Path(rel).is_absolute() or ".." in Path(rel).parts:
            return False
        path = (ROOT / rel).resolve()
        if not path.is_relative_to(ROOT) or not path.is_file() or not path.stat().st_size:
            return False
        if hashlib.sha256(path.read_bytes()).hexdigest() != hashes.get(rel):
            return False
    # Test names must be defined within the evidence-scoped test source, not
    # somewhere else in the suite with a coincidentally similar name.
    declared = set()
    for rel in test_files:
        declared.update(re.findall(r"^\s*def (test_[A-Za-z0-9_]+)\(",(ROOT/rel).read_text(),flags=re.M))
    if not all(isinstance(t,str) and t in known_tests and t in declared for t in tests):
        return False
    log_rel = receipt.get("log_file")
    if not isinstance(log_rel,str) or Path(log_rel).is_absolute() or ".." in Path(log_rel).parts:
        return False
    log = (ROOT/log_rel).resolve()
    if (not log.is_relative_to(ROOT) or not log.is_file() or
            hashlib.sha256(log.read_bytes()).hexdigest() != receipt.get("log_sha256")
            or receipt.get("kind") != "executed_source_tests"
            or receipt.get("exit_code") != 0 or receipt.get("hardware_uat") != "not_run"):
        return False
    return b"Ran " in log.read_bytes() and b"OK" in log.read_bytes()


def collect():
    baseline_text = BASELINE.read_text()
    names = re.findall(r"^\| ([a-z][a-z0-9_]*) \|", baseline_text, flags=re.M)
    if len(names) != 27 or len(set(names)) != 27:
        raise ValueError("owner baseline must contain exactly 27 distinct modules")
    contract = json.loads(CONTRACT.read_text())
    index = {item["id"]: item for item in contract["required_core"]}
    if len(index) != 39 or set(names) - set(index) != {"lte_ussd"}:
        raise ValueError("owner contract mismatch: must contain 39 active modules and 1 retired USSD module from original 27")
    evidence = json.loads(EVIDENCE.read_text()) if EVIDENCE.is_file() else {}
    records = evidence.get("modules", {})
    if not isinstance(records, dict):
        records = {}
    known_tests = set()
    for base in (ROOT / "scripts/tests", ROOT / "tests"):
        for file in base.glob("test_*.py"):
            known_tests.update(re.findall(r"^\s*def (test_[A-Za-z0-9_]+)\(", file.read_text(), flags=re.M))
    modules = []
    for name in names:
        if name == "lte_ussd":
            modules.append({
                "id": name, "status": "retired", "contract_state": "owner_permanently_retired",
                "source_evidence": [], "hardware_uat": "failed_owner"
            })
            continue
        item = index[name]
        record = records.get(name)
        if not isinstance(record, dict):
            record = {}
        if module_source_verified(item, record, known_tests):
            state = "source_verified"
            proof = record.get("implementation_files", [])
        elif name in PARTIAL and all((ROOT / f).is_file() and (ROOT / f).stat().st_size for f in PARTIAL[name]):
            state = "partial"
            proof = PARTIAL[name]
        else:
            state = "pending"
            proof = []
        modules.append({
            "id": name,
            "status": state,
            "contract_state": item["v2_state"],
            "source_evidence": proof,
            "hardware_uat": item.get("physical_uat", "not_run"),
        })
    counts = {key: sum(m["status"] == key for m in modules) for key in ("source_verified", "partial", "pending", "retired")}
    if sum(counts.values()) != 27 or counts["retired"] != 1:
        raise AssertionError("historical 27 must preserve one explicitly retired USSD")
    return {
        "updated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_head": _git_head(),
        "required_core_total": len(index),
        "target_modules": 26,
        "original_target_modules": 27,
        "retired_modules": counts["retired"],
        "completed": counts["source_verified"],
        "partial": counts["partial"],
        "pending": counts["pending"],
        "completed_percentage": round(100 * counts["source_verified"] / 26, 2),
        "modules": modules
    }


def _git_head():
    import subprocess
    return subprocess.check_output(
        ["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"],
        text=True).strip()


if __name__ == "__main__":
    result = collect()
    print(f"VeCI 26 MODUL AKTIF + 1 PENSIUN | SELESAI {result['completed']}/26 ({result['completed_percentage']}%)"
          f" | PARSIAL {result['partial']} | BELUM {result['pending']}"
          f" | commit {result['source_head']}")
    print("STATUS PER MODUL:")
    for module in result["modules"]:
        print(f"- {module['id']}: {module['status']}"
              + (f" ({', '.join(module['source_evidence'])})" if module["source_evidence"] else ""))
