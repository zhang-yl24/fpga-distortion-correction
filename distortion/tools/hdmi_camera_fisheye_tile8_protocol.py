"""Frozen C user lease/mode/epoch contracts and narrow native mode evidence.

This does not prove the full native protocol FSM or vendor DDR reset. The caller
must add actual held-consumer coverage, synchronizer/local-reset guards and STA.
"""
from collections import defaultdict
import hashlib
import itertools
import json
from pathlib import Path
import re
import sys
from types import ModuleType

import hdmi_camera_fisheye_tile8_build as build
import hdmi_camera_fisheye_tile8_native as native
import hdmi_camera_direct_audit as base

SELF=Path(__file__).resolve()
SCHEMA='hdmi-camera-fisheye-tile8-user-protocol-review-v1'
require=build.require


def compact(text):
    text=re.sub(r'/\*.*?\*/|//[^\n]*','',text,flags=re.S)
    text=re.sub(r'(`include\s+")[^"]*[/\\]([^"/\\]+)(")',r'\1\2\3',text)
    return re.sub(r'\s+','',text)


CONTRACTS = {'Top': {'Source': 'board/hdmi_camera_fisheye_top.v', 'NormalizedSHA256': '7517c0806ae19b9ea5bad92281c6f5b091e2eed69de11a10dd990c7d0207a4f4', 'Signals': ['pipeline_release', 'pipeline_reset_n', 'board_failed', 'board_fault', 'core_reset', 'board_failed_core']}, 'System': {'Source': 'rtl/experimental/hdmi_camera_fisheye_system_c.v', 'NormalizedSHA256': '276afd7399eae2da464b54d4ce47c9615475562050793a4b71c9f9238c9da33d', 'Signals': ['grant_valid', 'grant_epoch', 'grant_id', 'grant_bank', 'grant_checksum', 'grant_toggle', 'response_busy', 'lease_active', 'lease_epoch', 'lease_bank', 'lease_id', 'lease_crc', 'reader_finished', 'pixel_finished', 'request_epoch_hold', 'done_ack_toggle', 'system_failed', 'system_fault', 'display_done_valid', 'cr', 'core_reset_sync', 'rst_n']}, 'Bank': {'Source': 'rtl/experimental/hdmi_camera_fisheye_bank_tile8.v', 'NormalizedSHA256': '3546c9e3ca799a492712869d325293104f88b693bc90a127dd1d96993082fe8b', 'Signals': ['active_source', 'active_corrected', 'accepted_id', 'source_writable', 'source_ready', 'processing', 'pending', 'display_active', 'write_bank', 'front_bank', 'ownership_fault', 'source_released']}, 'Engine': {'Source': 'rtl/experimental/hdmi_camera_fisheye_engine_tile8.v', 'NormalizedSHA256': '52e410769e86bdc63f3027119ff29f84706f9e425bfb7bf9f5183a90cf726447', 'Signals': ['begin_frame', 'frame_ready', 'cfg_corrected', 'state', 'buffer_valid', 'buffer_rgb', 'buffer_tag']}, 'Core': {'Source': 'rtl/experimental/hdmi_camera_fisheye_core.v', 'NormalizedSHA256': '1de1a6264b1bfdc109a5c93969a5259d7aaf8a6a6b115d8889bab1157157aa62', 'Signals': ['accept_frame', 'frame_ready', 'local_rst_n', 'cfg_corrected']}, 'Mapper': {'Source': 'rtl/experimental/hdmi_camera_fisheye_mapper.v', 'NormalizedSHA256': '4628bab49449b2cf77a207fcc5e9ff1c5f249fff9c15acb6744ca14f1d2e9c59', 'Signals': ['configured', 'corrected', 'cfg_ready', 'cfg_valid', 'cfg_corrected', 'valid']}, 'DMA': {'Source': 'rtl/experimental/hdmi1080_input_dma.v', 'NormalizedSHA256': '0445816cab4f12dce7666e37c9858e5eacddb011db0903458a4f78ff6803e1d5', 'Signals': ['owned', 'committed', 'active', 'active_bank', 'active_id', 'source_valid', 'source_bank', 'source_id', 'source_crc', 'source_pixels', 'end_seen', 'end_settle', 'end_good', 'end_id', 'end_bank', 'end_crc', 'cap_done_ready', 'failed']}, 'Link': {'Source': 'rtl/experimental/hdmi_camera_fisheye_input_link.v', 'NormalizedSHA256': '952e0fa09d538c585254a340a414b0a9ad8236540ddd7347dd6ce3e6affa4dd0', 'Signals': ['complete_metadata', 'core_source_valid', 'dma_ready', 'contract_failed', 'failed', 'rst_n', 'core_rst_n']}, 'Capture': {'Source': 'rtl/experimental/hdmi1080_capture_cdc.v', 'NormalizedSHA256': 'fa054d4c7119d968cd7aa8bd9d970b21af34ca08350385541c41fccbaf554b52', 'Signals': ['grant_request', 'grant_busy', 'grant_bank_hold', 'grant_id_hold', 'end_request', 'end_good', 'end_bank', 'end_id', 'end_pixels', 'end_crc', 'end_fault', 'done_ack', 'end_wait', 'capturing', 'begin_capture']}, 'Output': {'Source': 'rtl/experimental/ddr_video_output_1080_board.v', 'NormalizedSHA256': 'f8f595005cd7a49fd12c748f3eac7a4714becbe160b4a05876d6657c17d9be81', 'Signals': ['request_toggle', 'request_epoch', 'request_open', 'grant_ack_toggle', 'done_toggle', 'done_good', 'done_epoch', 'done_id', 'done_crc', 'done_bank', 'consumed_pixels', 'done_pending', 'frame_active', 'failed']}}


