"""Exact two-counter source range proofs for the RGB888 snapshot candidate.

This is an inductive unsigned interval proof after coordinated reset, not a
simulation of millions of states. All assignment/use sites and actual elaborated
parameters are bound. Original source C diagnostics remain present; timing,
reset/CDC, native graph and hardware release require their own evidence.
"""
import argparse
import json
from pathlib import Path
import re

import hdmi_camera_snapshot_build_b as build

SELF=Path(__file__).resolve()
SCHEMA='hdmi-camera-snapshot-reduction-review-v1'
DRIVER='rtl/experimental/iic_dri_checked.v'
CONTROL='rtl/experimental/ms72xx_rearm_observed_ctl.v'
require,sha,read,ref=build.require,build.sha,build.read,build.ref
PUBLIC={
    'cfg_wait_count':{'Source':build.TOP,'Parameter':'CFG_SETTLE_CYCLES','Value':2700000,
        'Maximum':2699999,'Old':32,'New':22,'TokenCount':5,'Assignments':['0',"cfg_wait_count+1'b1"],
        'Uses':['reg[31:0]cfg_wait_count=0;',
            'if(!global_reset_n)begincfg_wait_count<=0;cfg_ready<=0;end',
            "if(cfg_wait_count<CFG_SETTLE_CYCLES-1)cfg_wait_count<=cfg_wait_count+1'b1;"],
        'Guard':"elseif(!cfg_ready)beginif(cfg_wait_count<CFG_SETTLE_CYCLES-1)cfg_wait_count<=cfg_wait_count+1'b1;elsecfg_ready<=1;end"},
    'watchdog':{'Source':DRIVER,'Parameter':'TIMEOUT_CYCLES','Value':100000,
        'Maximum':99999,'Old':32,'New':17,'TokenCount':6,'Assignments':['0','0','watchdog+1'],
        'Uses':['reg[31:0]divider,watchdog,complete_count;',
            'scl_low<=0;sda_low<=0;divider<=0;watchdog<=0;complete_count<=0;',
            'busy<=0;divider<=0;watchdog<=0;scl_low<=0;sda_low<=0;',
            'endelseif(watchdog>=TIMEOUT_CYCLES-1)begin','watchdog<=watchdog+1;'],
        'Guard':"endelseif(watchdog>=TIMEOUT_CYCLES-1)beginscl_low<=0;sda_low<=0;busy<=0;transaction_failed<=1;error_code<=4'hf;state<=IDLE;endelsebeginwatchdog<=watchdog+1;"}}


def uncomment(text):return re.sub(r'/\*.*?\*/|//[^\r\n]*',lambda m:'\n'*m[0].count('\n'),text,flags=re.S)
def compact(text):return re.sub(r'\s+','',uncomment(text))


def counter_contract(source,name):
    spec=PUBLIC[name];text=uncomment(source);flat=compact(source)
    uses=[{'Line':i,'Text':line.strip()} for i,line in enumerate(text.splitlines(),1) if re.search(r'\b'+name+r'\b',line)]
    require([re.sub(r'\s+','',r['Text']) for r in uses]==spec['Uses'],'additional/different direct counter use: '+name)
    require(len(re.findall(r'\b'+name+r'\b',text))==spec['TokenCount'],'counter token count differs: '+name)
    assignments=re.findall(re.escape(name)+r'<=([^;]+);',flat)
    require(assignments==spec['Assignments'] and flat.count(spec['Guard'])==1,'counter guarded next-state differs: '+name)
    if name=='watchdog':
        require(flat.count('if(state==IDLE)beginbusy<=0;divider<=0;watchdog<=0;')==1
            and flat.count('elseif(state==SUCCESS_HOLD)begin')==1,'watchdog reset/hold priority differs')
    return {'AllAssignmentAndUseSites':uses,'AssignmentRHS':assignments,'GuardedIncrementVerified':True,
        'ResetValue':0,'UnlistedCounterUses':False,'ImplicitHoldReviewed':True}


