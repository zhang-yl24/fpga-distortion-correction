"""Supplement frozen camera CDC structure with exact native interstage/Gray paths.

Read-only CPU audit; writes fresh evidence only. No PDS or hardware action.
"""
import argparse
from collections import Counter
import copy
from datetime import datetime, timezone
import hashlib
import itertools
import json
from pathlib import Path
import re

import audit_camera_vga_cdc as structure
import audit_camera_vga_hold as path_syntax

require,sha=structure.require,structure.sha
NUM=r'[-+]?\d+(?:\.\d+)?'


def blocks(path):
    block=[];start=0
    def needs_slack(value):
        return any(x.startswith(' Data arrival time') for x in value) and not any(
            re.match(r'^Path Class\s*:\s*combinational timing path\s*$',x) for x in value)
    with Path(path).open(encoding='gb18030',errors='strict') as stream:
        for number,line in enumerate(stream,1):
            if line.startswith('Startpoint'):
                require(not block or not needs_slack(block),'unfinished native path')
                block=[line];start=number
            elif block:
                block.append(line)
                if line.startswith(' Slack'):
                    yield block,start
                    block=[]
    require(not block or not needs_slack(block),'truncated native path at EOF')


def field(pattern,text,label):
    return structure.one(re.findall(pattern,text,re.M),label)


def normal_record(lines,report,line,query):
    value=path_syntax.parse_path(lines,report,line)
    require(value is not None,'interstage path missing ordinary setup/hold check')
    require((value['Source'],value['Endpoint'])==(query['Source'],query['Endpoint']),'interstage source/target mismatch')
    require(value['PathClass']=='sequential timing path','interstage path is not sequential')
    require(value['LaunchClock']==value['CaptureClock']==query['Clock'],'interstage clock mismatch')
    require(value['LaunchEdge']==value['CaptureEdge']=='rising','interstage edge mismatch')
    require(value['SlackState']=='MET' and value['SlackNS']>=0,'interstage path violates timing')
    require(value['TimingExceptions']==[],'interstage path unexpectedly excepted')
    text=''.join(lines)
    arrival=float(field(r'^ Data arrival time\s+('+NUM+r')\s+Logic Levels:.*$',text,'interstage arrival'))
    elapsed=round(arrival-value['LaunchClockDelayNS'],3)
    require(elapsed>=0,'negative clock-to-stage-input delay')
    value.update(Label=query['Label'],ClockToTargetInputNS=elapsed,
                 SignedLibraryCheckNS=float(field(r'^ '+('Setup' if value['Kind']=='setup' else 'Hold')+r' time\s+('+NUM+r')\s+'+NUM+r'\s*$',text,'library check')))
    value.pop('_Text',None)
    return value


def gray_record(lines,report,line):
    text=''.join(lines)
    source=field(r'^Startpoint\s*:\s*(\S+)\s*$',text,'Gray source')
    endpoint=field(r'^Endpoint\s*:\s*(\S+)\s*$',text,'Gray endpoint')
    corner=field(r'^Path Type\s*:\s*max \((slow|fast) corner\)\s*$',text,'Gray corner')
    bound=float(field(r'^Timing Exception\s*:\s*MaxDelay Path ('+NUM+r')ns -datapath_only\s*$',text,'Gray bound'))
    state,slack=field(r'^ Slack \((MET|VIOLATED)\)\s+('+NUM+r')\s*$',text,'Gray slack')
    require(state=='MET' and float(slack)>=0,'Gray max-delay timing failed')
    return {'Source':source,'Endpoint':endpoint,'Corner':corner,'BoundNS':bound,'SlackNS':float(slack),
            'ArrivalNS':float(field(r'^ Data arrival time\s+('+NUM+r')\s+Logic Levels:.*$',text,'Gray arrival')),
            'Report':str(report),'ReportLine':line,'PathSHA256':hashlib.sha256(text.encode()).hexdigest()}


