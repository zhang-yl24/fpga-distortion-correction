"""Independent probe lifecycle faults; every process is a local Python mock."""
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import camera720_through_probe as probe


@pytest.fixture
def lifecycle(tmp_path,monkeypatch):
    source=tmp_path/'input.adf';source.write_bytes(b'fixed candidate')
    monkeypatch.setattr(probe,'CANDIDATE_SHA',probe.sha(source))
    plan=tmp_path/'stage-plan.json';plan.write_text('mock only; no native execution')
    value={'Schema':probe.SCHEMA,'Target':probe.prep.TARGET,'WorkDirectory':str(tmp_path),
        'MaximumSeconds':300,'Command':['never-start-pds.exe'],'EDAExecuted':False,
        **{k:False for k in probe.fast.FALSE_FLAGS}}
    watched={source:probe.sha(source)}
    monkeypatch.setattr(probe,'validate',lambda *a:(value,watched))
    monkeypatch.setattr(probe,'os',SimpleNamespace(name='nt'))
    monkeypatch.setattr(probe,'observations',lambda *a:([{'observed':1},{'observed':2}],[]))
    state={'active':False,'polls':0,'stdout':probe.MARKER,'stderr':'','cleanup':[],'ticks':[0,0]}
    class Process:
        pid=910001
        def poll(self):return None if state['active'] else 0
        def wait(self,timeout):
            state['polls']+=1
            if state.get('finish_on_wait'):state['active']=False
            if state['active']:raise probe.subprocess.TimeoutExpired('mock',timeout)
            return 0
    process=Process()
    def popen(command,**kwargs):
        assert command==['never-start-pds.exe'] and kwargs['shell'] is False
        assert Path(kwargs['cwd'])==tmp_path
        kwargs['stdout'].write(state['stdout'].encode());kwargs['stdout'].flush()
        kwargs['stderr'].write(state['stderr'].encode());kwargs['stderr'].flush()
        if state.get('change_adf'):source.write_bytes(b'changed during mock native')
        return process
    def stop_owned(child,work,reason):
        assert child is process and Path(work)==tmp_path
        state['cleanup'].append(child.pid);state['active']=False
        return {'Complete':True,'OwnedPID':child.pid}
    monkeypatch.setattr(probe.subprocess,'Popen',popen)
    monkeypatch.setattr(probe.diagnostic.cleanup,'stop_owned_tree',stop_owned)
    monkeypatch.setattr(probe.time,'monotonic',lambda:state['ticks'].pop(0) if state['ticks'] else 0)
    return plan,state,value,source


def test_clean_probe_never_claims_timing_or_hardware_acceptance(lifecycle):
    path,state,value,_=lifecycle
    result=probe.execute(path,'a'*64)
    assert result['ExecutionPassed'] and result['ProbeObserved']
    assert result['Schema']==probe.RESULT_SCHEMA and result['PlanSchema']==probe.SCHEMA
    assert result['EDAExecuted'] and state['cleanup']==[]
    assert result['Cleanup']['DescendantLivenessIndependentlyVerified'] is False
    for flag in probe.fast.FALSE_FLAGS:assert result[flag] is False


@pytest.mark.parametrize('message',('C: critical warning','E: native error','F: fatal','ERROR: error','FATAL: fatal','Traceback (most recent call last):'))
def test_exit_zero_does_not_override_critical_diagnostics(lifecycle,message):
    path,state,_,_=lifecycle;state['stderr']=message
    result=probe.execute(path,'a'*64)
    assert result['ExitCode']==0 and result['Diagnostics']
    assert not result['ExecutionPassed'] and not result['ProbeObserved']


def test_timeout_stops_only_owned_mock_process(lifecycle):
    path,state,_,_=lifecycle;state.update(active=True,ticks=[0,301,302])
    result=probe.execute(path,'a'*64)
    assert result['TimedOut'] and state['cleanup']==[910001]
    assert not result['ExecutionPassed'] and not result['ProbeObserved']


def test_unexpected_stage_stops_owned_process(lifecycle):
    path,state,_,_=lifecycle
    state.update(active=True,stdout='Process "Synthesize" started.\n'+probe.MARKER)
    result=probe.execute(path,'a'*64)
    assert result['StoppedForUnexpectedStage'] and state['cleanup']==[910001]
    assert not result['ExecutionPassed'] and not result['ProbeObserved']


def test_candidate_mutation_is_reported_even_with_clean_exit(lifecycle):
    path,state,_,_=lifecycle;state['change_adf']=True
    result=probe.execute(path,'a'*64)
    assert not result['InputADFUnchanged'] and result['InputDrift']
    assert not result['ExecutionPassed'] and not result['ProbeObserved']


def test_observation_failure_is_retained_and_not_promoted(lifecycle,monkeypatch):
    path,*_=lifecycle
    issues=[{'Stage':'native-through-observation','Error':'missing actual launch'}]
    monkeypatch.setattr(probe,'observations',lambda *a:([],issues))
    result=probe.execute(path,'a'*64)
    assert result['ExecutionPassed'] and not result['ProbeObserved']
    assert result['ObservationFailures']==issues


def test_missing_completion_marker_fails_despite_exit_zero(lifecycle):
    path,state,_,_=lifecycle;state['stdout']='process exited without requested query completion'
    result=probe.execute(path,'a'*64)
    assert not result['CompletionMarker'] and not result['ExecutionPassed'] and not result['ProbeObserved']


def test_probe_tcl_has_only_two_fixed_through_queries_and_original_init(tmp_path):
    commands=probe.commands();script=probe.render(tmp_path)
    assert len(commands)==2 and script.count('report_path_timing ')==2
    assert probe.inspect.INIT in script
    assert [probe.selector(c,'through') for c in commands]==[probe.SOURCE_PARENT+'/L6Q',probe.SOURCE_PARENT+'/L5Q']
    assert all(probe.selector(c,'from')==probe.SOURCE and probe.selector(c,'to')==probe.ENDPOINT for c in commands)
    for token in ('genbit','program','save_design','set_false_path','set_max_delay','set_min_delay'):
        assert token not in script


def test_dropped_or_changed_through_header_rejected_before_path_parse(tmp_path):
    report=tmp_path/'native.rtr';expected=probe.commands()[0]
    for changed in (expected.replace(' -through {'+probe.SOURCE_PARENT+'/L6Q}',''),
                    expected.replace('/L6Q}', '/L5Q}')):
        report.write_text('| Tool Version : Fabric Compiler (version 2023.2-SP3 <build 154097>)\n'
            '| Design : '+probe.prep.TARGET+'\n| Tcl Command : '+changed+'\n',encoding='ascii')
        with pytest.raises(ValueError):probe.parse_report(report,{},expected)
