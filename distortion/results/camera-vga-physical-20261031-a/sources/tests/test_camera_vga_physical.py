from pathlib import Path
from copy import deepcopy
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import run_camera_vga_physical as physical
import run_camera_vga_export as export
import audit_camera_vga_physical as audit


def test_bound_camera_inputs_are_current():
    plan, watched = physical.bind_inputs(extra=(Path(export.__file__).resolve(),))
    assert plan['Target']=='camera_vga_output_top'
    assert len(plan['CompiledInputs'])==109
    assert physical.check_inputs(watched)==[]


def test_fresh_work_rejects_other_roots_and_nested_paths():
    for p in (physical.PROJECT/'build/camera-vga-output/new-query',
              physical.ROOT/'nested/new-query', physical.ROOT.parent/'unrelated/new-query', physical.BASE):
        with pytest.raises(ValueError, match='fresh canonical direct'):
            physical.fresh_work(p)
    assert physical.fresh_work(physical.ROOT/'query-cpu-test')==physical.ROOT/'query-cpu-test'


@pytest.mark.parametrize('value',[0,119,301,1800,True])
def test_deadline_is_bounded(value):
    with pytest.raises(ValueError, match='120..300'):
        physical.deadline(value)


def test_query_body_accepts_exact_read_only_operations():
    body=r'''puts {CAMERA_QUERY}
show -design_net {_N101}
show -dev_instance {CLMA_1_2;IOLHR_3_4}
get_pins -hierarchical -regexp {^(a\[0\]/CLK|b/RS)$}
.switch_db -route -input {@WORK@/input.adf} -output {@WORK@/routes.txt}
mpnr_report_timing -force_to_run -delay_type min_max -max_path 1000 -nworst 4 -report_exception TRUE
manual_route -help
'''
    assert len(physical.validate_query_body(body))==7
    tcl=physical.render_query(body,physical.ROOT/'query-cpu-test')
    assert '@WORK@' not in tcl
    assert tcl.count('mpnr -input ')==1


@pytest.mark.parametrize('body',[
    'show -design_net {_N101}; exec calc',
    'puts [exec calc]', 'source {unsafe.tcl}', 'pnr', 'compile -top_module camera_vga_output_top',
    'manual_route -net {_N101}', 'save_adif', 'set_false_path -from [get_pins {a}] -to [get_pins {b}]',
    'file copy {@WORK@/input.adf} {C:/outside.adf}',
    '.switch_db -route -input {@WORK@/input.adf} -output {@WORK@/../outside.txt}',
    'puts {x}\nexec calc',
])
def test_query_body_rejects_mutation_and_tcl_injection(body):
    with pytest.raises(ValueError):
        physical.validate_query_body(body)


def test_export_keeps_exact_context_and_uses_copied_adf():
    original=(physical.BASE/'timing.tcl').read_text(encoding='ascii')
    work=physical.ROOT/'export-cpu-test'
    text=export.render_tcl(original,physical.BASE.as_posix(),work)
    assert '-input_db_file {'+work.as_posix()+'/input.adf}' in text
    assert '-max_path 1000 -nworst 4 -report_exception TRUE' in text
    assert 'gen_netlist -force_to_run' in text and '-func_sim_only' in text
    assert 'pre-sta-final.adf' not in text
    assert export.STAGES==['Report Timing','Generate Netlist']
    with pytest.raises(ValueError,match='suffix differs'):
        export.render_tcl(original+'puts {unexpected}\n',physical.BASE.as_posix(),work)


def summary_row(slack=0.5, failed=0, total=7):
    return {'WorstSlackNS':slack,'TotalNegativeSlackNS':min(0,slack),
            'FailingChecks':failed,'TotalChecks':total}


def summary_fixture():
    targets={('phy_dq_sysclk_1','ddrphy_sysclk'),('rst_clk','ddrphy_sysclk'),
             ('ddrphy_sysclk','phy_dq_sysclk_1')}
    tables={}
    for corner in ('slow','fast'):
        for kind in ('setup','hold','recovery','removal','mpw'):
            tables[(corner,kind)]={('camera_pclk',):summary_row()} if kind=='mpw' else {
                ('camera_pclk','camera_pclk'):summary_row()}
            if kind in ('setup','hold'):
                tables[(corner,kind)].update({pair:summary_row(0.5 if kind=='setup' else -0.2,
                    0 if kind=='setup' else 1) for pair in targets})
    passing=deepcopy(tables)
    for (corner,kind), rows in passing.items():
        if kind in ('setup','hold'):
            for pair in targets:rows[pair]=summary_row(0.3)
    return tables,passing,targets


def test_summary_allows_only_three_data_pairs_and_preserves_checks():
    before,after,targets=summary_fixture()
    changes,_=audit.compare_summaries(before,after,targets)
    assert len(changes)==12
    after[('fast','hold')][('rst_clk','ddrphy_sysclk')]['TotalChecks']+=1
    with pytest.raises(ValueError,match='check count changed'):
        audit.compare_summaries(before,after,targets)


