"""Prepare unapplied exact slash-pin constraints from complete native STA paths.

By default the three DDR slice reset sources enter the FDC. The separately
observed CPD reset pair requires explicit inclusion and its own review.
This CPU tool never loads a PDS database, applies a constraint, or runs EDA.
"""
from pathlib import Path
from collections import Counter
import argparse
import hashlib
import json
import re


IP = "u_ddr3_test_h/u_ddrphy_top/"
SLICE = IP + "ddrphy_slice_top/"
PAIRS = {("rst_clk", "phy_dq_clk_0"): 34, ("ddrphy_sysclk", "phy_dq_clk_0"): 3,
         ("rst_clk", "phy_dq_sysclk_0"): 35, ("rst_clk", "phy_dq_clk_1"): 84,
         ("ddrphy_sysclk", "phy_dq_clk_1"): 4, ("rst_clk", "phy_dq_sysclk_1"): 84}
SOURCES = {IP + "ddrphy_reset_ctrl/ddrphy_dqs_rst": {"RST", "ISR_IOLHR", "OSR_IOLHR"},
           IP + "ddrphy_reset_ctrl/ddrphy_iol_rst": {"TSR"},
           IP + "ddrphy_training_ctrl/ddrphy_dqs_training_rstn": {"RST_TRAINING_N"}}
CPD_SOURCE = IP + "ddrphy_cpd_ctrl/ddrphy_cpd_rstn"
CPD_TARGET = IP + "u_ddrphy_cpd/cpd_inst/RST"
SAFE_NAME = re.compile(r"[A-Za-z0-9_./\[\]-]+\Z")


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def exception_baseline(text):
    headers = re.compile(r"(?m)^\| Exception type\s*:\s*(\S+)\s*$\n\| (Slow|Fast) Corner\s*$")
    matches = list(headers.finditer(text))
    result = []
    for index, match in enumerate(matches):
        if not match[1].startswith("set_false_path("):
            continue
        body = text[match.end():matches[index + 1].start() if index + 1 < len(matches) else len(text)]
        require("No such exception path." in body and not re.search(r"(?m)^Startpoint\s*:", body),
                "baseline already contains false-path exception paths")
        result.append({"ExceptionType": match[1], "Corner": match[2].lower(), "PathCount": 0})
    require(len(result) == 8 and len({(r["ExceptionType"], r["Corner"]) for r in result}) == 8,
            "all eight native false-path baseline sections are required")
    return result


