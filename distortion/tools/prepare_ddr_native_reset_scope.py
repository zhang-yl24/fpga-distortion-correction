"""Prepare unapplied slash-pin constraints from all 244 native PHY checks.

Stream native XML, retain four actual reset drivers, and use Timing-5001 native
object-name records instead of interpreting opaque Tcl collection handles.
Three primary drivers cover 243 checks/125 pins. The fourth CPD driver is
explicit and omitted from FDC unless --include-cpd and both native names match.
No EDA, main-FDC edit, or hardware operation is performed.
"""
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime, timezone
import argparse
import hashlib
import io
import json
import re
import xml.etree.ElementTree as ET

import prepare_ddr_ip_reset_constraints as reference


PROJECT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()
PREFIX = "u_ddr3_test_h/u_ddrphy_top/"
ALLOWED_PINS = frozenset(("RST", "RST_TRAINING_N", "TSR", "ISR_IOLHR", "OSR_IOLHR"))
PAIRS = {("rst_clk", "phy_dq_clk_0"): 34, ("ddrphy_sysclk", "phy_dq_clk_0"): 3,
         ("rst_clk", "phy_dq_sysclk_0"): 35, ("rst_clk", "phy_dq_clk_1"): 84,
         ("ddrphy_sysclk", "phy_dq_clk_1"): 4, ("rst_clk", "phy_dq_sysclk_1"): 84}
DRIVERS = {"dqs_reset": (PREFIX + "ddrphy_reset_ctrl/ddrphy_dqs_rst", 208, 104),
           "iol_reset": (PREFIX + "ddrphy_reset_ctrl/ddrphy_iol_rst", 28, 14),
           "training_reset": (PREFIX + "ddrphy_training_ctrl/ddrphy_dqs_training_rstn", 7, 7),
           "cpd_reset": (PREFIX + "ddrphy_cpd_ctrl/ddrphy_cpd_rstn", 1, 1)}
TIMING_MATCH = re.compile(r"^I: Timing-5001: The pattern '(.*)' in command '(.*)' match (\d+) objects below: (.*)$")
REQUIRED = {"Launch Clock", "Capture Clock", "Start Point", "End Point", "Slack"}


def _name(value, *, require_ip=True):
    if (not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_./\[\]-]+", value)
            or any(x in ("", ".", "..") for x in value.split("/"))
            or require_ip and not value.startswith(PREFIX)):
        raise ValueError("unsafe or non-IP slash-pin name")
    return value


def extract_checks(xml):
    """One bounded-memory pass: remove each completed native table."""
    needed = {f"report_timing_{c}_{part}" for c in ("slow", "fast") for part in ("recovery", "path_recovery")}
    found, stack = {}, []
    for event, element in ET.iterparse(xml, events=("start", "end")):
        if event == "start":
            stack.append(element)
            continue
        if element.tag == "table":
            name = element.get("id", "")
            if name in needed:
                if name in found:
                    raise ValueError("duplicate required native table")
                headers = [x.text or "" for x in element.findall("./column_headers/data")]
                rows = []
                for row in element.findall("./row"):
                    values = [x.text or "" for x in row.findall("data")]
                    if len(values) != len(headers):
                        raise ValueError("native row schema mismatch")
                    data = dict(zip(headers, values))
                    if (data.get("Launch Clock"), data.get("Capture Clock")) in PAIRS:
                        rows.append(data)
                found[name] = rows
            if len(stack) > 1:
                stack[-2].remove(element)
            element.clear()
        stack.pop()
        if needed <= found.keys():
            break
    if set(found) != needed:
        raise ValueError("incomplete two-corner native recovery tables")
    checks = {}
    for corner in ("slow", "fast"):
        summary = found[f"report_timing_{corner}_recovery"]
        totals = {(r["Launch Clock"], r["Capture Clock"]): int(r["Total Endpoints"]) for r in summary}
        if len(summary) != 6 or totals != PAIRS:
            raise ValueError("six native PHY clock groups/244 totals differ")
        rows = found[f"report_timing_{corner}_path_recovery"]
        if any(not REQUIRED <= row.keys() for row in rows):
            raise ValueError("required native path columns missing")
        counts = Counter((r["Launch Clock"], r["Capture Clock"]) for r in rows)
        identities = {(r["Launch Clock"], r["Capture Clock"], r["Start Point"], r["End Point"]) for r in rows}
        if len(rows) != 244 or len(identities) != 244 or dict(counts) != PAIRS:
            raise ValueError("path report is truncated, duplicated, or not all244 PHY checks")
        for pair in PAIRS:
            expected = next(r for r in summary if (r["Launch Clock"], r["Capture Clock"]) == pair)
            actual = sum(float(r["Slack"]) < 0 for r in rows if (r["Launch Clock"], r["Capture Clock"]) == pair)
            if actual != int(expected["Failing Endpoints"]):
                raise ValueError("detailed negative checks do not match native summaries")
        checks[corner] = rows
    identity = lambda rows: {(r["Launch Clock"], r["Capture Clock"], r["Start Point"], r["End Point"]) for r in rows}
    if identity(checks["slow"]) != identity(checks["fast"]):
        raise ValueError("two-corner check identities differ")
    return checks


