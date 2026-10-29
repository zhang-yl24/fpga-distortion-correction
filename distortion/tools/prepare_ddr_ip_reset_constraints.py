"""Prepare a separate, unapplied IP reset exception candidate; no EDA or hardware.

Only generated readable Inst/Pin inventories are parsed. Vendor sources are
hashed without decoding. Pin existence does not prove connectivity, PDS query
matching, or coverage of all 244 checks. The parent flow must probe and audit
these exact objects before applying any candidate.
"""
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone
import argparse
import hashlib
import json
import re
import xml.etree.ElementTree as ET

import prepare_board1080_timing as closure


PROJECT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()
IP_PREFIX = "u_ddr3_test_h/u_ddrphy_top/"
SLICE_PREFIX = IP_PREFIX + "ddrphy_slice_top/"
VENDOR_FDC = "vendor/reference/ddr/2_9_ddr3_test/2_9_ddr3_test/ddr3_test/ipcore/ddr3_test/pnr/ddr_test.fdc"
AUDIT = "results/ddr-reference-audit-20261028.json"
RESET_PINS = frozenset(("RST", "RST_TRAINING_N", "TSR", "ISR_IOLHR", "OSR_IOLHR"))
SOURCES = {
    "dqs_reset": (IP_PREFIX + "ddrphy_reset_ctrl/ddrphy_dqs_rst", "gopQ", "rst_clk"),
    "iol_reset": (IP_PREFIX + "ddrphy_reset_ctrl/ddrphy_iol_rst", "gopLUT6L5Q", "rst_clk"),
    "training_reset": (IP_PREFIX + "ddrphy_training_ctrl/ddrphy_dqs_training_rstn", "gopLUT6L5Q", "ddrphy_sysclk"),
}
EXPECTED_PRIMITIVES = {"gopDDRPHY": 4, "gopDQSL": 3, "gopTSERDES": 14, "gopIOL": 65,
                       "gopDDRPHY_IOCLKDIV": 2, "gopPPLL": 2}
EXPECTED_PIN_NAMES = {"gopDDRPHY": {"RST", "RST_TRAINING_N"},
                      "gopDQSL": {"RST", "RST_TRAINING_N"}, "gopTSERDES": {"TSR"},
                      "gopIOL": {"ISR_IOLHR", "OSR_IOLHR"},
                      "gopDDRPHY_IOCLKDIV": {"RST"}, "gopPPLL": {"RST"}}
EXPECTED_GROUPS = {"dqs_reset": 137, "iol_reset": 14, "training_reset": 7}
NAME = re.compile(r"[A-Za-z0-9_./\[\]-]+\Z")


def parse_netlist(path):
    """Parse generated Inst/Pin metadata, never encrypted or binary input."""
    path = Path(path)
    if path.suffix.lower() != ".netlist":
        raise ValueError("only generated readable .netlist Inst/Pin metadata is accepted")
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    if not lines or lines[0] != "Port":
        raise ValueError("missing generated netlist Port header")
    instances = {}
    index = 0
    while index < len(lines):
        if lines[index] != "Inst":
            index += 1
            continue
        if index + 2 >= len(lines) or lines[index + 2] != "Pin":
            raise ValueError("malformed Inst/Pin record")
        fields = lines[index + 1].split(";")
        if len(fields) != 2 or not all(fields):
            raise ValueError("invalid instance header")
        name, primitive = fields
        if name in instances:
            raise ValueError("duplicate instance in readable inventory: " + name)
        pins = {}
        index += 3
        while index < len(lines) and lines[index] and lines[index] not in ("Inst", "Net", "Clock"):
            fields = lines[index].split(";")
            if len(fields) != 2 or fields[1] not in ("1", "2", "3") or fields[0] in pins:
                raise ValueError("invalid or duplicate pin record: " + name)
            pins[fields[0]] = fields[1]
            index += 1
        instances[name] = {"Primitive": primitive, "Pins": pins}
    if not instances:
        raise ValueError("empty instance inventory")
    return instances


def _safe_object(name):
    if not NAME.fullmatch(name) or any(p in ("", ".", "..") for p in name.split("/")):
        raise ValueError("unsafe selected object name")
    return name