def coverage(rows,queries):
    actual=Counter((p['Source'],p['Endpoint'],p['Corner'],p['Kind']) for p in rows)
    expected={(q['Source'],q['Endpoint'],corner,kind) for q in queries
              for corner in ('slow','fast') for kind in ('setup','hold')}
    require(set(actual)==expected,'native interstage coverage missing/unexpected: '+str(sorted(expected-set(actual))))
    return [{'Source':q['Source'],'Endpoint':q['Endpoint'],'Label':q['Label'],'Clock':q['Clock'],
             'Corner':corner,'SetupSlackNS':min(p['SlackNS'] for p in rows if
                (p['Source'],p['Endpoint'],p['Corner'],p['Kind'])==(q['Source'],q['Endpoint'],corner,'setup')),
             'HoldSlackNS':min(p['SlackNS'] for p in rows if
                (p['Source'],p['Endpoint'],p['Corner'],p['Kind'])==(q['Source'],q['Endpoint'],corner,'hold')),
             'NativeVariantCount':sum(v for k,v in actual.items() if k[:3]==(q['Source'],q['Endpoint'],corner))}
            for q in queries for corner in ('slow','fast')]


def startup_graph_proof(netlist):
    g=structure.Graph(structure.physical.functional(netlist))
    def lut_for(net):
        name,pin=g.driver(net);cell=g.cells[name]
        require(cell['Primitive']=='V_LUT6CARRY' and pin in ('Z','Z5'),'startup gate not a LUT')
        ports=cell['Ports'];width=5 if pin=='Z5' else 6
        names=sorted({ports['I'+str(i)] for i in range(width)}-{"1'b0","1'b1"})
        init=int(cell['Parameters']['INIT'][4:],16)
        def evaluate(values):
            values={**values,"1'b0":0,"1'b1":1}
            address=sum(values[ports['I'+str(i)]]<<i for i in range(width))
            return (init>>address)&1
        return name,cell,names,evaluate
    clears=[]
    for q,expected in [('ref_reset[1]',{'nt_reset_n','power_ready'}),
                       ('core_reset[1]',{'nt_reset_n','power_ready','pipeline_release'})]:
        ff=g.by_q(q);net=g.ff[ff]['Ports']['SR'];name,cell,names,evaluate=lut_for(net)
        require(set(names)==expected,'startup clear has unexpected fault/other input')
        truth=[]
        for bits in itertools.product((0,1),repeat=len(names)):
            values=dict(zip(names,bits));actual=evaluate(values)
            require(actual==int(not all(values.values())),'startup clear truth differs')
            truth.append({**values,'Clear':actual})
        clears.append({'ResetSecondStage':ff,'ClearNet':net,'Driver':name,'Primitive':cell,
                       'TruthTable':truth,'ContainsRuntimeFaultInput':False})
    sticky=[]
    for q,release in [('power_ready','key_reset_sync[1]'),('pipeline_release','ref_reset[1]')]:
        ff=g.by_q(q);cell=g.ff[ff]
        require(g.clock(cell['Ports']['CK'])['Domain']=='board27' and cell['Ports']['CE']=="1'b1",'sticky startup register clock/enable differs')
        require(cell['Primitive']=='V_FFASYN' and cell['Parameters'].get('INIT')=="1'b0",'startup register reset differs')
        name,lut,names,evaluate=lut_for(cell['Ports']['D'])
        require(q in names and release in names,'startup hold feedback/release missing')
        others=[n for n in names if n not in (q,release)]
        for bits in itertools.product((0,1),repeat=len(others)):
            values={**dict(zip(others,bits)),q:1,release:1}
            require(evaluate(values)==1,'runtime input can clear sticky startup register')
        sticky.append({'Register':ff,'Q':q,'Driver':name,'Primitive':lut,'LocalRelease':release,
                       'HoldOneProvenForAllOtherInputs':True,'ExhaustiveAssignments':2**len(others)})
    return {'GlobalAndPipelineClearTruth':clears,'RegisteredStickyRelease':sticky,
            'Scope':'Actual final primitive LUT truth and registers; not a formal proof of the complete startup timer/protocol.',
            'RuntimeFaultCannotDirectlyReassertCommonClear':True}


