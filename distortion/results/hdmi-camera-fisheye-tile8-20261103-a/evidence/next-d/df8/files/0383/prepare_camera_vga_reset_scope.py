"""Derive unapplied camera reset scope from its own complete native report.

No historical endpoint counts, object inventories or inventory hashes are used.
The current native summary supplies expected coverage and arithmetic; actual
path records supply every source, endpoint and edge. No EDA is launched.
"""
from collections import defaultdict
from decimal import Decimal
from pathlib import Path
import argparse
import hashlib
import json
import re

import prepare_camera_vga_output as candidate

PROJECT = Path(__file__).resolve().parents[1]
IP = "u_ddr3_test_h/u_ddrphy_top/"
SLICE = IP + "ddrphy_slice_top/"
NUM = r"[-+]?\d+(?:\.\d+)?"
KEYS = ("Source", "Endpoint", "LaunchClock", "CaptureClock")
SAFE = re.compile(r"[A-Za-z0-9_./\[\]-]+\Z")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_sha(values):
    return hashlib.sha256(json.dumps(sorted(values), separators=(",", ":")).encode()).hexdigest()


def targeted_pair(launch, capture):
    return ((launch, capture) == ("board27", "rst_clk") or
            launch in ("rst_clk", "ddrphy_sysclk") and
            re.fullmatch(r"phy_dq_(?:sys)?clk_\d+", capture) is not None)


def classify(path):
    source, target = path["Source"], path["Endpoint"]
    require(SAFE.fullmatch(source) and SAFE.fullmatch(target), "unsafe native object name")
    require(source.endswith("/CLK"), "reset source must be an actual FF clock pin")
    launch, capture = path["LaunchClock"], path["CaptureClock"]
    if (launch, capture) == ("board27", "rst_clk"):
        require(source.rsplit("/", 2)[0] == "power_ready" and
                target.startswith(IP + "u_ddrphy_rst_seq_rstn_sync/sig_async_r1[0]/") and
                target.endswith("/RS"), "unexpected DDR entry reset path")
        return "entry_rdc"
    parent = source.rsplit("/", 2)[0]
    families = {IP + "ddrphy_reset_ctrl/ddrphy_dqs_rst": ("dqs_reset", {"RST", "ISR_IOLHR", "OSR_IOLHR"}),
                IP + "ddrphy_reset_ctrl/ddrphy_iol_rst": ("iol_reset", {"TSR"}),
                IP + "ddrphy_training_ctrl/ddrphy_dqs_training_rstn": ("training_reset", {"RST_TRAINING_N"})}
    if parent == IP + "ddrphy_cpd_ctrl/ddrphy_cpd_rstn":
        require(target == IP + "u_ddrphy_cpd/cpd_inst/RST" and
                (launch, capture) == ("rst_clk", "phy_dq_sysclk_0"), "unexpected CPD reset path")
        return "cpd_reset"
    require(parent in families, "unknown reset source family")
    family, pins = families[parent]
    require(target.startswith(SLICE) and target.rsplit("/", 1)[1] in pins,
            "non-reset target or reset family mismatch")
    require(launch == ("ddrphy_sysclk" if family == "training_reset" else "rst_clk"),
            "reset source clock differs")
    return family


