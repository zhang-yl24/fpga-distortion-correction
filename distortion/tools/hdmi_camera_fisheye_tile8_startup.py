"""C source reset separation: local core release for arbiter/contract only.

Actual C native synchronizers and consumer next-Q cofactors are supplied by
the independent native audit. No B raw-reset/idle invariant, vendor WREADY
phase, warm calibration state or source bytes alone grants native acceptance.
"""
import hashlib
from pathlib import Path
import re
import sys

import hdmi_camera_fisheye_tile8_protocol as protocol

build,native=protocol.build,protocol.native
SELF=Path(__file__).resolve()
SCHEMA='hdmi-camera-fisheye-tile8-startup-source-contract-v1'
require=build.require


def release_source(text,signal,clock,reset):
    flat=protocol.compact(text)
    assignments=[re.sub(r'\s+','',s)for s in re.findall(r'\b'+signal+r'\s*<=\s*([^;]+);',text)]
    require(assignments==['0',"{"+signal+"[0],1'b1}"],'release assignments changed')
    require('always@(posedge'+clock+'ornegedge'+reset+')'in flat and
            'if(!'+reset+')'in flat and signal+'<={'+signal+"[0],1'b1};"in flat,
            'release clock/assertion/shift contract changed')
    return {'Signal':signal,'Clock':clock,'CommonAsyncReset':reset,
            'Assignments':assignments,'Stages':2,'AsynchronousAssertionSynchronousRelease':True}


def source_contracts(plan,work,watched):
    bysource={x['Source']:x for x in plan['CompiledInputs']};proofs=[];texts={}
    for role in ('Top','System','Link'):
        spec=protocol.CONTRACTS[role];item=bysource[spec['Source']]
        original=build.ROOT/spec['Source'];compiled=Path(item['CompiledPath'])
        native.add(watched,original,item['OriginalSHA256']);native.add(watched,compiled,item['CompiledSHA256'])
        texts[role]=compiled.read_text(encoding='utf-8-sig')
        proof=protocol.contract(role,texts[role]);proof.update(Original=native.ref(original),Compiled=native.ref(compiled))
        proofs.append(proof)
    a=release_source(texts['Top'],'core_reset','core_clk','pipeline_reset_n')
    b=release_source(texts['System'],'core_reset_sync','core_clk','rst_n')
    top,system,link=(protocol.compact(texts[k])for k in ('Top','System','Link'))
    clauses={
      'TopSystemCommonReset':'.core_clk(core_clk),.pix_in_clk(pixclk_in),.pix_out_clk(pix_clk),.rst_n(pipeline_reset_n)',
      'SystemLocalRelease':'wire cr=core_reset_sync[1];',
      'LinkLocalAndRawReset':'.pix_clk(pix_in_clk),.sys_clk(core_clk),.rst_n(rst_n),.core_rst_n(cr)',
      'ContractLocalReset':'always @(posedge sys_clk) if(!core_rst_n)contract_failed<=0;',
      'ArbiterLocalReset':'ddr_write_arbiter shared_writes(.clk(sys_clk),.rst_n(core_rst_n)',
      'DMARawReset':'.pix_clk(pix_clk),.sys_clk(sys_clk),.rst_n(rst_n),.enable(enable && !failed)',
    }
    for name,clause in clauses.items():
        target=top if name=='TopSystemCommonReset'else system if name in ('SystemLocalRelease','LinkLocalAndRawReset')else link
        require(protocol.compact(clause)in target,'C reset separation clause differs: '+name)
    require(link.count('always@')==1 and 'always@(posedgesys_clk)'in link and
            'always@(posedgesys_clkornegedgerst_n)'not in link,
            'contract checker still uses raw asynchronous release')
    return {'Passed':True,'Proofs':proofs,'Missing':[],'Violations':[],'SourceOnly':True,
        'ReleaseSources':[a,b],'InstanceBindingClauses':clauses,
        'SharedWritesReset':'system/core_reset_sync[1]',
        'ContractCheckerReset':'system/core_reset_sync[1]',
        'DMAAndCaptureReset':'pipeline_reset_n raw common reset with their own local releases',
        'RuntimeFaultDoesNotCreateLocalReset':True,
        'WREADYNotAssumedConstant':True,'BResetValueIdleInvariantNotUsed':True,
        'ActualNativeTwoStageReleaseAndEveryConsumerCofactorRequired':True}


def review_sources(build_plan):
    build_plan=Path(build_plan).resolve();plan=build.validate(build_plan);watched={}
    native.add(watched,build_plan);native.add(watched,SELF);native.add(watched,protocol.SELF);native.add(watched,sys.executable)
    value={'Schema':SCHEMA,'Target':build.TARGET,'BuildPlan':native.ref(build_plan),'ExportReceipt':None,
        'LocalCoreResetContract':source_contracts(plan,build_plan.parent,watched),
        'Passed':True,'SourceOnly':True,'NativeGuardEvidenceProduced':False,
        'TimingOrHardwareReleaseAuthorized':False}
    protocol.add_helper_closure(watched)
    require(all(build.sha(p)==h for p,h in watched.items()),'C source reset contract drift')
    value['InputSHA256']={str(p):h for p,h in sorted(watched.items(),key=lambda x:str(x[0]))}
    return protocol.canonical_value(value),watched


def review(build_plan,export_receipt):
    value,watched=review_sources(build_plan);export_receipt=Path(export_receipt).resolve()
    receipt,inputs=native.bind_receipt(export_receipt)
    require(receipt['Mode']=='export'and Path(receipt['BuildPlan']).resolve()==Path(build_plan).resolve(),
            'actual same-plan C export required')
    native.merge(watched,inputs);value['ExportReceipt']=native.ref(export_receipt)
    value['InputSHA256']={str(p):h for p,h in sorted(watched.items(),key=lambda x:str(x[0]))}
    return protocol.canonical_value(value),watched


def verify(path):
    path=Path(path).resolve();saved=build.read(path)
    require(saved.get('Schema')==SCHEMA and saved.get('Target')==build.TARGET,'C source reset contract required')
    value,watched=review(saved['BuildPlan']['Path'],saved['ExportReceipt']['Path'])if saved['ExportReceipt']else review_sources(saved['BuildPlan']['Path'])
    require(saved==value,'C source reset contract differs from recomputation')
    native.add(watched,path)
    return saved,watched
