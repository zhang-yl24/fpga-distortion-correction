import copy
import json
from pathlib import Path
import sys
from unittest import mock

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import camera720_raw_cdc as tool
import test_camera720_cdc_native as fixtures


def header(target=tool.TARGET):
    return '| Tool Version : Fabric Compiler (version 2023.2-SP3 <build 154097>)\n| Design : '+target+'\n'


def test_prefix_adaptation_isolated():
    before=tool.monitor.PREFIX
    adapted=tool.scoped_monitor()
    assert adapted.PREFIX=='camera/monitor/' and tool.monitor.PREFIX==before
    assert adapted.monitor_scalar.__globals__['PREFIX']==adapted.PREFIX
    assert tool.monitor.monitor_scalar.__globals__['PREFIX']==before


def test_collector_never_credits_packed_other_launch(tmp_path):
    q=fixtures.query();p=tmp_path/'r.rtr'
    p.write_text(header()+fixtures.path(q)+fixtures.path(q,launch='src/L6Q'))
    rows,bad,other=tool.collect([q],[p])
    assert len(rows)==1 and not bad and other[0]['LaunchOutput']=='src/L6Q'
    coverage=tool.timing.coverage([q],rows,bad)
    assert coverage['CoveredCases']==1 and len(coverage['MissingCases'])==1


def test_other_target_and_truncated_report_rejected(tmp_path):
    q=fixtures.query();p=tmp_path/'r.rtr'
    p.write_text(header('camera720_transport_top')+fixtures.path(q))
    with pytest.raises(ValueError,match='target/version'):tool.collect([q],[p])
    p.write_text(header()+fixtures.path(q).split(' Slack')[0])
    with pytest.raises(ValueError,match='truncated'):tool.collect([q],[p])


def test_both_corners_and_ordinary_hold_required():
    q=fixtures.query(False)
    rows=[fixtures.parsed(q,c,'setup') for c in ('slow','fast')]
    cov=tool.timing.coverage([q],rows,[])
    assert cov['ExpectedCases']==4 and {r['Kind'] for r in cov['MissingCases']}=={'hold'}


def test_bounded_groups_preserve_every_launch_and_exact_outputs():
    queries=[]
    for s in range(9):
        for e in range(25):
            q=fixtures.query();q.update(Source=f's{s}/CLK',LaunchOutput=f's{s}/Q',Endpoint=f'e{e}/I0');queries.append(q)
    # Same packed CLK, different output must never share a through collection.
    q=copy.deepcopy(queries[0]);q['LaunchOutput']='s0/L5Q';queries.append(q)
    missing=[{k:q[k] for k in tool.timing.IDENTITY} for q in queries]
    groups=tool.bounded_groups(queries,missing)
    assert {tool.timing.identity(r) for g in groups for r in g['ExpectedIdentities']}=={tool.timing.identity(q) for q in queries}
    for g in groups:
        assert len(g['ExpectedIdentities'])<=256 and len(g['SourceLaunches'])*len(g['Endpoints'])<=8192
        assert ' -through {' in g['Command']
        for endpoint in g['Endpoints']:
            assert len({(r['Source'],r['LaunchOutput']) for r in g['ExpectedIdentities'] if r['Endpoint']==endpoint})<=2
    for body in tool.query_bodies(groups).values():
        assert sum(c.startswith('report_path_timing ') for c in tool.derived.inspect.query_commands(body))<=8


def test_bound_input_hash_drift_rejected(tmp_path):
    p=tmp_path/'input';p.write_text('one');watched={};tool.bind(watched,p);p.write_text('two')
    with pytest.raises(ValueError,match='drift'):tool.bind({},p,next(iter(watched.values())))


