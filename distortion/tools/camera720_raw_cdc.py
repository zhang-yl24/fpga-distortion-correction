"""CPU-only current720 raw IO/CDC proof and bounded native query preparation.

Existing helpers remain immutable. Prefix adaptation uses fresh function globals
owned only by this adapter; the imported module and its constants are untouched.
Every final proof must be rebuilt against exact current export/route receipts.
"""
import argparse
from collections import defaultdict
import copy
import hashlib
import itertools
import json
from pathlib import Path
import re
import types
import sys

import audit_camera_vga_cdc as base
import audit_camera720_monitor as monitor
import audit_raw_camera_delay_io_cdc as raw
import audit_board1080_pin_contract as pins
import audit_camera_vga_io as io
import camera720_native_endpoints as endpoints
import camera720_cdc_clm as clm
import camera720_cdc_sameble as sameble
import camera720_cdc_native as timing
import camera720_raw_derived_inspect as derived
import camera720_raw_reset_inspect as reset_inspect
import camera720_raw_reset_fast_inspect as fast_inspect
import camera720_io_evidence as native_io

SELF=Path(__file__).resolve()
PROJECT=SELF.parents[1]
WORK=PROJECT/'work/camera720-raw'
TARGET='raw_camera_capture_cam2_current720'
SCHEMA='camera720-current-raw-cdc-audit-v1'
PLAN_SCHEMA='camera720-current-raw-cdc-query-plan-v1'
PREFIX='camera/monitor/'
require,sha,canon=base.require,base.sha,base.canon


def scoped_monitor():
    """Clone pure functions into an isolated, explicit current-target namespace."""
    namespace=dict(vars(monitor));namespace['PREFIX']=PREFIX
    for name,value in vars(monitor).items():
        if isinstance(value,types.FunctionType) and value.__module__==monitor.__name__:
            namespace[name]=types.FunctionType(value.__code__,namespace,name,value.__defaults__,value.__closure__)
    return types.SimpleNamespace(**namespace)


def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))
def ref(path):return {'Path':str(Path(path).resolve()),'SHA256':sha(path)}
def bind(watched,path,expected=None):
    path=Path(path).resolve();require(path.is_file(),'missing bound input '+str(path))
    digest=sha(path);require(expected is None or digest==expected,'bound input drift '+str(path))
    require(str(path) not in watched or watched[str(path)]==digest,'inconsistent binding')
    watched[str(path)]=digest;return path


def inspection_binder(module,cache):
    namespace=dict(vars(module));physical=module.physical
    def completed(path,watched):
        key=(physical.__name__,str(Path(path).resolve()),sha(path))
        if key not in cache:
            closure={};value=physical.bind_completed(path,closure);cache[key]=(value,closure)
        value,closure=cache[key]
        for name,digest in closure.items():
            require(sha(name)==digest,'cached physical closure drift');watched[name]=digest
        return copy.deepcopy(value)
    namespace['physical']=types.SimpleNamespace(**{**vars(physical),'bind_completed':completed})
    for name,value in vars(module).items():
        if isinstance(value,types.FunctionType) and value.__module__==module.__name__:
            namespace[name]=types.FunctionType(value.__code__,namespace,name,value.__defaults__,value.__closure__)
    return namespace['bind_receipt']


def bind_native(path,mode,watched,candidate=None,cache=None):
    path=bind(watched,path);value=read(path)
    # Root adapter owns final-reset receipts; the common immutable content
    # checks below are supplemented by the exact receipt producer's binder.
    require(value.get('Target')==TARGET and value.get('Mode')==mode,'native target/mode differs')
    require(value.get('ExecutionPassed') is True and value.get('ExitCode')==0 and value.get('InputDrift')==[]
            and value.get('Diagnostics')==[] and value.get('InputADFUnchanged') is True,'native inspection incomplete')
    require(value.get('HardwareAccessed') is False and value.get('BitstreamRequested') is False,'inspection not read-only')
    actual=sha(bind(watched,value['SourceADF'],value['SourceADFSHA256']))
    require(candidate is None or actual==candidate,'native evidence belongs to another ADF')
    require(sha(bind(watched,path.parent/'input.adf'))==actual,'inspection ADF copy differs')
    for name,digest in value['InputSHA256'].items():bind(watched,name,digest)
    for name,digest in value['Artifacts'].items():bind(watched,path.parent/name,digest)
    bind(watched,value['BuildPlan'],value['BuildPlanSHA256'])
    binder={derived.SCHEMA:derived,reset_inspect.SCHEMA:reset_inspect,fast_inspect.SCHEMA:fast_inspect}
    require(value.get('Schema') in binder,'unrecognized inspection producer')
    producer=binder[value['Schema']]
    check=producer.bind_receipt if producer is fast_inspect else inspection_binder(producer,{} if cache is None else cache)
    checked,closure=check(path)
    require(checked==value,'producer binder result differs')
    for name,digest in closure.items():bind(watched,name,digest)
    return value


def artifact(receipt_path,value,suffix):
    matches=[Path(receipt_path).parent/name for name in value['Artifacts'] if name.endswith(suffix)]
    require(len(matches)==1,'one native artifact required: '+suffix)
    return matches[0]


def functional(text):
    require('2023.2-SP3<build 154097>' in text[:300],'unexpected native version')
    clean=re.sub(r'/\*.*?\*/|//[^\n]*|\(\*.*?\*\)',lambda x:'\n'*x[0].count('\n'),text,flags=re.S)
    require(re.findall(r'(?m)^module\s+(\w+)',clean)==[TARGET] and len(re.findall(r'(?m)^endmodule\b',clean))==1,'wrong native top')
    cells={}
    for match in base.physical.dialect.CELL.finditer(clean):
        n=match['name'].lstrip('\\');require(n not in cells,'duplicate primitive')
        cells[n]={'Primitive':match['primitive'],'Parameters':base.physical.dialect.bindings(match['parameters']),
                  'Ports':base.physical.dialect.bindings(match['ports'])}
    require(len(cells)==len(re.findall(r'(?m)^[ \t]*V_\w+\b',clean)),'incomplete primitive parse')
    placed={m['name'].lstrip('\\'):{'Site':m['site'],'Attributes':' '.join((m['attrs'] or '').split())} for m in base.physical.FF.finditer(text)}
    require(set(placed)=={n for n,c in cells.items() if c['Primitive'] in base.FF_TYPES},'incomplete FF placement')
    return {'Cells':cells,'FFPlacement':placed,'ModuleDeclarations':' '.join(base.physical.dialect.CELL.sub('',clean).split())}


class ExactCone:
    def __init__(self,g):self.g=g;self.cache={}
    def expression(self,net):
        if net in self.cache:return self.cache[net]
        leaves=sorted(monitor.support(self.g,net));require(len(leaves)<=12,'enable equivalence exceeds bounded Boolean cone')
        names=[self.g.ff[name]['Ports']['Q'] if kind=='ff' else name for kind,name in leaves]
        values=[]
        for bits in itertools.product((0,1),repeat=len(names)):
            result=monitor.possible_values(self.g,net,dict(zip(names,bits)))
            require(len(result)==1,'enable truth assignment not deterministic');values.append(next(iter(result)))
        self.cache[net]=(tuple(leaves),tuple(values));return self.cache[net]
    def exact(self,net,values,expected):
        fixed={gnet:values[canon(gnet)] for gnet in self.g.refs if canon(gnet) in values}
        require(monitor.possible_values(self.g,net,fixed)=={expected},'native protocol Boolean relation differs')


