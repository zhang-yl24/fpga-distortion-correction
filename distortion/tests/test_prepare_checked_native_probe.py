"""CPU-only synthetic build boundary; never execute EDA or certify a build.

The completed-build audit is explicitly stubbed only for positive preparation
fixtures. Real source/profile validation and all109 compiled copies stay active.
"""
from pathlib import Path
import copy
import json
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import prepare_checked_native_probe as tool
from test_prepare_board1080_checked import project

REAL_BUILD_AUDIT = tool.build.audit


@pytest.fixture
def synthetic(project, tmp_path, monkeypatch):
    source = project / "build/board1080-timing/checked-source-fixture"
    query = project / "build/board1080-timing/checked-query-fixture"
    export = project / "build/board1080-timing/checked-export-fixture"
    for path in (source, query, export):
        path.mkdir(parents=True)
    executable = tmp_path / "synthetic-pds.exe"
    executable.write_bytes(b"SYNTHETIC, NEVER EXECUTED")
    monkeypatch.setattr(tool.checked, "validate_repo_alias",
                        lambda project, alias: tool.checked.timing.alias_format(alias))
    plan = tool.checked.prepare(project, source, pds_shell=executable)
    adf = source / "place_route/board1080_top_pnr.adf"
    adf.parent.mkdir();adf.write_bytes(b"SYNTHETIC ADF, NOT AN FPGA BUILD")
    watched = {str((project / name).resolve()):digest for name,digest in plan["InputSHA256"].items()}
    watched.update({str(path.resolve()):tool.sha(path) for path in (adf, source/"plan.json", executable)})
    audited = dict(Schema="board1080-checked-full-build-audit-v1", SyntheticCPUFixture=True,
        ProcessSucceeded=True, NativeReturnCode=0, ADFUnchangedAcrossSTA=True,
        WorkDirectory=str(source.resolve()), InputSHA256=plan["InputSHA256"],
        FinalRoutedADF={"Path":str(adf.resolve()),"SHA256":tool.sha(adf)},
        EvidenceSHA256=watched, PDSVersion=tool.checked.timing.PDS_VERSION)
    calls=[]
    def synthetic_audit(actual_project,actual_source):
        assert actual_project==project.resolve() and actual_source==source.resolve()
        calls.append((actual_project,actual_source))
        return copy.deepcopy(audited)
    monkeypatch.setattr(tool.build,"audit",synthetic_audit)
    return project,source,query,export,plan,audited,calls


def test_positive_preparation_preserves_actual_checked_preparer_and_original_plan(synthetic):
    project,source,query,export,source_plan,audited,calls=synthetic
    before={str(p):tool.sha(p) for p in (source/"plan.json",source/"timing.tcl",
                                       source/"place_route/board1080_top_pnr.adf")}
    result=tool.prepare(project,source,query,export)
    assert len(calls)==1
    for kind,path in (("Query",query),("Export",export)):
        plan=result[kind]
        assert plan["PreparedOnly"] and plan["NewCheckedEvidenceRequired"]
        for key in ("EDAExecuted","HardwareAccessed","BitstreamRequested","TimingAccepted",
                    "PhysicalTimingReady","HardwareReleaseAllowed","ConstraintsApplied","ADFSaved"):
            assert plan[key] is False
        assert plan["SourceADFSHA256"]==audited["FinalRoutedADF"]["SHA256"]
        assert plan["SourceClosureSHA256"]==audited["InputSHA256"]
        for name,digest in plan["FilesSHA256"].items():
            assert tool.sha(path/name)==digest
        assert (path/"input.adf").read_bytes()==(source/"place_route/board1080_top_pnr.adf").read_bytes()
    query_tcl=(query/"query.tcl").read_text()
    assert "-max_path 1000 -nworst 4 -report_exception TRUE" in query_tcl
    for forbidden in ("set_false_path","get_pins","_N173","save_design","gen_bitstream","show -"):
        assert forbidden not in query_tcl
    original=(export/"original-generated.tcl").read_bytes()
    assert original==(export/"timing.tcl").read_bytes()
    prepared=json.loads((export/"plan.json").read_text())
    assert prepared["Tcl"]["SHA256"]==tool.checked.timing.sha_bytes(original)
    assert len(prepared["CompiledInputs"])==109
    assert result["Export"]["OriginalPlanUnmodified"]
    export_tcl=(export/"export.tcl").read_text()
    assert export_tcl==tool.render_export_tcl(original.decode("ascii"),prepared["AliasWorkDirectory"])
    assert export_tcl.count("\nadd_design ")==31
    assert "gen_netlist -force_to_run -input_db_file" in export_tcl
    assert " -func_sim_only" in export_tcl
    assert "gen_bitstream" not in export_tcl and "file copy" not in export_tcl
    assert export_tcl.index("gen_netlist")>export_tcl.index("if {[info script] ne {}}")
    assert result["Export"]["CommandToRunSeparately"][2].endswith("/export.tcl")
    assert all(tool.sha(Path(p))==digest for p,digest in before.items())