def interval_proof(maximum,old_bits,new_bits):
    require(all(type(n) is int for n in (maximum,old_bits,new_bits)) and 0<new_bits<old_bits<=64
        and 0<=maximum<(1<<new_bits),'reachable terminal must fit both unsigned widths')
    # For every q in [0,M], reset gives 0; hold gives q; and increment is
    # enabled only for q<M, hence q+1<=M<2**new_bits. No arithmetic wraps,
    # both comparisons see equal q, and both widths produce equal successors.
    return {'ReachableMinimum':0,'ReachableMaximum':maximum,'RequiredBits':max(1,maximum.bit_length()),
        'OriginalBits':old_bits,'ReducedBits':new_bits,'ReducedUnsignedMaximum':(1<<new_bits)-1,
        'ResetBaseVerified':True,'HoldPreservesInvariant':True,'GuardedAdvancePreservesInvariant':True,
        'AllReachableComparisonsAndSuccessorsEqual':True,'TerminalSentinelIncluded':True,
        'Method':'Unsigned interval induction: q<M implies q+1<=M<2**reduced_bits; reset=0 and hold=q.',
        'ReachableStatesEnumerated':False,'UnknownUnresetPowerUpStateAccepted':False,'SafetyAccepted':True}


def parameters(text):
    rows={};name=None;values=[]
    for line in text.splitlines()+['']:
        match=re.fullmatch(r'I: Module instance \{([^}]+)\} parameter value:',line)
        if name is not None and (not line.startswith('    ') or match):
            require(name not in rows and values,'duplicate/empty elaborated parameter block')
            require(len(values)==len({v.split(' = ',1)[0] for v in values}),'duplicate elaborated parameter')
            rows[name]=values;name=None;values=[]
        if match:name=match[1]
        elif name is not None:
            require(re.fullmatch(r'    \w+ = .+',line),'unparsed elaborated parameter');values.append(line.strip())
    return rows


def integer_parameters(block):
    result={}
    for row in block:
        m=re.fullmatch(r"(\w+) = (\d+)'b([01]+) \((\d+)'d(\d+)\)",row)
        require(m is not None,'integer parameter encoding differs')
        require(int(m[2])==int(m[4])==len(m[3]) and int(m[3],2)==int(m[5]),'elaborated binary/decimal mismatch')
        result[m[1]]=int(m[5])
    return result


CAPTURE_USES={'native_pixels': ['outputreg[31:0]done_id,source_crc,native_pixels,stored_bytes,', 'native_pixels<PIXELS;', 'done_id<=0;source_crc<=0;native_pixels<=0;stored_bytes<=0;fault_hold<=0;', 'native_pixels<=0;stored_bytes<=0;row_pixels<=0;line_count<=0;', "native_pixels!=PIXELS||stored_bytes!=BYTES)finish_frame(8'h23);", 'if(row_pixels>=NATIVE_WIDTH||line_count>=NATIVE_HEIGHT||native_pixels>=PIXELS)', "elsebeginrow_pixels<=row_pixels+1'b1;native_pixels<=native_pixels+1'b1;end"], 'row_pixels': ['reg[11:0]row_pixels,line_count;', 'fault_hold==0&&row_pixels<NATIVE_WIDTH&&line_count<NATIVE_HEIGHT&&', 'wireproduce=active_pixel&&line_count[0]&&row_pixels[0]&&stored_bytes<BYTES&&!real_vs_rise;', 'if(!row_pixels[0])begin', 'if(line_count[0])top_pair_q<=top_pairs[row_pixels>>1];', 'endelseif(!line_count[0])top_pairs[row_pixels>>1]<=horizontal_sum;', 'settle_count<=0;drain_count<=0;row_pixels<=0;line_count<=0;', 'native_pixels<=0;stored_bytes<=0;row_pixels<=0;line_count<=0;', 'elsebeginstate<=CAPTURE;row_pixels<=0;line_count<=0;end', 'if(de||previous_de||row_pixels!=0||line_count!=NATIVE_HEIGHT||', 'if(row_pixels>=NATIVE_WIDTH||line_count>=NATIVE_HEIGHT||native_pixels>=PIXELS)', "elsebeginrow_pixels<=row_pixels+1'b1;native_pixels<=native_pixels+1'b1;end", "if(row_pixels!=NATIVE_WIDTH)finish_frame(8'h25);", "elsebeginrow_pixels<=0;line_count<=line_count+1'b1;end"]}