def test_verification_recomputes_without_output_and_detects_forged_result(tmp_path):
    paths=[]
    for name in ('export','route','query'):
        p=tmp_path/name;p.write_text(name);paths.append(p)
    value={'Schema':tool.SCHEMA,'Target':tool.TARGET,'ExportReceipt':tool.ref(paths[0]),'RouteReceipt':tool.ref(paths[1]),
      'QueryReceipts':[tool.ref(paths[2])],'InputSHA256':{str(p):tool.sha(p) for p in paths},'ScopedDigitalChecksPassed':False}
    proof=tmp_path/'proof.json';proof.write_text(json.dumps(value));before={p.name:p.read_bytes() for p in tmp_path.iterdir()}
    with mock.patch.object(tool,'audit_value',return_value=(copy.deepcopy(value),value['InputSHA256'])) as recompute:
        actual,watched=tool.verify(proof)
        recompute.assert_called_once_with(str(paths[0]),str(paths[1]),[str(paths[2])])
        assert str(proof) in watched and actual==value
    assert before=={p.name:p.read_bytes() for p in tmp_path.iterdir()}
    forged={**value,'ScopedDigitalChecksPassed':True};proof.write_text(json.dumps(forged))
    with mock.patch.object(tool,'audit_value',return_value=(value,value['InputSHA256'])):
        with pytest.raises(ValueError,match='complete recomputation'):tool.verify(proof)


def test_wrong_schema_fails_before_recompute(tmp_path):
    p=tmp_path/'proof';p.write_text(json.dumps({'Schema':'old','Target':tool.TARGET}))
    with mock.patch.object(tool,'audit_value') as called:
        with pytest.raises(ValueError,match='wrong raw CDC'):tool.verify(p)
        called.assert_not_called()


def test_failed_native_receipt_not_accepted(tmp_path):
    p=tmp_path/'result.json';p.write_text(json.dumps({'Target':tool.TARGET,'Mode':'query','ExecutionPassed':False}))
    with pytest.raises(ValueError,match='inspection incomplete'):tool.bind_native(p,'query',{})


def test_gray_bound_requires_each_launch_at_both_corners():
    q=fixtures.query();q['LogicalRelationships']=[0]
    plan={'Queries':[q],'Structure':{'Gray':[{'Group':'gray','Source':'s','First':'f','SourceClock':'a'}]},
      'LogicalRelationships':[{'SourceFF':'s','DestinationFF':'f'}],'Constraints':fixtures.constraints()}
    rows=[fixtures.parsed(q,'slow')]
    bounds,missing=tool.gray_bounds(plan,rows)
    assert len(bounds)==1 and missing==[{'Stage':'gray-bound','Group':'gray','Corner':'fast'}]
    rows.append(fixtures.parsed(q,'fast'));bounds,missing=tool.gray_bounds(plan,rows)
    assert not missing and all(r['ConservativeSkewUpperBoundNS']==2 for r in bounds)
    rows[0]['ArrivalNS']=21
    with pytest.raises(ValueError,match='source period'):tool.gray_bounds(plan,rows)


def test_output_serialization_failure_does_not_create_partial_json(tmp_path):
    p=tmp_path/'proof.json'
    with mock.patch.object(tool,'audit_value',return_value=({'invalid':float('inf')},{})):
        with pytest.raises(ValueError):tool.audit('a','b',[],p)
    assert not p.exists()


@pytest.fixture(scope='module')
def candidate_graph():
    path=tool.WORK/'physical-export-b/generate_netlist'/f'{tool.TARGET}_sim.v'
    if not path.is_file():pytest.skip('optional native graph evidence absent')
    return tool.monitor.Graph(tool.functional(path.read_text(encoding='utf-8-sig')))


def test_actual_bank_address_mapping_and_admission_level(candidate_graph):
    g=candidate_graph
    memory=tool.preview_memory(g);assert memory['NativeDualPortSlices']==16
    policy=tool.protocol_review({},g)['AdmissionPolicy']
    assert len(policy['SourceConeRegisters'])==128 and policy['SingleSourceClock']=='board27'
    assert not policy['GlitchFreedomProven'] and not policy['SourceRegistered']


def test_preview_read_write_bank_swap_is_rejected(candidate_graph):
    graph=tool.monitor.Graph(copy.deepcopy(candidate_graph.g))
    c=graph.cells['picture/memory_0/gopdrm_36k/DRM36K']
    c['Ports']['ADDRB']=c['Ports']['ADDRA']
    with pytest.raises(ValueError,match='bank address differs'):tool.preview_memory(graph)


