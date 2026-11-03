"""Check actual arithmetic/memory output domains at their user FF consumers.

Input locality alone cannot establish the consumer domain of a bypassed DSP.
These facts come from the current audit, including its bound mode models and
complete non-FF source sets. Other PHY/PLL boundaries retain their separate
native acceptance review; this function grants no timing exceptions.
"""
from collections import Counter


KINDS={'V_APM_E2','V_DRM18K_E1','V_DRM36K_E1','V_RAM32X2','V_RAM64X1'}


def require(value,message):
    if not value:raise ValueError(message)


def review(scope):
    rows=scope.get('PrimitiveBoundaries');support=scope.get('NonFFSequentialSupport')
    require(isinstance(rows,list)and isinstance(support,dict)
        and support.get('AllNonFFSourceTokensRetained')is True
        and support.get('UnknownsNotConvertedToPrimaryInputs')is True,
        'complete current native non-FF source and consumer inventory required')
    macros={r['Cell']:r for r in rows};require(len(macros)==len(rows),'duplicate native macro identity')
    sets=support.get('SourceSets');consumers=support.get('Consumers')
    require(isinstance(sets,dict)and isinstance(consumers,list),'complete source-set references required')
    cache={};issues=[];counts=Counter();outside=Counter();comb=set();split=set();checked=0

    def domains(token,active=()):
        if token in cache:return cache[token]
        require(token not in active,'arithmetic output domain dependency cycle')
        name,pin=token[6:].rsplit('/',1);row=macros[name];kind=row['Primitive'];parameters=row['Parameters']
        clock=lambda p:{c['Domain']for c in row.get('ClockBindings',[])if c.get('Pin')==p}
        if kind=='V_APM_E2':
            proof=row.get('ActiveBitModeProof',{});facts=proof.get('ModeFacts',{})
            require(proof.get('Passed')is True and proof.get('Violations')==[], 'unverified actual arithmetic mode')
            require(type(facts.get('ActiveClockRequired'))is bool,'arithmetic register/bypass mode missing')
            if facts['ActiveClockRequired']:
                value=clock('CLK');require(value,'registered arithmetic output clock absent')
            else:
                comb.add(name);value=set()
                for binding in row.get('InputBindings',[]):
                    value.update(binding.get('FFDomains',[]))
                    for source in binding.get('Support',[]):
                        if source.startswith('macro:'):value.update(domains(source,active+(token,)))
                        else:require(source.startswith('ff:'),'unreviewed combinational arithmetic input source')
                # A fully constant combinational macro has no crossing domain.
                # Require the bound active-bit model to identify only constants.
                if not value:
                    operands=[v for port in proof.get('ActiveInputs',[])for v in port.get('MSBFirstTokens',[])]
                    require(operands and all(v in("1'b0","1'b1")for v in operands),
                        'combinational arithmetic output has no proved input domain')
        elif kind in('V_DRM18K_E1','V_DRM36K_E1'):
            proof=row.get('ActiveBitModeProof',{});facts=proof.get('ModeFacts',{})
            require(proof.get('Passed')is True and proof.get('Violations')==[], 'unverified actual memory mode')
            mode=parameters['RAM_MODE'].strip('"')
            require(mode in('SIMPLE_DUAL_PORT','TRUE_DUAL_PORT','SINGLE_PORT','ROM'),'unreviewed memory read mode')
            side='B'if mode=='SIMPLE_DUAL_PORT'else'A'if pin.startswith('DOA')else'B'if pin.startswith('DOB')else None
            require(side is not None,'unknown native memory output port')
            require(facts.get('PortFacts',{}).get(side,{}).get('CanReadUsedOutput')is True,
                'disabled memory read port has a consumer')
            value=clock('CLK'+side)
        elif kind in('V_RAM32X2','V_RAM64X1'):
            require(row.get('AsynchronousReadAddressIsNotWCLKFlipFlop')is True,
                'actual asynchronous memory read behavior is not reviewed')
            value=set(row.get('ReadAddressClockDomains',[]))or clock('WCLK')
        else:raise ValueError('unreviewed nested arithmetic input macro '+kind)
        require(value or kind=='V_APM_E2','native memory/registered arithmetic output clock absent')
        cache[token]=value;return value

    for consumer in consumers:
        # The source-partition audit independently binds the one actual DDR IP
        # hierarchy. Its internal PHY consumers are checked in that partition.
        if consumer['DestinationFF'].startswith('u_ddr3_test_h/'):continue
        key=consumer['SupportSetKey'];require(key in sets,'missing complete non-FF support-set reference')
        for token in sets[key]:
            if not token.startswith('macro:'):continue
            try:
                name,pin=token[6:].rsplit('/',1);row=macros[name];kind=row['Primitive']
                if kind not in KINDS:outside[kind]+=1;continue
                origin=domains(token);checked+=1;counts[kind]+=1
                if origin and origin!={consumer['DestinationClock']}:
                    issues.append({'Code':'MacroOutputConsumerDomainDiffers','Source':token,
                        'SourceDomains':sorted(origin),**consumer})
                if kind in('V_RAM32X2','V_RAM64X1'):
                    write={c['Domain']for c in row.get('ClockBindings',[])if c.get('Pin')=='WCLK'}
                    if write!=origin:split.add(name)
            except(ValueError,KeyError)as error:
                issues.append({'Code':'MacroOutputConsumerDomainUnresolved','Source':token,
                    'DestinationFF':consumer['DestinationFF'],'Detail':str(error)})
    return {'Passed':not issues,'CurrentUserFFMacroRelations':checked,'RelationsByPrimitive':dict(counts),
        'CombinationalAPMCellsChecked':len(comb),'LUTRAMSeparateWriteReadClockCells':len(split),
        'SeparateWriteReadRequiresExistingFIFOProtocolReview':bool(split),
        'OtherMacroRelationsRetainSeparateNativeReview':dict(outside),
        'Missing':[],'Violations':issues,'ExceptionsGenerated':False,'HardwareAccessed':False}