def capture_ranges(source):
    text=uncomment(source);flat=compact(source)
    guard=("if(row_pixels>=NATIVE_WIDTH||line_count>=NATIVE_HEIGHT||native_pixels>=PIXELS)"
        "finish_frame(8'h24);elsebeginrow_pixels<=row_pixels+1'b1;native_pixels<=native_pixels+1'b1;end")
    require(flat.count(guard)==1,'snapshot guarded pixel increment changed')
    require(flat.count('localparamintegerPIXELS=NATIVE_WIDTH*NATIVE_HEIGHT,BYTES=WIDTH*HEIGHT;')==1,
        'snapshot geometry terminal definition changed')
    expected={'native_pixels':['0','0',"native_pixels+1'b1"],
        'row_pixels':['0','0','0',"row_pixels+1'b1",'0']}
    rows=[]
    for name,old,new,maximum in (('native_pixels',32,21,1920*1080),('row_pixels',12,11,1920)):
        sites=[{'Line':i,'Text':line.strip()}for i,line in enumerate(text.splitlines(),1)if re.search(r'\b'+name+r'\b',line)]
        require([re.sub(r'\s+','',r['Text'])for r in sites]==CAPTURE_USES[name],
            'additional/different capture counter use: '+name)
        assignments=re.findall(name+r'<=([^;]+);',flat)
        require(assignments==expected[name],'additional/different capture counter assignment: '+name)
        rows.append({'Accumulator':name,'Parameter':'NATIVE_WIDTH*NATIVE_HEIGHT'if name=='native_pixels'else'NATIVE_WIDTH',
            'ActualParameterValue':maximum,'AllAssignmentAndUseSites':sites,'AssignmentRHS':assignments,
            'GuardedIncrementVerified':True,'ResetValue':0,'UnlistedCounterUses':False,
            **interval_proof(maximum,old,new)})
    return rows