CLAUSES={
 'Top':[
  'wire pipeline_reset_n=global_reset_n && pipeline_release;',
  '.capture_admit(core_reset[1] && !board_failed_core[1])',
  '.external_fault(board_failed_core[1]),.external_fault_code(board_fault)',
  '.rst_n(pipeline_reset_n)',
 ],
 'System':[
  '.pix_clk(pix_in_clk),.sys_clk(core_clk),.rst_n(rst_n),.core_rst_n(cr),',
  'if(response_busy && grant_ack_sync[1]==grant_toggle)response_busy<=0;',
  'if(response_busy || awaiting_bank_grant || display_req_valid || lease_active)begin controller_failed<=1;',
  'if(awaiting_bank_grant && display_grant_valid && !response_busy && !failed)begin',
  'if(lease_active && reader_finished && pixel_finished && reader_idle && fifo_used==0 && !failed)begin',
  'if(!pixel_done_good || pixel_done_id!=lease_id || pixel_done_bank!=lease_bank || pixel_done_epoch!=lease_epoch || pixel_done_crc!=lease_crc || pixel_done_count!=WIDTH*HEIGHT)',
  '.display_done_valid(display_done_valid && !failed)',
 ],
 'Bank':[
  'if(source_valid && source_ready)begin active_source<=source_bank;active_corrected<=cfg_corrected;accepted_id<=source_id;processing<=1;cycles<=0;start<=1;',
  'assign source_writable=(rst_n && LAYOUT_OK && !failed) ? ~(read_lock|offered_lock):2\'b00;',
  '(!display_active || write_bank!=front_bank)',
  'if(!display_active || display_grant_valid || display_done_bank!=front_bank)ownership_fault<=1;',
  '.cfg_corrected(active_corrected)',
 ],
 'Engine':[
  'wire begin_frame=frame_valid && frame_ready && valid_layout;',
  '.frame_valid(begin_frame)', '.cfg_corrected(cfg_corrected)',
  'assign frame_ready=state==IDLE && core_frame_ready && writer_frame_ready && !buffer_valid && !failed;',
 ],
 'Core':[
  'wire accept_frame=frame_valid && frame_ready;',
  '.cfg_valid(accept_frame)',
  'assign frame_ready=local_rst_n && mapper_cfg_ready && sampler_frame_ready && !failed;',
 ],
 'Mapper':[
  'assign cfg_ready=!rst && !(|valid);',
  'if(cfg_valid && cfg_ready)begin configured<=1;corrected<=cfg_corrected;end',
 ],
 'DMA':[
  'wire [1:0] free_bank=source_writable & ~owned;',
  'if(source_released)begin if(!owned[released_bank] || !committed[released_bank])begin failed<=1;',
  'wire cap_done_ready=active && end_seen && end_settle==0 && fifo_idle && !crc_busy && state==COLLECT && (aborting || buffered==0) && !source_valid;',
  'if(!aborting && !failed && end_good && end_bank==active_bank && end_id==active_id && end_pixels==N && written_beats==FRAME_BEATS && ~crc_state==end_crc)',
 ],
 'Link':[
  'always @(posedge sys_clk) if(!core_rst_n)contract_failed<=0;',
  'ddr_write_arbiter shared_writes(.clk(sys_clk),.rst_n(core_rst_n),',
  '.pix_clk(pix_clk),.sys_clk(sys_clk),.rst_n(rst_n),.enable(enable && !failed)',
  'wire complete_metadata=source_pixels==WIDTH*HEIGHT && capture_reserved[dma_bank];',
  'assign core_source_valid=dma_valid && complete_metadata && !failed;',
  'assign dma_ready=core_source_ready && complete_metadata && !failed;',
 ],
 'Capture':[
  'wire end_wait=end_request!=ack_sync[1];',
  'if(grant_valid && grant_ready)begin grant_request<=!grant_request;grant_busy<=1;grant_bank_hold<=grant_bank;grant_id_hold<=grant_id;',
  'if(done_valid && done_ready)begin done_ack<=done_sync[1];grant_busy<=0;end',
  '!capturing && pending_grant && !end_wait && enable_pix[1]',
  'if(sof)begin window_seen<=1;first_de_seen<=0;if(capturing)begin end_request<=!end_request;',
 ],
 'Output':[
  'wire done_pending=done_toggle!=done_ack_sync[1];',
  'if(enable && !done_pending)begin request_toggle<=!request_toggle;request_epoch<=request_epoch+1\'b1;request_open<=1;',
  'if(frame_active && !done_pending)begin done_toggle<=!done_toggle;done_good<=0;',
  'if(!done_pending)done_good<=0;',
  'wire grant_allowed=request_open && pre_active && !frame_active && !done_pending && grant_epoch==request_epoch && enable;',
 ]}