def parse_report(report):
    paths, summaries, block = [], {}, []
    section, first_line, design_seen = None, 0, False

    def finish():
        if not block:
            return
        text = "".join(block)
        if not re.search(r"(?m)^ Recovery time\s", text):
            return
        groups = re.findall(r"(?m)^Path Group\s*:\s*(\S+)\s*$", text)
        require(len(groups) == 1, "recovery record missing path group")
        if groups[0] != "rst_clk" and not re.fullmatch(r"phy_dq_(?:sys)?clk_\d+", groups[0]):
            return
        clocks = re.findall(r"(?m)^ Clock (\S+) \((rising|falling) edge\)", text)
        require(len(clocks) == 2, "recovery record missing clock edges")
        if not targeted_pair(clocks[0][0], clocks[1][0]):
            return

        def one(pattern, label):
            found = re.findall(pattern, text, re.M)
            require(len(found) == 1, "missing/ambiguous recovery " + label)
            return found[0]

        source = one(r"^Startpoint\s*:\s*(\S+)\s*$", "source")
        target = one(r"^Endpoint\s*:\s*(\S+)\s*$", "endpoint")
        corner = one(r"^Path Type\s*:\s*max \((slow|fast) corner\)\s*$", "corner")
        require(one(r"^Path Class\s*:\s*(.*?)\s*$", "class") == "async timing path",
                "recovery must remain an ordinary timed async path")
        require(one(r"^Path Group\s*:\s*(\S+)\s*$", "group") == clocks[1][0], "capture/group differs")
        state, slack = one(r"^ Slack \((MET|VIOLATED)\)\s+(" + NUM + r")\s*$", "slack")
        transition = one(r"^ \S+\s+tco\s+" + NUM + r"\s+" + NUM + r"\s+([rf])\s+\S+\s*$",
                         "data transition")
        body = []
        for line in block:
            if line.strip() and not set(line.strip()) <= set("-=*"):
                body.append(" ".join(line.split()))
            if line.startswith(" Slack"):
                break
        value = {"Source": source, "Endpoint": target, "Corner": corner,
                 "LaunchClock": clocks[0][0], "CaptureClock": clocks[1][0],
                 "LaunchEdge": clocks[0][1], "CaptureEdge": clocks[1][1],
                 "LaunchDataTransition": transition, "SlackNS": slack, "SlackState": state,
                 "NativeReportLine": first_line,
                 "NativePathSHA256": hashlib.sha256("\n".join(body).encode()).hexdigest()}
        value["Family"] = classify(value)
        paths.append(value)

    with Path(report).open(encoding="utf-8-sig") as stream:
        for line_number, line in enumerate(stream, 1):
            if re.fullmatch(r"\| Design\s*:\s*camera_vga_output_top\s*", line):
                design_seen = True
            header = re.fullmatch(r"Recovery Summary\((Slow|Fast) Corner\):\s*", line)
            if header:
                section = header[1].lower()
            elif re.match(r"^\w+(?: \w+)* Summary\(", line) or line.startswith("Startpoint"):
                section = None
            if section:
                row = re.fullmatch(r"\s*(\S+)\s+(\S+)\s+(" + NUM + r")\s+(" + NUM + r")\s+(\d+)\s+(\d+)\s*", line)
                if row:
                    key = (section, row[1], row[2])
                    require(key not in summaries, "duplicate native summary")
                    summaries[key] = {"WNS": row[3], "TNS": row[4], "Failing": int(row[5]), "Total": int(row[6])}
            if line.startswith("Startpoint"):
                finish()
                block, first_line = [line], line_number
            elif block:
                block.append(line)
    finish()
    require(design_seen, "report is not for camera_vga_output_top")
    return paths, summaries


