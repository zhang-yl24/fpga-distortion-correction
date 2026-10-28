"""Offline, conditional clock-action audit; never a complete sensor recipe or driver."""
from pathlib import Path
from fractions import Fraction
import argparse
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
APPROVED = ROOT/'build/offline-20261024'
MASKS = {0x3008:0x40, 0x3034:0x0f, 0x3035:0xff, 0x3036:0xff,
         0x3037:0x1f, 0x3039:0x80, 0x3103:0x02, 0x3108:0x3f}
PLL_REGS = {0x3034,0x3035,0x3036,0x3037,0x3108}
FINAL = {0x3008:0x40,0x3034:8,0x3035:0x40,0x3036:84,
         0x3037:0x13,0x3039:0,0x3103:2,0x3108:1}
LEGAL_PREDIV = {1,2,3,4,6,8}
MAX_VCO = 800_000_000


def integer(value, low, high, name):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(name+' must be an integer in '+str(low)+'..'+str(high))
    return value


def checked_write(address, value):
    """RMW preserves every bit outside its documented mask; it is not a byte value."""
    op = 'write' if MASKS[address]==0xff else 'rmw'
    return [{'op':op,'address':address,'mask':MASKS[address],'value':value},
            {'op':'read_check','address':address,'mask':MASKS[address],'expected':value}]


def proposed_actions():
    # No fabricated lock bit, settling delay, common analog table or final wake.
    actions = [{'op':'reset'},
               {'op':'read_check','address':0x3036,'mask':0xff,'expected':0x69},
               {'op':'read_check','address':0x3037,'mask':0x1f,'expected':0x03}]
    for address,value in [(0x3103,0),(0x3008,0x40),(0x3039,0x80),
            (0x3037,0x16),(0x3036,84),(0x3034,8),(0x3035,0x40),
            (0x3108,1),(0x3037,0x13),(0x3039,0),(0x3103,2)]:
        actions.extend(checked_write(address,value))
    return actions


