"""An initialization-only report cannot replace full final STA authority."""
from pathlib import Path
import sys

import pytest

sys.path.insert(0,str(Path('D:\\GravityLRT\\thu\\semester_4.5\\FPGAchina\\fpga-distortion-correction\\distortion')/'tools'))
import hdmi_camera_fisheye_tile8df8v3_target_query as query
import hdmi_camera_fisheye_tile8df8v3_scoped_native as full


@pytest.mark.parametrize('mode,proof',[
    ('export',Path('proof.json')),('report',Path('proof.json')),('query',None)])
def test_query_provider_never_accepts_an_export_or_unapplied_source(mode,proof):
    with pytest.raises(ValueError,match='query mode and the exact applied'):
        query.recipe(Path('missing-plan.json'),Path('missing-work'),mode,source_proof=proof)


def test_full_native_provider_and_targeted_queries_have_separate_receipt_authorities():
    assert full.SCHEMA!=query.SCHEMA and full.MARKER!=query.MARKER
    assert full.INIT.endswith('-max_path 10000 -nworst 4 -report_exception TRUE')
    assert query.INIT.endswith('-max_path 1 -nworst 1 -report_exception FALSE')
    assert query.MAX_PATHS==full.MAX_PATHS==10000


def test_actual_target_reports_preserve_both_corners_and_full_path_bounds():
    command=('report_path_timing -delay_type min_max -max_path 10000 -nworst 4 '
        '-report_exception TRUE -from {p:a/CLK} -through {p:a/Q} -to {p:b/D}\n')
    assert query.query_commands(command)==full.query_commands(command)
    with pytest.raises(ValueError):query.query_commands(command.replace('10000','10001'))
    with pytest.raises(ValueError):query.query_commands('puts {'+query.MARKER+'}\n')


@pytest.mark.parametrize('mode',['report','export'])
def test_direct_render_cannot_sneak_a_full_inspection_into_query_provider(mode):
    with pytest.raises(ValueError,match='only targeted query mode'):
        query.render(Path('plan.json'),Path('work'),mode,'P:/')


def test_initialization_needs_its_report_but_never_requires_a_full_exception_report(tmp_path,monkeypatch):
    source=tmp_path/'original.adf';source.write_bytes(b'bound current applied ADF')
    work=tmp_path/'query';work.mkdir();(work/'input.adf').write_bytes(source.read_bytes())
    (work/'stdout.log').write_text(query.MARKER+'\n')
    main=work/(query.TARGET+'.rtr');main.write_text('initialization only; not final STA')
    monkeypatch.setattr(query.build,'diagnostics',lambda directory:[])
    value={'ExpectedStages':[],'SourceReductionDiagnostics':{
        'SourceDiagnostics':[],'ReviewedReadonlyBodies':None},'SourceADF':str(source),
        'SourceADFSHA256':query.sha(source),'Mode':'query'}
    evidence=query.evidence(value,work,{})
    assert evidence['CompletionMarker'] and query.TARGET+'_exception.rtr'not in evidence['Artifacts']
    main.unlink()
    with pytest.raises(ValueError,match='initialization report missing'):
        query.evidence(value,work,{})


@pytest.mark.parametrize('maximum',[0,True,1201,float('inf')])
def test_targeted_deadline_remains_bounded_before_source_binding(maximum):
    with pytest.raises(ValueError,match='deadline'):
        query.recipe(Path('unused-plan'),query.build.WORK/'unused-query','query',
            maximum=maximum,source_proof=Path('applied-proof'))
