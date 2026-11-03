"""Independent native B reset/epoch cofactors; never generates timing scopes."""
import argparse
import ast
from functools import lru_cache
import hashlib
import itertools
import json
from pathlib import Path
import re
import sys

import hdmi_camera_snapshot_audit as audit

SELF=Path(__file__).resolve()
build,native,base=audit.build,audit.native,audit.base
require,sha,ref=build.require,build.sha,build.ref
SCHEMA='hdmi-camera-snapshot-native-reset-review-v1'


def static_helpers():
    pending=[SELF];seen=set()
    while pending:
        path=pending.pop()
        if path in seen:continue
        seen.add(path)
        for node in ast.walk(ast.parse(path.read_text(encoding='utf-8-sig'))):
            names=[]
            if isinstance(node,ast.Import):names=[n.name for n in node.names]
            elif isinstance(node,ast.ImportFrom)and node.module:names=[node.module]
            for name in names:
                child=SELF.parent/(name.split('.')[-1]+'.py')
                if child.is_file()and child not in seen:pending.append(child)
    return sorted(seen)


def possible(expr,fixed):
    """Sound bounded Boolean cofactor; independent leaves may overapproximate."""
    @lru_cache(None)
    def visit(node):
        kind=node[0]
        if kind=='constant':return frozenset((node[1],))
        if kind=='variable':return frozenset((fixed[node[1]],))if node[1]in fixed else frozenset((0,1))
        if kind=='not':return frozenset(1-v for v in visit(node[1]))
        if kind=='mux':return frozenset().union(*(visit(node[1+v])for v in visit(node[3])))
        require(kind=='lut','unknown native Boolean expression')
        return frozenset((node[1]>>sum(v<<i for i,v in enumerate(bits)))&1
            for bits in itertools.product(*(visit(n)for n in node[2])))
    return set(visit(expr))


def forced_next(g,name,fixed):
    cell=g.ff[name];params=cell['Parameters'];pins=cell['Ports']
    require(cell['Primitive']in ('V_FFASYN','V_FFSYN')and params.get('LRS_EN')in ('"TRUE"','"FALSE"')and
        params.get('SET_RESET')in ('"SET"','"RESET"'),'unreviewed native FF semantics')
    # Evaluate only Boolean branches that survive the fixed reset cofactor.
    # Unused CIN ports in native carry primitives are not primary inputs.
    @lru_cache(None)
    def net_values(net):
        net=audit.canon(net)
        if net in ("1'b0","1'b1"):return frozenset((int(net[-1]),))
        drivers=g.canonical_outputs.get(net,[])
        if not drivers:
            require(g.ports.get(net)in ('INPUT','INOUT'),'undriven relevant native cofactor input: '+net)
            key='primary:'+net;return frozenset((fixed[key],))if key in fixed else frozenset((0,1))
        require(len(drivers)==1,'ambiguous native cofactor driver')
        n,output=drivers[0];c=g.cells[n];p=c['Ports'];kind=c['Primitive']
        if n in g.ff:
            key='ff:'+n;return frozenset((fixed[key],))if key in fixed else frozenset((0,1))
        if kind in ('V_BUF','V_IBUF'):return net_values(p['I'])
        if kind=='V_INV':return frozenset(1-v for v in net_values(p['I']))
        if kind=='V_MUX2':return frozenset().union(*(net_values(p['I'+str(s)])for s in net_values(p['SEL'])))
        require(kind=='V_LUT6CARRY','unsupported relevant native cofactor primitive: '+kind)
        init=c['Parameters']['INIT'];require(re.fullmatch(r"64'h[0-9a-fA-F_]+",init),'invalid native LUT truth')
        number=int(init[4:].replace('_',''),16)
        def half(value):
            relevant=[i for i in range(5)if any(((value>>b)^(value>>(b^(1<<i))))&1 for b in range(32))]
            return frozenset((value>>sum(bit<<i for i,bit in zip(relevant,bits)))&1
                for bits in itertools.product(*(net_values(p['I'+str(i)])for i in relevant)))
        low=half(number&0xffffffff)
        if output=='Z5':return low
        if output=='COUT':
            result=frozenset()
            if 0 in low:result|=net_values(p['I5'])if c['Parameters'].get('I5_TO_CARRY','"TRUE"')=='"TRUE"'else half(number>>32)
            if 1 in low:result|=net_values(p['CIN'])
            return result
        require(output=='Z','unsupported native LUT output')
        high=half(number>>32)
        if low==high and len(low)==1:return low
        selectors=net_values(p['I5']if c['Parameters'].get('I5_TO_LUT')=='"TRUE"'else p['CIN'])
        return frozenset().union(*(high if s else low for s in selectors))
    sr=set(net_values(pins['SR']))if params['LRS_EN']=='"TRUE"'else {0}
    result=set()
    if 1 in sr:result.add(int(params['SET_RESET']=='"SET"'))
    if 0 in sr:
        ce=net_values(pins['CE'])
        if 0 in ce:result.update((fixed['ff:'+name],)if 'ff:'+name in fixed else (0,1))
        if 1 in ce:result.update(net_values(pins['D']))
    return result