def test_metadata_enable_semantic_equivalence_uses_exact_native_truth(candidate_graph):
    g=candidate_graph;cone=tool.ExactCone(g)
    flag=g.ff[g.by_q('pipeline/bridge/done_held')]['Ports']['CE']
    other=g.ff[g.by_q('pipeline/bridge/checksum_held[2]')]['Ports']['CE']
    assert flag!=other and cone.expression(flag)==cone.expression(other)


def test_recovery_only_queries_missing_launches_and_does_not_mix_sources():
    queries=[]
    for i in range(3):
        q=fixtures.query();q.update(Source=f's{i}/CLK',LaunchOutput=f's{i}/Q');queries.append(q)
    missing=[{k:queries[1][k] for k in tool.timing.IDENTITY}]
    groups=tool.recovery_groups(queries,missing)
    assert len(groups)==1 and groups[0]['SourceLaunches']=={'s1/CLK':'s1/Q'}
    assert groups[0]['ExpectedIdentities']==missing


def test_tx_combinational_maximum_without_slack_and_at_eof(tmp_path):
    def path(port,corner,kind='max'):
        return (f'Startpoint : picture/hs/opit_0_inv/CLK\nEndpoint : {port} (port)\n'
          f'Path Type : {kind} ({corner} corner)\nPath Class : combinational timing path\n'
          ' Clock pixel_clk (rising edge) 0.000 0.000\n'
          ' GPLL_7_463/CLKOUT0 td 0.064 2.188 video_pll/u_gpll/gpll_inst/CLKOUT0\n'
          ' Data arrival time 5.882 Logic Levels: 6\n')
    p=tmp_path/'tx.rtr';p.write_text(path('hs_out','slow')+path('hs_out','slow','min')+path('hs_out','fast'))
    rows=tool.tx_records(p,False)
    assert [(r['Corner'],r['DelayType']) for r in rows]==[('slow','max'),('fast','max')]
    assert rows[-1]['ReportLine']==15
    p.write_text(path('hs_out','slow').replace(' Data arrival time 5.882 Logic Levels: 6\n',''))
    with pytest.raises(ValueError,match='TX field'):tool.tx_records(p,False)


def test_actual_final_tx_native_reports_cover_all_ports_and_corners():
    directory=tool.WORK/'cdc-final-native-io/report_path_timing'
    reports=list(directory.glob('report_path_timing_*/report_timing/'+tool.TARGET+'.rtr'))
    if len(reports)!=3:pytest.skip('optional completed final IO evidence absent')
    rows=[r for p in reports for r in tool.tx_records(p,False)]
    assert {(r['Port'],r['Corner'],r['DelayType']) for r in rows}=={
        (p,c,'max') for p in tool.native_io.tx.PORTS for c in ('slow','fast')}


def test_held_latency_requires_each_physical_boundary_and_corner():
    relations=[];queries=[];records=[]
    for i,clock in enumerate(('board27','ddrphy_sysclk','pixel_clk')):
        relations.append({'DestinationClock':clock,'Purposes':[
          'monitor held bus to every first sequential consumer' if i==0 else 'raw/preview held data']})
        q=fixtures.query();q.update(Source=f's{i}/CLK',LaunchOutput=f's{i}/Q',LogicalRelationships=[i])
        queries.append(q);records += [fixtures.parsed(q,corner) for corner in ('slow','fast')]
    plan={'Queries':queries,'LogicalRelationships':relations,
          'Constraints':{'PeriodsNS':{'board27':37.037,'ddrphy_sysclk':8,'pixel_clk':13.468}}}
    rows,missing=tool.held_bounds(plan,records)
    assert len(rows)==6 and not missing
    assert min(r['ConsumptionLatencyLowerBoundNS'] for r in rows)==16
    rows,missing=tool.held_bounds(plan,records[:-1])
    assert missing==[{'Stage':'held-data-bound','Group':'preview_bank','Corner':'fast'}]
    records[2]['ArrivalNS']=16
    with pytest.raises(ValueError,match='consumption latency'):tool.held_bounds(plan,records)