def derive(build_plan):
    build_plan=Path(build_plan).absolute();work=build.work_path(build_plan.parent)
    plan=build.validate(build_plan);receipt=build.verify_execution(work/'execution-result.json');watched={}
    require(build.diagnostic_errors(receipt['Diagnostics'],plan)==[],'unknown snapshot source critical diagnostics')
    for key in ('InputSHA256','PreparedSHA256'):
        for name,h in plan[key].items():build.add(watched,name,h)
    source_bindings={}
    for source in (build.TOP,DRIVER,CONTROL,build.CAPTURE):
        rows=[r for r in plan['CompiledInputs'] if r['Source']==source];require(len(rows)==1,'unique compiled source required')
        row=rows[0];original=build.ROOT/source;compiled=work/'compiled'/source
        build.add(watched,original,row['OriginalSHA256']);build.add(watched,compiled,row['CompiledSHA256'])
        source_bindings[source]={'Original':ref(original),'Compiled':ref(compiled),'Changes':row['Changes']}
    compile_path=work/'compile/run.log';build.add(watched,compile_path,receipt['NativeLogSHA256']['compile/run.log'])
    blocks=parameters(compile_path.read_text(encoding='gb18030',errors='strict'))
    wanted={build.TARGET:{'INPUT_TIMING_CONFIGURED':1,'RX_VS_ACTIVE_LEVEL':1,'RX_DE_ACTIVE_LEVEL':1,'CFG_SETTLE_CYCLES':2700000},
        build.TARGET+'/hdmi_configuration':{'CLK_FRE':10000000,'IIC_FREQ':400000,'TIMEOUT_CYCLES':100000},
        build.TARGET+'/capture':{'NATIVE_WIDTH':1920,'NATIVE_HEIGHT':1080,'TIMEOUT_BITS':26},
        build.TARGET+'/hdmi_configuration/driver':{'CLK_FRE':10000000,'IIC_FREQ':400000,'T_WR':1,
            'ADDR_BYTE':2,'LEN_WIDTH':3,'DATA_BYTE':1,'TIMEOUT_CYCLES':100000}}
    require(all(integer_parameters(blocks.get(k,[]))==v for k,v in wanted.items()),'actual counter elaborated parameters differ')
    controller=compact((work/'compiled'/CONTROL).read_text(encoding='utf-8-sig'))
    require(controller.count('parameterintegerTIMEOUT_CYCLES=CLK_FRE/100')==1
        and controller.count('.CLK_FRE(CLK_FRE),.IIC_FREQ(IIC_FREQ),.T_WR(1),.ADDR_BYTE(2),.LEN_WIDTH(3),.DATA_BYTE(1),.TIMEOUT_CYCLES(TIMEOUT_CYCLES)')==1,
        'actual driver timeout forwarding differs')
    proofs=[]
    for name,spec in PUBLIC.items():
        contract=counter_contract((work/'compiled'/spec['Source']).read_text(encoding='utf-8-sig'),name)
        proofs.append({'Accumulator':name,'Source':source_bindings[spec['Source']],
            'Parameter':spec['Parameter'],'ActualParameterValue':spec['Value'],**contract,
            **interval_proof(spec['Maximum'],spec['Old'],spec['New'])})
    capture_path=work/'compiled'/build.CAPTURE
    for proof in capture_ranges(capture_path.read_text(encoding='utf-8-sig')):
        proof['Source']=source_bindings[build.CAPTURE];proofs.append(proof)
    for name,h in receipt['NativeLogSHA256'].items():build.add(watched,work/name,h)
    for path in (SELF,Path(build.__file__),build_plan,work/'execution-result.json'):build.add(watched,path)
    value={'Schema':SCHEMA,'Target':build.TARGET,'BuildPlan':ref(build_plan),'SourceBuildReceipt':ref(work/'execution-result.json'),
        'Passed':True,'SourceDiagnosticReviewPassed':True,'CounterProofs':proofs,'ActualParameters':wanted,
        'SourceDiagnostics':receipt['Diagnostics'],'DiagnosticsPreserved':True,'DiagnosticsCleared':False,
        'TimingAccepted':False,'HardwareReleaseAllowed':False,'ExternalACAccepted':False,'HardwareAccessed':False,
        'InputSHA256':dict(sorted(watched.items()))}
    return value,{Path(p):h for p,h in watched.items()}


def verify(path):
    path=Path(path).absolute();saved=read(path)
    require(saved.get('Schema')==SCHEMA and saved.get('Target')==build.TARGET,'snapshot source reduction review required')
    current,watched=derive(saved['BuildPlan']['Path']);require(current==saved,'snapshot source range proof changed')
    watched[path]=sha(path);return saved,watched


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build-plan',type=Path)
    p.add_argument('--output',type=Path);p.add_argument('--verify',type=Path);a=p.parse_args()
    if a.verify:verify(a.verify);print('{"Verified":true}');return 0
    require(a.build_plan and a.output,'--build-plan and --output required');value,_=derive(a.build_plan);build.write(a.output,value)
    print(json.dumps({'Passed':True,'SourceDiagnosticReviewPassed':True,'Proof':str(a.output)}));return 0


if __name__=='__main__':raise SystemExit(main())