def scalar_source_cones(netlist,scalar):
    g=structure.Graph(structure.physical.functional(netlist))
    # The frozen structural clock index only needed GPLL and application FFs.
    # Add actual PHY PLL lock outputs for this supplementary source-cone audit.
    for name,cell in g.cells.items():
        if cell['Primitive']=='V_PPLL' and cell['Ports'].get('LOCK'):
            g.outputs[cell['Ports']['LOCK']].append((name,'LOCK'))
    memo={}
    def walk(net,active=()):
        if net in memo:return memo[net]
        require(net not in active,'combinational input-cone cycle')
        if net in ("1'b0","1'b1"):return []
        drivers=g.outputs.get(net,[])
        if len(drivers)!=1:
            return [{'Kind':'unresolved_or_external','Net':net,'Drivers':drivers}]
        name,pin=drivers[0];cell=g.cells[name];kind=cell['Primitive'];ports=cell['Ports']
        if kind in structure.FF_TYPES:
            result=[{'Kind':'register','Net':net,'Cell':name,'Clock':g.clock(ports['CK'])['Domain']}]
        elif kind in ('V_BUF','V_INV') and pin=='Z':result=walk(ports['I'],active+(net,))
        elif kind=='V_LUT6CARRY' and pin in ('Z','Z5'):
            width=5 if pin=='Z5' else 6;init=int(cell['Parameters']['INIT'][4:],16)
            variables=sorted({ports['I'+str(i)] for i in range(width)}-{"1'b0","1'b1"})
            support=set()
            def evaluate(values):return (init>>sum(values[ports['I'+str(i)]]<<i for i in range(width)))&1
            for bits in itertools.product((0,1),repeat=len(variables)):
                values={**dict(zip(variables,bits)),"1'b0":0,"1'b1":1}
                for variable in variables:
                    changed={**values,variable:1-values[variable]}
                    if evaluate(values)!=evaluate(changed):support.add(variable)
            result=[r for v in sorted(support) for r in walk(v,active+(net,))]
        else:result=[{'Kind':'primitive_or_external','Net':net,'Cell':name,'Pin':pin,'Primitive':kind}]
        memo[net]=list({json.dumps(r,sort_keys=True):r for r in result}.values())
        return memo[net]
    return [{'Label':row['Label'],'First':row['First'],'FirstD':row['FirstPorts']['D'],
             'DestinationClock':row['DestinationClock'],'FunctionalSourceRoots':walk(row['FirstPorts']['D']),
             'Method':'Trace buffers/inverters and actual LUT Boolean support, stop at FF or external/opaque primitive.'}
            for row in scalar]