def direct_chain(g,second_q,label):
    second=g.by_q(second_q);first,pin=g.driver(g.ff[second]['Ports']['D'])
    require(first in g.ff and pin=='Q','direct first stage missing '+label)
    return g.chain(first,second,label)


def raw_scalars(g):
    specs=['camera_ready_ddr[1]','picture/cap_reset[1]','picture/ack_sync[1]',
           'picture/request_sync[1]','pipeline/bridge/arm_sync[1]','pipeline/bridge/done_sync[1]']
    specs += [p+x+'_sampled' for p in ('camera/initializer/bus/','hdmi/bus/') for x in ('scl','sda')]
    rows=[direct_chain(g,q,q) for q in specs]
    for row in rows:
        leaves=monitor.support(g,g.ff[row['First']]['Ports']['D'])
        row['SourceRegisters']=sorted(name for kind,name in leaves if kind=='ff')
        row['AsynchronousPrimaryInputs']=sorted(name for kind,name in leaves if kind=='primary')
        require(not(row['SourceRegisters'] and row['AsynchronousPrimaryInputs']),'mixed scalar register/primary cone')
    return rows


def raw_held(g):
    # Reuse unchanged raw metadata checks with the accurate native LUT selectors.
    namespace=dict(vars(raw));namespace['BooleanCone']=ExactCone
    fn=types.FunctionType(raw.held_structures.__code__,namespace,'held_structures',raw.held_structures.__defaults__)
    return fn(g)


def reset_chains(g):
    rows,replicas,qualifiers=[],[],[]
    for first in sorted(g.ff):
        if first.startswith('u_ddr3_test_h/') or '/FFAPP' in first or not re.search(r'reset(?:_sync)?\[0\]/',first):continue
        cell=g.ff[first];p=cell['Ports']
        require(g.constant_one(p['D']),'reset first stage must shift one')
        loads=[(n,pin) for n,pin in g.refs[p['Q']] if (n,pin)!=(first,'Q')]
        require(loads and all(n in g.ff and pin=='D' for n,pin in loads),'reset first-stage functional fanout')
        chains=[g.chain(first,n,first,replicated=len(loads)>1) for n,_ in loads]
        if cell['Primitive']=='V_FFSYN':
            require(first.startswith('test_reset_sync[0]/') and len(chains)==1,'unexpected synchronous reset qualifier')
            qualifiers+=chains;continue
        require(cell['Primitive']=='V_FFASYN' and cell['Parameters'].get('INIT')=="1'b0" and cell['Parameters'].get('SET_RESET')=='"RESET"','reset first stage is not async clear')
        if len(chains)==1:rows+=chains
        else:replicas.append({'First':first,'SecondStageCount':len(chains),'Chains':chains,'SeparateReleaseEdgesPossible':True,'FirstStageOnlyFeedsSecondStages':True})
    require(len(rows)+len(replicas)==8 and len(qualifiers)==1,'application reset families differ')
    return {'SingleChains':rows,'ReplicatedTrees':replicas,'SynchronousQualifiers':qualifiers}


def preview_memory(g):
    cells={n:c for n,c in g.cells.items() if n.startswith('picture/memory_') and c['Primitive']=='V_DRM36K_E1'}
    require(len(cells)==16,'preview must use sixteen independent dual-port RAM slices')
    rows=[];enable_nets=set()
    for name,c in sorted(cells.items()):
        p=c['Ports'];parameters=c['Parameters']
        require(parameters['RAM_MODE']=='"TRUE_DUAL_PORT"' and parameters['DATA_WIDTH_A']==parameters['DATA_WIDTH_B']=='1','preview RAM mode/width differs')
        require(g.clock(p['CLKA'])['Domain']=='camera_pclk' and g.clock(p['CLKB'])['Domain']=='pixel_clk','preview RAM clocks differ')
        for port,bank,address in [('ADDRA','picture/write_bank','picture/write_address'),('ADDRB','picture/read_bank','picture/read_address')]:
            actual=[canon(v.strip()) for v in p[port].strip('{}').split(',')]
            require(actual==["1'b1",bank]+[address+'['+str(i)+']' for i in range(13,-1,-1)],'preview RAM bank address differs')
        require(monitor.possible_values(g,p['WEB'],{})=={0} and g.constant_one(p['CEA']) and g.constant_one(p['CEB']),'preview read port must never write')
        enable_nets.add(p['WEA']);rows.append({'Cell':name,'WriteClock':'camera_pclk','ReadClock':'pixel_clk','WriteBank':'picture/write_bank','ReadBank':'picture/read_bank','ReadPortWritesDisabled':True})
    require(len(enable_nets)==1,'preview RAM slices have different write enables')
    enable=next(iter(enable_nets));cone=ExactCone(g)
    for condition in ({'picture/writing':0},{'picture/cap_reset[1]':0},{'picture/invalid_frame':1}):cone.exact(enable,condition,0)
    return {'Rows':rows,'NativeDualPortSlices':16,'NativeBankAddressBitsVerified':True,'WriteDisabledWhenNotWritingReadyOrInvalid':True,
      'SteadyEpochOwnership':'Source writes opposite held/read bank only after synchronized acknowledgement; whole-frame publish freezes writing. Read bank updates with ack at display boundary.',
      'ArbitraryResetEpochCollisionFreedomProven':False,'PreviewNotRawPayload':True}