def pin_object(instance, pin):
    _safe_object(instance)
    if pin not in RESET_PINS | {"CLK"}:
        raise ValueError("data or unapproved pin cannot be an exception object")
    if not instance.startswith(IP_PREFIX):
        raise ValueError("exception object outside the DDR IP")
    return instance + ":" + pin


def inventory(instances):
    sources = {}
    for family, (parent, primitive, domain) in SOURCES.items():
        matches = [(n, v) for n, v in instances.items() if n.rsplit("/", 1)[0] == parent]
        if len(matches) != 1:
            raise ValueError("missing or ambiguous exact source parent: " + family)
        name, cell = matches[0]
        if cell["Primitive"] != primitive or cell["Pins"].get("CLK") != "1":
            raise ValueError("wrong source primitive or missing input CLK: " + family)
        sources[family] = {"CanonicalParent": parent, "ActualInstance": name,
                           "Primitive": primitive, "SourceClockDomain": domain,
                           "ActualClockPin": pin_object(name, "CLK"),
                           "Alias": {"LogicalParentCLK": parent + "/CLK",
                                     "ActualBackendPin": pin_object(name, "CLK")},
                           "SuffixDiscovery": "One exact parent child; no assumed perm suffix or glob"}
    cells, candidates, excluded = [], {key: [] for key in SOURCES}, []
    for name, cell in instances.items():
        if not name.startswith(SLICE_PREFIX):
            continue
        pins = RESET_PINS.intersection(cell["Pins"])
        if not pins:
            continue
        primitive = cell["Primitive"]
        if primitive not in EXPECTED_PRIMITIVES or pins != EXPECTED_PIN_NAMES[primitive]:
            raise ValueError("unexpected reset primitive family/pins within IP slice")
        if any(cell["Pins"][p] != "1" for p in pins):
            raise ValueError("reset target must be an input pin")
        if primitive == "gopDDRPHY" and not re.fullmatch(
                re.escape(SLICE_PREFIX) + r"i_dqs_group\[[0-3]\]\.ddrphy_data_slice/u_ddc_dq/ddc_inst_PHY", name):
            raise ValueError("DDRPHY training target has an unexpected exact hierarchy")
        if primitive == "gopDQSL" and not re.fullmatch(
                re.escape(SLICE_PREFIX) + r"i_ca_group\[[0-2]\]\.u_ddc_ca/ddc_inst", name):
            raise ValueError("DQSL training target has an unexpected exact hierarchy")
        objects = [pin_object(name, p) for p in sorted(pins)]
        cells.append({"Instance": name, "Primitive": primitive, "InputResetPins": objects})
        if primitive in ("gopDDRPHY_IOCLKDIV", "gopPPLL"):
            excluded.extend(objects)
        elif primitive in ("gopDDRPHY", "gopDQSL"):
            candidates["dqs_reset"].append(pin_object(name, "RST"))
            candidates["training_reset"].append(pin_object(name, "RST_TRAINING_N"))
        elif primitive == "gopTSERDES":
            candidates["iol_reset"].append(pin_object(name, "TSR"))
        else:
            candidates["dqs_reset"].extend(objects)
    counts = dict(Counter(v["Primitive"] for v in cells))
    if counts != EXPECTED_PRIMITIVES:
        raise ValueError("reset primitive inventory count mismatch")
    for family, pins in candidates.items():
        pins.sort()
        if len(pins) != EXPECTED_GROUPS[family] or len(set(pins)) != len(pins):
            raise ValueError("missing or duplicate family target pins: " + family)
    return {"Sources": sources, "CandidateTargets": candidates, "CandidateTargetCount": 158,
            "RawResetInstanceCount": len(cells), "RawResetPinCount": sum(len(v["InputResetPins"]) for v in cells),
            "PrimitiveCounts": counts, "RawResetInstances": cells,
            "ExcludedPLLAndDividerPins": sorted(excluded),
            "DriverLoadConnectivityAvailable": False, "All244ChecksMatched": False}


def exact_regex(objects):
    if not objects or len(set(objects)) != len(objects):
        raise ValueError("nonempty unique exact objects required")
    return "^(" + "|".join(re.escape(n) for n in objects) + ")$"


