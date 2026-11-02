"""CPU-only fake completed-build binding; no actual EDA or board operation."""
import copy
import json
from pathlib import Path
import sys
import tempfile

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import camera720_stats_inspect as inspect


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    if isinstance(value,dict):value=json.dumps(value,indent=2)+'\n'
    path.write_bytes(value if isinstance(value,bytes) else value.encode('utf-8'))


@pytest.fixture
def fixture(monkeypatch):
    inspect.prep.WORK.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='inspect-fixture-build-',dir=inspect.prep.WORK) as b,\
         tempfile.TemporaryDirectory(prefix='inspect-fixture-stage-',dir=inspect.prep.WORK) as s:
        build=Path(b).resolve();stage=Path(s).resolve();stage.rmdir()
        assert build.parent==stage.parent==inspect.prep.WORK.resolve()
        original=build/'input.v';write(original,'module fixture; endmodule\n')
        top=build/'source'/inspect.TOP;header=build/'source'/inspect.HEADER
        payloads={top:b'module camera720_calibrated_stats_top; endmodule\n',header:b'// fixture header\n',
                  build/'source/manifest.json':b'{}\n',
                  build/'compiled'/inspect.TOP:b'module camera720_calibrated_stats_top; endmodule\n',
                  build/'compiled'/inspect.HEADER:b'// fixture header\n'}
        for p,data in payloads.items():write(p,data)
        pds=build/'bin/pds_shell.exe';write(pds,'CPU fixture, not executable')
        adf=build/'place_route'/(inspect.prep.TARGET+'_pnr.adf');write(adf,'FAKE ADF; never PDS')
        write(build/'pre-sta-final.adf',adf.read_bytes());digest=inspect.sha(adf)
        tcl=('set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676\n'
             'pnr -optimize_multi_corner_timing -fix_hold_violation\n'
             'if {[file exists '+inspect.literal(adf)+']} {\n'
             '    file copy '+inspect.literal(adf)+' '+inspect.literal(build/'pre-sta-final.adf')+'\n}\n'
             'report_timing -force_to_run -delay_type min_max -max_path 1000 -nworst 4 -report_exception TRUE\n').encode('ascii')
        write(build/'timing.tcl',tcl)
        payloads[build/'timing.tcl']=tcl
        payloads[build/'source-plan.json']=b'{}\n'
        write(build/'source-plan.json',payloads[build/'source-plan.json'])
        plan={'Schema':inspect.prep.SCHEMA,'Target':inspect.prep.TARGET,'SourcePreparation':{'Path':str(build/'source-fixture.json'),'SHA256':'0'*64},
              'PDS':{'Executable':str(pds),'ExecutableSHA256':inspect.sha(pds)},
              'MaximumSecondsForExternalExecutor':300,'InputSHA256':{str(original):inspect.sha(original)},
              'PreparedSHA256':{str(p):inspect.sha(p) for p in payloads},
              'ExpectedActualStages':['Compile','Synthesize','Device Map','Place','Route','Route Optimize','Report Timing'],
              'CommandToRunSeparately':[str(pds),'-file',(build/'timing.tcl').as_posix()]}
        path=build/'plan.json';write(path,{**plan,'PreparedUTC':'fixture'})
        events=[[name,event] for name in plan['ExpectedActualStages'] for event in ('started','done')]
        write(build/'execution-stdout.log',''.join('Process "'+name+'" '+event+'.\n' for name,event in events))
        write(build/'execution-stderr.log','')
        result={'Schema':'camera720-calibrated-stats-build-execution-v1','Target':inspect.prep.TARGET,
            'ExecutionCompletedWithoutError':True,'NativeExitCode':0,'SourcesStable':True,'ActualStagesComplete':True,
            'InputDrift':[],'Diagnostics':[],'TimedOut':False,'StoppedForUnexpectedStage':False,'Cleanup':{'Complete':True},
            'Plan':str(path),'PlanSHA256':inspect.sha(path),'EDAExecuted':True,
            'Command':plan['CommandToRunSeparately'],'ActualEvents':events,
            'HardwareAccessed':False,'BitstreamRequested':False,'TimingAccepted':False,'HardwareReleaseAllowed':False,
            'ExecutorSHA256':inspect.sha(inspect.diagnostic.__file__),
            'DatabaseSnapshotAudit':{'UnchangedAcrossSTA':True,'Snapshot':str(build/'pre-sta-final.adf'),
                'FinalRoutedDatabase':str(adf),'SnapshotSHA256':digest,'FinalRoutedDatabaseSHA256':digest},
            'LogSHA256':{name:inspect.sha(build/name) for name in ('execution-stdout.log','execution-stderr.log')}}
        receipt=build/'execution-result.json';write(receipt,result)
        monkeypatch.setattr(inspect.prep,'recipe',lambda *args:(copy.deepcopy(plan),payloads))
        monkeypatch.setattr(inspect.diagnostic,'validate_plan',lambda *args:(_ for _ in ()).throw(AssertionError('fresh-only validator must not be called')))
        monkeypatch.setattr(inspect.subprocess,'Popen',lambda *args,**kwargs:(_ for _ in ()).throw(AssertionError('no native process allowed')))
        yield {'build':build,'stage':stage,'plan':plan,'plan_path':path,'adf':adf,'sha':digest,
               'result':result,'receipt':receipt,'payloads':payloads,'tcl':tcl}