def parse_lines(lines):
    paths, summaries, block = [], {}, []
    section, start_line = None, 0

    def finish():
        text = "".join(block)
        if not text or not re.search(r"(?m)^ Recovery time\s", text):
            return
        group = re.findall(r"(?m)^Path Group\s*:\s*(\S+)\s*$", text)
        if len(group) == 1 and group[0] not in {pair[1] for pair in PAIRS}:
            return
        clocks = re.findall(r"(?m)^ Clock (\S+) \((rising|falling) edge\)", text)
        require(len(clocks) == 2, "recovery path must have two clock edges")
        pair = (clocks[0][0], clocks[1][0])
        if pair not in PAIRS:
            return
        values = {}
        for key, pattern in {
            "Source": r"(?m)^Startpoint\s*:\s*(\S+)\s*$",
            "Endpoint": r"(?m)^Endpoint\s*:\s*(\S+)\s*$",
            "PathGroup": r"(?m)^Path Group\s*:\s*(\S+)\s*$",
        }.items():
            found = re.findall(pattern, text)
            require(len(found) == 1, "missing or ambiguous " + key)
            values[key] = found[0]
        typ = re.findall(r"(?m)^Path Type\s*:\s*(max|min) \((slow|fast) corner\)", text)
        slack = re.findall(r"(?m)^ Slack \((MET|VIOLATED)\)\s+([-+\d.]+)", text)
        require(len(typ) == len(slack) == 1 and typ[0][0] == "max" and
                re.search(r"(?m)^Path Class\s*:\s*async timing path\s*$", text),
                "incomplete recovery path record")
        require(values["PathGroup"] == pair[1], "path group differs from capture clock")
        values.update({"Corner": typ[0][1], "LaunchClock": pair[0], "CaptureClock": pair[1],
                       "LaunchEdge": clocks[0][1], "CaptureEdge": clocks[1][1],
                       "Slack": float(slack[0][1]), "SlackState": slack[0][0],
                       "NativeReportLine": start_line})
        require((values["Slack"] < 0) == (values["SlackState"] == "VIOLATED"),
                "slack state contradicts value")
        paths.append(values)

    for number, line in enumerate(lines, 1):
        header = re.match(r"^Recovery Summary\((Slow|Fast) Corner\):", line)
        if header:
            section = header[1].lower()
        elif re.match(r"^\w+ Summary\(", line):
            section = None
        if section:
            row = re.fullmatch(r"\s*(\S+)\s+(\S+)\s+([-+\d.]+)\s+([-+\d.]+)\s+(\d+)\s+(\d+)\s*", line)
            if row and (row[1], row[2]) in PAIRS:
                key = (section, row[1], row[2])
                require(key not in summaries, "duplicate recovery summary row")
                summaries[key] = {"WNS": float(row[3]), "TNS": float(row[4]),
                                  "Failing": int(row[5]), "Total": int(row[6])}
        if line.startswith("Startpoint"):
            finish()
            block, start_line = [line], number
        elif block:
            block.append(line)
    finish()
    return paths, summaries


def classify(path):
    source, endpoint = path["Source"], path["Endpoint"]
    require(SAFE_NAME.fullmatch(source) and SAFE_NAME.fullmatch(endpoint), "unsafe path object")
    require(source.endswith("/CLK"), "source must be the actual clock pin")
    parent = source.rsplit("/", 2)[0]
    if parent == CPD_SOURCE:
        require(endpoint == CPD_TARGET and path["LaunchClock"] == "rst_clk" and
                path["CaptureClock"] == "phy_dq_sysclk_0", "unexpected CPD path")
        return "cpd_excluded"
    require(parent in SOURCES, "unapproved source in complete recovery evidence")
    require(endpoint.startswith(SLICE) and endpoint.rsplit("/", 1)[1] in SOURCES[parent],
            "data pin, external endpoint, or wrong reset source family")
    require(path["LaunchClock"] == ("ddrphy_sysclk" if "training_ctrl/" in parent else "rst_clk"),
            "source clock domain mismatch")
    return parent.rsplit("/", 1)[1]


def identity(path):
    return tuple(path[key] for key in ("Source", "Endpoint", "LaunchClock", "CaptureClock",
                                       "LaunchEdge", "CaptureEdge"))


