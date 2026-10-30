"""Read existing PDS artifacts; never run EDA or touch hardware.

The .netlist index exports instances/pins/net names, NOT net connectivity or
attributes. This review explicitly keeps those evidence boundaries separate.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re


OUTER = {"p_reset": 2, "r_reset": 2, "polarity_sync": 3,
         "hs_level_sync": 2, "vs_level_sync": 2,
         "timing_good_sync": 2, "timing_bad_sync": 2}
GEOMETRY = {"ack_sync": 2, "edge_meta": 32, "edge_sync": 32,
            "href_meta": 16, "href_sync": 16, "vs_meta": 16,
            "vs_sync": 16, "failed_sync": 2, "healthy_sync": 2,
            "p_enable": 2, "p_reset": 2, "r_enable": 2, "r_reset": 2,
            "request_sync": 2, "source_running_sync": 2}
MODULE_PREFIX = {"hdmi1080_input_status_cdc": "input_status/",
                 "dvp_mode_admission_monitor_cdc": "input_status/geometry/"}


def expected_registers():
    return [prefix + name + f"[{i}]"
            for prefix, groups in (("input_status/", OUTER),
                                   ("input_status/geometry/", GEOMETRY))
            for name, width in groups.items() for i in range(width)]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def one(build, pattern):
    paths = list(build.glob(pattern))
    if len(paths) != 1:
        raise ValueError(f"Expected exactly one {pattern}; found {len(paths)}")
    return paths[0]


def read_index(path):
    lines = path.read_text(encoding="utf-8", errors="strict").splitlines()
    instances = {}
    current = None
    for i, line in enumerate(lines):
        if line == "Inst":
            name, primitive = lines[i + 1].split(";")
            if name in instances:
                raise ValueError(f"Duplicate native instance: {name}")
            current = {"name": name, "primitive": primitive,
                       "line": i + 2, "pins": {}}
            instances[name] = current
        elif line in {"Net", "Clock", "Port"}:
            current = None
        elif current is not None and ";" in line and line != lines[current["line"] - 1]:
            pin, direction = line.split(";")
            if direction not in {"1", "2", "3"}:
                raise ValueError(f"Unknown pin direction at {path}:{i + 1}")
            if pin in current["pins"]:
                raise ValueError(f"Duplicate pin {current['name']}/{pin}")
            current["pins"][pin] = direction
    if not instances:
        raise ValueError(f"No instance index in {path}")
    return instances


def clean_net(value):
    return re.sub(r"\s+", "", value.lstrip("\\"))


def read_vm(path):
    lines = path.read_text(encoding="utf-8").splitlines()
    module = None
    registers = {}
    for i, line in enumerate(lines):
        m = re.match(r"module\s+(\S+)", line)
        if m:
            module = m.group(1)
        m = re.search(r"\b(GTP_DFF\w*)\s+#.*\)\)\s+(\\?\S+)\s+\(", line)
        if not m or module not in MODULE_PREFIX:
            continue
        name = MODULE_PREFIX[module] + m.group(2).lstrip("\\")
        if name in registers:
            raise ValueError(f"Duplicate VM register: {name}")
        attributes = dict(re.findall(r'(PAP_\w+)="([^"]*)"', line))
        block = []
        for following in lines[i + 1:]:
            block.append(following)
            if ");" in following:
                break
        pins = {pin: clean_net(net) for pin, net in
                re.findall(r"\.(\w+)\s*\(([^()]*)\)", "\n".join(block))}
        registers[name] = {"primitive": m.group(1), "line": i + 1,
                           "attributes": attributes, "connections": pins}
    return registers


def mapping_status(cells):
    if not cells:
        return "missing_independent_instance"
    if any(re.fullmatch(r"gopSRL\d+", c["primitive"]) for c in cells):
        return "merged_shift_register"
    if len(cells) != 1:
        return "multiple_backend_objects_unverified"
    c = cells[0]
    # Only the plain native register primitive is classified. Packed/unknown
    # primitives are exposed verbatim for review, never assumed equivalent.
    if c["primitive"] == "gopQ" and all(p in c["pins"] for p in ("D", "Q", "CLK")):
        return "independent_plain_register"
    return "primitive_semantics_unverified"


def link_pairs():
    pairs = []
    for stem, width in (("edge", 32), ("href", 16), ("vs", 16)):
        for i in range(width):
            pairs.append((f"input_status/geometry/{stem}_meta[{i}]",
                          f"input_status/geometry/{stem}_sync[{i}]"))
    for prefix, groups in (("input_status/", OUTER), ("input_status/geometry/", GEOMETRY)):
        for stem, width in groups.items():
            if stem.endswith("_meta") or stem in {"edge_sync", "href_sync", "vs_sync"}:
                continue
            for i in range(width - 1):
                pairs.append((f"{prefix}{stem}[{i}]", f"{prefix}{stem}[{i + 1}]"))
    return pairs


def native_paths(path):
    text = path.read_text(encoding="utf-8", errors="replace")
    starts = list(re.finditer(r"(?m)^Startpoint\s*:\s*(.+)$", text))
    result = []
    for i, m in enumerate(starts):
        block = text[m.start():starts[i + 1].start() if i + 1 < len(starts) else len(text)]
        end = re.search(r"(?m)^Endpoint\s*:\s*(.+)$", block)
        if end:
            result.append({"start": m.group(1).strip(), "end": end.group(1).strip(),
                           "line": text.count("\n", 0, m.start()) + 1,
                           "zero_logic_levels": bool(re.search(r"Logic Levels:\s*0\b", block))})
    return result


def review(build, baseline=None):
    build = Path(build).resolve()
    files = {"vm": one(build, "synthesize/*_syn.vm"),
             "synthesis_index": one(build, "synthesize/*_syn.netlist"),
             "route_index": one(build, "place_route/*_route.netlist"),
             "log": build / "native-stdout.log", "execution": build / "execution.json"}
    # Avoid relying on a top name when an experiment uses a different suffix.
    timing_files = [p for p in (build / "report_timing").glob("*.rtr") if "exception" not in p.name]
    if len(timing_files) != 1:
        raise ValueError("Expected one primary native timing report")
    files["timing"] = timing_files[0]
    bound = {str(p): sha(p) for p in files.values()}
    expected = expected_registers()
    assert len(expected) == len(set(expected)) == 161
    syn_index, routed = read_index(files["synthesis_index"]), read_index(files["route_index"])
    vm = read_vm(files["vm"])
    log = files["log"].read_text(encoding="utf-8", errors="replace")
    warnings = [{"line": n, "text": line} for n, line in enumerate(log.splitlines(), 1)
                if "PAP_ASYNC_REG" in line and re.search(r"invalid|ignore|not legal", line, re.I)]
    entries = []
    for name in expected:
        cells = [c for key, c in routed.items() if key == name or key.startswith(name + "/")]
        entries.append({"expected_instance": name, "synthesis_index": syn_index.get(name),
                        "synthesis_vm": vm.get(name), "route_objects": cells,
                        "route_mapping_status": mapping_status(cells),
                        "backend_attribute_visibility": "not_exported_by_route_index",
                        "candidate_fdc_not_applied": f"define_attribute {{i:{name}}} {{PAP_ASYNC_REG}} {{TRUE}}"})
    by_name = {e["expected_instance"]: e for e in entries}
    observed_paths = native_paths(files["timing"])
    links = []
    for first, second in link_pairs():
        left, right = vm.get(first, {}), vm.get(second, {})
        q = left.get("connections", {}).get("Q")
        d = right.get("connections", {}).get("D")
        a, b = by_name[first]["route_objects"], by_name[second]["route_objects"]
        observed = []
        if len(a) == len(b) == 1:
            observed = [p for p in observed_paths if p["start"].startswith(a[0]["name"] + "/")
                        and p["end"] == b[0]["name"] + "/D"]
        links.append({"first": first, "second": second,
                      "synthesis_q_net": q, "synthesis_d_net": d,
                      "synthesis_direct_q_to_d": bool(q is not None and q == d),
                      "native_timing_paths": observed,
                      "backend_connection_status": "direct_timing_path_observed" if any(
                          p["zero_logic_levels"] for p in observed) else "unverified_no_connectivity_export"})
    comparisons = None
    if baseline is not None:
        old_path = one(Path(baseline), "place_route/*_route.netlist")
        old = read_index(old_path)
        bound[str(old_path.resolve())] = sha(old_path)
        comparisons = {}
        for stem in ("edge_meta", "edge_sync", "href_meta", "href_sync", "vs_meta", "vs_sync"):
            pattern = re.compile(r"^input_status/geometry/" + stem + r"\[\d+\]/")
            comparisons[stem] = {"baseline": dict(Counter(c["primitive"] for k, c in old.items() if pattern.match(k))),
                                 "current": dict(Counter(c["primitive"] for k, c in routed.items() if pattern.match(k)))}
    for path, digest in bound.items():
        if sha(Path(path)) != digest:
            raise ValueError(f"Artifact changed during review: {path}")
    counts = dict(Counter(e["route_mapping_status"] for e in entries))
    return {"schema": "hdmi-cdc-native-mapping-review-v1", "created_utc": datetime.now(timezone.utc).isoformat(),
            "build": str(build), "hardware_accessed": False, "eda_started": False,
            "input_sha256": bound, "script_sha256": sha(Path(__file__)),
            "execution": json.loads(files["execution"].read_text(encoding="utf-8")),
            "expected_register_count": 161, "route_mapping_counts": counts,
            "pap_async_reg_rejection_warnings": warnings,
            "independent_plain_registers_verified": counts.get("independent_plain_register", 0) == 161,
            "backend_connections_all_verified": all(x["backend_connection_status"] == "direct_timing_path_observed" for x in links),
            "cdc_release_accepted": False,
            "limitations": ["Native index lists instance types/pins and net names, without driver/load associations or attributes.",
                            "Synthesis VM connectivity does not prove backend connectivity.",
                            "Absence of a warning does not prove the property persisted in final DB.",
                            "Only gopQ with D/Q/CLK pins is classified as a plain register; unknown primitives stay unverified.",
                            "This review is not a timing, CDC correctness, or hardware release signoff."],
            "baseline_bus_comparison": comparisons, "registers": entries, "stage_links": links,
            "next_native_steps": ["In an isolated copy of the fresh synthesis ADF, apply the enumerated exact-instance FDC properties before dev_map; reject missing/ambiguous objects and invalid-value warnings.",
                                  "Rebuild and inspect every first/second-stage mapped primitive; require independently addressable stages.",
                                  "For each independent pair query its exact mapped CLK/Q and next-stage D pins with anchored escaped regex; do not infer collection cardinality from opaque Tcl handles.",
                                  "Obtain native report_path_timing for exact stage pairs, or a functional connectivity export, where existing native reports do not expose direct paths."]}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--build", type=Path, required=True)
    p.add_argument("--baseline", type=Path)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    result = review(args.build, args.baseline)
    with args.output.open("x", encoding="utf-8", newline="\n") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(json.dumps({"output": str(args.output), "sha256": sha(args.output),
                      "mapping_counts": result["route_mapping_counts"],
                      "pap_async_reg_rejections": len(result["pap_async_reg_rejection_warnings"]),
                      "backend_connections_all_verified": result["backend_connections_all_verified"]}))
    return 0 if result["independent_plain_registers_verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