def audit_inventory(paths, summaries, require_complete=True):
    require(paths and summaries, "recovery evidence is empty")
    target_summaries = {k: v for k, v in summaries.items() if targeted_pair(k[1], k[2])}
    require(target_summaries, "target recovery groups are absent")
    require(not [k for k, v in summaries.items() if v["Failing"] and k not in target_summaries],
            "a recovery failure exists outside the proposed reset families")
    require({k[1:] for k in target_summaries if k[0] == "slow"} ==
            {k[1:] for k in target_summaries if k[0] == "fast"}, "corner summary groups differ")
    corners, all_groups, missing = {}, [], []
    for corner in ("slow", "fast"):
        rows = [p for p in paths if p["Corner"] == corner]
        grouped = defaultdict(list)
        for path in rows:
            require(classify(path) == path["Family"], "family classification drift")
            num = Decimal(path["SlackNS"])
            require(num.is_finite() and (path["SlackState"] == "VIOLATED") == num.is_signed(),
                    "native slack state differs")
            require(path["LaunchEdge"] == "rising" and path["CaptureEdge"] in ("rising", "falling"),
                    "unexpected recovery clock edge")
            grouped[tuple(path[k] for k in KEYS)].append(path)
        checks = []
        for key, variants in sorted(grouped.items()):
            identities = {(p["LaunchEdge"], p["CaptureEdge"], p["LaunchDataTransition"]) for p in variants}
            require(len(identities) == len(variants), "duplicate native edge/transition variant")
            require(len({p["NativePathSHA256"] for p in variants}) == len(variants), "duplicate native body")
            dual_edge = (key[1].endswith("/RST") and re.search(r"(?:/|\.)u_ddc_[^/]+/", key[1]) is not None and
                         re.fullmatch(r"phy_dq_clk_\d+", key[3]) is not None)
            expected_edges = {"rising", "falling"} if dual_edge else {"rising"}
            edges_complete = ({p["CaptureEdge"] for p in variants} == expected_edges and
                              len(variants) == len(expected_edges))
            if require_complete:
                require(edges_complete, "missing/unexpected DDR primitive capture-edge variant: " + key[1])
            worst = min(variants, key=lambda p: (Decimal(p["SlackNS"]), p["SlackState"] != "VIOLATED"))
            checks.append({**dict(zip(KEYS, key)), "Family": variants[0]["Family"],
                           "WorstSlackNS": worst["SlackNS"],
                           "Failing": any(p["SlackState"] == "VIOLATED" for p in variants),
                           "CaptureEdgesComplete": edges_complete,
                           "NativeVariants": variants})
        for key, native in sorted(target_summaries.items()):
            if key[0] != corner:
                continue
            members = [c for c in checks if (c["LaunchClock"], c["CaptureClock"]) == key[1:]]
            actual_wns = min((Decimal(c["WorstSlackNS"]) for c in members), default=None)
            actual_tns = sum((min(Decimal(0), Decimal(c["WorstSlackNS"])) for c in members), Decimal(0))
            failing = sum(c["Failing"] for c in members)
            complete = (len(members) == native["Total"] and failing == native["Failing"] and
                        actual_wns == Decimal(native["WNS"]) and actual_tns == Decimal(native["TNS"]))
            item = {"Corner": corner, "LaunchClock": key[1], "CaptureClock": key[2],
                    "NativeSummary": native, "ObservedLogicalChecks": len(members),
                    "ObservedVariants": sum(len(c["NativeVariants"]) for c in members),
                    "ReconstructedWNS": str(actual_wns), "ReconstructedTNS": str(actual_tns),
                    "ReconstructedFailing": failing, "Complete": complete}
            all_groups.append(item)
            if not complete:
                missing.append(item)
        corners[corner] = {"LogicalChecks": len(checks), "NativeVariants": len(rows),
                           "FailingChecks": sum(c["Failing"] for c in checks), "Checks": checks}
    inventories = {c: {tuple(p[k] for k in KEYS) for p in corners[c]["Checks"]} for c in corners}
    complete = (not missing and inventories["slow"] == inventories["fast"] and
                all(c["CaptureEdgesComplete"] for corner in corners.values() for c in corner["Checks"]))
    if require_complete:
        require(complete, "incomplete current recovery inventory; request full native paths, never copy old endpoint counts")
    return {"Complete": complete, "Groups": all_groups, "IncompleteGroups": missing, "Corners": corners,
            "LogicalInventorySHA256": {c: canonical_sha(inventories[c]) for c in corners},
            "HistoricalEndpointInventoryUsed": False, "TimingExceptionApproved": False}


