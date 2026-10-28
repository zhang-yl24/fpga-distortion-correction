"""Read-only CPU audit of a historical DDR reference; never a timing waiver.

Encrypted source bodies are only streamed into SHA256. No EDA or device process
is started. Clock-pair check counts do not establish endpoint identity.
"""
from pathlib import Path
import argparse
from collections import Counter
import hashlib
import json
import math
import re
import xml.etree.ElementTree as ET


REPO = Path(__file__).resolve().parents[2]
PROJECT = REPO / "distortion"
IP_RELATIVE = Path("platform/video_base/ipcore/ddr3_test")
REFERENCE = REPO / "vendor/reference/ddr/2_9_ddr3_test/2_9_ddr3_test/ddr3_test/ipcore/ddr3_test"
KINDS = tuple(corner + "_" + kind for corner in ("slow", "fast")
              for kind in ("setup", "hold", "recovery", "removal", "mpw"))
ALIASES = {"I_ips_ddr_top": "u_ddr3_test_h", "ref_clk_p": "clk_p", "free_clk": "board27"}
EXCLUDED_DDR_PAIRS = tuple(pair for bank in (0, 1) for pair in (
    ("rst_clk", f"phy_dq_clk_{bank}"), ("ddrphy_sysclk", f"phy_dq_clk_{bank}"),
    ("rst_clk", f"phy_dq_sysclk_{bank}")))


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def record(path):
    path = Path(path).resolve()
    return {"Path": str(path), "SHA256": sha(path)}


def _json_sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                                    ensure_ascii=False).encode("utf-8")).hexdigest()


def _element(element):
    return {"Tag": element.tag, "Attributes": dict(element.attrib),
            "Text": (element.text or "").strip(), "Children": [_element(x) for x in element]}


def read_idf(path):
    root = ET.parse(path).getroot()
    header, params = root.find("header"), root.find("param_list")
    if header is None or params is None:
        raise ValueError("IDF header and full parameter list are required")
    values, definitions = {}, {}
    for param in params.findall("param"):
        name = param.findtext("name")
        if not name or name in definitions or param.find("value") is None:
            raise ValueError("missing or duplicate IDF parameter")
        definitions[name] = _element(param)
        values[name] = param.findtext("value") or ""
    if not definitions:
        raise ValueError("empty IDF parameter list")
    return {"Header": _element(header), "Parameters": definitions, "Values": values}


def compare_idf(reference, current):
    left, right = read_idf(reference), read_idf(current)
    differences = sorted(name for name in left["Parameters"].keys() | right["Parameters"].keys()
                         if left["Parameters"].get(name) != right["Parameters"].get(name))
    geometry = ("MEM_TYPE", "MEM_DQ_WIDTH", "BANK_NUM", "MEM_ADDR_WIDTH", "MEM_BANK_WIDTH",
                "CTRL_ADDR_WIDTH", "CLKIN_FREQ", "DFI_CLK_PERIOD")
    return {"Reference": record(reference), "Current": record(current),
            "BytesIdentical": sha(reference) == sha(current),
            "HeaderIdentical": left["Header"] == right["Header"],
            "ReferenceHeaderSHA256": _json_sha(left["Header"]),
            "CurrentHeaderSHA256": _json_sha(right["Header"]),
            "ReferenceParametersSHA256": _json_sha(left["Parameters"]),
            "CurrentParametersSHA256": _json_sha(right["Parameters"]),
            "ReferenceParameterCount": len(left["Parameters"]),
            "CurrentParameterCount": len(right["Parameters"]),
            "AllParametersIdentical": not differences, "DifferingParameters": differences,
            "Geometry": {name: {"Reference": left["Values"].get(name),
                                 "Current": right["Values"].get(name)} for name in geometry}}


