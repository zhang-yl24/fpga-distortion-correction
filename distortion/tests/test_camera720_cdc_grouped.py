"""CPU-only grouping and actual-receipt boundary tests; no PDS execution."""
import copy
import hashlib
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import camera720_cdc_grouped as tool


def q(s,e,clock='board27'):
    return {'Source':s,'Endpoint':e,'Clock':clock,'Corners':['slow','fast'],'CheckKinds':['setup','hold']}


def test_many_sources_are_grouped_without_losing_pairs_or_cases():
    queries=[q(f'pipe/meta[{i}]/CLK',f'pipe/sync[{i}]/D') for i in range(601)]
    texts,groups=tool.bodies(queries, ['IO_1_2'])
    assert len(groups)==10
    assert len(texts)==3  # two complete five-query batches, then sites
    assert all(len(g['ExpectedPairs'])<=64 for g in groups)
    actual={(r['Source'],r['Endpoint']) for g in groups for r in g['ExpectedPairs']}
    assert actual=={(r['Source'],r['Endpoint']) for r in queries}
    assert tool.base.coverage(queries,[],[])['ExpectedCases']==2404
    assert all(sum(c.startswith('report_path_timing') for c in tool.inspect.query_commands(t))<=5 for t in texts)


def test_rectangle_counts_shared_sources_and_endpoints():
    queries=[q(f'meta[{s}]/CLK',f'sync[{e}]/D') for s in range(12) for e in range(10)]
    groups=tool.grouped_commands(queries,16)
    assert all(len(g['ExpectedPairs'])<=16 for g in groups)
    for g in groups:
        expected={(x['Source'],x['Endpoint']) for x in queries if x['Source'] in g['Sources'] and x['Endpoint'] in g['Endpoints']}
        assert expected=={(x['Source'],x['Endpoint']) for x in g['ExpectedPairs']}


def test_domains_and_bounds_cannot_share_a_native_group():
    queries=[q('a/CLK','b/D','board27'),q('c/CLK','d/D','camera_pclk')]
    cross={'Source':'e/CLK','Endpoint':'f/D','SourceClock':'camera_pclk','DestinationClock':'board27',
           'MaximumNS':8.0,'MinimumNS':0.0,'SourcePeriodNS':20.833,'Corners':['slow','fast'],
           'CheckKinds':['max-delay','min-delay']}
    queries.append(cross)
    assert len(tool.grouped_commands(queries))==3


@pytest.mark.parametrize('mutation',['unsafe','duplicate','corner','kind'])
def test_invalid_inventory_is_rejected(mutation):
    rows=[q('meta/CLK','sync/D')]
    if mutation=='unsafe':rows[0]['Source']='meta}; exec x; {'
    if mutation=='duplicate':rows.append(copy.deepcopy(rows[0]))
    if mutation=='corner':rows[0]['Corners']=['slow']
    if mutation=='kind':rows[0]['CheckKinds']=['setup']
    with pytest.raises(ValueError):tool.grouped_commands(rows)


@pytest.mark.parametrize('maximum,per_body',[(0,5),(65,5),(64,0),(64,6)])
def test_bounds_remain_small(maximum,per_body):
    with pytest.raises(ValueError):tool.bodies([q('a/CLK','b/D')],maximum_pairs=maximum,per_body=per_body)


def test_exact_missing_pairs_remain_pending_and_negative_variant_fails():
    queries=[q('a/CLK','b/D'),q('c/CLK','d/D')]
    records=[{'Source':'a/CLK','Endpoint':'b/D','Corner':c,'Kind':k,'SlackNS':1.0}
             for c in ('slow','fast') for k in ('setup','hold')]
    value=tool.base.coverage(queries,records,[])
    assert value['CoveredCases']==4 and len(value['MissingCases'])==4 and not value['EnumeratedPathsTimingPassed']
    records += [{**r,'Source':'c/CLK','Endpoint':'d/D'} for r in records]
    assert tool.base.coverage(queries,records,[{'Error':'negative variant'}])['EnumeratedPathsTimingPassed'] is False


def test_only_planned_group_or_bounded_exact_supplement_is_accepted():
    queries=[q('a/CLK','b/D'),q('c/CLK','d/D')]
    texts,_=tool.bodies(queries)
    plan={'Queries':queries}
    tool.approved_body(texts[0],plan,texts)
    exact=tool.base.group_commands(queries,exact=True)[0]['Command']+'\n'
    tool.approved_body(exact,plan,texts)
    with pytest.raises(ValueError):tool.approved_body(exact*6,plan,texts)
    with pytest.raises(ValueError):tool.approved_body(exact.replace('a/CLK','rogue/CLK'),plan,texts)


def test_explicit_original_plan_anchor_is_required_before_parsing(tmp_path,monkeypatch):
    monkeypatch.setattr(tool.prep,'WORK',tmp_path)
    p=tmp_path/'original.json';p.write_text('{}')
    with pytest.raises(ValueError,match='explicit completed v1 plan SHA'):
        tool.bind_original(p,'0'*64,{})