def bound(f,**kwargs):return inspect.bind(f['plan_path'],f['adf'],f['sha'],**kwargs)


def test_completed_build_rebinds_generated_top_even_when_native_artifacts_exist(fixture):
    f=fixture;write(f['build']/'native-extra.txt','actual stage artifact')
    p,watched=bound(f)
    assert p['Target']=='camera720_calibrated_stats_top'
    assert f['build']/'source'/inspect.TOP in watched and f['build']/'compiled'/inspect.TOP in watched
    assert f['adf'] in watched and f['receipt'] in watched


@pytest.mark.parametrize('fault',['old_target','source_top','compiled_header','snapshot','actual_stages','log_hash','flag','extra_source'])
def test_completed_build_rejects_wrong_identity_or_changed_inputs(fixture,fault):
    f=fixture
    if fault=='old_target':
        p=json.loads(f['plan_path'].read_text());p['Target']='camera720_transport_top';write(f['plan_path'],p)
    elif fault=='source_top':write(f['build']/'source'/inspect.TOP,'altered')
    elif fault=='compiled_header':write(f['build']/'compiled'/inspect.HEADER,'altered')
    elif fault=='snapshot':write(f['build']/'pre-sta-final.adf','different')
    elif fault=='actual_stages':
        write(f['build']/'execution-stdout.log','Process "Generate Bitstream" started.\n')
        f['result']['LogSHA256']['execution-stdout.log']=inspect.sha(f['build']/'execution-stdout.log')
        write(f['receipt'],f['result'])
    elif fault=='log_hash':write(f['build']/'execution-stderr.log','changed')
    elif fault=='flag':f['result']['HardwareAccessed']=True;write(f['receipt'],f['result'])
    else:write(f['build']/'source/extra.v','module extra;endmodule')
    with pytest.raises(ValueError):bound(f)


def test_unknown_diagnostic_cannot_hide_in_clean_receipt(fixture):
    f=fixture;write(f['build']/'native.log','C: Unknown critical issue\n')
    f['result']['LogSHA256']['native.log']=inspect.sha(f['build']/'native.log');write(f['receipt'],f['result'])
    with pytest.raises(ValueError,match='unreported C/E/F'):bound(f)


def test_known_width_failure_needs_exact_review_and_stays_failed(fixture):
    f=fixture
    line='C: Sdm-3003: [fixture.v(line number: 1)] Reduce accumulator counter size from 32 to 8. If this is not intended behavior, please drive counter with valid values.'
    write(f['build']/'compile/run.log',line+'\n')
    f['result']['ExecutionCompletedWithoutError']=False
    f['result']['Diagnostics']=['compile/run.log: '+line]
    f['result']['LogSHA256']['compile/run.log']=inspect.sha(f['build']/'compile/run.log');write(f['receipt'],f['result'])
    with pytest.raises(ValueError,match='explicit read-only review'):bound(f)
    review=f['build']/'review.json'
    write(review,inspect.readonly_review_payload(f['plan_path'],f['receipt'],f['adf'],f['result']))
    p,_=bound(f,review_path=review,review_sha=inspect.sha(review))
    value,_,_=inspect.recipe(f['plan_path'],f['adf'],f['sha'],f['stage'],'report',maximum=120,
                            review_path=review,review_sha=inspect.sha(review))
    assert value['BuildExecutionCompletedWithoutError'] is False and value['BuildDiagnosticsCleared'] is False
    assert not value['HardwareReleaseAllowed'] and not value['TimingAccepted']
    assert json.loads(f['receipt'].read_text())['ExecutionCompletedWithoutError'] is False
    altered=copy.deepcopy(f['result']);altered['Diagnostics']=['compile/run.log: E: syntax failure']
    with pytest.raises(ValueError,match='only explicit accumulator'):inspect.readonly_review_payload(f['plan_path'],f['receipt'],f['adf'],altered)