def protocol_review(watched,g):
    paths={'Monitor':PROJECT/'rtl/experimental/dvp_mode_admission_monitor.v',
           'Preview':PROJECT/'rtl/experimental/camera720_raw_preview.v',
           'Bridge':PROJECT/'rtl/camera_live_bridge.v','Capture':PROJECT/'rtl/raw_camera_capture.v',
           'Warmup':PROJECT/'rtl/experimental/capture_warmup.v','Writer':PROJECT/'rtl/ddr_video_writer.v',
           'Packer':PROJECT/'rtl/rgb565_burst_pack.v',
           'Frontend':PROJECT/'rtl/experimental/ov5640_current720_frontend.v',
           'Top':PROJECT/'board'/f'{TARGET}.v'}
    texts={k:bind(watched,p).read_text(encoding='utf-8-sig') for k,p in paths.items()}
    compact={k:re.sub(r'\s+','',pins.clean_verilog(t)) for k,t in texts.items()}
    required={'Preview':['held_bank<=write_bank;request<=!request;writing<=0;',
      'elseif(request==ack_sync[1])beginwrite_bank<=!held_bank;writing<=1;',
      'if(x==0&&y==0&&request_sync[1]!=acknowledge)beginread_bank<=held_bank;acknowledge<=request_sync[1];',
      'if(!cam_reset_sync[1])begin','if(!pix_reset_sync[1])begin'],
      'Monitor':['wiremonitor_reset_n=rst_n&&enable;','edge_gray<=edge_binary^(edge_binary>>1);',
      'vs_gray<=vs_binary^(vs_binary>>1);href_gray<=href_binary^(href_binary>>1);'],
      'Frontend':['!monitor_failed&&good_frames>=32\'d2;']}
    for group,needles in required.items():
        for needle in needles:require(needle in compact[group],'reviewed protocol changed '+group+':'+needle)
    require(compact['Preview'].count('always@(posedgecam_clkornegedgerst_n)')==2
            and compact['Preview'].count('always@(posedgepix_clkornegedgerst_n)')==1,'preview local resets changed')
    levels=[direct_chain(g,q,q) for q in ('camera_ready_ddr[1]','picture/cap_reset[1]')]
    level_nets={g.ff[r['First']]['Ports']['D'] for r in levels}
    require(len(level_nets)==1,'admission and preview do not sample the same source level')
    source_cone=monitor.support(g,next(iter(level_nets)))
    require(source_cone and all(k=='ff' and g.clock(g.ff[n]['Ports']['CK'])['Domain']=='board27' for k,n in source_cone),'admission level includes asynchronous primary or another clock')
    requirements={'Top':['capture_warmup#(.DELAY_MS(8000))sensor_warmup(',
      '.ready(test_reset_sync[1]&&camera_ready_ddr[1]),.armed(store_arm)',
      '.request_valid(store_arm),.request_ready(raw_ready)',
      'camera720_raw_previewpicture(.cam_clk(cam_pclk),.rst_n(rst_n&&pll_lock),.cam_ready(camera_ready)'],
      'Warmup':['assignarmed=rst_n&&ready&&count==WAIT_CYCLES;',
        "if(!rst_n||!ready)count<=0;elseif(count<WAIT_CYCLES)count<=count+1'b1;"],
      'Capture':['wiretransaction_rst_n=local_rst_n&&transaction_active;',
        'IDLE,COMPLETE:if(request_valid&&request_ready)begin',
        'held_base<=request_base_address;held_frame_id<=request_frame_id;',
        'held_camera_id<=request_camera_id;held_eye<=request_eye;',
        'CAPTURE:if(writer_done)state<=START_EXPORT;','EXPORT:if(exporter_done)begindone<=1;state<=COMPLETE;end'],
      'Bridge':['if(cap_rst_n&&frame_start)started<=1;',
        'if(!frozen&&cap_rst_n&&started&&(frame_invalid||(line_end&&odd)||frame_complete))begin',
        'valid_held<=frame_complete&&!frame_invalid&&!odd;',
        'checksum_held<=~checksum;'],
      'Packer':['wiresize_complete=(row==HEIGHT&&column==0&&lane==0);',
        'frame_complete<=active&&!dropping&&size_complete&&output_free;',
        'if(column!=WIDTH||lane!=0||row>=HEIGHT)begin'],
      'Writer':['fifo_data[257]!=(written_beats==0&&received==0)',
        'fifo_data[256]!=(written_beats+received==FRAME_BEATS-1)',
        'if(!source_valid||source_checksum!=~write_checksum)begin']}
    for group,needles in requirements.items():
        for needle in needles:require(needle in compact[group],'admission/frame-validation source changed '+group+':'+needle)
    require('camera_ready' not in compact['Capture'] and 'cap_reset' not in compact['Capture'],'readiness must not reset accepted raw transaction')
    return {'Sources':{k:ref(p) for k,p in paths.items()},'MonitorRegisteredGrayFormVerified':True,
      'PreviewOwnership':'Completed frame publishes held bank/request and stops writing; next write chooses opposite held bank only after ack_sync; display switches only at x=y=0 and acknowledges synchronized request.',
      'ResetEpoch':'Shared preview rst_n asynchronously clears local release chains; functional state resets synchronously in each local domain before use. Held/request reset to bank1/request0; read/ack reset to bank1/ack0. Camera-ready falling blocks capture independently; no new publication while not ready.',
      'MonitorEpoch':'rst_n && enable clears source/ref state, held data and toggles; each domain waits its local two-stage release. Authorization additionally requires two coherent good frames.',
      'AdmissionPolicy':{'SourceConeRegisters':sorted(n for _,n in source_cone),'SingleSourceClock':'board27',
        'NoAsynchronousPrimaryBypass':True,'BothConsumersSampleSameNet':True,'SourceRegistered':False,'GlitchFreedomProven':False,
        'RawGate':'Two-stage sampled readiness must remain high through 8000ms destination-clock warmup before a new transaction. A sampled low restarts warmup. The source is not claimed continuously high for an exact analog eight seconds.',
        'AcceptedTransactionDrain':'Admission latches base/id/camera/eye. Independent transaction_active owns shared capture/writer/export reset and drains an accepted transaction even if readiness falls.',
        'IndependentPayloadChecks':'Complete boundary,1280x720 line/pixel count,odd-byte rejection,first/last burst markers,written beat count,writer/source CRC then host payload size/CRC.',
        'PreviewOnly':'cap_reset can interrupt or delay preview; its private RAM is not the raw DDR payload.',
        'TimingAssumption':'Final full STA retains the actual 8ns datapath-only constraints from the 37.037ns source domain. Source combinational glitches may delay admission or preview; no multi-bit coherence or instantaneous revocation claim.'},
      'StoppedClockLimitation':'Stopped domain retains state until its reset-release chain or next clock services local reset. No claim of analog MTBF or arbitrary reset pulses shorter than clock requirements.',
      'FullSequentialFormalProof':False,'Scope':'Bounded static complete-source plus native Boolean protocol checks; diagnosis policy retains external AC limits.'}


def relationships(g,watched):
    mon=scoped_monitor();gray=raw.gray_structures(g)+mon.monitor_gray(g)
    scalar=raw_scalars(g)+mon.monitor_scalar(g)
    resets=reset_chains(g)
    held=mon.held_snapshot(g);held['AllFirstConsumers']=mon.held_first_sinks(g,held)
    held['HeldBusEndpointTraversalComplete']=held['AllFirstConsumers']['TraversalCompleteWithinReviewedPrimitiveSet']
    require(all(r['SourceAckResetExpressionIdentical'] for r in held['Rows']),
            'monitor held publication and ack reset differ')
    rawheld=raw_held(g)
    rows={};internal=[]
    def add(source,destination,pin,label,purpose):
        key=source,destination,pin
        sc,dc=(g.clock(g.ff[n]['Ports']['CK'])['Domain'] for n in key[:2])
        row=rows.setdefault(key,{'SourceFF':source,'DestinationFF':destination,'DestinationPin':pin,
             'SourceClock':sc,'DestinationClock':dc,'Labels':[],'Purposes':[],'OriginalEndpoints':[]})
        if label not in row['Labels']:row['Labels'].append(label)
        if purpose not in row['Purposes']:row['Purposes'].append(purpose)
    for row in gray:add(row['Source'],row['First'],'D',row['Label'],'registered Gray to first stage')
    for row in scalar:
        if row['Label'] in ('camera_ready_ddr[1]','picture/cap_reset[1]'):
            row['AsynchronousLevelScope']={'CombinationalSourceConeEnumerated':True,'SourceRegistered':False,
              'SourceGlitchFreedomProven':False,'PerLeafDataCoherenceTimingRequired':False,
              'Scope':'Single qualification level sampled by two stages; complete source cone retained. No coherent multibit claim. Raw frame validity/count/CRC independently checked after diagnostic capture.'}
            continue
        for source in row.get('SourceRegisters',[]):add(source,row['First'],'D',row['Label'],'scalar source to first stage')
    chains=gray+scalar+resets['SingleChains']+resets['SynchronousQualifiers']+[c for t in resets['ReplicatedTrees'] for c in t['Chains']]
    for row in chains:
        if row['SameBLE'] and row['InterstageLogic'] is None:
            internal.append({'SourceFF':row['First'],'DestinationFF':row['Second'],'DestinationPin':'D',
                             'Placement':row['FirstPlacement'],'Label':row['Label']})
        else:add(row['First'],row['Second'],'D',row['Label'],'ordinary synchronizer interstage')
    for row in held['AllFirstConsumers']['Rows']:
        for consumer in row['Consumers']:add(row['Source'],consumer['Cell'],consumer['Pin'],'held_snapshot['+str(row['Bit'])+']','monitor held bus to every first sequential consumer')
    for row in rawheld:add(row['Source'],row['Destination'],'D',row['Label'],'raw/preview held data')
    protocol=protocol_review(watched,g)
    return list(rows.values()),internal,{'Gray':gray,'Scalars':scalar,'Resets':resets,'MonitorHeld':held,'RawHeld':rawheld,'Protocols':protocol,'PreviewMemory':preview_memory(g)}