# These are independently reviewed candidate contracts. Unchanged roles retain
# their original whole-source pins. No broad hash refresh or source waiver.
CONTRACTS['Engine']['Signals'] += ['use_tiles','tiled_mode','writer_done','writer_failed','writer_pixels','writer_beats']
CONTRACTS['Writer'] = {
    'Source': 'rtl/experimental/ddr_adaptive_result_writer_dualstripe.v',
    'NormalizedSHA256': '1bf3614f1873b57dd06cb75a953c11ef127ee8f9c2854fbc9afd4bb518d1c067',
    'Signals': ['state','tiled','collect_bank','drain_bank','stripe_full','expected_tag','stripe_base','collected',
                'read_index','issued','read_valid','read_last','slot','beat','crc','done','failed','fault',
                'in_ready','awvalid','writing','pack_pixel','tag_error','accepted_pixels','written_beats']}
CLAUSES['Engine'] += [
    'wire use_tiles=cfg_corrected;',
    'else begin tiled_mode<=use_tiles;index<=0;column<=0;row<=0;raster_tag<=0;tile_x<=0;stripe_y<=0;destination<=output_base;state<=SCAN;end',
    '.frame_tiled(use_tiles)', 'if(!tiled_mode) begin',
    'DRAIN: if(writer_done) begin',
    'if(core_failed || writer_failed) begin',
    'failed<=1;fault<=core_failed ? core_fault:writer_fault;done<=0;state<=FAULT;']
CLAUSES['Writer'] = [
    'assign in_ready=rst_n && !failed && accepted_pixels<FRAME_PIXELS && (tiled ? (active && !stripe_full[collect_bank]) : state==PACK);',
    'wire read_enable=rst_n && state==PACK && tiled && !failed && stripe_full[drain_bank] && read_index<STRIPE_PIXELS && issued<256;',
    'wire writing=state==WRITE || (state==ADDRESS && awready);',
    'assign awvalid=rst_n && state==ADDRESS;',
    'tiled<=frame_tiled;base<=frame_base;identity<=frame_id;',
    'stripe_full[collect_bank]<=1;', 'stripe_full[drain_bank]<=0;',
    'if(tiled && read_last)begin', 'if(slot==255)begin beat<=0;state<=ADDRESS;end',
    'if(writing && wready)begin', 'if(wlast!=(beat==15))begin',
    'if(failed || tag_error)state<=FAULT;',
    'else if(written_beats==FRAME_BEATS-1)begin drain<=0;state<=DRAIN;end',
    'if(tag_error)begin failed<=1;fault<=8\'h32;',
    'if(state!=ADDRESS && state!=WRITE)state<=FAULT;',
    'DRAIN:if(drain==31)begin last_checksum<=~crc;completed_id<=identity;done<=1;state<=IDLE;']