@pytest.mark.parametrize('mode',['report','export','query'])
def test_native_modes_prepare_only_current_target_readonly_context(fixture,mode):
    f=fixture;body=None
    if mode=='query':body=f['build']/'body.txt';write(body,'get_ports -regexp {.*}\n')
    stage=inspect.prepare(f['plan_path'],f['adf'],f['sha'],f['stage'],mode,body,120)
    value,_=inspect.validate_prepared(stage)
    assert value['ExpectedActualStages']==(['Report Timing','Generate Netlist'] if mode=='export' else [])
    assert value['CompiledTop']['Path']==str(f['build']/'compiled'/inspect.TOP)
    assert value['CompiledHeader']['SHA256']==inspect.sha(f['build']/'compiled'/inspect.HEADER)
    text=(f['stage']/'stage.tcl').read_text()
    assert 'gen_bitstream' not in text and 'set_false_path' not in text
    assert str(f['stage']/'input.adf').replace('\\','/') in text
    if mode=='export':assert '-input_db_file' in text and 'gen_netlist' in text
    else:assert (f['stage']/'dummy.v').is_file()


@pytest.mark.parametrize('body',['gen_bitstream\n','exec {a}\n','source {x}\n','set_false_path -from {a} -to {b}\n',
    'get_ports -regexp {.*}; exec {bad}\n','puts {a\\}\nexec {bad}\n'])
def test_query_allowlist_rejects_mutations_and_injection(body):
    with pytest.raises(ValueError):inspect.query_commands(body)


def test_prepared_tcl_mutation_rejected(fixture):
    f=fixture;p=inspect.prepare(f['plan_path'],f['adf'],f['sha'],f['stage'],'report',maximum=120)
    with (f['stage']/'stage.tcl').open('ab') as stream:stream.write(b'gen_bitstream\n')
    with pytest.raises(ValueError,match='artifact drift'):inspect.validate_prepared(p)


def test_native_netlist_must_match_new_target(fixture):
    f=fixture;p=f['build']/'netlist.v'
    write(p,'module camera720_transport_top();\nV_DFF /* CLMA_1_2 */ cell();\nendmodule\n')
    assert not inspect.native_netlist_valid(p)
    write(p,'module camera720_calibrated_stats_top();\nV_DFF /* CLMA_1_2 */ cell();\nendmodule\n')
    assert inspect.native_netlist_valid(p)


def fake_finished_inspection(f,mode):
    stage=inspect.prepare(f['plan_path'],f['adf'],f['sha'],f['stage'],mode,maximum=120)
    value=json.loads(stage.read_text());events=[[s,e] for s in value['ExpectedActualStages'] for e in ('started','done')]
    write(f['stage']/'stdout.log',''.join('Process "'+s+'" '+e+'.\n' for s,e in events)+inspect.MARKER+'\n')
    write(f['stage']/'stderr.log','')
    report=f['stage']/('report_timing' if mode=='export' else '')/(inspect.prep.TARGET+'.rtr')
    write(report,'| Design : '+inspect.prep.TARGET+'\nFixture only, not native timing.\n')
    netlist=None
    if mode=='export':
        path=f['stage']/'generate_netlist'/(inspect.prep.TARGET+'_sim.v')
        write(path,'module camera720_calibrated_stats_top();\nV_DFF /* CLMA_1_2 */ cell();\nendmodule\n')
        netlist={'Path':str(path),'SHA256':inspect.sha(path),'Bytes':path.stat().st_size}
    result={**value,'StagePlanSHA256':inspect.sha(stage),'EDAExecuted':True,'ExecutionPassed':True,'ExitCode':0,
        'TimedOut':False,'StoppedForUnexpectedStage':False,'InputDrift':[],'Diagnostics':[],
        'CompletionMarker':True,'InputADFUnchanged':True,'Cleanup':{'Complete':True},'ActualEvents':events,
        'NativeNetlistWithFFloc':True if mode=='export' else None,'Netlist':netlist,
        'TimingReport':inspect.timing_report(f['stage'],mode),
        'Artifacts':{p.relative_to(f['stage']).as_posix():inspect.sha(p) for p in f['stage'].rglob('*')
                     if p.is_file() and p.suffix in ('.tcl','.log','.rtr','.v','.gnr','.txt','.fdc')}}
    path=f['stage']/'result.json';write(path,result)
    return path,result,report


@pytest.mark.parametrize('mode',['report','export'])
def test_finished_receipt_rebinds_real_target_artifact_inventory(fixture,mode):
    f=fixture;path,result,report=fake_finished_inspection(f,mode)
    bound_value,watched=inspect.bind_receipt(path)
    assert bound_value==result and report in watched
    assert not bound_value['TimingAccepted'] and not bound_value['HardwareReleaseAllowed']
    write(report,report.read_text()+'changed\n')
    with pytest.raises(ValueError):inspect.bind_receipt(path)


def test_tampered_saved_success_cannot_hide_missing_report(fixture):
    f=fixture;path,result,report=fake_finished_inspection(f,'report')
    report.unlink();result['Artifacts'].pop(report.relative_to(f['stage']).as_posix());write(path,result)
    with pytest.raises(ValueError,match='timing report missing'):inspect.bind_receipt(path)