def table(expressions,predicate,maximum=12):
    variables=sorted(set.union(set(),*(base.boolean.leaves(e)for e in expressions.values())))
    require(len(variables)<=maximum,'native reset mask truth bound exceeded')
    rows=[]
    for bits in itertools.product((0,1),repeat=len(variables)):
        values=dict(zip(variables,bits));observed={k:base.boolean.evaluate(e,values)for k,e in expressions.items()}
        require(observed==predicate(values),'native reset/epoch mask truth differs')
        rows.append({'Inputs':values,'Observed':observed})
    return {'Variables':variables,'AssignmentsChecked':len(rows),'TruthTable':rows}


def inactive(g,name):
    p=g.ff[name]['Parameters'];value=int(p['SET_RESET']=='"SET"')
    require(p.get('GRS_EN')=='"TRUE"'and p.get('INIT')=="1'b"+str(value),'native INIT/GRS does not match inactive value')
    return value


def native_reset_review(build_plan,export_receipt):
    build_plan,export_receipt=Path(build_plan).resolve(),Path(export_receipt).resolve();watched={}
    for p in static_helpers():native.add(watched,p)
    native.add(watched,Path(sys.executable).resolve());initial=dict(watched)
    plan=build.validate(build_plan)
    for key in ('InputSHA256','PreparedSHA256'):native.merge(watched,{Path(p):h for p,h in plan[key].items()})
    exported,inputs=native.bind_receipt(export_receipt);native.merge(watched,inputs)
    require(exported['Mode']=='export'and exported['Target']==build.TARGET and
        exported['BuildPlanSHA256']==sha(build_plan),'actual B export/build lineage differs')
    net=native.artifact(export_receipt,exported,build.TARGET+'_sim.v');native.add(watched,net)
    g=audit.graph(net.read_text(encoding='utf-8-sig'),build_plan.parent)
    aliases,alias_proofs=audit.literal_aliases(g,build_plan.parent,watched)
    resolve=lambda logical:audit.resolve_ff(g,logical,aliases)
    roles={key:resolve(logical)for key,logical in {
        'input':'input_reset[1]','sampler':'input_sampler/p_reset[1]',
        'packetizer':'packetizer/r_reset[1]','ref':'ref_reset[1]'}.items()}
    chains={key:base.release_chain(g,n,inactive(g,n))for key,n in roles.items()}
    power=resolve('power_ready');power_key='ff:'+power
    require(g.clock(g.ff[power]['Ports']['CK'])['Domain']=='board27','common power-ready is not reference-clocked')
    reset_expected=lambda a:{'SR':int(not(a['primary:reset_n']and a[power_key]))}
    asynchronous=sorted(n for n,c in g.ff.items()if c['Primitive']=='V_FFASYN'and
        g.clock(c['Ports']['CK'])['Domain']=='input_pixel')
    ready=[resolve('ready_pix['+str(i)+']')for i in (0,1)]
    request=[resolve('capture/request_sync['+str(i)+']')for i in (0,1)]
    expected=set(ready+request+[chains[k][p]for k in ('input','sampler')for p in ('First','Second')])
    require(len(asynchronous)==8 and set(asynchronous)==expected,'all eight current input-domain asynchronous consumers must be inventoried')
    guard={};release=roles['input'];ri=inactive(g,release)
    for name in asynchronous:
        cell=g.ff[name];iv=inactive(g,name)
        require(iv==0 and cell['Parameters']['LRS_EN']=='"TRUE"'and cell['Ports']['CE']=="1'b1",
            'input asynchronous inactive/CE/reset differs')
        sr=g.expression(cell['Ports']['SR']);proof=table({'SR':sr},reset_expected)
        require(forced_next(g,name,{'primary:reset_n':0})=={0}and forced_next(g,name,{power_key:0})=={0},
            'common assertion does not asynchronously force every input FF inactive')
        row={'Passed':True,'FF':name,'Primitive':cell['Primitive'],'Parameters':cell['Parameters'],'Ports':cell['Ports'],
            'Clock':g.clock(cell['Ports']['CK']),'CommonResetTruth':proof,'AsynchronousForcedPhysicalQ':0,
            'GRSInitialPhysicalQ':0,'NativeNextQForced':True,'Missing':[],'Violations':[]}
        if name in ready+request:
            require(forced_next(g,name,{'ff:'+release:ri})=={iv},'local release does not clear scalar consumer')
            row.update(LocalReleaseFF=release,InactiveReleasePhysicalQ=ri,NativeNextQForcedWhileLocalInactive=iv)
        else:row['ReleaseStageRole']=[key+':'+stage for key in ('input','sampler')for stage in ('First','Second')if chains[key][stage]==name]
        guard[name]=row
    # The reference packetizer has its own actual two-FF release sequence.
    for key in ('packetizer','ref'):
        for stage in ('First','Second'):
            n=chains[key][stage];c=g.ff[n]
            require(g.clock(c['Ports']['CK'])['Domain']=='board27','reference release uses wrong clock')
            table({'SR':g.expression(c['Ports']['SR'])},reset_expected)
    # Recover first stages from real Q support: packed aliases need not retain
    # their source-level names. Both native two-stage scalar guards are proved.
    masks={};ref_release=(roles['packetizer'],inactive(g,roles['packetizer']))
    held_roles={'boot':'capture/history_seen','done':'capture/done_hold','good':'capture/good_hold'}
    held={key:resolve(value)for key,value in held_roles.items()}
    for key in ('boot','done'):
        second=resolve('packetizer/'+key+'_sync[1]')
        candidates={v[3:]for v in g.support(g.ff[second]['Ports']['D'])if v.startswith('ff:')and v[3:]not in (second,ref_release[0])}
        require(len(candidates)==1,'one actual masked-source first stage required: '+key);first=next(iter(candidates))
        chain=base.scalar_chain(g,first,second,ref_release,'packetizer/'+key+'_sync')
        h=held[key];e=g.expression(g.ff[first]['Ports']['D'])
        truth=table({'Masked':e},lambda a,h=h:{'Masked':(a['ff:'+release]^ri)&a['ff:'+h]})
        require(forced_next(g,h,{'ff:'+release:ri})=={0},'old source hold does not clear on resumed local clock: '+key)
        masks[key]={'Passed':True,'HeldFF':h,'First':first,'Second':second,'SourceMaskTruth':truth,
            'SourceMaskZeroImmediatelyWhileLocalReleaseInactive':True,'SourceHeldNextQClearsOnFirstLocalResetEdge':True,
            'DestinationScalarChain':chain}
    good=resolve('packetizer/desc_good');good_expr=g.expression(g.ff[good]['Ports']['D'])
    good_truth=table({'Masked':good_expr},lambda a:{'Masked':(a['ff:'+release]^ri)&a['ff:'+held['good']]})
    require(forced_next(g,held['good'],{'ff:'+release:ri})=={0},'good hold is not reset before source release')
    masks['good']={'Passed':True,'HeldFF':held['good'],'ShadowFF':good,'SourceMaskTruth':good_truth,
        'SourceMaskZeroImmediatelyWhileLocalReleaseInactive':True,'SourceHeldNextQClearsOnFirstLocalResetEdge':True}
    # This sidecar proves native asynchronous masks and local reset cofactors.
    # Full BOOT/REQ FSM behavior remains in the separate source-epoch review
    # and actual stopped-PCLK small RTL regression; no whole-PDS FSM claim.
    toggle=resolve('packetizer/request_toggle')
    require(forced_next(g,toggle,{'ff:'+ref_release[0]:ref_release[1]})=={0},
        'reference local reset does not clear request toggle')
    epochs=[]
    for old_done,old_boot,old_good in itertools.product((0,1),repeat=3):
        epoch={'OldDONE':old_done,'OldBootHistory':old_boot,'OldGood':old_good,'InputLocalRelease':ri,
            'MaskedDONE':0,'MaskedBoot':0,'MaskedGood':0,'RequestToggleForcedZeroDuringReferenceLocalReset':True}
        epochs.append(epoch)
    for kind in {c['Primitive']for c in g.cells.values()}:
        native.add(watched,base.MODEL_ROOT/(kind+'.v'),audit.MODELS[kind])
    native.add(watched,build_plan);native.add(watched,SELF)
    require(not native.drift(watched)and not native.drift(initial),'native reset review inputs changed')
    value={'Schema':SCHEMA,'Target':build.TARGET,'Passed':True,'BuildPlan':ref(build_plan),
        'ExportReceipt':ref(export_receipt),'NativeNetlist':ref(net),'GuardProofByFF':guard,'ReleaseChains':chains,
        'InputAsyncFFs':asynchronous,'SourceMasks':masks,'CaptureReleaseSharedWithInputTrue':True,
        'CaptureLocalReleaseFF':release,'PacketizerLocalTwoStageReleaseVerifiedTrue':True,
        'StoppedPCLKEpoch':{'Passed':True,'Cases':epochs,'Scope':'Native source asynchronous masks and local reset cofactors only',
            'NativeRequestToggleFF':toggle,'PCLKStoppedCannotReassertMaskedSourceBootOrDONE':True,
            'FullNativeFSMInductionClaimed':False,
            'WholeBOOTREQEpochRequiresSeparateSourceProtocolAndStoppedClockRTLRegression':True},
        'Missing':[],'Violations':[],'TimingScopesGenerated':False,'TimingAccepted':False,
        'AnalogMetastabilityAccepted':False,'HardwareAccessed':False,'HardwareReleaseAllowed':False,
        'InputSHA256':{str(p):h for p,h in sorted(watched.items(),key=lambda row:str(row[0]))}}
    return json.loads(json.dumps(value)),watched


def verify(path):
    path=Path(path).resolve();saved=build.read(path)
    require(saved.get('Schema')==SCHEMA and saved.get('Target')==build.TARGET,'current native reset review required')
    current,watched=native_reset_review(saved['BuildPlan']['Path'],saved['ExportReceipt']['Path'])
    require(saved==current,'native reset review changed');native.add(watched,path);return saved,watched


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--build-plan',type=Path)
    p.add_argument('--export-receipt',type=Path);p.add_argument('--output',type=Path);p.add_argument('--verify',type=Path);a=p.parse_args()
    if a.verify:v,w=verify(a.verify)
    else:
        require(a.build_plan and a.export_receipt and a.output,'build-plan/export-receipt/output required')
        v,w=native_reset_review(a.build_plan,a.export_receipt);build.write(a.output,v)
    print(json.dumps({'Passed':v['Passed'],'InputAsyncFFs':len(v['GuardProofByFF']),'Watched':len(w)}));return 0


if __name__=='__main__':raise SystemExit(main())
