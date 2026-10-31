"""Prepare exact queries and an UNAPPLIED reset scope from the candidate report.

Reconstructs all native internal recovery variants with the existing strict
inventory auditor, then independently inventories the board-to-DDR entry pair.
No native tool, ADF mutation, constraint application or hardware is performed.
"""
from collections import defaultdict
from pathlib import Path
import argparse
import hashlib
import json
import re

import audit_ddr_recovery_variants as variants
import audit_processed_output_reset as reference


ENTRY_SOURCE = "power_ready/opit_0_inv_L6Q_perm/CLK"
ENTRY_TARGET = ("u_ddr3_test_h/u_ddrphy_top/u_ddrphy_rst_seq_rstn_sync/"
                "sig_async_r1[0]/opit_0_srl/RS")
require, sha = reference.require, reference.sha


def entry_checks(text):
    require(re.search(r"(?m)^\| Design\s*:\s*processed_output_top\s*$", text),
            "report is not for processed_output_top")
    found = []
    for block in re.split(r"(?m)(?=^Startpoint\s*:)", text)[1:]:
        if not re.search(r"(?m)^ Recovery time\s", block):
            continue
        if not re.search(r"(?m)^Path Group\s*:\s*rst_clk\s*$", block):
            continue
        clocks = re.findall(r"(?m)^ Clock (\S+) \((rising|falling) edge\)", block)
        require(len(clocks) == 2, "recovery record needs two clocks")
        if (clocks[0][0], clocks[1][0]) != ("board27", "rst_clk"):
            continue
        def one(pattern, label):
            values = re.findall(pattern, block, re.MULTILINE)
            require(len(values) == 1, "missing/ambiguous entry " + label)
            return values[0]
        source = one(r"^Startpoint\s*:\s*(\S+)\s*$", "source")
        endpoint = one(r"^Endpoint\s*:\s*(\S+)\s*$", "endpoint")
        require(source == ENTRY_SOURCE and endpoint == ENTRY_TARGET, "entry pins differ")
        require(one(r"^Path Class\s*:\s*(.*?)\s*$", "class") == "async timing path",
                "entry is not an ordinary timed asynchronous path")
        corner = one(r"^Path Type\s*:\s*max \((slow|fast) corner\)\s*$", "corner")
        state, slack = one(r"^ Slack \((MET|VIOLATED)\)\s+([-+]?\d+(?:\.\d+)?)\s*$", "slack")
        require((state == "VIOLATED") == variants.negative(slack), "entry slack state mismatch")
        found.append({"Source": source, "Endpoint": endpoint, "Corner": corner,
                      "LaunchClock": clocks[0][0], "CaptureClock": clocks[1][0],
                      "LaunchEdge": clocks[0][1], "CaptureEdge": clocks[1][1],
                      "SlackNS": slack, "SlackState": state})
    require(len(found) == 2 and {p["Corner"] for p in found} == {"slow", "fast"},
            "exactly one entry check per corner is required")
    for path in found:
        summary = re.search(r"Recovery Summary\(" + path["Corner"].title() +
                            r" Corner\):(.*?)(?=\w+(?: \w+)* Summary\(|Slow Corner|Fast Corner)",
                            text, re.DOTALL)
        require(summary is not None, "entry summary is missing")
        rows = re.findall(r"(?m)^\s*board27\s+rst_clk\s+([-+\d.]+)\s+([-+\d.]+)\s+(\d+)\s+(\d+)\s*$",
                          summary[1])
        require(len(rows) == 1, "missing/ambiguous entry summary row")
        wns, tns, failed, total = rows[0]
        require(int(total) == 1 and int(failed) == (path["SlackState"] == "VIOLATED")
                and variants.number(wns) == variants.number(path["SlackNS"])
                and variants.number(tns) == min(0, variants.number(path["SlackNS"])),
                "entry summary does not match its one complete native check")
    return found


