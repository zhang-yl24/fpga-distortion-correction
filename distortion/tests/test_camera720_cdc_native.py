import copy
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import camera720_cdc_native as tool


def constraints():
    return {'RelevantStatements': [
        {'Line': 811, 'Text': 'set_max_delay -datapath_only -from [get_clocks {a}] -to [get_clocks {b}] 8.0'},
        {'Line': 812, 'Text': 'set_min_delay -from [get_clocks {a}] -to [get_clocks {b}] 0.0'}],
        'PeriodsNS': {'a': 20.833, 'b': 37.037}}


def inventory(cross=True, outputs=('L5Q',)):
    rows, queries = [], []
    for index, output in enumerate(outputs):
        rows.append({'SourceNativeClockPin': 'src/CLK', 'SourceNativeOutputPin': 'src/'+output,
                     'SourceClock': 'a', 'DestinationClock': 'b' if cross else 'a',
                     'NativeBoundaries': [{'Endpoint': 'dst/I2'}]})
        requirement = {'CheckKinds': ['max-delay','min-delay'], 'Corners': ['slow','fast'],
                       'SourceClock': 'a', 'DestinationClock': 'b', 'MaximumNS': 8.0,
                       'MinimumNS': 0.0, 'SourcePeriodNS': 20.833} if cross else {
                           'Clock': 'a', 'Corners': ['slow','fast'], 'CheckKinds': ['setup','hold']}
        queries.append({'Source':'src/CLK','LaunchOutput':'src/'+output,'Endpoint':'dst/I2',
                        'Requirements':requirement,'LogicalRelationships':[index]})
    return {'MappingPassed':True, 'NativeTimingAccepted':False,
            'LogicalRelationships':rows,'Queries':queries}


def query(cross=True, output='L5Q'):
    return tool.normalize_queries(inventory(cross,(output,)),constraints())[0]


def path(q, corner='slow', kind=None, launch=None, slack=None):
    cross = 'Clock' not in q
    kind = kind or ('max-delay' if cross else 'setup')
    typ = 'max' if kind in ('setup','max-delay') else 'min'
    check = 'Setup' if typ == 'max' else 'Hold'
    slack = (5.9 if cross else 2.0) if slack is None else slack
    exception = ('Timing Exception : MaxDelay Path 8.000ns -datapath_only\n'
                 'Exception constraint line number: 811\n') if cross else ''
    clocks = '' if cross else ' Clock a (rising edge) 0.000 0.000\n'
    return (f'Startpoint : {q["Source"]}\nEndpoint : {q["Endpoint"]}\n'
            f'Path Group : {q.get("DestinationClock",q.get("Clock"))}\n'
            f'Path Type : {typ} ({corner} corner)\nPath Class : sequential timing path\n'+exception+
            clocks+f' CLMA_1_2/Q tco 0.100 0.100 r {launch or q["LaunchOutput"]}\n'
            ' Data arrival time 2.000 Logic Levels: 0\n'+clocks+
            f' {check} time -0.100 7.900\n'
            f' Slack ({"MET" if slack >= 0 else "VIOLATED"}) {slack:.3f}\n')


def parsed(q,corner='slow',kind=None,**kw):
    return tool.parse_record(path(q,corner,kind,**kw).splitlines(True),'r.rtr',1,q)


def header():
    return '| Tool Version : Fabric Compiler (version 2023.2-SP3 <build 154097>)\n| Design : camera720_transport_top\n'


def test_crossing_contract_is_explicit_max_only_not_min_pass():
    q=query()
    assert q['CheckKinds']==['max-delay']
    assert q['HoldAnalysisSuppressed'] and q['MinDelayNotAccepted']
    assert q['DeclaredMinimum']=={'Line':812,'Text':constraints()['RelevantStatements'][1]['Text'],'BoundNS':0.0}
    rows=[parsed(q,c) for c in q['Corners']]
    assert tool.coverage([q],rows,[])['EnumeratedPathsTimingPassed']
    assert tool.coverage([q],rows[:1],[])['MissingCases'][0]['Corner']=='fast'


def test_same_domain_still_requires_hold_and_both_corners():
    q=query(False)
    rows=[parsed(q,c,'setup') for c in q['Corners']]
    result=tool.coverage([q],rows,[])
    assert result['ExpectedCases']==4 and not result['Complete']
    assert {r['Kind'] for r in result['MissingCases']}=={'hold'}
    rows += [parsed(q,c,'hold') for c in q['Corners']]
    assert tool.coverage([q],rows,[])['EnumeratedPathsTimingPassed']


def test_packed_clk_does_not_merge_distinct_launches():
    qs=tool.normalize_queries(inventory(True,('L5Q','L6Q')),constraints())
    rows=[parsed(qs[0],c) for c in qs[0]['Corners']]
    result=tool.coverage(qs,rows,[])
    assert result['CoveredCases']==2 and len(result['MissingCases'])==2
    assert {r['LaunchOutput'] for r in result['MissingCases']}=={'src/L6Q'}
    with pytest.raises(ValueError,match='identity'):
        parsed(qs[0],launch='src/L6Q')


@pytest.mark.parametrize('change',[lambda v:v['RelevantStatements'].pop(0),
    lambda v:v['RelevantStatements'][0].update(Text=v['RelevantStatements'][0]['Text'].replace(' -datapath_only','')),
    lambda v:v['RelevantStatements'].append(v['RelevantStatements'][0]),
    lambda v:v['PeriodsNS'].update(a=12.0)])
def test_crossing_suppression_requires_exact_effective_policy(change):
    value=constraints();change(value)
    with pytest.raises(ValueError):tool.normalize_queries(inventory(),value)