def audit_sequence(actions, *, nominal_xvclk_hz=24_000_000, upper_xvclk_hz=27_000_000):
    integer(nominal_xvclk_hz,6_000_000,27_000_000,'nominal XVCLK Hz')
    integer(upper_xvclk_hz,nominal_xvclk_hz,27_000_000,'upper XVCLK Hz')
    if type(actions) is not list or not actions:
        raise ValueError('nonempty ordered action list required')
    known = {}; confirmed = {}; errors = []; trace = []; unknown = []
    pending = None; pending_full_byte = None; pre6 = False; mult84 = False; epoch = -1
    declared_reads = supplied_reads = 0; reset_seen = False

    def error(index, code, detail):
        errors.append({'action_index':index,'code':code,'detail':detail})

    def ratio(mult,pre,frequency):
        return Fraction(frequency*mult,pre)

    def final_tree():
        return all(confirmed.get(a)==v for a,v in FINAL.items() if a not in (0x3039,0x3103))

    for index, action in enumerate(actions):
        if type(action) is not dict or type(action.get('op')) is not str:
            raise ValueError('action must be an object with string op')
        op=action['op']
        if op=='reset':
            if set(action)!={'op'}:raise ValueError('reset has no guessed timing or register fields')
            if pending:error(index,'UNREAD_WRITE','reset erased a write before its read check')
            known={};confirmed={};pending=None;pending_full_byte=None;pre6=False;mult84=False;epoch+=1;reset_seen=True
            unknown.append({'epoch':epoch,'reset_action':index,'first_control_write_action':None,
                'first_control_read_check_action':None,'physical_VCO_before_control_proven':False})
            trace.append({'action_index':index,'op':op,'epoch':epoch,'VCO_model_hz':None})
            continue
        if not reset_seen:error(index,'MISSING_RESET','a reset/unknown-interval boundary must precede actions')
        if op=='wait':
            if set(action)!={'op','cycles'}:raise ValueError('wait only declares bounded reference-clock cycles; no lock claim')
            integer(action['cycles'],1,0xffffffff,'wait cycles')
            trace.append({'action_index':index,'op':op,'cycles':action['cycles'],
                          'PLL_lock_observed':None,'wait_is_lock_evidence':False})
            continue
        required={'op','address','mask','expected' if op=='read_check' else 'value'}
        allowed=required|({'observed','bus_error'} if op=='read_check' else {'pre_read'} if op=='rmw' else set())
        if op not in ('write','rmw','read_check') or not required.issubset(action) or not set(action).issubset(allowed):
            raise ValueError('unsupported/incomplete clock action schema')
        address=integer(action['address'],0,0xffff,'address');mask=integer(action['mask'],1,255,'mask')
        value=integer(action['expected' if op=='read_check' else 'value'],0,255,'value')
        if address not in MASKS:raise ValueError('register is outside this narrow documented clock/standby model')
        if mask!=MASKS[address] or value&~mask:
            error(index,'WRONG_MASK','use exact documented field mask and no unmasked value bits')
        if op=='read_check':
            declared_reads+=1
            if 'observed' in action:
                observed=integer(action['observed'],0,255,'observed byte');supplied_reads+=1
                if observed&mask!=value&mask:error(index,'OBSERVED_MISMATCH','supplied byte fails the masked expectation')
                if pending_full_byte is not None and observed!=pending_full_byte:
                    error(index,'PRESERVED_BITS_MISMATCH','supplied RMW pre-read/write/read values do not preserve outside-mask bits')
            if 'bus_error' in action and integer(action['bus_error'],0,15,'bus error'):
                error(index,'SCCB_READ_ERROR','a matching value never overrides a read bus error')
            if pending is not None:
                if (address,mask,value)!=pending:
                    error(index,'READBACK_NOT_FOR_PENDING_WRITE','wrong address, mask or expected value')
                else:
                    confirmed[address]=value
                    if address==0x3037 and value==0x16:
                        pre6=True
                        if unknown and unknown[-1]['first_control_read_check_action'] is None:
                            unknown[-1]['first_control_read_check_action']=index
                    if address==0x3036 and value==84 and pre6:mult84=True
                pending=None;pending_full_byte=None
            elif address not in known:
                if (address,mask,value) not in ((0x3036,0xff,0x69),(0x3037,0x1f,3)):
                    error(index,'UNSUPPORTED_INITIAL_EXPECTATION','only documented default69/03 declarations seed this conditional model')
            elif known[address]!=value:
                error(index,'UNBACKED_READ_EXPECTATION','read expectation differs from the prior declared write')
            known[address]=value
            trace.append({'action_index':index,'op':op,'address':address,'mask':mask,'expected':value,
                'evidence':'supplied_unverified_observation' if 'observed' in action else 'declared_expectation_only',
                'observed':action.get('observed'),'bus_error':action.get('bus_error'),
                'hardware_readback_verified':False})
            continue
        if pending:error(index,'UNREAD_WRITE','each write requires its own read check before another write')
        if op!=('write' if mask==0xff else 'rmw'):
            error(index,'RMW_REQUIRED','partial fields must preserve bits outside the mask through read/modify/write')
        if address in PLL_REGS and not (confirmed.get(0x3103)==0 and confirmed.get(0x3008)==0x40 and confirmed.get(0x3039)==0x80):
            error(index,'PLL_OUTPUT_NOT_ISOLATED','first confirm pad system clock, standby and bypass; none proves VCO off')
        if address==0x3036 and (value!=84 or not pre6):
            error(index,'MULTIPLIER_ORDER','this branch permits mult84 only after confirmed prediv6/root2')
        if address==0x3037:
            if value not in (0x16,0x13):error(index,'PREDIV_BRANCH','only reviewed pre6/root2 then pre3/root2 actions are supported')
            if value==0x13 and not (pre6 and mult84 and all(confirmed.get(a)==v for a,v in ((0x3034,8),(0x3035,0x40),(0x3108,1)))):
                error(index,'FINAL_PREDIV_ORDER','final pre3 requires confirmed pre6, mult84 and remaining dividers')
        if address in (0x3034,0x3035,0x3108) and value!=FINAL[address]:
            error(index,'OTHER_CLOCK_BRANCH','value does not belong to the documented84/4 RGB565 model')
        if address==0x3008 and value!=0x40:error(index,'FINAL_WAKE_NOT_IMPLEMENTED','this audit ends in standby; it cannot authorize a complete sensor wake')
        if address==0x3039 and (value not in (0,0x80) or (value==0 and not final_tree())):
            error(index,'BYPASS_RELEASE_ORDER','release bypass only after the complete controlled clock tree is read-checked')
        if address==0x3103 and (value not in (0,2) or (value==2 and not (final_tree() and confirmed.get(0x3039)==0))):
            error(index,'PLL_SELECT_ORDER','select PLL only after controlled read checks and confirmed bypass release')
        known[address]=value;pending=(address,mask,value)
        pre_read=integer(action['pre_read'],0,255,'RMW pre-read byte') if 'pre_read' in action else None
        pending_full_byte=((pre_read&~mask)|value) if pre_read is not None else None
        row={'action_index':index,'op':op,'address':address,'mask':mask,'value':value,
             'outside_mask_preserved_by_RMW_contract':op=='rmw','VCO_model_hz':None,
             'RMW_pre_read':pre_read,'RMW_pre_read_evidence':('supplied_unverified_observation' if pre_read is not None
                 else 'declared_runtime_read_preserve_contract') if op=='rmw' else None,
             'RMW_expected_full_written_byte_from_supplied_pre_read':pending_full_byte,
             'RMW_execution_verified_on_hardware':False}
        if address in (0x3036,0x3037):
            mult=known.get(0x3036);pre=known.get(0x3037,0)&15
            if mult is None or 0x3037 not in known:
                error(index,'PLL_STATE_UNKNOWN','read-check initial multiplier and predivider before modeling a changed state')
            elif pre not in LEGAL_PREDIV or not (4<=mult<=127 or 128<=mult<=252 and mult%2==0):
                error(index,'ILLEGAL_PLL_FIELD','datasheet multiplier or predivider domain violated')
            else:
                upper=ratio(mult,pre,upper_xvclk_hz);nominal=ratio(mult,pre,nominal_xvclk_hz)
                row.update(multiplier=mult,predivider=pre,VCO_model_hz=float(nominal),upper_VCO_model_hz=float(upper))
                if upper>MAX_VCO:error(index,'VCO_EXCEEDS_LOCAL_LIMIT','static changed-state model exceeds800MHz at the declared input upper bound')
            if unknown and unknown[-1]['first_control_write_action'] is None:
                unknown[-1]['first_control_write_action']=index
        trace.append(row)
    if pending:error(len(actions),'MISSING_READBACK','last write has no matching read check')
    complete=pending is None and all(confirmed.get(address)==known.get(address)==value for address,value in FINAL.items())
    if not complete:error(len(actions),'INCOMPLETE_CLOCK_ACTIONS','required clock fields/output-selection read checks are missing')
    return {'schema':1,'static_model_passed':not errors,'hardware_accessed':False,'hardware_release_allowed':False,
        'complete_720_initialization':False,'nominal_XVCLK_hz':nominal_xvclk_hz,'upper_XVCLK_hz':upper_xvclk_hz,
        'XVCLK_measured_hz':None,'local_VCO_upper_limit_hz':MAX_VCO,'unknown_intervals':unknown,
        'bypass_or_standby_proves_VCO_off':False,'PLL_lock_observed':None,'PLL_settling_guarantee_source':None,
        'all_actions_analog_validated':False,
        'low_VCO_model_caveat':{'local_minimum_usable_VCO_guaranteed_hz':None,
            'Linux_inferred_lower_bound_hz':500_000_000,'Linux_inference_is_guaranteed_local_spec':False,
            'low_VCO_usability_or_lock_verified':False,
            'static_changed_states_below_inferred_lower_at_upper_input':[
                {'action_index':row['action_index'],'VCO_model_hz':row['VCO_model_hz'],
                 'upper_VCO_model_hz':row['upper_VCO_model_hz']}
                for row in trace if row.get('upper_VCO_model_hz') is not None and row['upper_VCO_model_hz']<500_000_000]},
        'declared_read_check_count':declared_reads,'supplied_observation_count':supplied_reads,
        'observations_are_independently_verified_hardware':False,'errors':errors,'trace':trace,
        'final_clock_model_if_all_declared_read_checks_succeed':{
            'VCO_nominal_hz':float(Fraction(nominal_xvclk_hz*84,3)),
            'VCO_upper_hz':float(Fraction(upper_xvclk_hz*84,3)),
            'PCLK_nominal_hz':float(Fraction(nominal_xvclk_hz*84,3*4*2*2)),
            'PCLK_upper_hz':float(Fraction(upper_xvclk_hz*84,3*4*2*2)),
            'physical_frequency_or_lock_verified':False} if complete else None,
        'unimplemented_required_work':['source-bound common720 initialization/crop/HTS/VTS/AEC/banding',
            'supported PLL settling/lock evidence; no delay or lock bit invented',
            'unique final wake and complete post-wake read checks',
            'PCLK-domain activity and exact2560-byte by720-line freshness monitor/CDC',
            'new RTL/host contract/final timing and separately authorized hardware acceptance'],
        'limits':'Conditional static register-action model only. Initial reset/default interval and register-switch transients are not bounded physical VCO proof. Pre6 stages472.5/378MHz at27MHz input are below the Linux-inferred500MHz lower bound; local minimum usability and analog lock are unproven. Static upper-bound acceptance does not validate every analog action. Expected read checks are not measurements. RMW preserves undocumented bits by declared contract or supplied unverified pre-read, not hardware proof; a masked match alone cannot excuse a write-data NACK. Standby/bypass is not PLL power-off. No complete720 recipe, RTL, PCLK implementation, measured clock, frame rate, optics or hardware release.'}