def prepare(report, output):
    report, output = Path(report).resolve(), Path(output).resolve()
    require(not output.exists(), "output directory must be new")
    digest = sha(report)
    internal = variants.audit_file(report)
    text = report.read_text(encoding="utf-8-sig")
    external = entry_checks(text)
    source_proof = reference.audit_vendor_sources()
    groups = defaultdict(set)
    for check in internal["Corners"]["slow"]["Checks"]:
        groups[check["Source"]].add(check["Endpoint"])
    require(sorted(map(len, groups.values())) == [1, 7, 14, 104], "four actual reset driver groups differ")
    groups[ENTRY_SOURCE].add(ENTRY_TARGET)
    queries, body, fdc = [], [], [
        "# UNAPPLIED proposal only: four internal reset drivers plus one entry pair.",
        "# Requires current native exact-name proof AND separate entry netlist/ADF binding.",
        "# This file is not approval to apply constraints or release hardware.",
    ]
    for number, (source, targets) in enumerate(sorted(groups.items()), 1):
        target_list = sorted(targets)
        patterns = ["^(" + "|".join(re.escape(n) for n in names) + ")$"
                    for names in ([source], target_list)]
        commands = ["get_pins -hierarchical -regexp {" + pattern + "}" for pattern in patterns]
        body.extend([f"puts {{PROCESSED_RESET_QUERY_{number}_SOURCE}}", commands[0],
                     f"puts {{PROCESSED_RESET_QUERY_{number}_TARGETS}}", commands[1]])
        fdc.append("set_false_path -from [" + commands[0] + "] -to [" + commands[1] + "]")
        queries.append({"Source": source, "Targets": target_list,
                        "FromRegex": patterns[0], "ToRegex": patterns[1],
                        "ExpectedFromCount": 1, "ExpectedTargetCount": len(target_list),
                        "ExpectedNativeFromNames": ["t:" + source],
                        "ExpectedNativeToNames": ["t:" + name for name in target_list],
                        "EntryRDC": source == ENTRY_SOURCE})
    payloads = {"internal-recovery.json": json.dumps(internal, indent=2) + "\n",
                "vendor-reference.json": json.dumps(source_proof, indent=2) + "\n",
                "query-body.tcl": "\n".join(body) + "\n",
                "proposed-scope.fdc": "\n".join(fdc) + "\n"}
    plan = {"Schema": "processed-output-reset-scope-proposal-v1",
            "Status": "prepared_unapplied_pending_native_and_entry_review",
            "Report": {"Path": str(report), "SHA256": digest},
            "InternalChecksPerCorner": 244, "InternalUniqueSourceEndpointPairs": 126,
            "InternalCorners": {corner: {key: result[key] for key in
                ("NativeVariantCount", "LogicalCheckCount", "FailingChecks", "NonnegativeChecks")}
                for corner, result in internal["Corners"].items()},
            "EntryChecks": external, "NativeQueries": queries,
            "LogicalPinClockInventorySHA256": internal["LogicalInventorySHA256"],
            "SourceEndpointPairsSHA256": internal["SourceEndpointPairsSHA256"],
            "HelperSHA256": {str(Path(module.__file__).resolve()): sha(module.__file__)
                             for module in (variants, variants.recovery, reference, reference.entry,
                                            reference.candidate)},
            "ToolSHA256": sha(__file__),
            "FilesSHA256": {name: hashlib.sha256(data.encode("utf-8")).hexdigest()
                            for name, data in payloads.items()},
            "ConstraintsApplied": False, "NativeQueriesVerified": False,
            "EntryConnectivityVerified": False, "TimingExceptionApproved": False,
            "HardwareAccessed": False, "HardwareReleaseAllowed": False}
    require(sha(report) == digest, "report changed during audit")
    payloads["plan.json"] = json.dumps(plan, indent=2) + "\n"
    output.mkdir(parents=True)
    for name, data in payloads.items():
        with (output / name).open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(data)
    return plan


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    result = prepare(args.report, args.output_dir)
    print(json.dumps({"Status": result["Status"], "InternalCorners": result["InternalCorners"],
                      "Groups": [q["ExpectedTargetCount"] for q in result["NativeQueries"]]}, indent=2))


if __name__ == "__main__":
    main()