def group_checks(checks):
    groups = {family: {"SourceClockPin": None, "Targets": set(), "ChecksByCorner": {}} for family in DRIVERS}
    for corner in ("slow", "fast"):
        grouped = defaultdict(list)
        for row in checks[corner]:
            source, target = _name(row["Start Point"]), _name(row["End Point"])
            if not source.endswith("/CLK") or "rst_seq_rstn_sync" in source + target:
                raise ValueError("external entry or invalid source cannot enter scope")
            pin = target.rsplit("/", 1)[-1]
            if pin not in ALLOWED_PINS:
                raise ValueError("data/D/TX_DATA or unapproved endpoint cannot enter scope")
            parent = source.rsplit("/", 2)[0]
            families = [name for name, (expected, _, _) in DRIVERS.items() if parent == expected]
            if len(families) != 1:
                raise ValueError("unknown actual reset driver")
            family = families[0]
            if ((family == "training_reset" and pin != "RST_TRAINING_N")
                    or (family == "iol_reset" and pin != "TSR")
                    or (family == "dqs_reset" and pin not in ("RST", "ISR_IOLHR", "OSR_IOLHR"))
                    or (family == "cpd_reset" and target != PREFIX + "u_ddrphy_cpd/cpd_inst/RST")):
                raise ValueError("target reset family differs from its actual driver")
            if (family != "cpd_reset" and not target.startswith(PREFIX + "ddrphy_slice_top/")):
                raise ValueError("target outside exact PHY slice scope")
            previous = groups[family]["SourceClockPin"]
            if previous is not None and previous != source:
                raise ValueError("ambiguous actual source pin in a driver family")
            groups[family]["SourceClockPin"] = source
            groups[family]["Targets"].add(target)
            grouped[family].append(row)
        for family, (_, expected_checks, expected_targets) in DRIVERS.items():
            rows = grouped[family]
            if len(rows) != expected_checks or len({r["End Point"] for r in rows}) != expected_targets:
                raise ValueError("actual driver coverage differs from244/126 inventory")
            groups[family]["ChecksByCorner"][corner] = rows
    for value in groups.values():
        value["Targets"] = sorted(value["Targets"])
    if len(set(pin for g in groups.values() for pin in g["Targets"])) != 126:
        raise ValueError("expected126 unique PHY endpoint pins")
    return groups