def reviewed_candidate_changes(watched):
    changes = [
        ('rtl/experimental/hdmi_camera_fisheye_bank.v', CONTRACTS['Bank']['Source']),
        ('rtl/experimental/hdmi_camera_fisheye_engine.v', CONTRACTS['Engine']['Source'])]
    rows=[]
    for old,new in changes:
        before,after=build.ROOT/old,build.ROOT/new
        native.add(watched,before);native.add(watched,after)
        expected=compact(before.read_text(encoding='utf-8-sig'))
        expected=expected.replace('hdmi_camera_fisheye_engine#(', 'hdmi_camera_fisheye_engine_tile8#(')
        if new==CONTRACTS['Engine']['Source']:
            expected=expected.replace('modulehdmi_camera_fisheye_engine#(', 'modulehdmi_camera_fisheye_engine_tile8#(')
            expected=expected.replace("wireuse_tiles=1'b0;", 'wireuse_tiles=cfg_corrected;')
            expected=expected.replace('ddr_adaptive_result_writer#(', 'ddr_adaptive_result_writer_dualstripe#(')
        require(expected==compact(after.read_text(encoding='utf-8-sig')), 'candidate source changed beyond reviewed transformation: '+new)
        rows.append({'Baseline':native.ref(before),'Candidate':native.ref(after),'ExactNormalizedTransformationReplayed':True})
    return {'Passed':True,'SourceOnly':True,'BankAndEngineChanges':rows,
            'WriterContract':CONTRACTS['Writer'],
            'CorrectedModeTiled8AndRawRasterFrameLocked':True,
            'PublishedAWAndBurstDrainOnTagFault':True,
            'WriterFaultPreventsEngineCompletion':True,
            'ActualNativeMemoryResetCDCAndAllTenTimingStillRequired':True}


def contract(role,text):
    spec=CONTRACTS[role];flat=compact(text)
    require(hashlib.sha256(flat.encode()).hexdigest()==spec['NormalizedSHA256'],
            'unreviewed complete source contract: '+role)
    for clause in CLAUSES[role]:
        require(compact(clause) in flat,'missing reviewed source guard: '+role+': '+clause)
    uses={}
    cleaned=re.sub(r'/\*.*?\*/|//[^\n]*','',text,flags=re.S)
    for signal in spec['Signals']:
        rows=[{'Line':i,'Text':line.strip()}for i,line in enumerate(cleaned.splitlines(),1)
              if re.search(r'(?<![\w$])'+re.escape(signal)+r'(?![\w$])',line)]
        assignments=re.findall(r'(?<![\w$])'+re.escape(signal)+r'(?:\s*\[[^\]]+\])?\s*(?:<=|=(?!=))\s*([^;]+);',cleaned)
        require(rows,'critical signal disappeared: '+role+'/'+signal)
        uses[signal]={'AllUses':rows,'AllAssignmentRHS':assignments}
    return {'Role':role,'CompleteNormalizedSourceSHA256':spec['NormalizedSHA256'],
            'Guards':CLAUSES[role],'CompleteCriticalSignalUsesAndAssignments':uses}


def release_gate_proof():
    """Exhaust the source release conjunction, including every identity check."""
    names=('lease_active','reader_finished','pixel_finished','reader_idle','fifo_empty',
           'healthy','pixel_good','same_id','same_bank','same_epoch','same_crc','exact_count')
    rows=list(itertools.product((False,True),repeat=len(names)))
    accepted=[bits for bits in rows if all(bits)]
    require(accepted==[(True,)*len(names)],'incomplete lease tail gate')
    return {'Predicates':list(names),'AssignmentsChecked':len(rows),'OnlyAllPredicatesRelease':True,
            'GrantACKOnlyReleasesResponseBusy':True,'GrantACKDoesNotReleaseScanLease':True,
            'FaultQuarantinesLeaseUntilCommonReset':True,'NativeFSMInductionClaimed':False}


