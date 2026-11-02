"""CPU-only extraction of this candidate's exact hold branches and setup margins.

Native queries are emitted, never executed. Branch identities come from fresh
timing data; coordinate distance is not a predicted routing delay.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re

import audit_camera_vga_hold as timing
import audit_raw_camera_routes as routes
import camera720_stats_hold_route_near as waypoint
import run_raw_camera_delay_route_reset as commands
from camera720_calibrated_inspect import query_commands

TARGET = 'camera720_view_toggle_top'
SELF = Path(__file__).resolve()
require, sha = timing.require, timing.sha


def ref(path):
    return {'Path':str(Path(path).resolve()), 'SHA256':sha(path)}


def write(path, value):
    with Path(path).open('x', encoding='utf-8', newline='\n') as f:
        json.dump(value, f, indent=2)
        f.write('\n')


def report_identity(path):
    with Path(path).open(encoding='utf-8-sig') as f:
        head=''.join(f.readline() for _ in range(16))
    require(re.findall(r'(?m)^\| Design\s*:\s*(\S+)\s*$',head)==[TARGET],
            'exact view-toggle native report required')


def extract(full_report, extra_reports=()):
    full_report=Path(full_report).resolve()
    report_identity(full_report)
    failed, summaries, initial_ref=timing.read_report(full_report)
    identities={timing.identity(p) for p in failed if p['Kind']=='hold' and p['SlackNS']<0}
    require(identities, 'no failing branch to investigate')
    for s in summaries:
        if s['Kind']=='hold' and s['FailingChecks']:
            actual={timing.identity(p) for p in failed if p['Kind']=='hold' and p['SlackNS']<0
                    and (p['Corner'],p['LaunchClock'],p['CaptureClock'])==
                        (s['Corner'],s['LaunchClock'],s['CaptureClock'])}
            require(len(actual)==s['FailingChecks'], 'full native hold detail differs from summary')
    paths, provenance=[],[]
    for report in (full_report,*map(Path,extra_reports)):
        report=report.resolve()
        report_identity(report)
        selected,_,evidence=timing.read_report(report,identities)
        paths.extend(selected)
        provenance.append(evidence)
    rows,excerpts=[],{}
    for number,key in enumerate(sorted(identities),1):
        cases,seen=[],set()
        for path in paths:
            if timing.identity(path)!=key:
                continue
            value=timing.parse_path(path['_Lines'],path['Report'],path['ReportLine'])
            if value['PathSHA256'] in seen:
                continue
            seen.add(value['PathSHA256'])
            filename=f'path-{number:02d}-{value["Corner"]}-{value["Kind"]}-{len(cases)+1}.txt'
            excerpts[filename]=value.pop('_Text')
            value['Excerpt']=filename
            cases.append(value)
        hold=[p for p in cases if p['Kind']=='hold']
        require({p['Corner'] for p in hold}=={'slow','fast'}, 'both native hold corners required')
        terms={(p['DataTrace'][-2]['Name'],p['DataTrace'][-2]['FromRoutePin'],
                p['DataTrace'][-2]['ToRoutePin'],p['DataTrace'][-2]['Fanout']) for p in cases}
        require(len(terms)==1, 'terminal branch differs across exact timing cases')
        net,start,end,fanout=next(iter(terms))
        require(fanout==1 and re.fullmatch(r'_N\d+',net), 'single-load native terminal branch required')
        margins={}
        for corner in ('slow','fast'):
            setup=[p['SlackNS'] for p in cases if p['Corner']==corner and p['Kind']=='setup']
            margins[corner]={'HoldSlackNS':min(p['SlackNS'] for p in hold if p['Corner']==corner),
                'ExactSetupFound':bool(setup),'ExactSetupSlackNS':min(setup) if setup else None}
        throughs=sorted({p['DataTrace'][0]['LogicalResource'] for p in cases})
        rows.append({'PathNumber':number,**dict(zip(('Source','Endpoint','LaunchClock','CaptureClock'),key[:4])),
                     'Cases':cases,'Margins':margins,'ActualLaunchOutputs':throughs,
                     'PhysicalRepairCandidate':{'Net':net,'FromRoutePin':start,'ToRoutePin':end,'Fanout':fanout,
                         'Endpoint':key[1],'BranchOnly':True,'TimingWaiverAllowed':False}})
    body=[]
    for row in rows:
        for i,through in enumerate(row['ActualLaunchOutputs']):
            body += [f'puts {{VIEW_HOLD_{row["PathNumber"]}_{i}}}',
                'report_path_timing -delay_type min_max -max_path 1000 -nworst 8 -report_exception TRUE '
                '-from {t:'+row['Source']+'} -through {t:'+through+'} -to {t:'+row['Endpoint']+'}']
        body.append('show -design_net {'+row['PhysicalRepairCandidate']['Net']+'}')
    body='\n'.join(body)+'\n'
    query_commands(body)
    missing_launch=[]
    for row in rows:
        observed={(c['DataTrace'][0]['LogicalResource'],c['Corner'],c['Kind']) for c in row['Cases']}
        missing_launch += [{'PathNumber':row['PathNumber'],'Through':through,'Corner':corner,'Kind':kind}
            for through in row['ActualLaunchOutputs'] for corner in ('slow','fast') for kind in ('setup','hold')
            if (through,corner,kind) not in observed]
    result={'Schema':'camera720-view-toggle-hold-analysis-v1','Target':TARGET,
            'CreatedUTC':datetime.now(timezone.utc).isoformat(),
            'InputReports':provenance,'FullReport':initial_ref,'HoldFailingPathCount':len(rows),
            'Paths':rows,'MissingExactSetup':[{'PathNumber':r['PathNumber'],'Corner':c}
                for r in rows for c,m in r['Margins'].items() if not m['ExactSetupFound']],
            'MissingLaunchCases':missing_launch,
            'Parser':ref(timing.__file__),'Producer':ref(SELF),
            'HardwareAccessed':False,'EDAExecuted':False,'TimingAccepted':False}
    return result,excerpts,body


def derive_waypoints(analysis_path, dump_path):
    analysis_path,dump_path=Path(analysis_path).resolve(),Path(dump_path).resolve()
    analysis=json.loads(analysis_path.read_text())
    require(analysis['Schema']=='camera720-view-toggle-hold-analysis-v1' and analysis['Target']==TARGET,
            'current view-switch hold extraction required')
    require(not analysis['MissingExactSetup'], 'exact dual-corner setup must be queried before routing')
    require(analysis.get('MissingLaunchCases')==[], 'all actual launch outputs need dual-corner setup/hold')
    for report in analysis['InputReports']:
        require(sha(report['Path'])==report['SHA256'], 'measured report changed')
    require(all(m['ExactSetupSlackNS']>0 for r in analysis['Paths'] for m in r['Margins'].values()),
            'positive exact setup margin required')
    targets=[r['PhysicalRepairCandidate'] for r in analysis['Paths']]
    parsed=routes.inspect(dump_path,targets)
    selections,wire=waypoint.select_waypoints(parsed,targets)
    rows=[{'Net':s['Target']['Net'],'Branch':s['Target']['ToRoutePin'],
           'Pins':'>'.join(s['Selected']['Pins'])+';'} for s in selections]
    command_list=commands.route_commands(rows,targets,parsed['_Occupied'])
    evidence={'Schema':'raw-camera-waypoint-selection-v1','WirePattern':ref(wire),'Selections':selections}
    commands.validate_waypoint_evidence(evidence,rows,targets,parsed)
    return {'Schema':'camera720-view-toggle-hold-route-plan-v1','Target':TARGET,
            'HoldAnalysis':ref(analysis_path),'RouteDump':ref(dump_path),'WirePattern':ref(wire),
            'Selections':selections,'Routes':rows,'Targets':targets,'Commands':command_list,
            'BranchInventory':parsed['BranchInventory'],
            'NonRouteSemanticSHA256':parsed['NonRouteSemanticSHA256'],
            'ExcludedBlockSHA256':parsed['ExcludedBlockSHA256'],
            'InputSHA256':{str(p):sha(p) for p in (SELF,Path(routes.__file__),Path(routes.common.__file__),
                                               Path(waypoint.__file__),Path(commands.__file__))},
            'EDAExecuted':False,'HardwareAccessed':False,'TimingAccepted':False,
            'Limits':'Unused officially connected waypoint experiment; no delay prediction. Fresh route comparison, functional/placement equivalence and full dual-corner STA required.'}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--report',type=Path)
    p.add_argument('--extra-report',type=Path,action='append',default=[])
    p.add_argument('--output-dir',type=Path)
    p.add_argument('--analysis',type=Path)
    p.add_argument('--route-dump',type=Path)
    p.add_argument('--route-plan',type=Path)
    a=p.parse_args()
    if a.analysis:
        require(a.route_dump and a.route_plan and not a.route_plan.exists(), 'fresh route-plan output required')
        plan=derive_waypoints(a.analysis,a.route_dump)
        write(a.route_plan,plan)
        print(json.dumps({'PreparedOnly':True,'RoutePlan':str(a.route_plan),'Routes':plan['Routes']}))
        return 0
    require(a.report and a.output_dir and not a.output_dir.exists(), 'fresh hold-analysis directory required')
    result,excerpts,body=extract(a.report,a.extra_report)
    a.output_dir.mkdir(parents=True)
    write(a.output_dir/'hold-analysis.json',result)
    (a.output_dir/'query.tcl').write_text(body,encoding='ascii',newline='\n')
    for name,text in excerpts.items():
        (a.output_dir/name).write_text(text,encoding='utf-8',newline='\n')
    print(json.dumps({'HoldFailures':result['HoldFailingPathCount'],'MissingExactSetup':result['MissingExactSetup'],
                     'Query':str(a.output_dir/'query.tcl')}))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