def make_fdc(objects):
    lines = ["# DiagnosticOnly=true; NotApplied=true; EDAStarted=false",
             "# Standalone IP reset/training candidate; never overwrite the primary diagnostic FDC.",
             "# 158 pin-existence candidates are NOT 244 proven connected timing checks.",
             "# Probe exact backend inst:pin collections after map; zero/ambiguous matches must fail.",
             "# No board27/free_clk groups, external reset-entry exception or data endpoint cut."]
    queries = []
    for family in SOURCES:
        source = objects["Sources"][family]["ActualClockPin"]
        targets = objects["CandidateTargets"][family]
        source_regex, target_regex = exact_regex([source]), exact_regex(targets)
        lines.append("# " + family + ": one source CLK; " + str(len(targets)) + " exact target pin candidates")
        lines.append("set_false_path -from [get_pins -hierarchical -regexp {" + source_regex
                     + "}] -to [get_pins -hierarchical -regexp {" + target_regex + "}]")
        queries.append({"Family": family, "FromRegex": source_regex, "ExpectedSourceObjects": 1,
                        "ToRegex": target_regex, "ExpectedTargetObjects": len(targets),
                        "PDSCollectionMatchingVerified": False})
    return "\n".join(lines) + "\n", queries


def _within(root, path):
    root, path = Path(root).resolve(), Path(path).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError("input file missing or outside the repository")
    return path


def bind_inputs(project, manifest_name, vendor_fdc_name, audit_name):
    project = Path(project).resolve()
    repo = project.parent
    roles = closure.validate_manifest(project, manifest_name)
    vendor_fdc = _within(repo, repo / closure.relative_name(vendor_fdc_name))
    audit_path = closure.inside(project, audit_name)
    audit = json.loads(audit_path.read_text(encoding="utf-8-sig"))
    current_idf = closure.inside(project, closure.IDF)
    reference_ip = vendor_fdc.parent.parent
    reference_idf = _within(repo, reference_ip / "ddr3_test.idf")
    rows = audit.get("SourceClosure", {}).get("Sources", [])
    if (audit.get("IDF", {}).get("BytesIdentical") is not True
            or audit.get("IDF", {}).get("Current", {}).get("SHA256") != closure.sha(current_idf)
            or closure.sha(reference_idf) != closure.sha(current_idf)
            or audit.get("Constraints", {}).get("Reference", {}).get("SHA256") != closure.sha(vendor_fdc)):
        raise ValueError("reference audit IDF/FDC binding differs from current files")
    by_name = {row.get("RelativePath"): row for row in rows}
    expected = {name[len(closure.IP) + 1:] for name in roles["IDFExpandedSources"]}
    if len(rows) != 74 or len(by_name) != 74 or set(by_name) != expected:
        raise ValueError("reference audit must bind the exact 74-source closure")
    hashes = {"distortion/" + n: h for n, h in {
        **roles["SourceSHA256"], **roles["ConstraintSHA256"], **roles["AuxiliarySHA256"]}.items()}
    for relative, row in by_name.items():
        source = closure.inside(project, closure.IP + "/" + relative)
        vendor_source = _within(repo, reference_ip / relative)
        digest = closure.sha(source)
        if (row.get("CurrentSHA256") != digest or row.get("ReferenceSHA256") != digest
                or row.get("ManifestSHA256") != digest or closure.sha(vendor_source) != digest
                or row.get("BytesIdentical") is not True or row.get("CurrentManifestBindingMatches") is not True):
            raise ValueError("reference audit source binding mismatch: " + relative)
        hashes[vendor_source.relative_to(repo).as_posix()] = digest
    for path in (vendor_fdc, reference_idf, audit_path, SELF, Path(closure.__file__).resolve()):
        path = _within(repo, path)
        hashes[path.relative_to(repo).as_posix()] = closure.sha(path)
    return hashes


def fresh_output(project, value):
    project = Path(project).resolve()
    root = project / "build/ddr-ip-reset-constraints"
    output = Path(value).absolute()
    if (root.resolve() != root or output.resolve() != output or output.parent != root
            or not re.fullmatch(r"[A-Za-z0-9_-]+", output.name)
            or output.exists() and (not output.is_dir() or any(output.iterdir()))):
        raise ValueError("output must be a fresh child of build/ddr-ip-reset-constraints")
    return output