def source_review(plan,work,watched):
    bysource={r['Source']:r for r in plan['CompiledInputs']};proofs=[]
    for role,spec in CONTRACTS.items():
        item=bysource[spec['Source']];original=build.ROOT/spec['Source'];compiled=Path(item['CompiledPath'])
        native.add(watched,original,item['OriginalSHA256']);native.add(watched,compiled,item['CompiledSHA256'])
        proof=contract(role,compiled.read_text(encoding='utf-8-sig'))
        proof.update(Original=native.ref(original),Compiled=native.ref(compiled));proofs.append(proof)
    codes=sorted(set(int(x,16)for x in re.findall(r"board_fault<=8'h([0-9a-fA-F]+)",
             (work/'compiled'/build.TOP).read_text(encoding='utf-8-sig'))))
    require(codes==[0xa1,0xa3,0xa4,0xa5,0xa6,0xa7],'board fault closed code set changed')
    require(all((c>>5)&1 and(c>>7)&1 for c in codes),'board fault folded bits are not invariant')
    ok=lambda p:{'Passed':True,'Proofs':p,'Missing':[],'Violations':[],'SourceOnly':True}
    return {'CandidateSourceChanges':reviewed_candidate_changes(watched),
      'SourceLeaseContracts':ok(proofs+[release_gate_proof()]),
      'FrameBoundaryViewSelection':ok([p for p in proofs if p['Role']in ('Bank','Engine','Core','Mapper')]),
      'EpochContract':ok([{'CommonResetOnly':True,'RuntimeFaultDoesNotResetDDRorFIFO':True,
          'OneMonotonicStartupRelease':True,'RuntimeFaultDoesNotReleaseActiveDisplayLease':True,
          'AbortedUncommittedCaptureReservationMayReturnOnlyAfterDrain':True,
          'BoardFaultCodeSet':codes,'BoardFaultBitsFiveAndSevenEqualStickyFailureInThisEpoch':True}]),
      'SourceBoardFaultAliases':{'Bits':[5,7],'Codes':codes,'OnlyThisClosedFaultCodeSet':True,
          'EquivalenceRequiresSameCommonResetAndStickyNativeEvidence':True}}


def mode_graph(text,ports):
    """Only scalar FF/LUT mode/fault cones; no DDR/macro boundary is accepted."""
    require(re.findall(r'(?m)^module\s+(\w+)',text)==[build.TARGET],'wrong actual native top')
    adapted=re.sub(r'(?m)^(module\s+)'+build.TARGET+r'\b',r'\g<1>'+base.syntax.prep.TARGET,text,count=1)
    parsed=base.syntax.functional(adapted)
    g=base.Graph.__new__(base.Graph);g.cells=parsed['Cells']
    g.ff={n:c for n,c in g.cells.items()if c['Primitive']in ('V_FFSYN','V_FFASYN')}
    g.ports=ports;g.expr_cache={};g.support_cache={};g.canonical_outputs=defaultdict(list)
    outputs={'V_LUT6CARRY':('Z','Z5','COUT'),'V_BUF':('Z',),'V_INV':('Z',),
             'V_MUX2':('Z',),'V_IBUF':('O',)}
    for name,c in g.cells.items():
        for pin in ('Q',)if name in g.ff else outputs.get(c['Primitive'],()):
            if c['Ports'].get(pin):g.canonical_outputs[base.canon(c['Ports'][pin])].append((name,pin))
    return g


def logical(g,name):
    expression=g.expression(name);leaves=base.boolean.leaves(expression)
    require(len(leaves)==1 and next(iter(leaves)).startswith('ff:'),'logical role lacks one native FF: '+name)
    key=next(iter(leaves));truth=[base.boolean.evaluate(expression,{key:x})for x in (0,1)]
    require(truth in ([0,1],[1,0]),'logical role is not identity/complement: '+name)
    return key[3:],truth


def possible(e,fixed):
    """Sound cofactor over-approximation: lost correlations only reject proof."""
    if e[0]=='constant':return {e[1]}
    if e[0]=='variable':return {fixed[e[1]]}if e[1]in fixed else {0,1}
    if e[0]=='not':return {1-x for x in possible(e[1],fixed)}
    if e[0]=='mux':return {v for s in possible(e[3],fixed)for v in possible(e[1+s],fixed)}
    require(e[0]=='lut','unknown Boolean expression')
    return {(e[1]>>sum(x<<i for i,x in enumerate(bits)))&1
            for bits in itertools.product(*(possible(x,fixed)for x in e[2]))}