def test_real_unfinished_source_build_rejected_before_any_write(synthetic,monkeypatch):
    project,source,query,export,*_=synthetic
    monkeypatch.setattr(tool.build,"audit",REAL_BUILD_AUDIT)
    with pytest.raises((ValueError,FileNotFoundError)):
        tool.prepare(project,source,query,export)
    assert not list(query.iterdir()) and not list(export.iterdir())


@pytest.mark.parametrize("mutation",["failed_audit","wrong_adf","unbound_adf","source_drift","closure_missing","closure_mismatch"])
def test_bad_build_identity_rejects_without_preparation(synthetic,mutation):
    project,source,query,export,plan,audited,_=synthetic
    if mutation=="failed_audit":audited["ProcessSucceeded"]=False
    elif mutation=="wrong_adf":audited["FinalRoutedADF"]["Path"]=str(source/"old.adf")
    elif mutation=="unbound_adf":audited["EvidenceSHA256"].pop(audited["FinalRoutedADF"]["Path"])
    elif mutation=="source_drift":(source/"place_route/board1080_top_pnr.adf").write_bytes(b"changed")
    elif mutation=="closure_missing":
        name=next(iter(audited["InputSHA256"]))
        audited["EvidenceSHA256"].pop(str((project/name).resolve()))
    else:audited["InputSHA256"]={}
    with pytest.raises(ValueError):tool.prepare(project,source,query,export)
    assert not list(query.iterdir()) and not list(export.iterdir())


@pytest.mark.parametrize("mutation",["same_dir","wrong_prefix","nonempty","outside"])
def test_fresh_directory_scope_rejects_before_preparer(synthetic,mutation,tmp_path):
    project,source,query,export,*_=synthetic
    if mutation=="same_dir":export=query
    elif mutation=="wrong_prefix":
        query=project/"build/board1080-timing/old-query";query.mkdir()
    elif mutation=="nonempty":(query/"keep.txt").write_text("do not overwrite")
    else:query=tmp_path/"outside";query.mkdir()
    with pytest.raises(ValueError):tool.prepare(project,source,query,export)
    assert not (export/"plan.json").exists()


def test_tcl_template_change_fails_closed():
    with pytest.raises(ValueError,match="suffix"):
        tool.render_export_tcl("gen_bitstream\n","P:/distortion/build/board1080-timing/checked-export")


def test_second_prepare_cannot_overwrite_evidence(synthetic):
    project,source,query,export,*_=synthetic
    tool.prepare(project,source,query,export)
    before=tool.sha(query/"query-plan.json")
    with pytest.raises(ValueError,match="fresh existing"):
        tool.prepare(project,source,query,export)
    assert tool.sha(query/"query-plan.json")==before