def audit(receipt_path,structure_path,query_path,output_dir):
    receipt_path,structure_path,query_path,output_dir=map(lambda p:Path(p).resolve(),(receipt_path,structure_path,query_path,output_dir))
    receipt=json.loads(receipt_path.read_text(encoding='utf-8-sig'));stage=receipt_path.parent
    old=json.loads(structure_path.read_text());plan=json.loads(query_path.read_text())
    require(old['Schema']=='camera-vga-cdc-structural-v1' and old['AuditPassed'],'unverified structure')
    require(plan['Schema']=='camera-vga-cdc-query-plan-v1','unexpected query schema')
    require(old['CandidateADFSHA256']==plan['InputADFSHA256']==structure.FINAL_SHA,'candidate mismatch')
    require(all(sha(p)==v for p,v in old['InputSHA256'].items()),'frozen structure dependency drift')
    require(receipt['ExecutionPassed'] and receipt['ExitCode']==0 and receipt['InputDrift']==[] and receipt['Diagnostics']==[],'native execution failed or drifted')
    require(receipt['HardwareAccessed'] is False and receipt['SourceADFSHA256']==receipt['ResultADFSHA256']==structure.FINAL_SHA,'native candidate/hardware scope differs')
    require(sha(stage/'input.adf')==sha(stage/'pre-sta.adf')==structure.FINAL_SHA,'native snapshot/final ADF drift')
    require(receipt.get('PreSTAEqualsResultADF',True) is True,'native snapshot differs')
    reports=[]
    for name,digest in receipt['Artifacts'].items():
        if name.endswith('.rtr'):
            path=stage/Path(name.replace('\\','/'))
            require(sha(path)==digest,'native report artifact drift')
            reports.append(path)
    require(reports,'no native reports')
    reset=old['ResetReleaseStructure']
    original_rows=old['ScalarSynchronizers']+reset['PackedOrSingleSecondStageChains']+[
        c for tree in reset['ReplicatedSecondStageTrees'] for c in tree['Chains']]
    expected_pairs={(q['Source'],q['Endpoint']) for row in original_rows for q in row['NativeQueries']}
    require({(q['Source'],q['Endpoint']) for q in plan['Queries']}==expected_pairs,
            'query plan does not match frozen actual interstage inventory')
    missing={b['NativeEndpoint'] for b in old['GrayBitSynchronizers'] if any(
        group['Group']==b['Group'] and b['NativeEndpoint'] not in {p['Endpoint'] for p in group['Paths']}
        for group in old['GrayPhysicalGroups'])}
    require({q['Endpoint'] for q in plan['GrayCoverageQueries']}==missing,'Gray query plan differs from frozen coverage gap')
    queries={(q['Source'],q['Endpoint']):q for q in plan['Queries']}
    gray_queries={(q['Source'],q['Endpoint']):q for q in plan['GrayCoverageQueries']}
    rows=[];gray=[];seen=set()
    for report in reports:
        for lines,line in blocks(report):
            text=''.join(lines)
            pair=(field(r'^Startpoint\s*:\s*(.+?)\s*$',text,'path source'),
                  field(r'^Endpoint\s*:\s*(.+?)\s*$',text,'path endpoint'))
            if pair in queries and not report.name.endswith('_exception.rtr'):
                value=normal_record(lines,report,line,queries[pair])
                if value['PathSHA256'] not in seen:rows.append(value);seen.add(value['PathSHA256'])
            if pair in gray_queries and 'MaxDelay Path' in text and re.search(r'^Path Type\s*:\s*max ',text,re.M):
                value=gray_record(lines,report,line)
                signature=(value['Source'],value['Endpoint'],value['Corner'],value['ArrivalNS'],value['SlackNS'],value['BoundNS'])
                if signature not in seen:gray.append(value);seen.add(signature)
    bounds=coverage(rows,list(queries.values()))
    expected_gray={(q['Source'],q['Endpoint'],corner) for q in gray_queries.values() for corner in ('slow','fast')}
    require({(p['Source'],p['Endpoint'],p['Corner']) for p in gray}==expected_gray,'missing targeted Gray max-delay coverage')
    complete=copy.deepcopy(old);groups=complete['GrayPhysicalGroups']
    for group in groups:
        bits=[b for b in old['GrayBitSynchronizers'] if b['Group']==group['Group']]
        target={b['NativeEndpoint'] for b in bits}
        records={r['Endpoint']:r for r in group['Paths']}
        for row in gray:
            if row['Corner']!=group['Corner'] or row['Endpoint'] not in target:continue
            require(row['BoundNS']==group['Constraint']['BoundNS'] and 0<=row['ArrivalNS']<group['SourcePeriodNS'],'Gray constraint/source-period bound violated')
            if row['Endpoint'] in records:
                previous=records[row['Endpoint']]
                require(all(previous[k]==row[k] for k in ('Source','Endpoint','Corner','BoundNS','SlackNS','ArrivalNS')),'previous Gray reported value differs')
            else:records[row['Endpoint']]=row
        require(set(records)==target,'final Gray bus coverage incomplete')
        group.update(Paths=[records[k] for k in sorted(records)],CoverageComplete=True,
                     MaximumArrivalNS=max(r['ArrivalNS'] for r in records.values()),
                     ConservativeSkewUpperBoundNS=max(r['ArrivalNS'] for r in records.values()))
    inputs=[receipt_path,structure_path,query_path,stage/'input.adf',stage/'pre-sta.adf',Path(__file__),
            Path(structure.__file__),Path(path_syntax.__file__)]+reports
    watched={str(p):sha(p) for p in inputs}
    tool_hashes={str(p.resolve()):sha(p) for p in (Path(__file__),Path(structure.__file__),
                  Path(path_syntax.__file__),Path(structure.physical.__file__))}
    proof={'Schema':'camera-vga-cdc-native-v1','AuditPassed':True,'CandidateADFSHA256':structure.FINAL_SHA,
           'AuditedUTC':datetime.now(timezone.utc).isoformat(),'InputSHA256':watched,'ToolSHA256':tool_hashes,'InterstageBounds':bounds,
           'InterstagePaths':rows,'SupplementalGrayPaths':gray,
           'Summary':{'ExactInterstagePairs':len(queries),'ExactInterstageCornerKindCases':len(queries)*4,
                      'NativeInterstageVariants':len(rows),'AllInterstageChecksMet':True,'GrayCoverageComplete':True,
                      'MinimumInterstageSetupNS':min(p['SlackNS'] for p in rows if p['Kind']=='setup'),
                      'MinimumInterstageHoldNS':min(p['SlackNS'] for p in rows if p['Kind']=='hold')},
           'Scope':{'AnalogMTBFProven':False,'AllCDCUniversallyProven':False,
                    'DigitalTimingOnly':'All requested ordinary interstage paths and full actual Gray bit coverage; held mailbox protocol is separate evidence.'},
           'HardwareAccessed':False,'EDAExecutedByThisAudit':False,'HardwareReleaseAllowed':False}
    netlist=structure.one([Path(p) for p in old['InputSHA256'] if p.endswith('camera_vga_output_top_sim.v')],'bound final netlist')
    proof['StartupPrimitiveProof']=startup_graph_proof(netlist)
    proof['ScalarFirstStageSourceCones']=scalar_source_cones(netlist,old['ScalarSynchronizers'])
    output_dir.mkdir(parents=True,exist_ok=True)
    proof_path=output_dir/'native-cdc-proof.json'
    with proof_path.open('x',encoding='utf-8') as f:json.dump(proof,f,indent=2);f.write('\n')
    complete['AuditedUTC']=proof['AuditedUTC']
    complete['Scope']['NativeInterstageTimingComplete']=True
    complete['Scope']['GrayDatapathBoundComplete']=True
    complete['Summary']['GrayPhysicalCoverageComplete']=True
    complete['SupplementalNativeProof']={'Path':str(proof_path),'SHA256':sha(proof_path),'Summary':proof['Summary']}
    complete['StartupPrimitiveProof']=proof['StartupPrimitiveProof']
    complete['ScalarFirstStageSourceCones']=proof['ScalarFirstStageSourceCones']
    complete['OriginalStructuralProof']={'Path':str(structure_path),'SHA256':sha(structure_path)}
    complete['InputSHA256'].update(watched)
    complete['ToolSHA256']=tool_hashes
    complete['InputSHA256'][str(proof_path)]=sha(proof_path)
    require(all(sha(p)==v for p,v in watched.items()),'native proof input drift')
    with (output_dir/'cdc-structure.json').open('x',encoding='utf-8') as f:json.dump(complete,f,indent=2);f.write('\n')
    print(json.dumps({'Output':str(output_dir),'AuditPassed':True,**proof['Summary']}))
    return proof


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--receipt',type=Path,required=True)
    p.add_argument('--structure',type=Path,required=True)
    p.add_argument('--query-plan',type=Path,required=True)
    p.add_argument('--output-dir',type=Path,required=True)
    a=p.parse_args();audit(a.receipt,a.structure,a.query_plan,a.output_dir)


if __name__=='__main__':main()