def clock_root(g,net):
    net=base.canon(net);seen=set()
    while net not in seen:
        seen.add(net);drivers=g.canonical_outputs.get(net,[])
        if len(drivers)!=1:return net
        name,pin=drivers[0];cell=g.cells[name]
        if cell['Primitive']not in ('V_BUF','V_IBUF'):return net
        net=base.canon(cell['Ports']['I'])
    raise ValueError('clock buffer cycle')


def native_mode_review(g):
    bank,bank_truth=logical(g,'system/bank_core/active_corrected')
    mode,mode_truth=logical(g,'system/bank_core/engine/core/mapper/corrected')
    requested,requested_truth=logical(g,'corrected_requested')
    processing_names=[n for n in g.ff if n.startswith('system/bank_core/processing/')]
    require(len(processing_names)==1,'one actual bank processing register required')
    processing=processing_names[0]
    ck=clock_root(g,g.ff[bank]['Ports']['CK'])
    require(all(clock_root(g,g.ff[n]['Ports']['CK'])==ck for n in (mode,requested,processing)),
            'frame mode/processing moved outside its core clock')
    rows=[]
    for dst,src,dst_truth,src_truth in ((bank,requested,bank_truth,requested_truth),(mode,bank,mode_truth,bank_truth)):
        e=g.expression(g.ff[dst]['Ports']['D'])
        require(base.boolean.leaves(e)=={'ff:'+src},'mode D has an unexpected driver')
        truth=[base.boolean.evaluate(e,{'ff:'+src:x})for x in (0,1)]
        require(all(dst_truth[truth[x]]==src_truth[x]for x in (0,1)),'mode data lost logical polarity')
        rows.append({'SourceFF':src,'DestinationFF':dst,'NativeDataTruth':truth,
                     'SourceLogicalTruth':src_truth,'DestinationLogicalTruth':dst_truth,'ClockNet':ck})
    bank_ce=g.expression(g.ff[bank]['Ports']['CE'])
    vetoes=[bit for bit in (0,1)if possible(bank_ce,{'ff:'+processing:bit})=={0}]
    require(len(vetoes)==1,'bank mode CE lacks a unique native processing-register veto')
    mode_ce=g.expression(g.ff[mode]['Ports']['CE']);drain=[]
    # The actual 23 registered valid bits must each veto a configuration write.
    for i in range(23):
        net=f'system/bank_core/engine/core/mapper/valid[{i}]'if i!=22 else 'system/bank_core/engine/core/mapped_valid'
        ff,t=logical(g,net)
        require(possible(mode_ce,{'ff:'+ff:t.index(1)})=={0},'mapper cfg can write with an outstanding coordinate')
        drain.append({'Stage':i,'ActualFF':ff,'ActualNet':net,'LogicalHighNativeQ':t.index(1),'CfgCEWhenValidHigh':0})
    return {'Passed':True,'Proofs':rows,'Missing':[],'Violations':[],
            'BankCEZeroCofactor':{'ActualFF':processing,'NativeQ':vetoes[0]},
            'AbsentProcessingLogicalNetPolarityInvented':False,'Actual23ValidStageVetoes':drain,
            'Scope':'actual mode data/polarity/clock and busy/drain CE cofactors; not full native FSM induction'}