def legacy_tail_counterexample():
    # Even granting the old mult96 write an exact matching read check, a later
    # pre6/mult84/pre3 tail cannot erase the earlier864MHz model at27MHz input.
    actions=proposed_actions()
    return actions[:9]+checked_write(0x3036,96)+actions[9:]


def source_evidence():
    paths=[ROOT/'rtl/experimental/ov5640_cadence_trial_init.v',ROOT/'board/ov5640_cadence_trial_commands.vh',
        ROOT/'output/project/720p初始化顺序补充核查-20261025.md',
        ROOT/'output/project/ov5640-720p-bounded-clock-source-plan-20261025.json',
        ROOT.parent/'hardware_check/ov5640-datasheet.txt']
    expected={'ov5640_cadence_trial_init.v':'66e2a8236ca8a5d7bb56e46893cf640d3aa9e8b2c4f4b9119340cabfbb153ec7',
        'ov5640_cadence_trial_commands.vh':'53428872aa14e6120eed93d876c889ef5155b3c196c014db77c4578b2bd50674',
        'ov5640-datasheet.txt':'7070560b10ec15649e4ca39cf0cb91875f8f1589907d5d2a1d203fbaf7e1e435'}
    evidence=[]
    for path in paths:
        digest=hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
        evidence.append({'path':str(path),'exists':path.is_file(),
            'sha256':digest,'recorded_critical_source_sha256':expected.get(path.name),
            'recorded_critical_source_matches':digest==expected[path.name] if path.name in expected else None})
    table=paths[1].read_text() if paths[1].is_file() else ''
    return evidence, "9'd251: camera_command=32'h30366000;" in table


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--actions',type=Path,help='ordered JSON array; supplied observations remain unverified input')
    parser.add_argument('--output',type=Path,required=True,help='fresh JSON file directly in the existing approved scratch root')
    parser.add_argument('--nominal-xvclk-hz',type=int,default=24_000_000)
    parser.add_argument('--upper-xvclk-hz',type=int,default=27_000_000)
    args=parser.parse_args(argv)
    path=args.output.resolve()
    if path.parent!=APPROVED.resolve() or not path.parent.is_dir() or path.exists():
        parser.error('output must be a fresh file directly in existing approved scratch; no new directory/overwrite')
    actions=json.loads(args.actions.read_text(encoding='utf-8-sig')) if args.actions else proposed_actions()
    result=audit_sequence(actions,nominal_xvclk_hz=args.nominal_xvclk_hz,upper_xvclk_hz=args.upper_xvclk_hz)
    evidence,legacy_source_matches=source_evidence()
    legacy=audit_sequence(legacy_tail_counterexample(),nominal_xvclk_hz=args.nominal_xvclk_hz,upper_xvclk_hz=args.upper_xvclk_hz)
    result.update(actions=actions,source_evidence=evidence,legacy_mult96_source_matches=legacy_source_matches,
        legacy_tail_counterexample=legacy,tool_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    result['source_evidence_available']=all(item['exists'] and item['recorded_critical_source_matches'] is not False
        for item in evidence) and legacy_source_matches
    with path.open('x',encoding='utf-8') as stream:json.dump(result,stream,indent=2,allow_nan=False);stream.write('\n')
    print(json.dumps({'output':str(path),'static_model_passed':result['static_model_passed'],
        'source_evidence_available':result['source_evidence_available'],'legacy_tail_rejected':not legacy['static_model_passed'],
        'hardware_release_allowed':False}))
    return 0 if result['static_model_passed'] and result['source_evidence_available'] else 1


if __name__=='__main__':raise SystemExit(main())