def compare_sources(reference_ip, project, source_manifest, *, ip_relative=IP_RELATIVE,
                    expected_source_count=74, expected_vp_count=71):
    reference_ip, project = Path(reference_ip).resolve(), Path(project).resolve()
    manifest = json.loads(Path(source_manifest).read_text(encoding="utf-8-sig"))
    names, hashes = manifest.get("source_files"), manifest.get("SourceSHA256")
    if (not isinstance(names, list) or any(not isinstance(n, str) for n in names)
            or len(set(names)) != len(names) or not isinstance(hashes, dict)):
        raise ValueError("unique source_files and SourceSHA256 closure required")
    prefix = Path(ip_relative).as_posix().rstrip("/") + "/"
    idf_name = prefix + "ddr3_test.idf"
    if idf_name not in names or hashes.get(idf_name, "").lower() != sha(project / idf_name):
        raise ValueError("current IDF is absent from or differs from its source manifest binding")
    selected = [name for name in names if name.startswith(prefix) and name != idf_name]
    vp_count = sum(Path(name).suffix.lower() == ".vp" for name in selected)
    if len(selected) != expected_source_count or vp_count != expected_vp_count:
        raise ValueError("DDR synthesis source closure count differs from the declared audit scope")
    rows = []
    for name in selected:
        current = (project / name).resolve()
        reference = (reference_ip / name[len(prefix):]).resolve()
        if (not current.is_relative_to((project / ip_relative).resolve())
                or not reference.is_relative_to(reference_ip)
                or not current.is_file() or not reference.is_file()):
            raise ValueError("DDR source missing or outside the declared IP closure: " + name)
        bound = hashes.get(name)
        if not isinstance(bound, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", bound):
            raise ValueError("DDR source manifest hash missing or invalid: " + name)
        a, b = sha(reference), sha(current)
        rows.append({"RelativePath": name[len(prefix):], "Reference": str(reference),
                     "Current": str(current), "ReferenceSHA256": a, "CurrentSHA256": b,
                     "ManifestSHA256": bound.lower(), "BytesIdentical": a == b,
                     "CurrentManifestBindingMatches": b == bound.lower()})
    return {"Manifest": record(source_manifest), "SynthesisSourceCount": len(rows),
            "EncryptedVPCount": vp_count, "EncryptedBodyHandling": "SHA256 only; no decoding or text output",
            "AllSourceBytesIdentical": all(row["BytesIdentical"] for row in rows),
            "AllCurrentManifestBindingsMatch": all(row["CurrentManifestBindingMatches"] for row in rows),
            "Sources": rows}


def normalize(text):
    for old, new in ALIASES.items():
        text = re.sub(r"(?<![A-Za-z0-9_])" + re.escape(old) + r"(?![A-Za-z0-9_])", new, text)
    text = re.sub(r"\{([^{}\s]+)\}", r"\1", text)
    return " ".join(text.split())


def read_fdc(path):
    groups = {name: [] for name in ("DDRClocks", "SupportClocks", "DDRGeneratedClocks",
                                    "DDRMulticycle", "DDRUncertainty", "DDRPAP_LOC", "AsyncGroups")}
    for raw in Path(path).read_text(encoding="utf-8-sig").replace("\\\n", " ").splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        line = normalize(raw)
        command = line.split()[0]
        ddr = bool(re.search(r"\b(?:ref_clk|rst_clk|ddrphy_sysclk|phy_dq_(?:sys)?clk_\d+)\b", line))
        key = None
        if command == "create_clock":
            match = re.search(r"-name\s+(\S+)", line)
            if match and match[1] == "board27":
                key = "SupportClocks"
            elif ddr:
                key = "DDRClocks"
        elif command == "create_generated_clock" and ddr:
            key = "DDRGeneratedClocks"
        elif command == "set_multicycle_path" and ddr:
            key = "DDRMulticycle"
        elif command == "set_clock_uncertainty" and ddr:
            key = "DDRUncertainty"
        elif command == "define_attribute" and "PAP_LOC" in line and "u_ddr3_test_h" in line:
            key = "DDRPAP_LOC"
        elif command == "set_clock_groups" and "-asynchronous" in line:
            key = "AsyncGroups"
        if key:
            groups[key].append(line)
    return groups


def compare_fdc(reference, current):
    left, right = read_fdc(reference), read_fdc(current)
    for categories in (left, right):
        if any(not categories[name] for name in ("DDRClocks", "DDRGeneratedClocks", "DDRMulticycle",
                                                "DDRUncertainty", "DDRPAP_LOC")):
            raise ValueError("required DDR constraint category is missing")
    result = {}
    for name in left:
        a, b = Counter(left[name]), Counter(right[name])
        result[name] = {"ReferenceCount": sum(a.values()), "CurrentCount": sum(b.values()),
                        "Identical": a == b, "OnlyReference": list((a-b).elements()),
                        "OnlyCurrent": list((b-a).elements())}
    return {"Reference": record(reference), "Current": record(current), "Aliases": ALIASES,
            "Normalization": "Whitespace and braces around single atoms only; no Tcl execution or numeric relaxation.",
            "SupportClockDifferenceRetained": "free_clk/board27 period and source-port differences remain visible.",
            "Categories": result}


def table(tree, name, *, recursive=False):
    tables = [node for node in tree.iter("table") if node.get("id") == name]
    if len(tables) != 1 or tables[0].find("column_headers") is None:
        raise ValueError("missing or duplicate timing table: " + name)
    headers = [data.text or "" for data in tables[0].find("column_headers").findall("data")]
    if not headers or len(set(headers)) != len(headers):
        raise ValueError("invalid timing table headers: " + name)
    rows = []
    for row in tables[0].findall(".//row" if recursive else "row"):
        values = [data.text or "" for data in row.findall("data")]
        if len(values) != len(headers):
            raise ValueError("timing table row schema mismatch: " + name)
        rows.append(dict(zip(headers, values)))
    if not rows:
        raise ValueError("empty timing table: " + name)
    return rows


def count(value):
    if not re.fullmatch(r"\d+", value):
        raise ValueError("timing endpoint count must be a nonnegative integer")
    return int(value)


def read_timing(path):
    tree = ET.parse(path).getroot()
    summaries, counts = {}, {}
    for kind in KINDS:
        rows = table(tree, "report_timing_" + kind)
        summaries[kind] = rows
        mpw = kind.endswith("mpw")
        slack_key = "WPWS" if mpw else "WHS(ns)" if kind.endswith(("hold", "removal")) else "WNS(ns)"
        failed_key, total_key = ("Failing End Point", "Total End Point") if mpw else ("Failing Endpoints", "Total Endpoints")
        failed_checks = total_checks = failing_groups = 0
        for row in rows:
            slack = float(row[slack_key])
            failed, total = count(row[failed_key]), count(row[total_key])
            if not math.isfinite(slack) or failed > total:
                raise ValueError("invalid timing slack or endpoint counts")
            failed_checks += failed
            total_checks += total
            failing_groups += bool(slack < 0 or failed)
        counts[kind] = {"Groups": len(rows), "FailingGroups": failing_groups,
                        "FailedChecks": failed_checks, "TotalChecks": total_checks}
    clocks = table(tree, "report_timing_clock_summary", recursive=True)
    interactions = table(tree, "report_clock_interaction")
    required = {"Launch Clock", "Capture Clock", "Inter-Clock Constrains", "Total End Point(TNS)", "Total End Point(THS)"}
    if any(not required.issubset(row) for row in interactions):
        raise ValueError("clock interaction schema incomplete")
    excluded = []
    for row in interactions:
        launch, capture = normalize(row["Launch Clock"]), normalize(row["Capture Clock"])
        if (row["Inter-Clock Constrains"].strip() == "Asynchronous Groups"
                and launch in ("rst_clk", "ddrphy_sysclk")
                and re.fullmatch(r"phy_dq_(?:sys)?clk_[01]", capture)):
            excluded.append({"LaunchClock": launch, "CaptureClock": capture,
                             "TNSChecks": count(row["Total End Point(TNS)"]),
                             "THSChecks": count(row["Total End Point(THS)"])})
    same = {}
    for kind, rows in summaries.items():
        if kind.endswith(("setup", "hold")):
            for row in rows:
                if row["Launch Clock"] == row["Capture Clock"]:
                    same.setdefault(normalize(row["Launch Clock"]), set()).add(kind)
    clock_names = {normalize(row["Clock Name"]) for row in clocks}
    needed = {corner+"_"+kind for corner in ("slow", "fast") for kind in ("setup", "hold")}
    observed_pairs = [(row["LaunchClock"], row["CaptureClock"]) for row in excluded]
    exact_six = len(observed_pairs) == 6 and set(observed_pairs) == set(EXCLUDED_DDR_PAIRS)
    return {"XML": record(path), "TimingSummaryCounts": counts, "TimingSummaries": summaries,
            "ClockSummary": clocks, "ClockInteractions": interactions,
            "InteractionStatusCounts": dict(Counter(row["Inter-Clock Constrains"] for row in interactions)),
            "ClockNames": sorted(clock_names),
            "SameClockSetupHoldCoverage": {name: sorted(kinds) for name, kinds in same.items()},
            "ClocksWithoutFullSameClockSetupHold": sorted(name for name in clock_names if same.get(name) != needed),
            "NoSameClockRowIsNotPass": True,
            "ExcludedDDRClockPairs": excluded,
            "ExactSixExcludedDDRClockPairsObserved": exact_six,
            "ExcludedDDRTNSChecks": sum(row["TNSChecks"] for row in excluded),
            "ExcludedDDRTHSChecks": sum(row["THSChecks"] for row in excluded),
            "CountUnits": "Per-check/per-corner counts, not unique FFs. TNS and THS are separate and are never added."}


def compare_current(reference, current):
    comparisons = {}
    for corner in ("slow", "fast"):
        rows = current["TimingSummaries"][corner + "_recovery"]
        pairs = {}
        for row in rows:
            key = (normalize(row["Launch Clock"]), normalize(row["Capture Clock"]))
            pairs[key] = pairs.get(key, 0) + count(row["Failing Endpoints"])
        matched = []
        for edge in reference["ExcludedDDRClockPairs"]:
            observed = pairs.get((edge["LaunchClock"], edge["CaptureClock"]))
            matched.append({**edge, "CurrentFailingRecoveryChecks": observed,
                            "CountMatchesReferenceExcludedTNS": observed == edge["TNSChecks"]})
        comparisons[corner] = {"ClockPairs": matched,
                               "AllCountsMatch": reference["ExactSixExcludedDDRClockPairsObserved"] and all(row["CountMatchesReferenceExcludedTNS"] for row in matched)}
    return {"CornerComparisons": comparisons, "CountMatchNotEndpointIdentityProven": True,
            "CurrentEndpointIdentityProven": False,
            "Limits": "Clock-pair count correspondence cannot identify physical endpoints or authorize exclusions."}


def audit_reference(reference_ip=REFERENCE, project=PROJECT, source_manifest=None, current_fdc=None,
                    *, current_xml=None, current_final_adf=None,
                    expected_source_count=74, expected_vp_count=71):
    reference_ip, project = Path(reference_ip).resolve(), Path(project).resolve()
    if (current_xml is None) != (current_final_adf is None):
        raise ValueError("current XML and final ADF must be provided together")
    if current_final_adf is not None and Path(current_final_adf).suffix.lower() != ".adf":
        raise ValueError("current final routed ADF required, not a report or PRR index")
    source_manifest = Path(source_manifest) if source_manifest else project / "board/board1080-cdc-reset-sources.json"
    current_fdc = Path(current_fdc) if current_fdc else project / "board/board1080-cdc-reset-diagnostic.fdc"
    reference_timing = read_timing(reference_ip / "pnr/report_timing/rtr.db")
    result = {"Schema": 1, "DiagnosticOnly": True, "HardwareReleaseAllowed": False,
              "PhysicalTimingReady": False, "CurrentRecoveryResolved": False,
              "CurrentEndpointIdentityProven": False, "HardwareAccessed": False, "EDAStarted": False,
              "Scope": "ReferenceOnly" if current_xml is None else "HistoricalAndCurrentCountComparison",
              "IDF": compare_idf(reference_ip / "ddr3_test.idf", project / IP_RELATIVE / "ddr3_test.idf"),
              "SourceClosure": compare_sources(reference_ip, project, source_manifest,
                                                expected_source_count=expected_source_count, expected_vp_count=expected_vp_count),
              "Constraints": compare_fdc(reference_ip / "pnr/ddr_test.fdc", current_fdc),
              "ReferenceTiming": reference_timing,
              "CurrentEndpointIdentityUnverified": True,
              "Limits": "Historical reference != resolution of current 245 recovery failures. No exception is applied. No endpoint identity or current signoff follows from equal source hashes or counts."}
    optional = ("pnr/place_route/test_ddr_pnr.adf", "pnr/place_route/test_ddr_pnr.netlist",
                "pnr/report_timing/test_ddr.rtr", "pnr/ddr3_test.rcf", "generate.log", "readme.txt")
    result["ReferenceArtifacts"] = {name: record(reference_ip/name) for name in optional if (reference_ip/name).is_file()}
    if current_xml is not None:
        current_timing = read_timing(current_xml)
        result["CurrentTiming"] = current_timing
        result["CurrentFinalADF"] = record(current_final_adf)
        result["CurrentXMLToADFBindingIndependentlyVerified"] = False
        result["RecoveryCountComparison"] = compare_current(reference_timing, current_timing)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-ip", type=Path, default=REFERENCE)
    parser.add_argument("--project", type=Path, default=PROJECT)
    parser.add_argument("--source-manifest", type=Path)
    parser.add_argument("--current-fdc", type=Path)
    parser.add_argument("--current-xml", type=Path)
    parser.add_argument("--current-final-adf", type=Path)
    parser.add_argument("--output", type=Path, required=True, help="new JSON output; never overwritten")
    args = parser.parse_args(argv)
    if args.output.exists():
        parser.error("output already exists; evidence is never overwritten")
    try:
        result = audit_reference(args.reference_ip, args.project, args.source_manifest, args.current_fdc,
                                 current_xml=args.current_xml, current_final_adf=args.current_final_adf)
        with args.output.open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(result, stream, indent=2, ensure_ascii=False, allow_nan=False)
            stream.write("\n")
    except (ValueError, KeyError, OSError, ET.ParseError) as error:
        parser.exit(1, str(error) + "\n")
    print(json.dumps({"Output": str(args.output.resolve()), "DiagnosticOnly": True,
                      "HardwareReleaseAllowed": False, "Scope": result["Scope"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