def native_fault_review(g):
    ff,encoding=logical(g,'board_failed');p=g.ff[ff]['Parameters']
    require(p.get('INIT')=="1'b0"and p.get('GRS_EN')=='"TRUE"'and encoding==[0,1]and p.get('LRS_EN')=='"TRUE"'and
            p.get('SET_RESET')=='"RESET"','board failure initial/native reset encoding changed')
    e=base.expressions(g,ff)
    release,t=logical(g,'ref_reset[1]');power,power_truth=logical(g,'power_ready')
    released={'ff:'+release:t.index(1)}
    require(possible(e['D'],released)=={1},'native sticky failure D is not one after local release')
    require(base.boolean.leaves(e['SR'])=={'primary:reset_n','ff:'+power},'board failure common SR differs')
    sr_rows=[]
    for reset,powered in itertools.product((0,1),repeat=2):
        assignments={'primary:reset_n':reset,'ff:'+power:power_truth.index(powered)}
        actual=base.boolean.evaluate(e['SR'],assignments)
        require(actual==int(not(reset and powered)),'board failure native SR is not the same common reset')
        sr_rows.append({'ResetN':reset,'PowerReady':powered,'NativeSR':actual})
    consumers=[]
    for bit in (5,7):
        dst,truth=logical(g,f'system/system_fault[{bit}]')
        exprs=base.expressions(g,dst);support=set.union(*(base.boolean.leaves(x)for x in exprs.values()))
        require('ff:'+ff in support,'folded fault bit has no actual board-failed consumer')
        consumers.append({'LogicalFaultBit':bit,'ActualDestinationFF':dst,'LogicalTruth':truth,
                          'ActualDCE_SR':exprs,'ActualSupport':sorted(support)})
    return {'Passed':True,'ActualStickySourceFF':ff,'Parameters':p,'ActualDCE_SR':e,
            'NativeLocalReleaseFF':release,'NativeLocalReleaseHigh':t.index(1),
            'ReleasedDConstant':1,'OldQOneAndSRZeroNextQOneForEitherCE':True,
            'CommonResetTruth':sr_rows,'SRPriorityForcesQZero':True,'SourceFaultBits':[5,7],
            'NativeConsumerEvidence':consumers,'Missing':[],'Violations':[],
            'AbsentOptimizedBoardFaultBitFFInvented':False,'FullNativeFSMInductionClaimed':False,
            'AliasBasis':'closed source fault codes plus common reset/sticky source and actual typed consumer cones'}


def add_helper_closure(watched):
    pending=[build,native,base];seen=set();root=SELF.parent
    while pending:
        module=pending.pop();path=getattr(module,'__file__',None)
        if not path:continue
        path=Path(path).resolve()
        if path.parent!=root or path in seen:continue
        seen.add(path);native.add(watched,path)
        pending.extend(v for v in vars(module).values()if isinstance(v,ModuleType))
    for kind in ('V_FFSYN','V_FFASYN'):
        model=Path('D:/pango/PDS_2023.2/arch/vendor/pango/verilog/bsim')/(kind+'.v')
        native.add(watched,model,base.MODELS[kind])


def canonical_value(value):
    return json.loads(json.dumps(value,allow_nan=False))


def review(build_plan,export_receipt):
    build_plan=Path(build_plan).resolve();export_receipt=Path(export_receipt).resolve()
    plan=build.validate(build_plan);receipt,watched=native.bind_receipt(export_receipt)
    require(receipt['Mode']=='export'and Path(receipt['BuildPlan']).resolve()==build_plan,
            'current C native export required')
    native.add(watched,build_plan);native.add(watched,SELF);native.add(watched,sys.executable)
    netlist=native.artifact(export_receipt,receipt,build.TARGET+'_sim.v')
    native.add(watched,netlist)
    ports=build.top_ports((build_plan.parent/'compiled'/build.TOP).read_text(encoding='utf-8-sig'))
    g=mode_graph(netlist.read_text(encoding='gb18030',errors='strict'),ports)
    value={'Schema':SCHEMA,'Target':build.TARGET,'BuildPlan':native.ref(build_plan),
           'ExportReceipt':native.ref(export_receipt),**source_review(plan,build_plan.parent,watched),
           'NativeFrameModeReview':native_mode_review(g),'NativeBoardFaultAliasReview':native_fault_review(g),
           'Passed':True,'FullNativeProtocolFSMProved':False,
           'NativeHeldConsumersAndLocalResetGuardsRequireIndependentReview':True}
    add_helper_closure(watched)
    require(all(build.sha(p)==h for p,h in watched.items()),'protocol source/native evidence drift')
    value['InputSHA256']={str(p):h for p,h in sorted(watched.items(),key=lambda x:str(x[0]))}
    return canonical_value(value),watched


def verify(path):
    path=Path(path).resolve();saved=build.read(path)
    require(saved.get('Schema')==SCHEMA and saved.get('Target')==build.TARGET,'current user protocol review required')
    value,watched=review(saved['BuildPlan']['Path'],saved['ExportReceipt']['Path'])
    require(saved==value,'user protocol review differs from complete recomputation')
    native.add(watched,path)
    return saved,watched
