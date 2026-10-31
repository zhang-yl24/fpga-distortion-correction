import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import archive_camera_vga_ready as archive


@pytest.fixture
def scope(tmp_path,monkeypatch):
    project=tmp_path/'distortion';work=project/'work/camera-vga-output';work.mkdir(parents=True)
    monkeypatch.setattr(archive,'PROJECT',project);monkeypatch.setattr(archive,'WORK',work)
    monkeypatch.setattr(archive.physical,'PROJECT',project);monkeypatch.setattr(archive.physical,'WORK',work)
    return project,work


def test_only_explicit_snapshot_documents_accepted(scope):
    project,work=scope;live=project/'README.md';live.write_text('live')
    with pytest.raises(ValueError):archive.snapshot(live)
    snap=work/'ready-document-snapshot-a';snap.mkdir();p=snap/'README.md';p.write_text('snapshot')
    assert archive.snapshot(p)==p


@pytest.mark.parametrize('name',['final.adf','camera.sbit','camera.bit','route-dump.txt','vendor.v'])
def test_large_or_vendor_native_payloads_remain_references(scope,name):
    project,work=scope;path=work/name;path.write_text('data')
    assert archive.reason(path)


def test_explicit_python_source_is_copyable(scope):
    project,work=scope;(project/'tools').mkdir();path=project/'tools/new_camera.py';path.write_text('print(1)')
    assert archive.source(path)==path
    assert archive.reason(path) is None


def native_stage(work,exit_code=1):
    stage=work/'bit-failed-a';stage.mkdir();log=stage/'stdout.log';log.write_text('native failed')
    receipt={'Schema':'camera-vga-bitstream-execution-v1','FinishedUTC':'2026-10-31T00:00:00+00:00',
             'ExitCode':exit_code,'HardwareAccessed':False,'TimedOut':False,'StoppedForUnexpectedStage':False,
             'InputDrift':[],'Diagnostics':['E: expected failure'],'Artifacts':{'stdout.log':archive.sha(log)}}
    (stage/'execution-result.json').write_text(json.dumps(receipt));return stage


def test_native_failure_is_preserved_not_relabelled(scope):
    _,work=scope;path=native_stage(work);_,status=archive.stage(path)
    assert status['ExitCode']==1 and status['FailedTrialPreserved'] and not status['ExecutionPassed']


def test_zero_exit_with_diagnostics_is_still_failed(scope):
    _,work=scope;_,status=archive.stage(native_stage(work,0))
    assert status['FailedTrialPreserved']


def test_modified_completed_artifact_rejected(scope):
    _,work=scope;path=native_stage(work);(path/'stdout.log').write_text('changed')
    with pytest.raises(ValueError,match='drift'):archive.stage(path)


def test_incomplete_stage_rejected(scope):
    _,work=scope;path=work/'bit-running';path.mkdir();(path/'execution-start.json').write_text('{}')
    with pytest.raises(ValueError,match='completed'):archive.stage(path)


def test_copy_and_decoded_readback_detects_corruption(scope):
    project,work=scope;source=work/'report.rtr';source.write_text('full timing report\n'*1000)
    dest=project/'results/camera-vga-ready-test';dest.mkdir(parents=True)
    row=archive.physical.copy_bound(source,dest/'report.rtr.gz',True)
    archive.physical.verify_payloads(dest,{'report.rtr.gz':row})
    (dest/'report.rtr.gz').write_bytes(b'corrupted')
    with pytest.raises(ValueError,match='hash'):archive.physical.verify_payloads(dest,{'report.rtr.gz':row})


def test_source_list_cannot_select_vendor_hdl(scope):
    project,work=scope;vendor=project/'vendor';vendor.mkdir();path=vendor/'netlist.v';path.write_text('vendor')
    with pytest.raises(ValueError,match='tool/test'):archive.source(path)


def test_bit_project_closure_is_bound_even_without_program(scope):
    project,work=scope;bitwork=work/'bit-valid';bitwork.mkdir()
    dependency=project/'compiled-input.v';dependency.write_text('actual source')
    plan={'ProjectInputSHA256':{str(dependency):archive.sha(dependency)}}
    (bitwork/'bitstream-plan.json').write_text(json.dumps(plan))
    assert archive.bit_dependencies(bitwork)=={dependency:archive.sha(dependency)}
    dependency.write_text('changed actual source')
    with pytest.raises(ValueError,match='dependency drift'):archive.bit_dependencies(bitwork)


def test_empty_bit_closure_is_rejected(scope):
    project,work=scope;bitwork=work/'bit-invalid';bitwork.mkdir()
    (bitwork/'bitstream-plan.json').write_text(json.dumps({'ProjectInputSHA256':{}}))
    with pytest.raises(ValueError,match='no project input closure'):archive.bit_dependencies(bitwork)
