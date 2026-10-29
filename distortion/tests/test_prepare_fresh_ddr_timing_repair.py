"""CPU-only fresh profile admission and failure-before-output regressions."""
from pathlib import Path
import copy
import hashlib
import json
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import prepare_fresh_ddr_timing_repair as tool


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def mutate(path, change):
    data = json.loads(path.read_text(encoding="utf-8"))
    change(data)
    put(path, data)


@pytest.fixture
def prepared_inputs(tmp_path, monkeypatch):
    project = tmp_path / "repo/distortion"
    project.mkdir(parents=True)
    source = project / "fresh.adf"
    source.write_bytes(b"CPU-only fresh ADF fixture")
    monkeypatch.setattr(tool, "SOURCE_SHA256", sha(source))
    report = project / "fresh.rtr"
    report.write_bytes(b"CPU-only native report, parser covered independently")
    monkeypatch.setattr(tool, "REPORT_SHA256", sha(report))
    # Reuse the real admitted inventory; parsing and edge coverage have their
    # own adversarial suite. Here replay equality is independently controlled.
    inventory = json.loads((Path(__file__).resolve().parents[1] /
                           "results/board1080-native-recovery-20261029.json").read_text())
    checks = [{"Source": row["Source"], "Endpoint": row["Endpoint"]}
              for row in inventory["FullNativeRecoveryPaths"] if row["Corner"] == "slow"]
    replay = {"Input": {"Path": str(report), "SHA256": sha(report)},
              "Corners": {"slow": {"Checks": checks}},
              "SourceEndpointPairsSHA256": tool.variants.PAIR_SHA256}
    evidence = put(project / "variants.json", replay)
    monkeypatch.setattr(tool.variants, "audit_file", lambda _path: copy.deepcopy(replay))
    netlist = project / "fresh-sim.v"
    netlist.write_text("CPU-only structural fixture", encoding="ascii")
    monkeypatch.setattr(tool, "ENTRY_SHA256", sha(netlist))
    entry_replay = {"Status": "pass", "FirstStageFunctionalFanout": 1, "OutputLoadCount": 11,
                    "RawClearBufferCount": 9, "Stages": ["first", "second"]}
    audit = put(project / "entry.json", {**entry_replay,
        "Input": {"Path": str(netlist), "SHA256": sha(netlist), "Bytes": netlist.stat().st_size},
        "InputADF": {"Path": str(source), "SHA256": sha(source)},
        "AuditToolSHA256": sha(Path(tool.entry.__file__))})
    monkeypatch.setattr(tool.entry, "audit_text", lambda _text: copy.deepcopy(entry_replay))
    inputs = {}
    sources = {}
    for index in range(109):
        name = f"rtl/source{index}.v"
        path = project / name
        path.parent.mkdir(exist_ok=True)
        path.write_text(f"module source{index}; endmodule", encoding="ascii")
        sources[name] = sha(path)
        inputs[str(path)] = sha(path)
    roles = {"SourceSHA256": sources, "ConstraintSHA256": {}, "AuxiliarySHA256": {}}
    monkeypatch.setattr(tool.closure, "validate_manifest", lambda _project: roles)
    monkeypatch.setattr(tool.old, "PROFILE_HASHES", {})
    export = put(project / tool.EXPORT_PLAN, {"AuthorityADFSHA256": sha(source), "InputSHA256": inputs})
    monkeypatch.setattr(tool, "EXPORT_PLAN_SHA256", sha(export))
    route_log = project / tool.ROUTE_LOG
    route_log.parent.mkdir(parents=True)
    route_log.write_text("route for net _N173 :\n" + "\n".join(tool.ORIGINAL_ROUTE) +
        "\nExecuting : show -design_net _N173 successfully.\nSite CLMA_357_619 (6) :\n" +
        "adj_wrdq_5[52]/LUT6_inst_perm (gopLUT6 using impl_devCL6 , devCL6)\n" +
        "Site IOLHR_364_624 (1) :\ndq_loop[6].u_iobuf_dq/opit_1 (gopIOL using impl , devIOL)\n", encoding="ascii")
    monkeypatch.setattr(tool, "ROUTE_LOG_SHA256", sha(route_log))
    admission = put(project / tool.ADMISSION, {"NewADFSHA256": sha(source), "InputADFUnchanged": True,
        "ObservedReturnCode": 0, "OriginalDataBranchRouteVerified": tool.ORIGINAL_ROUTE,
        "KnownDriverAndLoadPresentAtExpectedSites": True,
        "SourceEndpointPairsSHA256": tool.variants.PAIR_SHA256,
        "EvidenceSHA256": {"distortion/" + tool.ROUTE_LOG: sha(route_log)}})
    groups = {}
    for row in checks:
        groups.setdefault(row["Source"], set()).add(row["Endpoint"])
    all_groups = {**groups, tool.old.ENTRY_SOURCE: {tool.old.ENTRY_TARGET}}
    records = [{"Count": len(names), "NativeNames": ["t:" + name for name in names]}
               for source_pin, targets in all_groups.items() for names in ([source_pin], sorted(targets))]
    log = project / "pins.log"
    log.write_text("\n".join("I: Timing-5001: The pattern 'exact' in command 'get_pins -hierarchical -regexp exact' "
        f"match {record['Count']} objects below: " + " ".join(record["NativeNames"]) for record in records) +
        "\nFRESH_EXACT_PIN_QUERY_COMPLETE\n", encoding="ascii")
    parsed = tool.native.parse_native_matches(log)
    _, queries = tool.old.make_scopes(groups, parsed)
    query = put(project / "query-result.json", {"Schema": "fresh-native-pin-query-v1",
        "Passed": True, "ExitCode": 0, "InputDrift": [], "Diagnostics": [],
        "ConstraintsApplied": False, "ADFSaved": False, "HardwareAccessed": False,
        "SourceADF": str(source), "SourceADFSHA256": sha(source),
        "QueryLog": str(log), "QueryLogSHA256": sha(log), "NativeRecords": parsed, "ExactQueries": queries,
        "InputSHA256": {str(source): sha(source), str(evidence): sha(evidence)}})
    executable = project / "pds_shell.exe"
    executable.write_bytes(b"CPU fixture; never execute")
    monkeypatch.setattr(tool.closure, "validate_repo_alias", lambda _project, alias: tool.closure.alias_format(alias))
    return dict(project=project, source=source, report=report, replay=replay, evidence=evidence, audit=audit,
                netlist=netlist, roles=roles, export=export, route_log=route_log, admission=admission,
                log=log, query=query, executable=executable, output=project / "build/ddr-timing-repair/candidate")