def prepare(project, netlist, out_dir, *, manifest_name=closure.DEFAULT_MANIFEST,
            vendor_fdc_name=VENDOR_FDC, audit_name=AUDIT):
    project = Path(project).resolve()
    repo = project.parent
    path = _within(project, netlist)
    netlist_hash = closure.sha(path)
    objects = inventory(parse_netlist(path))
    fdc, queries = make_fdc(objects)
    hashes = bind_inputs(project, manifest_name, vendor_fdc_name, audit_name)
    hashes[path.relative_to(repo).as_posix()] = netlist_hash
    output = fresh_output(project, out_dir)
    for name, digest in hashes.items():
        if closure.sha(_within(repo, repo / name)) != digest:
            raise ValueError("input changed during preparation: " + name)
    stage = "FinalPNR" if path.name.endswith("_route_optimize.netlist") else "UnverifiedReadableInventory"
    plan = {"Schema": "ddr-ip-reset-constraints-candidate-v1", "DiagnosticOnly": True,
            "NotApplied": True, "EDAStarted": False, "HardwareAccessed": False,
            "HardwareReleaseAllowed": False, "PhysicalTimingReady": False,
            "PreparedUTC": datetime.now(timezone.utc).isoformat(), "InventorySource": path.relative_to(repo).as_posix(),
            "InventorySourceStage": stage, "MapStageObjectMatchingVerified": False,
            "All244ChecksMatched": False, "PDSFdcSyntaxAndCollectionsVerified": False,
            "InputSHA256RepoRelative": hashes, "Manifest": "distortion/" + manifest_name,
            "OriginalVendorFDC": vendor_fdc_name, "ReferenceAudit": "distortion/" + audit_name,
            "Objects": objects, "Queries": queries,
            "CandidateFDC": {"Path": (output / "scope-reset.fdc").relative_to(repo).as_posix(),
                             "SHA256": hashlib.sha256(fdc.encode("ascii")).hexdigest()},
            "AllowedClockPairChecks": [
                {"Launch": a, "Capture": b, "ExpectedTotalChecksPerCorner": count}
                for a, b, count in [("rst_clk", "phy_dq_clk_0", 34), ("ddrphy_sysclk", "phy_dq_clk_0", 3),
                    ("rst_clk", "phy_dq_sysclk_0", 35), ("rst_clk", "phy_dq_clk_1", 84),
                    ("ddrphy_sysclk", "phy_dq_clk_1", 4), ("rst_clk", "phy_dq_sysclk_1", 84)]],
            "Acceptance": ["Probe exact collections; one source and expected158 target candidates, zero/ambiguous names must reject.",
                "Bind fresh map inventory aliases; final-PNR object names are not assumed valid after map.",
                "Audit native exception paths: only six stated IP-internal clock pairs, all244 total checks per corner.",
                "158 pin-existence candidates and max_path20 samples do not prove full connected path coverage.",
                "Keep board27 reset entry, custom CDC and core-to-divided-PHY data setup/hold checks timed.",
                "Do not fall back to global clock groups, broad hierarchy false paths or data endpoints."]}
    output.mkdir(parents=True, exist_ok=True)
    with (output / "scope-reset.fdc").open("x", encoding="ascii", newline="\n") as stream:
        stream.write(fdc)
    with (output / "plan.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(plan, stream, indent=2, ensure_ascii=False)
        stream.write("\n")
    return plan


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--netlist", required=True, type=Path)
    parser.add_argument("--out-dir", required=True, type=Path)
    parser.add_argument("--manifest", default=closure.DEFAULT_MANIFEST)
    parser.add_argument("--vendor-fdc", default=VENDOR_FDC, help="repository-relative original vendor FDC")
    parser.add_argument("--reference-audit", default=AUDIT, help="distortion-relative reference audit JSON")
    args = parser.parse_args(argv)
    try:
        result = prepare(PROJECT, args.netlist, args.out_dir, manifest_name=args.manifest,
                         vendor_fdc_name=args.vendor_fdc, audit_name=args.reference_audit)
    except (ValueError, OSError, UnicodeError, ET.ParseError) as exc:
        parser.error(str(exc))
    print(json.dumps({"PreparedOnly": True, "NotApplied": True, "Sources": 3,
                      "CandidatePins": result["Objects"]["CandidateTargetCount"],
                      "FDC": result["CandidateFDC"]["Path"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