def query_scope(inventory):
    require(inventory["Complete"], "incomplete inventory cannot produce a constraint proposal")
    groups, families = defaultdict(set), {}
    for check in inventory["Corners"]["slow"]["Checks"]:
        source = check["Source"]
        groups[source].add(check["Endpoint"])
        require(source not in families or families[source] == check["Family"], "one source spans reset families")
        families[source] = check["Family"]
    queries, body, fdc = [], [], ["# UNAPPLIED: current camera native report only; pending native pin and reset-graph proof.",
                                "# No clock groups, data false paths, old endpoint lists or hardware release."]
    for index, (source, targets) in enumerate(sorted(groups.items()), 1):
        targets = sorted(targets)
        patterns = ["^(" + "|".join(re.escape(n) for n in names) + ")$" for names in ([source], targets)]
        commands = ["get_pins -hierarchical -regexp {" + pattern + "}" for pattern in patterns]
        body += [f"puts {{CAMERA_VGA_RESET_QUERY_{index}_SOURCE}}", commands[0],
                 f"puts {{CAMERA_VGA_RESET_QUERY_{index}_TARGETS}}", commands[1]]
        fdc.append("set_false_path -from [" + commands[0] + "] -to [" + commands[1] + "]")
        queries.append({"Source": source, "Targets": targets, "Family": families[source],
                        "EntryRDC": families[source] == "entry_rdc",
                        "FromRegex": patterns[0], "ToRegex": patterns[1],
                        "ExpectedFromCount": 1, "ExpectedTargetCount": len(targets),
                        "ExpectedNativeFromNames": ["t:" + source],
                        "ExpectedNativeToNames": ["t:" + target for target in targets]})
    return queries, "\n".join(body) + "\n", "\n".join(fdc) + "\n"


def prepare(report, adf, output, allow_incomplete=False):
    report, adf, output = Path(report).resolve(), Path(adf).resolve(), Path(output).resolve()
    require(report.is_file() and adf.is_file() and not output.exists(), "existing inputs and fresh output directory required")
    before = {str(p): sha(p) for p in (report, adf)}
    paths, summaries = parse_report(report)
    inventory = audit_inventory(paths, summaries, require_complete=not allow_incomplete)
    roles = candidate.validate()
    plan = {"Schema": "camera-vga-reset-scope-proposal-v1",
            "Status": "prepared_unapplied_pending_native_and_netlist_review" if inventory["Complete"] else "incomplete_native_inventory_no_proposal",
            "Report": {"Path": str(report), "SHA256": before[str(report)]},
            "SourceADF": {"Path": str(adf), "SHA256": before[str(adf)]},
            "CandidateManifest": {"Path": str(PROJECT / candidate.MANIFEST), "SHA256": sha(PROJECT / candidate.MANIFEST)},
            "Complete": inventory["Complete"], "NativeQueries": [],
            "SourceClosureValidated": True, "DDRInstanceProvenance": roles["DDRBodyComparison"],
            "ReportNativeADFBindingVerified": False, "ConstraintsApplied": False,
            "NativeQueriesVerified": False, "ResetConnectivityVerified": False,
            "TimingExceptionApproved": False, "HardwareAccessed": False, "HardwareReleaseAllowed": False,
            "ToolSHA256": sha(__file__), "FilesSHA256": {}}
    payloads = {"recovery-inventory.json": json.dumps(inventory, indent=2) + "\n"}
    if inventory["Complete"]:
        queries, query, fdc = query_scope(inventory)
        plan["NativeQueries"] = queries
        plan["UniqueSourceEndpointPairs"] = sum(q["ExpectedTargetCount"] for q in queries)
        payloads.update({"query-body.tcl": query, "proposed-scope.fdc": fdc})
    require(all(sha(name) == digest for name, digest in before.items()), "input changed during scope preparation")
    plan["FilesSHA256"] = {name: hashlib.sha256(data.encode()).hexdigest() for name, data in payloads.items()}
    payloads["plan.json"] = json.dumps(plan, indent=2) + "\n"
    output.mkdir(parents=True)
    for name, data in payloads.items():
        with (output / name).open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(data)
    return plan


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--adf", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--allow-incomplete", action="store_true")
    args = parser.parse_args()
    plan = prepare(args.report, args.adf, args.output_dir, args.allow_incomplete)
    print(json.dumps({"Status": plan["Status"], "Complete": plan["Complete"],
                      "Groups": [{"Family": q["Family"], "Targets": q["ExpectedTargetCount"]} for q in plan["NativeQueries"]]}))


if __name__ == "__main__":
    main()
