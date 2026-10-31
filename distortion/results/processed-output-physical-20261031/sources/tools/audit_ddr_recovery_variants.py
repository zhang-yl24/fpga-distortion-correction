"""Audit the fresh board1080 report's 251 variants / 244 internal reset checks.

This CPU-only audit is scoped to the already inventoried six DDR clock pairs.
Logical identity includes both pins AND both clocks. Seven DDC reset checks
have two capture edges; every native record, transition and body hash survives
the grouping. Counts, worst slack and TNS must reconstruct the native summary.
No constraints, ADF, EDA, entry-RDC acceptance or hardware approval are produced.
"""
from collections import Counter, defaultdict
from decimal import Decimal, InvalidOperation
from pathlib import Path
import argparse
import hashlib
import json
import re

import prepare_ddr_native_recovery_constraints as recovery


KEYS = ("Source", "Endpoint", "LaunchClock", "CaptureClock")
CORNERS = ("slow", "fast")
# Canonical sorted pin-and-clock tuples in the distributed 2026-10-29 inventory.
INVENTORY_SHA256 = "61ac8f734294003db3f6086dc3906b50f2d54c8312720fb0cae8a7ddb0d3927b"
PAIR_SHA256 = "3b618334e27a72bcd8636dedcc1e9d82f32db47645e3469ba8b577b136f8a92f"
NUM = r"[-+]?\d+(?:\.\d+)?"
ROW = re.compile(r"^\s*(\S+)\s+(\S+)\s+(" + NUM + r")\s+(" + NUM + r")\s+(\d+)\s+(\d+)\s*$")
EXTRA_EDGES = {
    **{recovery.SLICE + f"i_ca_group[{i}].u_ddc_ca/ddc_inst/RST": "phy_dq_clk_0" for i in range(3)},
    **{recovery.SLICE + f"i_dqs_group[{i}].ddrphy_data_slice/u_ddc_dq/ddc_inst_PHY/RST": "phy_dq_clk_1" for i in range(4)},
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def canonical_sha(values):
    return hashlib.sha256(json.dumps(sorted(values), separators=(",", ":")).encode("ascii")).hexdigest()


def number(value):
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError("invalid native slack") from None
    require(result.is_finite(), "non-finite native slack")
    return result


def negative(value):
    # A rounded native -0.000 is still a negative, failing observation.
    value = number(value)
    return value < 0 or value == 0 and value.is_signed()


def parse_lines(lines):
    """Stream the large report; retain only the six internal recovery groups."""
    paths, summaries, block = [], {}, []
    section, start_line, details = None, 0, False

    def finish():
        text = "".join(block)
        if not re.search(r"(?m)^ Recovery time\s", text):
            return
        groups = re.findall(r"(?m)^Path Group\s*:\s*(\S+)\s*$", text)
        if len(groups) == 1 and groups[0] not in {p[1] for p in recovery.PAIRS}:
            return
        clocks = re.findall(r"(?m)^ Clock (\S+) \((rising|falling) edge\)", text)
        require(len(clocks) == 2, "recovery record needs both clock edges")
        if (clocks[0][0], clocks[1][0]) not in recovery.PAIRS:
            return

        def one(pattern, label):
            found = re.findall(pattern, text, re.MULTILINE)
            require(len(found) == 1, "missing or ambiguous native " + label)
            return found[0]

        source = one(r"^Startpoint\s*:\s*(\S+)\s*$", "source")
        endpoint = one(r"^Endpoint\s*:\s*(\S+)\s*$", "endpoint")
        group = one(r"^Path Group\s*:\s*(\S+)\s*$", "group")
        corner = one(r"^Path Type\s*:\s*max \((slow|fast) corner\)\s*$", "recovery type")
        require(one(r"^Path Class\s*:\s*(.*?)\s*$", "class") == "async timing path",
                "recovery record must remain a timed asynchronous path")
        require(len(re.findall(r"(?m)^ Recovery time\s", text)) == 1, "ambiguous recovery record")
        require(group == clocks[1][0], "path group differs from capture clock")
        state, slack = one(r"^ Slack \((MET|VIOLATED)\)\s+(" + NUM + r")\s*$", "slack")
        transition = one(r"^ \S+\s+tco\s+" + NUM + r"\s+" + NUM + r"\s+([rf])\s+\S+\s*$", "source data transition")
        require((state == "VIOLATED") == negative(slack), "slack state contradicts native value")
        body = []
        for line in block:
            if line.strip() and not set(line.strip()) <= set("-=*"):
                body.append(" ".join(line.split()))
            if line.startswith(" Slack"):
                break
        value = {"Source": source, "Endpoint": endpoint, "LaunchClock": clocks[0][0],
                      "CaptureClock": clocks[1][0], "LaunchEdge": clocks[0][1],
                      "CaptureEdge": clocks[1][1], "Corner": corner, "SlackNS": slack,
                      "SlackState": state, "LaunchDataTransition": transition,
                      "NativeReportLine": start_line,
                      "NativePathSHA256": hashlib.sha256("\n".join(body).encode("utf-8")).hexdigest()}
        recovery.classify(value)
        paths.append(value)

    for lineno, line in enumerate(lines, 1):
        if not details:
            header = re.fullmatch(r"Recovery Summary\((Slow|Fast) Corner\):\s*", line)
            if header:
                section = header[1].lower()
            elif re.match(r"^\w+(?: \w+)* Summary\(", line):
                section = None
            if section:
                row = ROW.fullmatch(line)
                if row and (row[1], row[2]) in recovery.PAIRS:
                    key = (section, row[1], row[2])
                    require(key not in summaries, "duplicate recovery summary row")
                    summaries[key] = {"WNS": row[3], "TNS": row[4],
                                      "Failing": int(row[5]), "Total": int(row[6])}
        if line.startswith("Startpoint"):
            details = True
            finish()
            block, start_line = [line], lineno
        elif block:
            block.append(line)
    finish()
    return paths, summaries


def audit(paths, summaries):
    require(set(summaries) == {(c, *p) for c in CORNERS for p in recovery.PAIRS},
            "all twelve internal recovery summary rows are required")
    require(all(p.get("Corner") in CORNERS for p in paths), "unexpected path corner")
    require(len({(p["Corner"], p["NativePathSHA256"]) for p in paths}) == len(paths),
            "duplicate native path record")
    for p in paths:
        require((p["LaunchClock"], p["CaptureClock"]) in recovery.PAIRS, "unexpected internal clock pair")
        recovery.classify(p)
        require(p["LaunchEdge"] == "rising" and p["CaptureEdge"] in ("rising", "falling"),
                "unexpected launch or capture edge")
        require(p["LaunchDataTransition"] in ("r", "f"), "invalid source data transition")
        require(p["SlackState"] in ("MET", "VIOLATED") and
                (p["SlackState"] == "VIOLATED") == negative(p["SlackNS"]),
                "slack state contradicts native value")
        require(re.fullmatch(r"[0-9a-f]{64}", p["NativePathSHA256"]) and
                type(p["NativeReportLine"]) is int and p["NativeReportLine"] > 0,
                "native signature and source line are required")
    result = {"Schema": "ddr-recovery-variant-audit-v1", "AuditPassed": True,
              "Scope": "Six internal DDR recovery clock pairs only",
              "LogicalCheckIdentity": list(KEYS), "LogicalInventorySHA256": INVENTORY_SHA256,
              "SourceEndpointPairsSHA256": PAIR_SHA256, "Corners": {}, "Groups": [],
              "EntryRDCAudited": False, "TimingExceptionApproved": False,
              "ConstraintsApplied": False, "HardwareAccessed": False, "HardwareReleaseAllowed": False}
    for corner in CORNERS:
        rows = [p for p in paths if p["Corner"] == corner]
        grouped = defaultdict(list)
        for p in rows:
            grouped[tuple(p[k] for k in KEYS)].append(p)
        require(len(grouped) == 244 and canonical_sha(grouped) == INVENTORY_SHA256,
                "logical pin-and-clock inventory differs from the 244-check profile")
        require(canonical_sha({key[:2] for key in grouped}) == PAIR_SHA256, "126 exact pin pairs differ")
        require(len(rows) == 251, "all 251 native variants per corner are required")
        checks, multiple = [], []
        for key, variants in sorted(grouped.items()):
            multiple_edge = key[1] in EXTRA_EDGES and key[3] == EXTRA_EDGES[key[1]]
            edges = {(p["LaunchEdge"], p["CaptureEdge"]) for p in variants}
            expected = {("rising", "rising"), ("rising", "falling")} if multiple_edge else {("rising", "rising")}
            require(edges == expected and len(variants) == len(expected),
                    "missing, duplicate or unexpected native edge variant for " + key[1])
            worst = min(variants, key=lambda p: (number(p["SlackNS"]), p["SlackState"] != "VIOLATED"))
            check = dict(zip(KEYS, key), Family=recovery.classify(variants[0]),
                         WorstSlackNS=worst["SlackNS"], Failing=any(p["SlackState"] == "VIOLATED" for p in variants),
                         Edges=[list(edge) for edge in sorted(edges)],
                         NativeVariants=sorted(variants, key=lambda p: p["NativeReportLine"]))
            checks.append(check)
            if multiple_edge:
                multiple.append(dict(zip(KEYS, key)))
        require(len(multiple) == 7, "seven DDC dual-capture-edge checks are required")
        require(Counter(p["Family"] for p in checks) == {"ddrphy_dqs_rst":208, "ddrphy_iol_rst":28,
                "ddrphy_dqs_training_rstn":7, "cpd_excluded":1}, "reset family coverage differs")
        for pair, count in recovery.PAIRS.items():
            members = [p for p in checks if (p["LaunchClock"], p["CaptureClock"]) == pair]
            native = summaries[(corner, *pair)]
            wns = min(number(p["WorstSlackNS"]) for p in members)
            tns = sum((min(Decimal(0), number(p["WorstSlackNS"])) for p in members), Decimal(0))
            failing = sum(p["Failing"] for p in members)
            require(len(members) == native["Total"] == count, "logical check total differs from native summary")
            require(failing == native["Failing"], "logical failure count differs from native summary")
            require(wns == number(native["WNS"]) and tns == number(native["TNS"]),
                    "worst-per-check WNS/TNS differs from native summary")
            result["Groups"].append({"Corner":corner, "LaunchClock":pair[0], "CaptureClock":pair[1],
                                     "NativeSummary":native, "LogicalChecks":len(members),
                                     "NativeVariants":sum(len(p["NativeVariants"]) for p in members),
                                     "ReconstructedWNS":str(wns), "ReconstructedTNS":str(tns),
                                     "ReconstructedFailing":failing})
        result["Corners"][corner] = {"NativeVariantCount":len(rows), "LogicalCheckCount":len(checks),
                                      "FailingChecks":sum(p["Failing"] for p in checks),
                                      "NonnegativeChecks":sum(not p["Failing"] for p in checks),
                                      "DualCaptureEdgeChecks":multiple, "Checks":checks}
    result["Limitations"] = ["This audit proves report coverage and arithmetic, not reset-release safety.",
                              "Entry RDC, native pin queries and resulting exception effects need separate evidence."]
    return result


def audit_file(report):
    report = Path(report).resolve()
    before = recovery.sha(report)
    with report.open(encoding="utf-8-sig") as stream:
        paths, summaries = parse_lines(stream)
    result = audit(paths, summaries)
    require(recovery.sha(report) == before, "report changed during audit")
    result["Input"] = {"Path":str(report), "SHA256":before}
    result["AuditToolSHA256"] = recovery.sha(__file__)
    result["ScopeClassifierSHA256"] = recovery.sha(recovery.__file__)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)
    result = audit_file(args.report)
    data = json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    if args.output:
        with args.output.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(data)
    else:
        print(data, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
