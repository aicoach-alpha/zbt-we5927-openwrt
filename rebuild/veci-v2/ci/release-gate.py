#!/usr/bin/env python3
"""Fail closed: source success is never proof that VeCI v2 can be flashed."""
import argparse
import json
from pathlib import Path
import sys

BASE = Path(__file__).resolve().parents[1]
CONTRACT = BASE / "contracts/veci-v2-rebuild-contract.json"


def evaluate(contract, evidence):
    blockers = []
    if contract.get("board_id") != "ZBT-WE5927-DSIM":
        blockers.append("wrong_board")
    if contract.get("openwrt_version") != "25.12.6":
        blockers.append("wrong_openwrt")
    if contract.get("flash_mtd_bytes") != 7995392:
        blockers.append("wrong_mtd")
    if len(contract.get("required_core", [])) < 35:
        blockers.append("incomplete_core_contract")
    for feature in contract.get("required_core", []):
        if feature.get("v2_state") != "source_verified":
            blockers.append("source_not_complete:" + feature["id"])
        if feature.get("physical_uat") != "pass":
            blockers.append("hardware_uat_missing:" + feature["id"])
    for gate in contract.get("mandatory_gates", []):
        if not evidence.get(gate, False):
            blockers.append("required_gate_missing:" + gate)
    if evidence.get("signed_image_hash_verified") is not True:
        blockers.append("signed_image_not_verified")
    if evidence.get("firmware_image_bytes", 0) > 7995392 - 1048576 or (
            evidence.get("firmware_image_bytes", 0) <= 0):
        blockers.append("raw_image_size_or_headroom")
    if contract.get("flash_authorized") is not True:
        blockers.append("contract_disallows_flash")
    return sorted(set(blockers))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path)
    args = parser.parse_args()
    contract = json.loads(CONTRACT.read_text())
    evidence = json.loads(args.evidence.read_text()) if args.evidence else {}
    blockers = evaluate(contract, evidence)
    print(json.dumps({
        "board": contract["board_id"],
        "openwrt": contract["openwrt_version"],
        "required_modules": len(contract["required_core"]),
        "source_verified": sum(x["v2_state"] == "source_verified"
                               for x in contract["required_core"]),
        "hardware_accepted": sum(x["physical_uat"] == "pass"
                                 for x in contract["required_core"]),
        "flash_allowed": len(blockers) == 0,
        "blocker_count": len(blockers),
        "blockers": blockers
    }, indent=2))
    return 0 if not blockers else 3


if __name__ == "__main__":
    sys.exit(main())
