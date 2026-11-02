"""Release adapters keep exact candidate identity and explicit hardware boundary."""
from pathlib import Path
import builtins
import dis
import sys
import types

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import camera720_view_toggle_bitstream as bit
import camera720_view_toggle_program as program
import camera720_view_toggle_cdc_proof as cdc


def test_reused_functions_have_all_referenced_globals_in_candidate_namespace():
    def missing(code,namespace):
        for instruction in dis.get_instructions(code):
            if instruction.opname=='LOAD_GLOBAL':
                assert instruction.argval in namespace or hasattr(builtins,instruction.argval), instruction.argval
        for constant in code.co_consts:
            if isinstance(constant,types.CodeType):missing(constant,namespace)
    for module in (bit,program,cdc):
        for value in vars(module).values():
            if isinstance(value,types.FunctionType) and value.__globals__ is vars(module):
                missing(value.__code__,vars(module))


def test_old_modules_remain_immutable_and_new_schemas_are_explicit():
    assert bit.base.prep.TARGET=='camera720_calibrated_stats_delay_top'
    assert bit.prep.TARGET=='camera720_view_toggle_top'
    assert program.SCHEMA=='camera720-view-toggle-sram-plan-v1'
    assert bit.REQUEST_FIELDS=={'Schema','Target','BuildPlan','CandidateADF','FinalInspectionReceipt',
        'ResetApplicationReceipt','ResetEffectAudit','FinalCDCProof','BuildDiagnosticsDisposition',
        'SystemSimulation','BaselineAuthority'}
    assert cdc.algorithms.TARGET=='camera720_calibrated_stats_delay_top'
    assert cdc.TARGET=='camera720_view_toggle_top'


def test_runtime_gate_requires_exact_new_marker_and_fresh_sta_before_generation():
    digest='a'*64
    log='\n'.join(['Process "Report Timing" started.','Process "Report Timing" done.',
        bit.GATE+' '+digest,'Process "Generate Bitstream" started.',
        'Process "Generate Bitstream" done.',bit.COMPLETE])
    assert len(bit.events(log,digest))==6
    for broken in (log.replace(bit.GATE,'CAMERA720_CALIBRATED_STATS_DELAY_GATE_PASS'),
                   log.replace(digest,'b'*64),log.replace('Process "Report Timing" done.','')):
        with pytest.raises(ValueError):bit.events(broken,digest)


@pytest.mark.parametrize('powered,notified,timeout',[
    (False,True,90),(True,False,90),(True,True,0),(True,True,301),(True,True,float('nan'))])
def test_programming_boundary_requires_authorization_notification_and_finite_timeout(powered,notified,timeout):
    with pytest.raises(ValueError):program.execution_authorization(powered,notified,timeout)


def test_sram_scripts_do_not_write_flash():
    scripts=program.scripts(Path('D:/candidate/camera720_view_toggle_top.sbit'))
    assert set(scripts)=={'scan','program'}
    assert all('flash' not in s.lower() for s in scripts.values())
    assert 'camera720_view_toggle_top.sbit' in scripts['program']


def test_cdc_gate_cannot_accept_prior129_pin_candidate():
    with pytest.raises(ValueError):
        bit.cdc_flags({'Schema':'camera720-calibrated-stats-delay-cdc-proof-v1',
            'Target':'camera720_calibrated_stats_delay_top'},'a'*64,{})


def test_query_body_batching_respects_native_grammar_bound(monkeypatch):
    groups=[{'PinCommand':'get_pins -hierarchical -regexp {^(s|q|d)$}',
        'Command':'report_path_timing -delay_type min_max -max_path 1000 -nworst 8 -report_exception TRUE -from {s} -through {q} -to {d}'}
        for _ in range(161)]
    monkeypatch.setattr(cdc.adapter.grouped,'groups',lambda q,m:groups)
    selected,bodies=cdc.query_bodies([],[],80)
    assert len(selected)==161 and len(bodies)==3
    assert [len(cdc.final.native.query_commands(body)) for body in bodies.values()]==[160,160,2]
    with pytest.raises(ValueError):cdc.query_bodies([],[],81)


def test_bit_render_selects_exact_audited_adf_and_native_gate(monkeypatch,tmp_path):
    monkeypatch.setattr(bit.final,'export_prefix',lambda path:'native-context\n')
    work=tmp_path/'bit-a'
    text=bit.render({'PlanPath':tmp_path/'plan.json','CandidateSHA256':'c'*64},work)
    assert text.index('report_timing ')<text.index('--gate ')<text.index('gen_bit_stream ')
    assert text.count('-input_db_file {'+work.as_posix()+'/audited-final.adf}')==2
    assert bit.GATE+' '+'c'*64 in text
    assert 'CAMERA720_CALIBRATED_STATS_DELAY' not in text