def prepare(values):
    return tool.prepare(values["project"], values["source"], values["evidence"], values["audit"],
                        values["log"], values["output"], native_query_result=values["query"],
                        pds_shell=values["executable"])


def reject(values, pattern):
    with pytest.raises((ValueError, KeyError), match=pattern):
        prepare(values)
    assert not values["output"].exists()


def test_exact_clone_and_fresh_evidence_bindings(prepared_inputs, monkeypatch, tmp_path):
    v = prepared_inputs
    monkeypatch.chdir(tmp_path)  # Relative internal profile paths must use project.
    result = prepare(v)
    assert v["source"].read_bytes() == (v["output"] / "input.adf").read_bytes()
    assert result["PreparedOnly"] is True
    for key in ("EDAExecuted", "HardwareAccessed", "BitstreamRequested", "TimingAccepted", "HardwareReleaseAllowed"):
        assert result[key] is False
    assert result["FreshEvidence"]["SourceFiles"] == 109
    assert result["FreshEvidence"]["NativeVariantsPerCorner"] == 251
    assert result["FreshEvidence"]["LogicalChecksPerCorner"] == 244
    assert result["FreshEvidence"]["EntryOutputLoads"] == 11
    assert len(result["ExactQueries"]) == 5
    assert len(result["CommandsRunSeparatelyInOrder"]) == 2
    assert str(v["query"]) in result["InputSHA256"]
    assert str(v["export"]) in result["InputSHA256"]
    for name, digest in result["FilesSHA256"].items():
        assert sha(v["output"] / name) == digest
    repair = (v["output"] / "repair.tcl").read_text()
    report = (v["output"] / "report.tcl").read_text()
    assert "manual_route" in repair and "save_adif" in repair and "report_timing" not in repair
    assert "manual_route" not in report and "save_adif" not in report
    assert "gen_bit_stream" not in repair + report
    assert str(v["source"]) not in repair + report


def test_old_adf_rejected(prepared_inputs):
    v = prepared_inputs
    v["source"].write_bytes(b"historical baseline")
    reject(v, "pinned fresh ADF")


def test_wrong_entry_export_even_self_consistent_is_rejected(prepared_inputs):
    v = prepared_inputs
    v["netlist"].write_bytes(b"other export")
    mutate(v["audit"], lambda d: d["Input"].update(SHA256=sha(v["netlist"])))
    reject(v, "pinned fresh export")


def test_entry_wrong_adf_rejected(prepared_inputs):
    v = prepared_inputs
    mutate(v["audit"], lambda d: d["InputADF"].update(SHA256=tool.old.BASELINE_SHA256))
    reject(v, "InputADF differs")