def parse_native_matches(path):
    records = []
    with Path(path).open(encoding="utf-8-sig", errors="replace") as stream:
        for line in stream:
            match = TIMING_MATCH.fullmatch(line.rstrip("\r\n"))
            if not match:
                continue
            pattern, command, count, rendered = match.groups()
            if not command.startswith("get_pins "):
                continue
            names = rendered.split()
            if len(names) != int(count) or len(set(names)) != len(names):
                raise ValueError("native Timing-5001 count/list mismatch")
            for name in names:
                if not name.startswith("t:"):
                    raise ValueError("native pin records must use the measured t: prefix")
                # A native diagnostic may also query board reset entry pins.
                # Retain safe evidence records; only exact allowed IP sets may
                # be selected by make_scope below.
                _name(name[2:], require_ip=False)
            records.append({"Pattern": pattern, "Command": command, "Count": int(count), "NativeNames": names})
    if not records:
        raise ValueError("no native Timing-5001 full pin-name evidence")
    return records


def make_scope(groups, native_records, *, include_cpd=False):
    if type(include_cpd) is not bool:
        raise ValueError("include_cpd must be explicitly boolean")
    emitted, proof = [], []
    lines = ["# DiagnosticOnly=true; NotApplied=true; EDAStarted=false",
             "# Actual native slash-pin reset checks; no inst:pin aliases or opaque-handle counts.",
             "# Collection matching is proven only by Timing-5001 object-name records; path effects still require audit."]
    for family, group in groups.items():
        if family == "cpd_reset" and not include_cpd:
            continue
        source = group["SourceClockPin"]
        targets = group["Targets"]
        _name(source)
        for pin in targets:
            _name(pin)
        for role, names in (("from", [source]), ("to", targets)):
            expected = {"t:" + pin for pin in names}
            matches = [record for record in native_records if set(record["NativeNames"]) == expected]
            if not matches:
                raise ValueError("no exact native object match record: " + family + ":" + role)
            proof.append({"Family": family, "Role": role, "Count": len(names), "NativeEvidence": matches[0]})
        # Native query records show bare slash names match t:slash-name objects.
        # Do not use the older, untested backend-colon pin representation.
        lines.append("set_false_path -from [get_pins -hierarchical -regexp {" + reference.exact_regex([source])
                     + "}] -to [get_pins -hierarchical -regexp {" + reference.exact_regex(targets) + "}]")
        emitted.append(family)
    return "\n".join(lines) + "\n", proof, emitted


def inventory_tsv(checks):
    columns = ["Corner", "Launch Clock", "Capture Clock", "Start Point", "End Point", "Slack"]
    rows = ["\t".join(columns)]
    for corner in ("slow", "fast"):
        for row in sorted(checks[corner], key=lambda r: (r["Launch Clock"], r["Capture Clock"], r["End Point"])):
            values = [corner] + [row[name] for name in columns[1:]]
            if any("\t" in value or "\n" in value or "\r" in value for value in values):
                raise ValueError("unsafe inventory TSV cell")
            rows.append("\t".join(values))
    return "\n".join(rows) + "\n"