def build(paths, summaries, *, include_cpd=False):
    require(type(include_cpd) is bool, "include_cpd must be boolean")
    for path in paths:
        path["Family"] = classify(path)
    corners = {corner: [p for p in paths if p["Corner"] == corner] for corner in ("slow", "fast")}
    for corner, values in corners.items():
        require(len(values) == 244, "all 244 recovery checks are required for " + corner)
        require(len({identity(p) for p in values}) == 244, "duplicate recovery path identities")
        for pair, count in PAIRS.items():
            rows = [p for p in values if (p["LaunchClock"], p["CaptureClock"]) == pair]
            key = (corner, *pair)
            require(key in summaries and len(rows) == summaries[key]["Total"] == count,
                    "native summary/path count mismatch or truncated report")
            require(sum(p["Slack"] < 0 for p in rows) == summaries[key]["Failing"],
                    "native summary/path failure count mismatch")
    require({identity(p) for p in corners["slow"]} == {identity(p) for p in corners["fast"]},
            "corner path identity sets differ")
    require(sum(p["Slack"] >= 0 for p in corners["fast"]) == 11,
            "all 11 nonnegative fast recovery checks are required")
    full_pairs = sorted({(p["Source"], p["Endpoint"]) for p in paths})
    approved = [pair for pair in full_pairs if not pair[0].startswith(CPD_SOURCE + "/")]
    excluded = [pair for pair in full_pairs if pair not in approved]
    require(len(full_pairs) == 126 and len(approved) == 125 and len(excluded) == 1,
            "unexpected exact source/endpoint inventory")
    require(Counter(p["Family"] for p in corners["slow"]) == {
        "ddrphy_dqs_rst": 208, "ddrphy_iol_rst": 28, "ddrphy_dqs_training_rstn": 7, "cpd_excluded": 1},
        "complete source-family coverage differs")
    candidate_pairs = full_pairs if include_cpd else approved
    covered = 244 if include_cpd else 243
    fdc = [f"# Unapplied native slash-pin candidate: {len(candidate_pairs)} exact source/endpoint pairs.",
           f"# Covers {covered} of 244 recovery checks per corner; CPD opt-in={include_cpd}.",
           "# Exact object counts/names require native Timing-5001 log verification.",
           "# get_pins returns opaque handles: Tcl llength cannot prove collection size.",
           "# No clock groups, data endpoints, or fallback patterns.", ""]
    for index, (source, endpoint) in enumerate(candidate_pairs, 1):
        fdc.extend([f"# Exact pair {index:03d}",
                    "set_false_path -from [get_pins -hierarchical -regexp {^" + re.escape(source) + "$}] "
                    "-to [get_pins -hierarchical -regexp {^" + re.escape(endpoint) + "$}]"])
    fdc.append("")
    groups = [{"LaunchClock": pair[0], "CaptureClock": pair[1], "ChecksPerCorner": count,
               "Corners": {corner: summaries[(corner, *pair)] for corner in corners}}
              for pair, count in PAIRS.items()]
    return {"Status": "prepared_unapplied", "All244NativeChecksEnumeratedPerCorner": True,
            "All244CandidateCoverage": include_cpd, "CandidateChecksPerCorner": covered,
            "FullUniqueSourceEndpointPairs": 126, "CandidateUniqueSourceEndpointPairs": len(candidate_pairs),
            "CPDIncluded": include_cpd,
            "SixClockPairs": groups,
            "ExactCandidatePairs": [{"Source": s, "Endpoint": e} for s, e in candidate_pairs],
            "ExcludedPendingCPD": [] if include_cpd else [{"Source": s, "Endpoint": e} for s, e in excluded],
            "FastNonnegativeChecks": [p for p in corners["fast"] if p["Slack"] >= 0],
            "FullNativeRecoveryPaths": paths, "ConstraintsApplied": False,
            "NativeQueryProbeStillRequired": True}, "\n".join(fdc)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--exception-report", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--fdc", type=Path, required=True)
    parser.add_argument("--include-cpd-reset", action="store_true",
                        help="include the separately reviewed exact CPD reset pair")
    args = parser.parse_args()
    with args.report.open(encoding="utf-8-sig") as stream:
        paths, summaries = parse_lines(stream)
    result, fdc = build(paths, summaries, include_cpd=args.include_cpd_reset)
    result["Input"] = {"Path": str(args.report.resolve()), "SHA256": sha(args.report)}
    if args.exception_report:
        result["ExceptionReport"] = {"Path": str(args.exception_report.resolve()),
                                     "SHA256": sha(args.exception_report)}
        result["BaselineFalsePathSections"] = exception_baseline(
            args.exception_report.read_text(encoding="utf-8-sig"))
    result["ToolSHA256"] = sha(__file__)
    result["CandidateFdcSHA256"] = hashlib.sha256(fdc.encode("utf-8")).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.fdc.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.fdc.write_text(fdc, encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("Status", "CandidateChecksPerCorner",
                      "FullUniqueSourceEndpointPairs", "CandidateUniqueSourceEndpointPairs")}, indent=2))


if __name__ == "__main__":
    main()
