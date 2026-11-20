#!/usr/bin/env python3
"""Truthful 27-module source progress from canonical contract and evidence.

The 'partial' label means source files exist in the owner worktree. It never
means the feature works on hardware. The initial 27 are frozen by the owner
source-reuse manifest so completed modules cannot vanish from the denominator.
"""
import json
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
    "system_logs_diagnostics": [RUNTIME + "veci2-system-admin", "scripts/tests/test_owner_system_admin_source.py"],
    "system_time_ntp": [RUNTIME + "veci2-system-admin", "scripts/tests/test_owner_system_admin_source.py"],
    "system_leds_buttons": [RUNTIME + "veci2-system-admin", "scripts/tests/test_owner_system_admin_source.py"],
    "system_access_ssh_https": [RUNTIME + "veci2-access", "scripts/tests/test_owner_reuse_existing_source.py"],
    "firmware_24x7_observability": [RUNTIME + "veci2-system-admin", "scripts/tests/test_owner_system_admin_source.py"],
}


def module_source_verified(entry, record, known_tests):
    if entry.get("v2_state") != "source_verified" or record.get("status") != "pass":
        return False
    files = record.get("implementation_files")
    tests = record.get("test_ids")
    if not isinstance(files, list) or not isinstance(tests, list) or not files or not tests:
        return False
    for rel in files:
        if not isinstance(rel, str) or rel.startswith("/") or ".." in Path(rel).parts:
            return False
        path = ROOT / rel
        if not path.is_file() or path.stat().st_size == 0:
            return False
    return all(isinstance(t, str) and t in known_tests for t in tests)


def collect():
    baseline_text = BASELINE.read_text()
    names = re.findall(r"^\| ([a-z][a-z0-9_]*) \|", baseline_text, flags=re.M)
    if len(names) != 27 or len(set(names)) != 27:
        raise ValueError("owner baseline must contain exactly 27 distinct modules")
    contract = json.loads(CONTRACT.read_text())
    index = {item["id"]: item for item in contract["required_core"]}
    if len(index) != 40 or not set(names).issubset(index):
        raise ValueError("owner contract mismatch: must contain 40 modules and original 27")
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
    counts = {key: sum(m["status"] == key for m in modules) for key in ("source_verified", "partial", "pending")}
    if sum(counts.values()) != 27:
        raise AssertionError("counts must sum to 27")
    return {
        "updated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_head": _git_head(),
        "required_core_total": len(index),
        "target_modules": 27,
        "completed": counts["source_verified"],
        "partial": counts["partial"],
        "pending": counts["pending"],
        "completed_percentage": round(100 * counts["source_verified"] / 27, 2),
        "modules": modules
    }


def _git_head():
    import subprocess
    return subprocess.check_output(
        ["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"],
        text=True).strip()


if __name__ == "__main__":
    result = collect()
    print(f"VeCI 27 MODUL | SELESAI {result['completed']}/27 ({result['completed_percentage']}%)"
          f" | PARSIAL {result['partial']} | BELUM {result['pending']}"
          f" | commit {result['source_head']}")
    print("STATUS PER MODUL:")
    for module in result["modules"]:
        print(f"- {module['id']}: {module['status']}"
              + (f" ({', '.join(module['source_evidence'])})" if module["source_evidence"] else ""))