def prepare(project, xml, native_log, out_dir, *, include_cpd=False):
    project = Path(project).resolve()
    repo = project.parent
    xml = reference._within(project, xml)
    native_log = reference._within(project, native_log)
    input_hashes = {xml.relative_to(repo).as_posix(): reference.closure.sha(xml),
                    native_log.relative_to(repo).as_posix(): reference.closure.sha(native_log)}
    checks = extract_checks(xml)
    groups = group_checks(checks)
    records = parse_native_matches(native_log)
    fdc, proof, emitted = make_scope(groups, records, include_cpd=include_cpd)
    hashes = reference.bind_inputs(project, reference.closure.DEFAULT_MANIFEST, reference.VENDOR_FDC, reference.AUDIT)
    hashes.update(input_hashes)
    for helper in (SELF, Path(reference.__file__).resolve()):
        helper = reference._within(repo, helper)
        hashes[helper.relative_to(repo).as_posix()] = reference.closure.sha(helper)
    root = project / "build/ddr-native-reset-scope"
    output = Path(out_dir).absolute()
    if (root.resolve() != root or output.resolve() != output or output.parent != root
            or not re.fullmatch(r"[A-Za-z0-9_-]+", output.name)
            or output.exists() and (not output.is_dir() or any(output.iterdir()))):
        raise ValueError("output must be a fresh child of build/ddr-native-reset-scope")
    for name, digest in hashes.items():
        if reference.closure.sha(reference._within(repo, repo / name)) != digest:
            raise ValueError("bound input changed during preparation")
    inventory = inventory_tsv(checks)
    targets = sorted({pin for group in groups.values() for pin in group["Targets"]})
    plan = {"Schema": "ddr-native-actual-reset-scope-v1", "DiagnosticOnly": True, "NotApplied": True,
            "EDAStarted": False, "HardwareAccessed": False, "HardwareReleaseAllowed": False,
            "PreparedUTC": datetime.now(timezone.utc).isoformat(), "InputSHA256RepoRelative": hashes,
            "ActualCheckRowsPerCorner": 244, "ActualUniqueTargets": 126, "ActualDriverFamilies": 4,
            "DriverGroups": groups, "Targets": targets, "NativeNameFormat": "t:<full hierarchy>/<pin>",
            "QueryNameFormat": "<full hierarchy>/<pin>; exact anchored regexp; no inst:pin alias",
            "OpaqueCollectionHandlesUsedAsCounts": False, "NativeMatchedObjectProof": proof,
            "EmittedFamilies": emitted, "CPDIncluded": include_cpd,
            "EmittedCheckCountPerCorner": sum(DRIVERS[name][1] for name in emitted),
            "EmittedUniqueTargetCount": sum(DRIVERS[name][2] for name in emitted),
            "CPDExcludedChecks": [] if include_cpd else groups["cpd_reset"]["ChecksByCorner"]["slow"],
            "All244NativeChecksEnumerated": True, "All244ExceptionEffectsValidated": False,
            "InventoryTSV": {"Path": (output / "inventory.tsv").relative_to(repo).as_posix(),
                             "SHA256": hashlib.sha256(inventory.encode("utf-8")).hexdigest()},
            "CandidateFDC": {"Path": (output / "native-reset-scope.fdc").relative_to(repo).as_posix(),
                             "SHA256": hashlib.sha256(fdc.encode("ascii")).hexdigest()},
            "Acceptance": ["Inventory has four actual drivers; do not assign the CPD endpoint to dqs_reset.",
                "Default emits three primary families:243 checks/125 pins; CPD stays timed unless explicitly included with exact native proof.",
                "This preparation applies no constraint; native exception/path effects still need a separate loaded-DB audit.",
                "Board27 reset entry, custom CDC, data D/TX_DATA setup/hold and unrelated pin families must remain timed."]}
    output.mkdir(parents=True, exist_ok=True)
    for name, content, encoding in (("inventory.tsv", inventory, "utf-8"), ("native-reset-scope.fdc", fdc, "ascii")):
        with (output / name).open("x", encoding=encoding, newline="\n") as stream:
            stream.write(content)
    with (output / "plan.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(plan, stream, indent=2, ensure_ascii=False)
        stream.write("\n")
    return plan


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--xml", required=True, type=Path)
    parser.add_argument("--native-query-log", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--include-cpd", action="store_true", help="requires separate exact native source+target proof")
    args = parser.parse_args(argv)
    try:
        result = prepare(PROJECT, args.xml, args.native_query_log, args.out_dir, include_cpd=args.include_cpd)
    except (ValueError, OSError, KeyError, UnicodeError, ET.ParseError) as exc:
        parser.error(str(exc))
    print(json.dumps({"NotApplied": True, "InventoryChecksPerCorner": 244, "InventoryTargets": 126,
                      "EmittedChecksPerCorner": result["EmittedCheckCountPerCorner"],
                      "EmittedTargets": result["EmittedUniqueTargetCount"], "CandidateFDC": result["CandidateFDC"]["Path"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