def make_queries(mappings,constraints):
    maxima,minima=timing.constraint_pairs(constraints);queries={}
    for i,row in enumerate(mappings):
        sc,dc=row['SourceClock'],row['DestinationClock']
        for boundary in row['NativeBoundaries']:
            key=row['SourceNativeClockPin'],row['SourceNativeOutputPin'],boundary['Endpoint']
            q=queries.setdefault(key,{'Source':key[0],'LaunchOutput':key[1],'Endpoint':key[2],'LogicalRelationships':[],'Corners':['slow','fast']})
            q['LogicalRelationships'].append(i)
            if sc==dc:q.update(Clock=sc,CheckKinds=['setup','hold'],HoldAnalysisSuppressed=False,MinDelayNotAccepted=False)
            else:
                require((sc,dc) in maxima and (sc,dc) in minima,'unconstrained crossing '+str((sc,dc)))
                q.update(SourceClock=sc,DestinationClock=dc,CheckKinds=['max-delay'],MaximumNS=maxima[sc,dc]['BoundNS'],
                         SourcePeriodNS=constraints['PeriodsNS'][sc],EffectiveMaximum=maxima[sc,dc],DeclaredMinimum=minima[sc,dc],
                         HoldAnalysisSuppressed=True,MinDelayNotAccepted=True,SuppressionReason=timing.POLICY)
    return [queries[k] for k in sorted(queries)]


def bounded_groups(queries,missing,maximum=256):
    require(type(maximum) is int and 1<=maximum<=256,'bounded physical query size required')
    needed={timing.identity(r) for r in missing};groups=[]
    for q in sorted((q for q in queries if timing.identity(q) in needed),key=lambda q:(timing.domain(q),timing.identity(q))):
        for group in groups:
            if group['Domain']!=list(timing.domain(q)):continue
            sources=dict(group['SourceLaunches']);ends=set(group['Endpoints']);sources[q['Source']]=q['LaunchOutput'];ends.add(q['Endpoint'])
            if q['Source'] in group['SourceLaunches'] and group['SourceLaunches'][q['Source']]!=q['LaunchOutput']:continue
            per_endpoint={(r['Source'],r['LaunchOutput']) for r in group['ExpectedIdentities'] if r['Endpoint']==q['Endpoint']}|{(q['Source'],q['LaunchOutput'])}
            if len(per_endpoint)>2 or len(sources)>128 or len(sources)*len(ends)>8192 or len(group['ExpectedIdentities'])>=maximum:continue
            group['SourceLaunches'],group['Endpoints']=sources,sorted(ends);group['ExpectedIdentities'].append({k:q[k] for k in timing.IDENTITY});break
        else:groups.append({'Domain':list(timing.domain(q)),'SourceLaunches':{q['Source']:q['LaunchOutput']},'Endpoints':[q['Endpoint']],'ExpectedIdentities':[{k:q[k] for k in timing.IDENTITY}]})
    for group in groups:
        sources=sorted(group['SourceLaunches']);outputs=sorted(group['SourceLaunches'].values());ends=group['Endpoints'];actual=sorted(set(sources+outputs+ends))
        pattern='^('+'|'.join(re.escape(v) for v in actual)+')$'
        group.update(Pins=actual,PinPattern=pattern,PinCommand='get_pins -hierarchical -regexp {'+pattern+'}',
          Command='report_path_timing -delay_type min_max -max_path 1000 -nworst 8 -report_exception TRUE -from {'+' '.join(sources)+'} -through {'+' '.join(outputs)+'} -to {'+' '.join(ends)+'}')
    require({timing.identity(r) for g in groups for r in g['ExpectedIdentities']}==needed,'grouping loses identity')
    return groups


def query_bodies(groups,per_body=8):
    require(type(per_body) is int and 1<=per_body<=8,'at most eight timing commands per native context')
    result={}
    for start in range(0,len(groups),per_body):
        body='# Exact current raw720 endpoints; coverage requires actual launch/corner results.\n'+'\n'.join(c for g in groups[start:start+per_body] for c in (g['PinCommand'],g['Command']))+'\n'
        derived.inspect.query_commands(body);result[f'query-{start//per_body:02}.tcl']=body
    return result


def recovery_groups(queries,missing):
    wanted={timing.identity(r) for r in missing if all(k in r for k in timing.IDENTITY)};buckets=defaultdict(list)
    for q in queries:
        if timing.identity(q) in wanted:buckets[(timing.domain(q),q['Source'],q['LaunchOutput'])].append(q)
    groups=[]
    for (domain,source,output),rows in sorted(buckets.items()):
        for start in range(0,len(rows),128):
            selected=sorted(rows,key=timing.identity)[start:start+128];ends=sorted({q['Endpoint'] for q in selected});ps=sorted({source,output,*ends})
            pattern='^('+'|'.join(re.escape(p) for p in ps)+')$'
            groups.append({'Domain':list(domain),'SourceLaunches':{source:output},'Endpoints':ends,
              'ExpectedIdentities':[{k:q[k] for k in timing.IDENTITY} for q in selected],'Pins':ps,'PinPattern':pattern,
              'PinCommand':'get_pins -hierarchical -regexp {'+pattern+'}',
              'Command':'report_path_timing -delay_type min_max -max_path 1000 -nworst 8 -report_exception TRUE -from {'+source+'} -through {'+output+'} -to {'+' '.join(ends)+'}'})
    require({timing.identity(r) for g in groups for r in g['ExpectedIdentities']}==wanted,'single recovery loses identity')
    return groups


def io_structure(export,text,g,watched):
    build=read(export['BuildPlan']);directory=Path(export['BuildPlan']).parent
    paths={'top':PROJECT/'board'/f'{TARGET}.v','fdc':Path(build['Constraints']['FDC']),
      'pcf':directory/'device_map'/f'{TARGET}.pcf','prt':directory/'place_route'/f'{TARGET}_prr_route_optimize.prt',
      'official':PROJECT/'platform/video_base/HDMI_IN_DDR3_HDMI_OUT_top.fdc',
      'cam_reference':PROJECT/'board/raw_camera_capture_cam2_ref.fdc',
      'cam_pins':PROJECT/'board/raw_camera_capture_cam2_ref-pins.json'}
    texts={k:bind(watched,p).read_text(encoding='utf-8-sig') for k,p in paths.items()}
    namespace=dict(vars(raw));namespace['prep']=types.SimpleNamespace(TARGET=TARGET)
    fn=types.FunctionType(raw.pin_audit.__code__,namespace,'pin_audit',raw.pin_audit.__defaults__)
    result=fn(texts['top'],text,texts['fdc'],texts['pcf'],texts['prt'],texts['official'],texts['cam_reference'],json.loads(texts['cam_pins']))
    delays=raw.input_delay_structures(g)
    return result,delays


