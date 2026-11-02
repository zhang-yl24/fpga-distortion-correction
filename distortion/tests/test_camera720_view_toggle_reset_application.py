"""View-toggle reset tooling rejects unrelated timing waivers and stale evidence."""
from pathlib import Path
import copy
import sys
from unittest import mock

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import camera720_view_toggle_final_inspect as inspect
import camera720_view_toggle_reset_apply as physical
import camera720_view_toggle_reset_effect as effect


def tables():
    row={'FailingChecks':0,'WorstSlackNS':0.125,'TotalNegativeSlackNS':0,'TotalChecks':5}
    return {(c,k):{('a','b'):dict(row)} for c in ('slow','fast') for k in physical.timing.native.KINDS}


def test_only_exact_current_reset_groups_can_be_excluded():
    values=tables()
    values[('slow','recovery')][('a','b')]['FailingChecks']=2
    values[('slow','recovery')][('a','b')]['WorstSlackNS']=-0.5
    inventory={'Groups':[{'Corner':'slow','LaunchClock':'a','CaptureClock':'b'}]}
    physical.nonreset_checks(values,inventory)
    values[('fast','hold')][('a','b')]['FailingChecks']=1
    with pytest.raises(ValueError,match='unresolved non-proposed'):
        physical.nonreset_checks(values,inventory)


@pytest.mark.parametrize('kind',physical.timing.native.KINDS)
def test_complete_both_corner_tables_required(kind):
    values=tables();del values[('slow',kind)]
    with pytest.raises(ValueError,match='ten complete'):
        physical.nonreset_checks(values,{'Groups':[]})


def test_reset_render_saves_only_requested_reset_commands(tmp_path):
    commands=['set_false_path -from [get_pins -hierarchical -regexp {^(a/CLK)$}] -to [get_pins -hierarchical -regexp {^(b/RS)$}]']
    text=physical.render(tmp_path,commands)
    assert text.count(commands[0])==1
    assert text.count('save_adif')==1
    assert 'post-init.adf' in text and 'saved-reset.adf' in text
    assert all(token not in text for token in ('route_net','gen_bitstream','program_device','set_clock_groups'))


@pytest.mark.parametrize('body',['save_adif\n','route_net -net {_N1}\n',
                                 'gen_bitstream\n','puts {'+inspect.MARKER+'}\n'])
def test_final_inspector_does_not_accept_mutations_or_spoofed_markers(tmp_path,body):
    with pytest.raises(ValueError):
        inspect.render(tmp_path/'plan.json',tmp_path,'query',body)


def test_report_does_not_accept_custom_body(tmp_path):
    with pytest.raises(ValueError,match='no custom body'):
        inspect.render(tmp_path/'plan.json',tmp_path,'report','puts {x}\n')


def test_fresh_inspector_reads_only_exact_candidate_copy(tmp_path):
    text=inspect.render(tmp_path/'plan.json',tmp_path,'report')
    assert text.count(inspect.INIT)==1
    assert 'mpnr -input {'+tmp_path.as_posix()+'/input.adf}' in text
    assert '.switch_db -route' in text
    assert all(token not in text for token in ('save_adif','route_net','gen_bitstream','program_device'))


def test_reset_derive_rejects_export_route_from_different_adfs(tmp_path):
    export={'Mode':'export','SourceADF':'A','SourceADFSHA256':'a'*64,'BuildPlan':'P','BuildPlanSHA256':'b'*64}
    route={**export,'Mode':'report','SourceADFSHA256':'c'*64}
    with mock.patch.object(inspect,'bind_receipt',side_effect=[(export,{}),(route,{})]):
        with pytest.raises(ValueError,match='different ADF or build'):
            physical.derive(tmp_path/'export.json',tmp_path/'route.json')


def test_diagnostics_scan_includes_critical_errors_and_tracebacks(tmp_path):
    (tmp_path/'stdout.log').write_text('I: okay\nCRITICAL: failed\nTraceback (most recent call last):\n',encoding='utf-8')
    assert len(inspect.diagnostics(tmp_path))==2


def test_artifact_output_inventory_cannot_omit_generated_files(tmp_path):
    (tmp_path/'stage.tcl').write_text('puts {test}\n',encoding='ascii')
    (tmp_path/'other.json').write_text('{}',encoding='ascii')
    (tmp_path/'result.rtr').write_text('native timing',encoding='ascii')
    assert set(inspect.artifacts(tmp_path))=={'stage.tcl','result.rtr'}


def false_sections():
    result={}
    for corner in ('slow','fast'):
        for kind in ('setup','hold','recovery','removal'):
            key=[{'Endpoint':'view_control/key_sync[0]/opit_0_inv_srl/D',
                  'Transition':t,'SHA256':corner+kind+t} for t in ('r','f')] if kind in ('setup','hold') else []
            result[(corner,kind)]={'Key':key,'Reset':[]}
    return result


def test_existing_key_pad_exceptions_preserved_but_only_reset_paths_added():
    before=false_sections();after=copy.deepcopy(before)
    inv={'Corners':{c:{'Checks':[]} for c in ('slow','fast')}}
    result=effect.compare_false_paths(before,after,inv)
    assert result['NoOtherDataFalsePaths']
    assert result['PreservedKEY1Endpoint'].endswith('/D')
    after[('slow','setup')]['Reset'].append({'Source':'data','Endpoint':'sink',
        'LaunchClock':'a','CaptureClock':'b','LaunchEdge':'rising','CaptureEdge':'rising',
        'LaunchDataTransition':'r','NativePathSignature':'data'})
    with pytest.raises(ValueError,match='unexpected or missing'):
        effect.compare_false_paths(before,after,inv)


def test_key_exception_route_delay_cannot_change():
    before=false_sections();after=copy.deepcopy(before)
    after[('fast','hold')]['Key'][0]['SHA256']='altered-key-route'
    inv={'Corners':{c:{'Checks':[]} for c in ('slow','fast')}}
    with pytest.raises(ValueError,match='KEY1 pad exception path changed'):
        effect.compare_false_paths(before,after,inv)


def test_two_native_capture_variants_can_share_source_pad_transition():
    before=false_sections();after=copy.deepcopy(before)
    for collection in (before,after):
        for row in collection.values():
            for path in row['Key']:path['Transition']='r'
    inv={'Corners':{c:{'Checks':[]} for c in ('slow','fast')}}
    assert effect.compare_false_paths(before,after,inv)['NoOtherDataFalsePaths']


def test_literal_duplicate_key_variant_rejected():
    before=false_sections();before[('slow','setup')]['Key'][1]=copy.deepcopy(before[('slow','setup')]['Key'][0])
    inv={'Corners':{c:{'Checks':[]} for c in ('slow','fast')}}
    with pytest.raises(ValueError,match='duplicate or invalid'):
        effect.compare_false_paths(before,copy.deepcopy(before),inv)


def test_key_exception_cannot_reach_second_synchronizer_or_data_endpoint(tmp_path):
    header='| Exception type  : set_false_path(setup)\n| Slow Corner\n'
    body=('Startpoint  : key1_n (port)\nEndpoint : view_control/key_sync[1]/opit_0_inv_srl/D\n'
          'Path Group : ddrphy_sysclk\nPath Type : max (slow corner)\n'
          'Path Class : false timing path\nTiming Exception  :  False Path\n'
          ' C23 0.000 0.000 r key1_n (port)\n Clock ddrphy_sysclk (rising edge)\n')
    path=tmp_path/'exception.rtr';path.write_text(header+body,encoding='ascii')
    with pytest.raises(ValueError,match='KEY1 false path reaches another'):
        effect.false_paths(path)