def native_fixture(tmp_path,monkeypatch):
    monkeypatch.setattr(tool.prep,'WORK',tmp_path)
    monkeypatch.setattr(tool.prep,'PROJECT',tmp_path)
    work=tmp_path/'query-a';work.mkdir()
    source=tmp_path/'candidate.adf';source.write_bytes(b'candidate')
    pds=tmp_path/'pds_shell.exe';pds.write_bytes(b'inert executable; never run')
    body=tmp_path/'body.tcl';body.write_text('show -dev_instance {IO_1_2}\n')
    native_source=tmp_path/'native.py';native_source.write_bytes(b'native snapshot')
    monkeypatch.setattr(tool.native,'SELF',native_source)
    fast_source=tmp_path/'fast.py';fast_source.write_bytes(b'fast snapshot')
    monkeypatch.setattr(tool.fast,'SELF',fast_source)
    candidate={'Path':str(source),'SHA256':tool.sha(source)}
    seed_ref={'Path':str(tmp_path/'seed.json'),'SHA256':'a'*64}
    original={'BuildPlanSHA256':'b'*64,'Command':[str(pds)]}
    seed={'SourceADF':candidate}
    context=(seed,original,{source:tool.sha(source)})
    script='whitelisted script\n'
    expected={'Schema':tool.native.SCHEMA,'Target':tool.prep.TARGET,'Mode':'query','WorkDirectory':str(work),
              'SourceADF':str(source),'SourceADFSHA256':tool.sha(source),'BuildPlanSHA256':'b'*64,
              'QueryBody':str(body),'MaximumSeconds':300,'Command':[str(pds)],
              'InputSHA256':{str(body):tool.sha(body)},'ExpectedActualStages':[]}
    monkeypatch.setattr(tool.fast,'envelope',lambda *args,**kwargs:(copy.deepcopy(expected),script))
    (work/'input.adf').write_bytes(source.read_bytes())
    (work/'executor-snapshot.py').write_bytes(native_source.read_bytes())
    (work/'stage.tcl').write_bytes(script.encode('ascii'))
    (work/'dummy.v').write_bytes(tool.native.physical.DUMMY.encode('ascii'))
    stage={**expected,'PreparedUTC':'2026-11-01T00:00:00Z'}
    (work/'stage-plan.json').write_text(json.dumps(stage))
    (work/'stdout.log').write_text(tool.native.MARKER+'\n')
    (work/'stderr.log').write_bytes(b'')
    (work/'probe.rtr').write_text('actual native report\n')
    value={**stage,'ExecutionPassed':True,'ExitCode':0,'TimedOut':False,'StoppedForUnexpectedStage':False,
           'InputDrift':[],'Diagnostics':[],'CompletionMarker':True,'InputADFUnchanged':True,
           'Cleanup':{'Complete':True},'EDAExecuted':True,'ActualEvents':[],
           **{flag:False for flag in tool.fast.FALSE_FLAGS},'StagePlanSHA256':tool.sha(work/'stage-plan.json'),
           'FastExecutionSeed':seed_ref,'FastExecutor':tool.ref(fast_source),
           'FullSourceProofReused':True,'AllProofInputsRehashed':True,
           'Artifacts':{name:tool.sha(work/name) for name in ('stage.tcl','stdout.log','stderr.log','probe.rtr')}}
    receipt=work/'result.json';receipt.write_text(json.dumps(value))
    return receipt,value,candidate,seed_ref,context


def test_actual_fast_receipt_binds_bytes_without_pds(tmp_path,monkeypatch):
    path,value,candidate,seed_ref,context=native_fixture(tmp_path,monkeypatch)
    watched={}
    actual=tool.bind_native_fast(path,'query',watched,candidate,'b'*64,seed_ref,context)
    assert actual==value and path in watched and path.parent/'probe.rtr' in watched


@pytest.mark.parametrize('mutation',['candidate','seed','mode','body','tcl','snapshot','report','marker','error','stage_hash','claim'])
def test_native_fast_rejects_false_or_changed_evidence(tmp_path,monkeypatch,mutation):
    path,value,candidate,seed_ref,context=native_fixture(tmp_path,monkeypatch)
    if mutation=='candidate':value['SourceADFSHA256']='c'*64
    if mutation=='seed':value['FastExecutionSeed']={**seed_ref,'SHA256':'c'*64}
    if mutation=='mode':value['Mode']='report'
    if mutation=='body':Path(value['QueryBody']).write_text('show -dev_instance {OTHER}\n')
    if mutation=='tcl':(path.parent/'stage.tcl').write_text('malicious\n')
    if mutation=='snapshot':(path.parent/'executor-snapshot.py').write_text('changed\n')
    if mutation=='report':(path.parent/'probe.rtr').write_text('changed report\n')
    if mutation=='marker':
        (path.parent/'stdout.log').write_text('no completion\n')
        value['Artifacts']['stdout.log']=tool.sha(path.parent/'stdout.log')
    if mutation=='error':
        (path.parent/'stdout.log').write_text('ERROR: native failure\n'+tool.native.MARKER+'\n')
        value['Artifacts']['stdout.log']=tool.sha(path.parent/'stdout.log')
    if mutation=='stage_hash':value['StagePlanSHA256']='c'*64
    if mutation=='claim':value['TimingAccepted']=True
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError):tool.bind_native_fast(path,'query',{},candidate,'b'*64,seed_ref,context)


def test_seed_context_for_another_candidate_is_rejected(tmp_path,monkeypatch):
    path,value,candidate,seed_ref,context=native_fixture(tmp_path,monkeypatch)
    bad=copy.deepcopy(context);bad[0]['SourceADF']={**candidate,'SHA256':'c'*64}
    with pytest.raises(ValueError,match='seed context'):
        tool.bind_native_fast(path,'query',{},candidate,'b'*64,seed_ref,bad)