def watch_tools(watched):
    seen=set();pending=[base,monitor,raw,pins,io,endpoints,clm,sameble,timing,derived,reset_inspect,fast_inspect,native_io]
    while pending:
        module=pending.pop();path=getattr(module,'__file__',None)
        if not path or Path(path).suffix!='.py' or (PROJECT/'tools').resolve() not in Path(path).resolve().parents or path in seen:continue
        seen.add(path);bind(watched,path)
        pending.extend(v for v in vars(module).values() if isinstance(v,types.ModuleType))
    bind(watched,SELF)


def prepare_value(export_receipt,route_receipt,cache=None):
    cache={} if cache is None else cache
    watched={};ex=bind_native(export_receipt,'export',watched,cache=cache);candidate=ex['SourceADFSHA256']
    rr=bind_native(route_receipt,'report',watched,candidate,cache=cache)
    net=artifact(export_receipt,ex,TARGET+'_sim.v');dump=artifact(route_receipt,rr,'route-dump.txt')
    text=net.read_text(encoding='utf-8-sig');g=monitor.Graph(functional(text))
    rows,internal,structure=relationships(g,watched)
    pinmap,delays=io_structure(ex,text,g,watched)
    placements=clm.placed_luts(text,g)
    parents={base.native_parent(r[k]) for r in rows+internal for k in ('SourceFF','DestinationFF')}
    parents|={n.rsplit('/',2)[0] for n in placements}
    route=endpoints.route_objects(dump,parents)
    mapper=clm.Mapper(g,route,placements)
    mapped=[mapper.map(row) for row in rows]
    native_luts=endpoints.native_lut_bindings(g,route,mapped)
    baseline={'Schema':'camera720-native-endpoints-v1','SameBLEInterstageInventory':internal,
              'LogicalRelationships':mapped,'Queries':[],'CandidateADF':{'Path':ex['SourceADF'],'SHA256':candidate},
              'BuildPlanSHA256':ex['BuildPlanSHA256']}
    direct=sameble.derive(g,route,baseline)
    require(not direct['LogicalRelationships'],'unexpected same-BLE routed supplement')
    build=read(ex['BuildPlan']);fdc=bind(watched,build['Constraints']['FDC'],build['Constraints']['SHA256'])
    constraints,_=base.constraint_inventory(fdc)
    queries=make_queries(mapped,constraints)
    full_report=artifact(export_receipt,ex,TARGET+'.rtr')
    initial_records,initial_issues,initial_other=collect(queries,[full_report])
    initial=timing.coverage(queries,initial_records,initial_issues)
    missing=initial['MissingCases']
    groups=bounded_groups(queries,missing)
    bodies=query_bodies(groups)
    bodies['query-io.tcl']=io_queries(ex,text,g,pinmap,export_receipt)
    bind(watched,timing.MANUAL,timing.MANUAL_SHA)
    watch_tools(watched)
    result={'Schema':PLAN_SCHEMA,'Target':TARGET,'FinalCandidateADFSHA256':candidate,'ExportReceipt':ref(export_receipt),
      'RouteReceipt':ref(route_receipt),'BuildPlan':ref(ex['BuildPlan']),'Netlist':ref(net),'RouteDump':ref(dump),
      'Constraints':constraints,'Structure':structure,'LogicalRelationships':mapped,'DirectInternalChains':direct,
      'Pins':pinmap,'InputDelayMapping':delays,'NativeLUTBindings':native_luts,'NativePolicy':timing.policy_reference(),
      'Queries':queries,'QueryGroups':groups,'QueryBodies':bodies,'InputSHA256':watched,'Producer':ref(SELF),
      'ExpectedCases':initial['ExpectedCases'],'NativeQueryCount':len(queries),'Missing':missing,'Violations':initial_issues,
      'InitialCoverage':initial,'InitialRecords':initial_records,'InitialOtherLaunches':initial_other,
      'ScopedDigitalChecksPassed':False,'ExternalACAccepted':False,'AnalogMTBFProven':False,'HardwareReleaseAllowed':False}
    require(all(sha(p)==h for p,h in watched.items()),'inputs changed during CPU preparation')
    return result,watched


