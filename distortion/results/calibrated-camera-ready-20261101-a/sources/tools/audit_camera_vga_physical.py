"""Compare this camera candidate's exact route repair and scoped reset effects.

CPU-only audit. Original/current native reports, actual functional exports and
the camera-derived reset inventory are the evidence; no historical pin counts.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

import audit_ddr_entry_reset_netlist as dialect
import audit_ddr_final_timing as native
import audit_camera_vga_hold as hold

require = native.require
sha = hold.sha
KEYS = ('Source','Endpoint','LaunchClock','CaptureClock')
EXPECTED_FF_COUNT = 17417
FF = re.compile(r'(?P<attrs>\(\*[^*]*\*\)\s*)?'
    r'(?P<primitive>V_FFASYN|V_FFSYN)\s*/\*\s*(?P<site>\w+)\s*\*/\s*'
    r'(?:#\s*\((?P<parameters>.*?)\)\s*)?'
    r'(?P<name>\\\S+|[A-Za-z_$][\w$]*)\s*\((?P<ports>.*?)\)\s*;', re.S)

def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':')).encode()).hexdigest()

def functional(path):
    text=Path(path).read_text(encoding='utf-8-sig')
    require('2023.2-SP3<build 154097>' in text[:300], 'native export version differs')
    clean=re.sub(r'/\*.*?\*/|//[^\n]*|\(\*.*?\*\)',lambda m:'\n'*m[0].count('\n'),text,flags=re.S)
    require(re.findall(r'(?m)^module\s+(\w+)',clean)==['camera_vga_output_top']
        and len(re.findall(r'(?m)^endmodule\b',clean))==1,'one flat camera module required')
    cells={}
    for m in dialect.CELL.finditer(clean):
        name=m['name'].lstrip('\\')
        require(name not in cells,'duplicate primitive')
        cells[name]={'Primitive':m['primitive'],'Parameters':dialect.bindings(m['parameters']),
                     'Ports':dialect.bindings(m['ports'])}
    require(cells and len(cells)==len(re.findall(r'(?m)^[ \t]*V_\w+\b',clean)), 'incomplete primitive parse')
    placements={}
    for m in FF.finditer(text):
        name=m['name'].lstrip('\\')
        require(name in cells and name not in placements,'unmatched/duplicate FF placement')
        placements[name]={'Site':m['site'],'Attributes':' '.join((m['attrs'] or '').split())}
    ffs={n for n,c in cells.items() if c['Primitive'] in ('V_FFASYN','V_FFSYN')}
    require(ffs and set(placements)==ffs,'every FF must have native location evidence')
    return {'Cells':cells,'ModuleDeclarations':' '.join(dialect.CELL.sub('',clean).split()),'FFPlacement':placements}

def compare_exports(before,after):
    a,b=functional(before),functional(after)
    require(len(a['FFPlacement'])==EXPECTED_FF_COUNT,'baseline camera FF inventory differs')
    for k in a:
        require(a[k]==b[k],'functional/placement changed: '+k)
    return {'FunctionalGraphIdentical':True,'AllFFPlacementsIdentical':True,
            'Cells':len(a['Cells']),'FFCount':len(a['FFPlacement']),
            'PartSHA256':{k:digest(v) for k,v in a.items()}}

def summaries(path):
    with Path(path).open(encoding='utf-8-sig') as stream:
        return native.parse_summaries(stream)

def compare_summaries(before,after,target_pairs,inventory=None):
    require(set(before)==set(after),'summary tables changed')
    reset_counts={}
    if inventory:
        require(inventory['Complete'],'incomplete reset inventory')
        for g in inventory['Groups']:
            require(g['Complete'],'incomplete reset group')
            key=(g['Corner'],g['LaunchClock'],g['CaptureClock'])
            require(key not in reset_counts,'duplicate reset inventory clock pair')
            reset_counts[key]=g['ObservedLogicalChecks']
    changes,totals=[],{}
    for (corner,kind),old in before.items():
        now=after[(corner,kind)]
        cuts={k[1:]:v for k,v in reset_counts.items() if k[0]==corner} if kind in ('recovery','removal') else {}
        require(set(now)==set(old)-set(cuts),'unexpected timed pair added/removed')
        require(set(cuts)<=set(old),'reset inventory pair absent from baseline')
        for p,n in cuts.items():
            require(old[p]['TotalChecks']==n,'removed check count differs from current reset inventory')
        for pair,row in now.items():
            require(row['TotalChecks']==old[pair]['TotalChecks'],'timed check count changed')
            allowed=kind in ('setup','hold') and pair in target_pairs
            require(allowed or row==old[pair],'unrelated timing summary changed: '+str((corner,kind,pair)))
            if allowed:
                require(row['FailingChecks']==0 and row['WorstSlackNS']>=0 and row['TotalNegativeSlackNS']==0,
                        'target pair still fails')
            if row!=old[pair]:
                changes.append({'Corner':corner,'Kind':kind,'Clocks':pair,'Before':old[pair],'After':row})
        totals[corner+'_'+kind]={'WorstSlackNS':min(r['WorstSlackNS'] for r in now.values()),
            'FailingChecks':sum(r['FailingChecks'] for r in now.values()),
            'TimedChecks':sum(r['TotalChecks'] for r in now.values()),'RemovedResetChecks':sum(cuts.values())}
        if inventory or kind!='recovery':
            require(totals[corner+'_'+kind]['FailingChecks']==0,'remaining timing failures')
    return changes,totals

def target_paths(path,targets,require_complete=True):
    rows,block,start=[],[],0
    def finish():
        if not block:return
        body=''.join(block)
        source=re.findall(r'^Startpoint\s*:\s*(.+?)\s*$',body,re.M)
        endpoint=re.findall(r'^Endpoint\s*:\s*(.+?)\s*$',body,re.M)
        if len(source)==len(endpoint)==1 and (source[0],endpoint[0]) in targets:
            record=hold.parse_path(block,str(path),start)
            if record:
                record.pop('_Text',None); rows.append(record)
    with Path(path).open(encoding='utf-8-sig') as stream:
        for n,line in enumerate(stream,1):
            if line.startswith('Startpoint'):
                if block:
                    require('Path Class  : combinational timing path' in ''.join(block)
                        and not re.search(r'^ (?:Setup|Hold) time', ''.join(block), re.M),
                        'truncated timed record')
                block=[line];start=n
            elif block:
                block.append(line)
                if line.startswith(' Slack'):
                    finish();block=[]
    if block:
        require('Path Class  : combinational timing path' in ''.join(block)
            and not re.search(r'^ (?:Setup|Hold) time', ''.join(block), re.M),'truncated EOF record')
    if require_complete:
        for pair in targets:
            found={(r['Corner'],r['Kind']) for r in rows if (r['Source'],r['Endpoint'])==pair}
            require(found=={(c,k) for c in ('slow','fast') for k in ('setup','hold')},'exact target setup/hold missing')
    return rows

def combined_target_paths(paths,targets):
    rows=[r for path in paths for r in target_paths(path,targets,False)]
    for pair in targets:
        found={(r['Corner'],r['Kind']) for r in rows if (r['Source'],r['Endpoint'])==pair}
        require(found=={(c,k) for c in ('slow','fast') for k in ('setup','hold')},
                'exact target setup/hold missing: '+str(pair))
    return rows

def compare_target_identities(before,after):
    """Routing may change delays, never the timed clock/edge/exception identity."""
    def identities(rows):
        return {tuple(p[k] for k in (*KEYS,'LaunchEdge','CaptureEdge','Corner','Kind','PathClass'))
                +(tuple(p['TimingExceptions']),) for p in rows}
    require(identities(before)==identities(after),'target clock/edge/check/exception identity changed')

def target_exception_identity(block):
    text=''.join(block)
    p=native.path_record(block)
    value={k:p[k] for k in (*KEYS,'LaunchEdge','CaptureEdge','Corner','PathClass')}
    types=re.findall(r'^Path Type\s*:\s*(max|min) \((slow|fast) corner\)\s*$',text,re.M)
    require(len(types)==1,'target exception min/max type ambiguous')
    value['PathType']=types[0][0]
    value['TimingExceptions']=re.findall(r'^Timing Exception\s*:\s*(.+?)\s*$',text,re.M)
    require(len(value['TimingExceptions'])==1,'target exception constraint identity ambiguous')
    transitions=re.findall(r'^ \S+\s+tco\s+'+native.NUM+r'\s+'+native.NUM+r'\s+([rf])\s+',text,re.M)
    require(len(transitions)==1,'target exception source transition ambiguous')
    value['SourceTransition']=transitions[0]
    return value

def exceptions(path,targets):
    sections,pending,section,block={},None,None,[]
    def finish():
        if not block or section is None or section[1].startswith('set_false_path('):return
        text=''.join(block)
        source=re.findall(r'^Startpoint\s*:\s*(.+?)\s*$',text,re.M)
        endpoint=re.findall(r'^Endpoint\s*:\s*(.+?)\s*$',text,re.M)
        require(len(source)==len(endpoint)==1,'exception endpoint ambiguous')
        if (source[0],endpoint[0]) in targets:
            value=target_exception_identity(block)
            sections[section].append(('repaired-target',digest(value)))
        else:
            body=[]
            for line in block:
                if line.strip() and not set(line.strip())<=set('=-*'):body.append(native.normalize(line))
                if line.startswith(' Slack'):break
            sections[section].append(('unchanged-path',digest(body)))
    with Path(path).open(encoding='gb18030',errors='strict') as stream:
        for line in stream:
            header=native.EX_HEADER.fullmatch(line.rstrip('\r\n'))
            if header:
                finish();block=[];section=None;pending=header[1];continue
            corner=re.fullmatch(r'\| (Slow|Fast) Corner\s*',line)
            if pending is not None and corner:
                section=(corner[1].lower(),pending)
                require(section not in sections,'duplicate exception section')
                sections[section]=[];pending=None;continue
            if line.startswith('Startpoint'):finish();block=[line]
            elif block:block.append(line)
    finish()
    require(len(sections)==24,'all native exception sections required')
    return {str(k):{'Count':len(v),'SHA256':digest(sorted(v))} for k,v in sections.items() if not k[1].startswith('set_false_path(')}

def audit(args):
    paths=[Path(getattr(args,k)) for k in ('baseline_report','candidate_report','baseline_exceptions',
           'candidate_exceptions','baseline_netlist','candidate_netlist','hold_analysis','candidate_adf','snapshot')]
    if args.reset_inventory:paths.append(Path(args.reset_inventory))
    paths+=args.baseline_target_report+args.candidate_target_report
    watched={str(p.resolve()):sha(p) for p in paths}
    require(sha(args.candidate_adf)==sha(args.snapshot),'ADF changed across STA')
    analysis=json.loads(Path(args.hold_analysis).read_text())
    require(analysis['HoldFailingPathCount']==3,'expected camera three-path evidence')
    targets={(p['Source'],p['Endpoint']) for p in analysis['Paths']}
    pairs={(p['LaunchClock'],p['CaptureClock']) for p in analysis['Paths']}
    inventory=json.loads(Path(args.reset_inventory).read_text()) if args.reset_inventory else None
    a,ac=summaries(args.baseline_report);b,bc=summaries(args.candidate_report)
    require(ac==bc,'clock definitions/loads changed')
    changes,totals=compare_summaries(a,b,pairs,inventory)
    old=combined_target_paths([args.baseline_report]+args.baseline_target_report,targets)
    new=combined_target_paths([args.candidate_report]+args.candidate_target_report,targets)
    compare_target_identities(old,new)
    require(all(p['SlackNS']>=0 for p in new),'target setup/hold failure')
    for p in analysis['Paths']:
        pair=(p['Source'],p['Endpoint']);net=p['PhysicalRepairCandidate']
        for row in old+new:
            if (row['Source'],row['Endpoint'])==pair:
                end=row['DataTrace'][-2]
                require((end['Name'],end['FromRoutePin'],end['ToRoutePin'])==
                    (net['Net'],net['FromRoutePin'],net['ToRoutePin']),'target net/pins changed')
    for path,baseline in ((args.baseline_exceptions,True),(args.candidate_exceptions,False)):
        with Path(path).open(encoding='gb18030') as stream:sections=native.parse_false_paths(stream)
        if baseline or not inventory:
            require(all(not rows for rows in sections.values()),'unexpected false paths')
        else:
            expected={c:{tuple(p[k] for k in (*KEYS,'LaunchEdge','CaptureEdge'))
                for check in inventory['Corners'][c]['Checks'] for p in check['NativeVariants']} for c in ('slow','fast')}
            falsecounts=native.validate_exception_sets(sections,expected)
    oe,ne=exceptions(args.baseline_exceptions,targets),exceptions(args.candidate_exceptions,targets)
    require(oe==ne,'other exception paths or target exception identities changed')
    graph=compare_exports(args.baseline_netlist,args.candidate_netlist)
    require(all(sha(p)==h for p,h in watched.items()),'input drift during audit')
    return {'Schema':'camera-vga-physical-comparison-v1','AuditedUTC':datetime.now(timezone.utc).isoformat(),
        'AuditPassed':True,'ResetScoped':bool(inventory),'AllInternalChecksMet':all(v['FailingChecks']==0 for v in totals.values()),
        'ClockDefinitionsAndLoadsUnchanged':True,'NoDataFalsePaths':True,'Changes':changes,'CornerSummaries':totals,
        'TargetBaselinePaths':old,'TargetCandidatePaths':new,'FunctionalComparison':graph,
        'OtherExceptionComparison':oe,'FalsePathCounts':falsecounts if inventory else {},'InputSHA256':watched,
        'ToolSHA256':{str(Path(p).resolve()):sha(p) for p in (__file__,hold.__file__,native.__file__,dialect.__file__)},
        'HardwareAccessed':False,'HardwareReleaseAllowed':False,'ExternalIOAccepted':False,
        'Limits':'Internal STA and functional/FF placement only; full-route/provenance/reset-structure audits remain separate.'}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('baseline-report','candidate-report','baseline-exceptions','candidate-exceptions',
                 'baseline-netlist','candidate-netlist','hold-analysis','candidate-adf','snapshot','output'):
        p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--reset-inventory',type=Path)
    p.add_argument('--baseline-target-report',type=Path,action='append',default=[])
    p.add_argument('--candidate-target-report',type=Path,action='append',default=[])
    args=p.parse_args();result=audit(args)
    with args.output.open('x',encoding='utf-8') as stream:json.dump(result,stream,indent=2);stream.write('\n')
    print(json.dumps({k:result[k] for k in ('AuditPassed','AllInternalChecksMet','CornerSummaries','FunctionalComparison')}))

if __name__=='__main__':main()