@pytest.mark.parametrize('transform',[
    lambda s:s.replace('src/L5Q','src/L6Q'),
    lambda s:s.replace(' tco ',' td '),
    lambda s:s.replace('number: 811','number: 812'),
    lambda s:s.replace('8.000ns','9.000ns'),
    lambda s:s.replace(' -datapath_only',''),
    lambda s:s.replace('Path Group : b','Path Group : a'),
    lambda s:s.replace('Slack (MET) 5.900','Slack (VIOLATED) -0.001'),
    lambda s:s.replace('Slack (MET) 5.900','Slack (MET) 6.900'),
    lambda s:s.replace('Path Type : max','Path Type : min'),
])
def test_native_crossing_rejects_wrong_identity_policy_or_arithmetic(transform):
    q=query()
    with pytest.raises(ValueError):tool.parse_record(transform(path(q)).splitlines(True),'r.rtr',1,q)


def test_ordinary_paths_cannot_use_exception_or_wrong_clock():
    q=query(False)
    for txt in (path(q).replace('Clock a','Clock b',1),
                path(q).replace('Path Class','Timing Exception : False Path\nPath Class'),
                path(q).replace('(rising edge)','(falling edge)',1)):
        with pytest.raises(ValueError):tool.parse_record(txt.splitlines(True),'r.rtr',1,q)


def test_collector_retains_other_launch_without_credit_and_bad_variant(tmp_path):
    q=query();p=tmp_path/'native.rtr'
    p.write_text(header()+path(q)+path(q)+path(q,launch='src/L6Q')+path(q,slack=-0.01),encoding='ascii')
    rows,violations,excluded=tool.collect([q],[p])
    assert len(rows)==1 and len(violations)==1
    assert excluded[0]['LaunchOutput']=='src/L6Q'
    assert not tool.coverage([q],rows,violations)['EnumeratedPathsTimingPassed']


def test_truncated_report_cannot_be_accepted(tmp_path):
    q=query();p=tmp_path/'truncated.rtr'
    p.write_text(header()+path(q).split(' Slack')[0],encoding='ascii')
    with pytest.raises(ValueError,match='truncated'):tool.collect([q],[p])


def test_unrelated_port_path_is_filtered_before_strict_identity(tmp_path):
    q=query();p=tmp_path/'ports.rtr'
    unrelated=path(q).replace('Startpoint : src/CLK','Startpoint : cam_data[0] (port)')
    p.write_text(header()+unrelated+path(q),encoding='ascii')
    rows,violations,_=tool.collect([q],[p])
    assert len(rows)==1 and not violations


def test_grouping_keeps_identity_budget_and_at_most_four_launches_per_endpoint():
    qs=[]
    for i in range(70):
        q=query();q.update(Source=f'src{i}/CLK',LaunchOutput=f'src{i}/L5Q');qs.append(q)
    missing=tool.coverage(qs,[],[])['MissingCases']
    groups=tool.groups_for(qs,missing)
    assert len(groups)==18
    assert sum(len(g['ExpectedIdentities']) for g in groups)==70
    bodies=tool.query_bodies(groups,3)
    assert all(sum(c.startswith('report_path_timing') for c in tool.inspect.query_commands(s))<=3 for s in bodies.values())
    assert not any('show -dev_instance' in s for s in bodies.values())
    with pytest.raises(ValueError):tool.query_bodies(groups,5)


def test_pin_enumeration_requires_complete_exact_native_objects():
    q=query();g=tool.groups_for([q],tool.coverage([q],[],[])['MissingCases'])[0]
    log="I: Timing-5001: The pattern '"+g['PinPattern']+"' match 3 objects below: "+' '.join('t:'+p for p in g['Pins'])
    assert tool.validate_pin_log(log,[g])==[]
    assert tool.validate_pin_log(log.replace('match 3','match 4'),[g])
    assert tool.validate_pin_log(log.rsplit(' t:',1)[0],[g])
    assert tool.validate_pin_log('',[g])


def test_invalid_relationship_clock_and_duplicate_identity_rejected():
    for mutate in (lambda v:v['LogicalRelationships'][0].update(SourceClock='other'),
                   lambda v:v['Queries'].append(copy.deepcopy(v['Queries'][0])),
                   lambda v:v['Queries'][0].update(LaunchOutput='x/L5Q')):
        value=inventory();mutate(value)
        with pytest.raises(ValueError):tool.normalize_queries(value,constraints())


def test_targeted_header_must_retain_every_filter_and_command_index():
    commands=[tool.timing_command('s1/CLK s2/CLK','d1/I0 d2/I1'),tool.timing_command('s3/CLK','d3/D')]
    header='| Tcl Command : report_path_timing -nworst 8 -max_path 1000 -from {t:s1/CLK\tt:s2/CLK} -to {t:d1/I0 t:d2/I1}\n'
    name='report_path_timing/report_path_timing_1/report_timing/a.rtr'
    tool.validate_report_filter(name,header,commands)
    for bad in (header.replace('\tt:s2/CLK',''), header.replace(' t:d2/I1',''),
                header.replace('t:s1/CLK','t:wrong/CLK')):
        with pytest.raises(ValueError,match='filters'):
            tool.validate_report_filter(name,bad,commands)
    with pytest.raises(ValueError):tool.validate_report_filter(name.replace('_1/','_2/'),header,commands)


def test_group_rectangle_also_limits_unlisted_source_endpoint_combinations():
    qs=[]
    for i in range(17):
        q=query();q.update(Source=f's{i}/CLK',LaunchOutput=f's{i}/L5Q',Endpoint=f'd{i}/I0');qs.append(q)
    groups=tool.groups_for(qs,tool.coverage(qs,[],[])['MissingCases'])
    for g in groups:
        ss,es=tool.query_filter(g['Command'])
        assert len(ss)<=4 and len(ss)*len(es)<=64