@pytest.mark.parametrize("field,value", [("RawClearBufferCount", 0), ("Stages", ["forged"]), ("ExtraClaim", True)])
def test_complete_entry_result_is_replayed(prepared_inputs, field, value):
    v = prepared_inputs
    mutate(v["audit"], lambda d: d.update({field: value}))
    reject(v, "full functional replay")


def test_complete_variant_result_is_replayed(prepared_inputs):
    v = prepared_inputs
    mutate(v["evidence"], lambda d: d["Corners"]["slow"]["Checks"].pop())
    reject(v, "full native replay")


def test_wrong_report_even_rehashed_is_rejected(prepared_inputs):
    v = prepared_inputs
    v["report"].write_bytes(b"old report")
    mutate(v["evidence"], lambda d: d["Input"].update(SHA256=sha(v["report"])))
    reject(v, "not the fresh native report")


def test_report_drift_rejected(prepared_inputs):
    v = prepared_inputs
    v["report"].write_bytes(b"drift")
    reject(v, "native report hash mismatch")


def test_export_plan_cannot_be_relabelled(prepared_inputs):
    v = prepared_inputs
    mutate(v["export"], lambda d: d.update(AuthorityADFSHA256=tool.old.BASELINE_SHA256))
    reject(v, "export plan hash mismatch")


def test_source_drift_rejected(prepared_inputs):
    v = prepared_inputs
    (v["project"] / "rtl/source0.v").write_text("changed HDL")
    reject(v, "export input hash mismatch")


def test_missing_source_inventory_rejected(prepared_inputs):
    v = prepared_inputs
    v["roles"]["SourceSHA256"].pop("rtl/source0.v")
    reject(v, "109 source files")


def test_route_log_drift_rejected(prepared_inputs):
    v = prepared_inputs
    v["route_log"].write_text("different net placement")
    reject(v, "route query log hash mismatch")


def test_route_claim_cannot_override_canonical_branch(prepared_inputs):
    v = prepared_inputs
    mutate(v["admission"], lambda d: d.update(OriginalDataBranchRouteVerified=["wrong branch"]))
    reject(v, "route/site admission differs")


@pytest.mark.parametrize("field,value", [("Passed", False), ("ExitCode", 1), ("InputDrift", ["source"]),
                                         ("Diagnostics", ["ERROR"])])
def test_native_query_execution_failures_rejected(prepared_inputs, field, value):
    v = prepared_inputs
    mutate(v["query"], lambda d: d.update({field: value}))
    reject(v, "did not finish cleanly")


@pytest.mark.parametrize("field", ["ConstraintsApplied", "ADFSaved", "HardwareAccessed"])
def test_native_query_must_be_readonly(prepared_inputs, field):
    v = prepared_inputs
    mutate(v["query"], lambda d: d.update({field: True}))
    reject(v, "must be read-only")


def test_native_query_old_adf_binding_rejected(prepared_inputs):
    v = prepared_inputs
    mutate(v["query"], lambda d: d.update(SourceADFSHA256=tool.old.BASELINE_SHA256))
    reject(v, "source ADF differs")


def test_native_query_binding_required(prepared_inputs):
    v = prepared_inputs
    v["query"] = None
    reject(v, "binding is required")


def test_native_wrong_names_fail_even_with_updated_log_hash(prepared_inputs):
    v = prepared_inputs
    v["log"].write_text(v["log"].read_text().replace("/RST ", "/DATA ", 1))
    mutate(v["query"], lambda d: d.update(QueryLogSHA256=sha(v["log"])))
    reject(v, "missing exact native object-name")


def test_native_query_invented_records_rejected(prepared_inputs):
    v = prepared_inputs
    mutate(v["query"], lambda d: d["NativeRecords"].pop())
    reject(v, "records differ from replay")


def test_nonempty_output_rejected(prepared_inputs):
    v = prepared_inputs
    v["output"].mkdir(parents=True)
    sentinel = v["output"] / "existing.txt"
    sentinel.write_text("preserve")
    with pytest.raises(ValueError, match="fresh or empty"):
        prepare(v)
    assert sentinel.read_text() == "preserve"


def test_inputs_rechecked_after_parsing(prepared_inputs, monkeypatch):
    v = prepared_inputs
    original = tool.old.make_scripts
    def drifting(alias):
        v["source"].write_bytes(b"changed late")
        return original(alias)
    monkeypatch.setattr(tool.old, "make_scripts", drifting)
    reject(v, "bound input changed during preparation")


def test_path_escape_rejected(prepared_inputs):
    v = prepared_inputs
    outside = v["project"].parent / "outside.adf"
    outside.write_bytes(v["source"].read_bytes())
    v["source"] = outside
    reject(v, "inside distortion")