def prepare(export_receipt,route_receipt,output_dir):
    value,watched=prepare_value(export_receipt,route_receipt)
    out=Path(output_dir).resolve();require(not out.exists(),'fresh query directory required');out.mkdir(parents=True)
    for name,body in value['QueryBodies'].items():(out/name).write_text(body,encoding='ascii',newline='\n')
    (out/'query-plan.json').write_text(json.dumps(value,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    return value


def io_queries(ex,text,g,pinmap,export_receipt):
    report=artifact(export_receipt,ex,TARGET+'.rtr');records=dvp_records([report])
    pairs=[]
    for port in sorted(native_io.PORTS):
        values=[r for r in records if r['Port']==port and r['DelayType']=='max']
        require(values,'actual DVP setup endpoint absent')
        pairs.append((port,min(values,key=lambda r:r['SlackNS'])['Endpoint']))
    sources=[]
    for port in sorted(native_io.tx.PORTS-{'pix_clk'}):
        buffers=[n for n,c in g.cells.items() if c['Primitive'] in ('V_OBUF','V_OBUFT') and canon(c['Ports'].get('O',''))==port]
        require(len(buffers)==1,'one actual TX output buffer required')
        if g.cells[buffers[0]]['Primitive']=='V_OBUFT':require(g.cells[buffers[0]]['Ports']['T']=="1'b0",'TX tristate must be disabled')
        leaves=monitor.support(g,g.cells[buffers[0]]['Ports']['I'])
        require(leaves and all(kind=='ff' and name.startswith('picture/') for kind,name in leaves),'TX output data origin differs')
        sources += [base.native_parent(name)+'/CLK' for _,name in leaves]
    commands=['show -dev_instance {'+site+'}' for site in sorted({r['Site'] for r in pinmap['PinInventory']})]
    commands += ['report_path_timing -delay_type min_max -max_path 1000 -nworst 8 -report_exception TRUE -from {'+' '.join(p for p,e in pairs)+'} -to {'+' '.join(sorted({e for p,e in pairs}))+'}',
      'report_path_timing -delay_type min_max -max_path 1000 -nworst 8 -report_exception TRUE -from {'+' '.join(sorted(set(sources)))+'} -to {'+' '.join(sorted(native_io.tx.PORTS-{'pix_clk'}))+'}',
      'report_path_timing -delay_type min_max -max_path 100 -nworst 8 -report_exception TRUE -from {clk_27m} -to {pix_clk}']
    body='# Current actual IO sites and conditional DVP/TX details.\n'+'\n'.join(commands)+'\n'
    derived.inspect.query_commands(body);return body


def collect(queries,reports):
    lookup={timing.identity(q):q for q in queries};pairs={(q['Source'],q['Endpoint']) for q in queries}
    rows,violations,other,seen=[],[],defaultdict(int),set()
    for report in sorted(set(map(Path,reports))):
        with report.open(encoding='gb18030') as stream:head=''.join(next(stream,'') for _ in range(18))
        require('2023.2-SP3 <build 154097>' in head and re.search(r'^\| Design\s*:\s*'+re.escape(TARGET)+r'\s*$',head,re.M),'native report target/version differs')
        for lines,line in timing.native.blocks(report):
            text=''.join(lines);source=timing.field(r'^Startpoint\s*:\s*(.+?)\s*$',text,'source')
            endpoint=timing.field(r'^Endpoint\s*:\s*(.+?)\s*$',text,'endpoint')
            if (source,endpoint) not in pairs:continue
            try:
                launch=timing.launch_row(text)['LaunchOutput'];key=(source,launch,endpoint)
                if key not in lookup:other[key]+=1;continue
                value=timing.parse_record(lines,report,line,lookup[key])
            except ValueError as error:
                violations.append({'Source':source,'Endpoint':endpoint,'Report':str(report),'ReportLine':line,'Stage':'native-path-validation','Error':str(error)});continue
            if value['PathSHA256'] not in seen:seen.add(value['PathSHA256']);rows.append(value)
    return rows,violations,[dict(zip(timing.IDENTITY,k),ObservedVariants=v) for k,v in sorted(other.items())]


def query_checks(path,value,queries):
    body=Path(value['QueryBody']).read_text(encoding='ascii');commands=derived.inspect.query_commands(body)
    native_commands=[c for c in commands if c.startswith('report_path_timing ')];issues=[];groups=[]
    known={q[k] for q in queries for k in timing.IDENTITY};previous=None
    for command in commands:
        if command.startswith('get_pins -hierarchical -regexp '):previous=command;continue
        if not command.startswith('report_path_timing '):continue
        sources,destinations=timing.query_filter(command)
        # Separate port-path IO queries are checked by the conditional DVP parser.
        if sources<=native_io.PORTS or destinations<=native_io.tx.PORTS:continue
        require(sources|destinations<=known,'query includes an unbound physical CDC endpoint')
        through=re.findall(r'-through \{([^}]+)\}',command)
        require(len(through)<=1,'ambiguous through filter')
        outputs=set(through[0].split()) if through else set()
        require(outputs<=known,'query has unknown launch output')
        require(previous is not None,'CDC timing query lacks exact pin enumeration')
        pattern=previous.split(' -regexp {',1)[1][:-1]
        require(pattern.startswith('^(') and pattern.endswith(')$'),'pin enumeration must be exact alternatives')
        actual=[re.sub(r'\\(.)',r'\1',s) for s in pattern[2:-2].split('|')]
        require(len(actual)==len(set(actual)) and set(actual)<=known and sources|destinations|outputs<=set(actual),'pin enumeration identity differs')
        group={'PinPattern':pattern,'Pins':actual};groups.append(group);previous=None
    log=(Path(path).parent/'stdout.log').read_text(encoding='gb18030')
    issues+=timing.validate_pin_log(log,groups)
    reports=[]
    for name in value['Artifacts']:
        if not name.endswith('.rtr') or name.endswith('_exception.rtr'):continue
        report=Path(path).parent/name
        if 'report_path_timing' not in name:continue
        with report.open(encoding='gb18030') as stream:head=''.join(next(stream,'') for _ in range(18))
        timing.validate_report_filter(name,head,native_commands)
        index=int(re.search(r'report_path_timing_(\d+)/',name.replace('\\','/'))[1])-1
        expected=re.findall(r'-through \{([^}]+)\}',native_commands[index])
        report_command=re.findall(r'^\| Tcl Command\s*:\s*(.*?)\s*$',head,re.M)[0]
        actual=re.findall(r'-through \{([^}]+)\}',report_command)
        normalize=lambda values:[{s[2:] if s.startswith(('t:','p:')) else s for s in v.split()} for v in values]
        require(normalize(actual)==normalize(expected),'native through filter changed or dropped')
        reports.append(report)
    require(len(reports)==len(native_commands),'targeted native report count differs')
    return reports,issues,log


def dvp_records(reports):
    namespace=dict(vars(native_io));namespace['SINK_PREFIXES']=('picture/receiver/','pipeline/bridge/capture/','camera/monitor/')
    fn=types.FunctionType(native_io.dvp_records.__code__,namespace,'dvp_records',native_io.dvp_records.__defaults__)
    return fn(reports)


def tx_records(report,require_complete=True):
    # Only the reviewed source hierarchy is adapted; every reported path is
    # still parsed from the bound current-target report, without text rewriting.
    records=[]
    def port_blocks():
        # Unconstrained combinational maxima have no Slack row. The frozen
        # sequential parser deliberately yields only checked sequential paths.
        block=[];start=0
        with Path(report).open(encoding='gb18030') as stream:
            for number,line in enumerate(stream,1):
                if line.startswith('Startpoint'):
                    if block:yield block,start
                    block=[line];start=number
                elif block:block.append(line)
        if block:yield block,start
    for lines,line in port_blocks():
        text=''.join(lines);match=re.findall(r'^Endpoint\s*:\s*(\S+) \(port\)\s*$',text,re.M)
        if len(match)!=1 or match[0] not in native_io.tx.PORTS:continue
        port=match[0];field=lambda p:timing.field(p,text,'TX field')
        kind,corner=field(r'^Path Type\s*:\s*(min|max) \((slow|fast) corner\)\s*$')
        # The declared diagnostic contract is pad maxima only. Native minima
        # present in min_max reports are not an external setup/hold acceptance.
        if kind!='max':continue
        require(field(r'^Path Class\s*:\s*(.+?)\s*$')=='combinational timing path','TX expected unconstrained combinational path')
        source=field(r'^Startpoint\s*:\s*(.+?)\s*$');clocks=re.findall(r'^ Clock (\S+) \((rising|falling) edge\)',text,re.M)
        require((source.startswith('picture/') and clocks==[('pixel_clk','rising')]) if port!='pix_clk' else source=='clk_27m (port)' and not clocks,'TX source/clock differs')
        require('video_pll/u_gpll/gpll_inst/CLKOUT0' in text,'TX PLL differs')
        records.append({'Port':port,'Corner':corner,'DelayType':kind,'Source':source,'ReportedPadArrivalNS':float(field(r'^ Data arrival time\s+('+native_io.NUMBER+r')\s+Logic Levels:')),
          'Report':str(report),'ReportLine':line,'PathSHA256':hashlib.sha256(text.encode()).hexdigest()})
    from collections import Counter
    if require_complete:require({(r['Port'],r['Corner'],r['DelayType']) for r in records}=={(p,c,'max') for p in native_io.tx.PORTS for c in ('slow','fast')},'all 56 TX native maximum cases required')
    return records


def physical_model_basis(plan,g,watched):
    documents={timing.MANUAL:timing.MANUAL_SHA,
      Path('D:/pango/PDS_2023.2/doc/Tcl_Command_User_Guide.pdf'):'7be74cf2d0fba752cc7016a47b994d9bfb05805f4c7b19fb4d15266033de9ba4',
      Path('D:/pango/PDS_2023.2/doc/Timing_Analyzer_User_Guide.pdf'):'9d04d214d74f95348ce292b3c244e6ee880dd7095014209db243f8b8c1b2b420'}
    for p,h in documents.items():bind(watched,p,h)
    extract=bind(watched,PROJECT/'work/camera720-clm-timing-manual-evidence.json','1d86f0682e8df259efd30000daf3660c7ccc544b382a3cba4e4fb6d4b1096524')
    require({Path(r['Document']):r['SHA256'] for r in read(extract)}==documents,'vendor extract closure differs')
    represented=set();merged=[]
    for q in plan['Queries']:
        indices=q['LogicalRelationships'];represented.update(indices)
        rows=[plan['LogicalRelationships'][i] for i in indices]
        if len(rows)==1:continue
        cells=[g.ff[r['DestinationFF']] for r in rows]
        require(len({r['DestinationPlacement']['Site'] for r in rows})==1,'merged physical endpoint spans sites')
        require(len({c['Ports']['CK'] for c in cells})==1 and len({c['Primitive'] for c in cells})==1 and all(c['Parameters']==cells[0]['Parameters'] for c in cells),'merged endpoint has heterogeneous clock/FF parameters')
        merged.append({**{k:q[k] for k in timing.IDENTITY},'LogicalRelationships':indices,
          'DestinationFFs':[r['DestinationFF'] for r in rows],'PhysicalSite':rows[0]['DestinationPlacement']['Site'],
          'ActualClockNet':cells[0]['Ports']['CK'],'Primitive':cells[0]['Primitive'],'Parameters':cells[0]['Parameters']})
    require(represented==set(range(len(plan['LogicalRelationships']))),'physical queries omit logical relationships')
    return {'Documents':[ref(p) for p in documents],'Extract':ref(extract),'MergedQueries':merged,
      'MergedQueryCount':len(merged),'AllMergedGroupsHomogeneous':True,'LogicalRelationshipsRetained':len(represented),
      'VendorPhysicalSequentialTimingModelReliedUpon':True,'CompletePhysicalCaseCoverageRequiredSeparately':True,
      'FinalCandidateFullSTARequiredSeparately':True,'PhysicalTimingAggregationProved':False,
      'IndividualFFArcsEnumerated':False,'IndependentWorstOverInternalFFFormulaClaimed':False,
      'DirectInternalChainsScope':'Exact same-BLE Q-to-D chains without external receiving pins rely on the vendor packed sequential model and independent final full STA; no individual internal arc values invented.'}


def gray_bounds(plan,records):
    by_identity=defaultdict(list)
    for row in records:by_identity[timing.identity(row)].append(row)
    query_map={timing.identity(q):q for q in plan['Queries']};groups=defaultdict(list);missing=[]
    for row in plan['Structure']['Gray']:
        groups[row['Group']].append(row)
    result=[]
    for group,bits in sorted(groups.items()):
        indexes={i for i,r in enumerate(plan['LogicalRelationships']) if any(r['SourceFF']==b['Source'] and r['DestinationFF']==b['First'] for b in bits)}
        keys={key for key,q in query_map.items() if indexes.intersection(q['LogicalRelationships'])}
        for corner in ('slow','fast'):
            actual=[r for k in keys for r in by_identity[k] if r['Corner']==corner and r['Kind']=='max-delay']
            if {timing.identity(r) for r in actual}!=keys:missing.append({'Stage':'gray-bound','Group':group,'Corner':corner});continue
            worst=max(r['ArrivalNS'] for r in actual);best=min(r['ArrivalNS'] for r in actual)
            period=plan['Constraints']['PeriodsNS'][bits[0]['SourceClock']]
            require(0<=best<=worst<period,'Gray propagation spread exceeds source period')
            result.append({'Group':group,'Bits':len(bits),'Corner':corner,'MaximumReportedArrivalNS':worst,
              'MinimumOfReportedMaximaNS':best,'ReportedMaximumSpreadNS':worst-best,
              'ConservativeSkewUpperBoundNS':worst,'SourcePeriodNS':period,
              'BoundBasis':'All arrival paths are nonnegative and every launch-qualified maximum is below one source period. Maximum arrival bounds interbit propagation spread; minimum of maxima is not a measured minimum delay.'})
    return result,missing


def held_bounds(plan,records):
    """Bound held-data propagation against the reviewed publication handshake.

    Native coverage remains every first sequential consumer. The latency claim
    applies to released-operation consumption; it does not prove reset epochs.
    """
    groups=defaultdict(set)
    for i,row in enumerate(plan['LogicalRelationships']):
        if 'monitor held bus to every first sequential consumer' in row['Purposes']:
            groups[('monitor_snapshot',row['DestinationClock'])].add(i)
        if 'raw/preview held data' in row['Purposes']:
            groups[('preview_bank' if row['DestinationClock']=='pixel_clk' else 'raw_metadata',row['DestinationClock'])].add(i)
    require(set(groups)=={('monitor_snapshot','board27'),('raw_metadata','ddrphy_sysclk'),('preview_bank','pixel_clk')},
            'held-data scope differs')
    by_identity=defaultdict(list)
    for row in records:by_identity[timing.identity(row)].append(row)
    result=[];missing=[]
    for (group,clock),indices in sorted(groups.items()):
        queries={timing.identity(q):q for q in plan['Queries'] if indices.intersection(q['LogicalRelationships'])}
        require(queries,'held-data has no mapped physical boundaries')
        budget=2*plan['Constraints']['PeriodsNS'][clock]
        for corner in ('slow','fast'):
            actual=[r for key in queries for r in by_identity[key] if r['Corner']==corner and r['Kind']=='max-delay']
            if {timing.identity(r) for r in actual}!=set(queries):
                missing.append({'Stage':'held-data-bound','Group':group,'Corner':corner});continue
            worst=max(r['ArrivalNS'] for r in actual)
            require(0<=worst<budget and all(q['MaximumNS']<=budget for q in queries.values()),
                    'held-data propagation exceeds reviewed consumption latency')
            result.append({'Group':group,'Corner':corner,'LogicalRelationships':len(indices),
              'PhysicalQueries':len(queries),'MaximumReportedArrivalNS':worst,'DestinationClock':clock,
              'MinimumDestinationPeriodsBeforeConsumption':2,'ConsumptionLatencyLowerBoundNS':budget,
              'ReleasedOperationOnly':True,'AllFirstConsumerBoundaryMaximaCovered':True,
              'ArbitraryStoppedClockResetEpochProven':False})
    return result,missing


def audit_value(export_receipt,route_receipt,query_receipts):
    require(isinstance(query_receipts,(list,tuple)) and len(query_receipts)==len(set(map(str,query_receipts))),'query receipt list must be distinct')
    cache={};plan,watched=prepare_value(export_receipt,route_receipt,cache)
    candidate=plan['FinalCandidateADFSHA256'];ex=read(export_receipt)
    main=artifact(export_receipt,ex,TARGET+'.rtr');reports=[main];logs=[];issues=[];refs=[]
    for path in sorted(map(Path,query_receipts)):
        value=bind_native(path,'query',watched,candidate,cache)
        require(value['BuildPlanSHA256']==plan['BuildPlan']['SHA256'],'query build plan differs')
        found,bad,log=query_checks(path,value,plan['Queries']);reports.extend(found);issues.extend(bad);refs.append(ref(path))
        if re.search(r'^Site \S+ \(\d+\) :',log,re.M):logs.append(log)
    records,bad,other=collect(plan['Queries'],reports);issues+=bad
    covered=timing.coverage(plan['Queries'],records,issues);missing=list(covered['MissingCases'])
    gray,gray_missing=gray_bounds(plan,records);missing+=gray_missing
    held,held_missing=held_bounds(plan,records);missing+=held_missing
    monitor_held=plan['Structure']['MonitorHeld']
    monitor_held['HeldBusPhysicalBoundComplete']=not any(r['Group']=='monitor_snapshot' for r in held_missing)
    monitor_held['AllFirstConsumers']['PhysicalBoundComplete']=monitor_held['HeldBusPhysicalBoundComplete']
    monitor_held['Limits']='Released-operation source and native Boolean handshake, complete first-consumer traversal and actual physical max-delay coverage. Final full STA and separate reset-effect gate remain required; no analog metastability or arbitrary stopped-clock reset claim.'
    pinmap=plan['Pins']
    if len(logs)==1:io.apply_native_sites(pinmap,logs[0])
    else:missing.append({'Stage':'native-io-site-inventory','ObservedCompleteSiteLogs':len(logs),'Expected':1})
    electrical=native_io.io_parameters(plan['RouteDump']['Path'],pinmap)
    pinmap['FinalNativeElectricalAttributesVerified']=electrical['Passed']
    dvp=native_io.dvp_summary(dvp_records(reports));missing += [dict(Stage='conditional-dvp',**r) for r in dvp['MissingCases']]
    tx=[r for p in reports for r in tx_records(p,False)];tx_cases={(r['Port'],r['Corner'],r['DelayType']) for r in tx}
    tx_expected={(p,c,'max') for p in native_io.tx.PORTS for c in ('slow','fast')}
    missing += [dict(zip(('Port','Corner','DelayType'),k),Stage='native-tx-maxima') for k in sorted(tx_expected-tx_cases)]
    commands=native_io.tx.commands(bind(watched,PROJECT/'board/ms7210_commands.vh').read_text(),
      bind(watched,PROJECT/'platform/video_base/source/hdmi/ms7210_ctl.v').read_text())
    g=monitor.Graph(functional(Path(plan['Netlist']['Path']).read_text(encoding='utf-8-sig')))
    basis=physical_model_basis(plan,g,watched)
    watch_tools(watched)
    result={**plan,'Schema':SCHEMA,'QueryReceipts':refs,'Records':records,'CaseCoverage':covered['CaseCoverage'],
      'ExpectedCases':covered['ExpectedCases'],'ObservedCases':covered['CoveredCases'],'Missing':missing,'Violations':issues,
      'GrayTimingBounds':gray,'HeldDataTimingBounds':held,'ExcludedOtherLaunches':other,'PhysicalSTABasis':basis,
      'ScopedDigitalChecksPassed':not missing and not issues,'NativeElectricalParameters':electrical,
      'DVP':dvp,'TX':{'Vendor49CommandsIdentical':True,'Commands':commands,'NativeMaximumPaths':tx,
        'NativeMinimumDelaysObtained':False,'RegisterSamplingInterpretationVerified':False},
      'InputSHA256':watched,'ToolSHA256':{p:h for p,h in watched.items() if Path(p).parent==SELF.parent},
      'HardwareAccessed':False,'EDAExecuted':False,'OpticalCorrectionAccepted':False,
      'Limits':'Scoped digital diagnostic capture evidence, vendor physical STA model and final full STA gate. External DVP/TX AC, board voltages, arbitrary stopped-clock resets, analog MTBF and individual internal-FF aggregation remain unproven.'}
    require(all(sha(p)==h for p,h in watched.items()),'audit inputs drifted')
    return result,watched


def verify(proof_path):
    proof_path=Path(proof_path).resolve();saved=read(proof_path)
    require(saved.get('Schema')==SCHEMA and saved.get('Target')==TARGET,'wrong raw CDC proof')
    bound={};bind(bound,proof_path)
    for name,digest in saved['InputSHA256'].items():bind(bound,name,digest)
    for item in [saved['ExportReceipt'],saved['RouteReceipt']]+saved['QueryReceipts']:bind(bound,item['Path'],item['SHA256'])
    actual,watched=audit_value(saved['ExportReceipt']['Path'],saved['RouteReceipt']['Path'],[r['Path'] for r in saved['QueryReceipts']])
    normalize=lambda v:json.loads(json.dumps({k:x for k,x in v.items() if k not in ('CreatedUTC','InputSHA256')}))
    require(normalize(actual)==normalize(saved),'saved raw CDC proof differs from complete recomputation')
    for name,digest in watched.items():bind(bound,name,digest)
    return actual,bound


def audit(export_receipt,route_receipt,query_receipts,output):
    value,_=audit_value(export_receipt,route_receipt,query_receipts)
    payload=json.dumps(value,indent=2,allow_nan=False)+'\n';path=Path(output)
    require(not path.exists(),'fresh proof output required');path.write_text(payload,encoding='utf-8')
    return value


def observe(plan_path,query_receipts):
    """Fast partial CPU observation; never a release proof or graph substitute."""
    plan_path=Path(plan_path).resolve();plan=read(plan_path)
    require(plan.get('Schema')==PLAN_SCHEMA and plan.get('Target')==TARGET,'wrong partial query plan')
    watched={};bind(watched,plan_path)
    for key in ('ExportReceipt','RouteReceipt','Netlist','RouteDump','BuildPlan'):
        item=plan[key];bind(watched,item['Path'],item['SHA256'])
    ex=read(plan['ExportReceipt']['Path']);require(ex['SourceADFSHA256']==plan['FinalCandidateADFSHA256'],'partial plan candidate differs')
    report=artifact(plan['ExportReceipt']['Path'],ex,TARGET+'.rtr');bind(watched,report,ex['Artifacts'][report.relative_to(Path(plan['ExportReceipt']['Path']).parent).as_posix()])
    reports=[report];issues=[];refs=[]
    for path in query_receipts:
        value=bind_native(path,'query',watched,plan['FinalCandidateADFSHA256'])
        new,bad,_=query_checks(path,value,plan['Queries']);reports+=new;issues+=bad;refs.append(ref(path))
    rows,bad,other=collect(plan['Queries'],reports);issues+=bad;coverage=timing.coverage(plan['Queries'],rows,issues)
    return {'Schema':'camera720-raw-partial-cdc-observation-v1','FinalCandidateADFSHA256':plan['FinalCandidateADFSHA256'],
      'Plan':ref(plan_path),'AcceptedReceipts':refs,'Coverage':coverage,'Violations':issues,'Records':rows,
      'ExcludedOtherLaunches':other,'InputSHA256':watched,'HardwareReleaseAllowed':False,'GraphRecomputed':False}


def prepare_recovery(plan_path,observation,output_dir):
    plan=read(plan_path);require(observation['Plan']==ref(plan_path) and observation['FinalCandidateADFSHA256']==plan['FinalCandidateADFSHA256'],'recovery observation plan differs')
    require(not observation['Violations'],'do not recover from timing violations')
    groups=recovery_groups(plan['Queries'],observation['Coverage']['MissingCases']);bodies=query_bodies(groups,per_body=8)
    out=Path(output_dir);require(not out.exists(),'fresh recovery output required');out.mkdir()
    for name,body in bodies.items():(out/name).write_text(body,encoding='ascii',newline='\n')
    value={'Schema':'camera720-raw-cdc-recovery-plan-v1','FinalCandidateADFSHA256':plan['FinalCandidateADFSHA256'],
      'OriginalPlan':ref(plan_path),'AcceptedReceipts':observation['AcceptedReceipts'],'Missing':observation['Coverage']['MissingCases'],
      'Groups':groups,'Bodies':{name:ref(out/name) for name in bodies},'HardwareReleaseAllowed':False}
    (out/'recovery-plan.json').write_text(json.dumps(value,indent=2,allow_nan=False)+'\n',encoding='utf-8');return value


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--export-receipt',type=Path)
    p.add_argument('--route-receipt',type=Path);p.add_argument('--output-dir',type=Path)
    p.add_argument('--query-receipt',type=Path,action='append');p.add_argument('--output',type=Path);p.add_argument('--verify',type=Path)
    a=p.parse_args()
    if a.verify:v,_=verify(a.verify)
    elif a.output:v=audit(a.export_receipt,a.route_receipt,a.query_receipt or [],a.output)
    else:
        require(a.output_dir is not None,'output directory required for preparation')
        v=prepare(a.export_receipt,a.route_receipt,a.output_dir)
    print(json.dumps({k:v[k] for k in ('Schema','FinalCandidateADFSHA256','NativeQueryCount','ExpectedCases','ObservedCases','ScopedDigitalChecksPassed') if k in v}))


if __name__=='__main__':main()