@pytest.mark.parametrize('kind',['setup','hold','recovery','removal','mpw'])
def test_summary_rejects_unrelated_row_drift(kind):
    before,after,targets=summary_fixture()
    pair=('camera_pclk',) if kind=='mpw' else ('camera_pclk','camera_pclk')
    after[('slow',kind)][pair]['WorstSlackNS']=0.6
    with pytest.raises(ValueError,match='unrelated timing summary'):
        audit.compare_summaries(before,after,targets)


def test_summary_reset_cuts_require_exact_inventory_counts():
    before,after,targets=summary_fixture()
    pair=('board27','rst_clk')
    groups=[]
    for corner in ('slow','fast'):
        for kind in ('recovery','removal'):
            before[(corner,kind)][pair]=summary_row(-0.3 if kind=='recovery' else 0.2,
                1 if kind=='recovery' else 0,1)
        groups.append({'Corner':corner,'LaunchClock':pair[0],'CaptureClock':pair[1],
                       'ObservedLogicalChecks':1,'Complete':True})
    inventory={'Complete':True,'Groups':groups}
    audit.compare_summaries(before,after,targets,inventory)
    inventory['Groups'].append(deepcopy(groups[0]))
    with pytest.raises(ValueError,match='duplicate reset'):
        audit.compare_summaries(before,after,targets,inventory)


def identity_row():
    return dict(Source='source/CLK',Endpoint='target/D',LaunchClock='a',CaptureClock='b',
                LaunchEdge='rising',CaptureEdge='rising',Corner='fast',Kind='hold',
                PathClass='sequential timing path',TimingExceptions=['MultiCycle Path Setup -end 2'],SlackNS=0.2)


@pytest.mark.parametrize('field,value',[
    ('LaunchClock','other'),('CaptureEdge','falling'),('Kind','setup'),
    ('TimingExceptions',['MultiCycle Path Setup -end 3'])])
def test_target_detail_identity_cannot_drift(field,value):
    before=identity_row();after=deepcopy(before);after[field]=value
    with pytest.raises(ValueError,match='identity changed'):
        audit.compare_target_identities([before],[after])
    after=deepcopy(before);after['SlackNS']=0.8
    audit.compare_target_identities([before],[after])


def exception_block():
    return '''Startpoint : source/CLK
Endpoint : target/D
Path Group : b
Path Type : min (fast corner)
Path Class : sequential timing path
Timing Exception : MultiCycle Path Setup -end 2
 Clock a (rising edge) 0.0
 CLMA_1_2/Q tco 0.100 0.200 r source/Q
 Clock b (rising edge) 0.0
 Slack (MET) 0.100
'''.splitlines(keepends=True)


def test_target_multicycle_identity_ignores_delays_but_keeps_type():
    text=''.join(exception_block())
    original=audit.target_exception_identity(exception_block())
    changed=audit.target_exception_identity(text.replace('0.100 0.200','0.300 0.500').splitlines(keepends=True))
    assert original==changed
    changed=audit.target_exception_identity(text.replace('min (fast','max (fast').splitlines(keepends=True))
    assert original!=changed
    with pytest.raises(ValueError,match='source transition ambiguous'):
        audit.target_exception_identity(text.replace(' tco ',' td ').splitlines(keepends=True))


def test_false_path_set_rejects_data_and_missing_reset():
    keys=(*audit.KEYS,'LaunchEdge','CaptureEdge')
    row=dict(zip(keys,('reset/CLK','native/RS','rst','phy','rising','rising')))
    row.update(LaunchDataTransition='r',NativePathSignature='one')
    expected={c:{tuple(row[k] for k in keys)} for c in ('slow','fast')}
    sections={(c,k):[dict(row)] if k in ('recovery','removal') else []
              for c in ('slow','fast') for k in ('setup','hold','recovery','removal')}
    audit.native.validate_exception_sets(sections,expected)
    sections[('slow','setup')]=[dict(row)]
    with pytest.raises(ValueError,match='unexpected or missing'):
        audit.native.validate_exception_sets(sections,expected)
    sections[('slow','setup')]=[];sections[('fast','recovery')]=[]
    with pytest.raises(ValueError,match='unexpected or missing'):
        audit.native.validate_exception_sets(sections,expected)


def test_equal_truncated_exports_cannot_pass(monkeypatch):
    small={'Cells':{'ff':{}},'ModuleDeclarations':'module camera_vga_output_top','FFPlacement':{'ff':{}}}
    monkeypatch.setattr(audit,'functional',lambda _:deepcopy(small))
    with pytest.raises(ValueError,match='FF inventory differs'):
        audit.compare_exports('before','after')


def test_native_camera_export_has_all_ff_locations():
    path=physical.ROOT/'export-baseline-20261031-a/generate_netlist/camera_vga_output_top_sim.v'
    result=audit.functional(path)
    assert len(result['Cells'])==36469
    assert len(result['FFPlacement'])==17417
