"""Native eight-bit camera delay graph, with enumerated first sequential sinks.

This is a structural fanout overapproximation: all connected outputs of a LUT
are followed, without claiming Boolean sensitization or external AC margin.
"""
import re
import audit_camera_vga_cdc as cdc

require, one = cdc.require, cdc.one
COMBINATIONAL = {'V_LUT6CARRY': ({'I0','I1','I2','I3','I4','I5','CIN'}, {'Z','Z5','COUT'}),
                 'V_BUF': ({'I'}, {'Z'}), 'V_INV': ({'I'}, {'Z'})}
DRM_PARAMETERS = {'RAM_MODE':'"SIMPLE_DUAL_PORT"', 'DATA_WIDTH_A':'64', 'DATA_WIDTH_B':'64',
                  'WRITE_MODE_A':'"NORMAL_WRITE"', 'WRITE_MODE_B':'"NORMAL_WRITE"',
                  'RAM_CASCADE':'"NONE"', 'ECC_WRITE_EN':'"FALSE"', 'ECC_READ_EN':'"FALSE"'}
# Reviewed native model: SDP_MODE/PORTA samples DIB_int at posedge CLKA;
# mem_write_a's 64-bit case ignores parity positions 8,17,26,35 in each half.
# This is a recorded model reference, not a dynamically trusted external file.
DRM_MODEL_REFERENCE = {'RelativePDSPath':'arch/vendor/pango/verilog/bsim/V_DRM36K_E1.v',
    'SHA256':'224ad428a209ba704b58c24a505b9290648a95e4ae585494b80296bc9e0f1c96',
    'ClockSemanticsLines':[1155,1169], 'DataMappingLines':[829,847],
    'Scope':'Only the explicitly checked SIMPLE_DUAL_PORT 64/64, no-ECC, no-cascade configuration.'}


def scalar(value):
    """One explicit scalar wire/bit or one-bit literal; no ranges or operators."""
    value=value.strip()
    require(re.fullmatch(r"1'[bB][01xXzZ]|[A-Za-z_$][A-Za-z0-9_$]*(?:\[\d+\])?|"
                         r"\\[^\s{},]+(?:\s+\[\d+\])?",value), 'unparsed camera fanout expression')
    return cdc.canon(value)


def flat_data_bus(value):
    require(value.startswith('{') and value.endswith('}') and value.count('{')==value.count('}')==1,
            'native DRM data requires a flat explicit 36-bit concatenation')
    bits=[scalar(v) for v in value[1:-1].split(',')]
    require(len(bits)==36, 'native DRM data concatenation width differs')
    return list(reversed(bits))


def references(g):
    """Index only reviewed scalar syntax; inspect unfamiliar uses on demand.

    The shared CDC graph intentionally treats vector bindings as opaque. This
    private index expands only DRM DIA/DIB, with physical pin bit numbers.
    No graph is mutated and no packed-vector consumer can evade bypass checks.
    """
    ports=[(name,pin,cell['Primitive'],value.strip()) for name,cell in g.cells.items()
           for pin,value in cell['Ports'].items() if value]
    cache={}
    def refs(net):
        net=cdc.canon(net)
        if net in cache:return cache[net]
        # Also catch a bus range/whole-bus use that hides the individual bit.
        base=re.sub(r'\[\d+\]$','',net)
        pattern=re.compile(r'(?<![A-Za-z0-9_$])'+re.escape(base)+r'(?![A-Za-z0-9_$])')
        result=set()
        for name,pin,kind,value in ports:
            if not pattern.search(cdc.canon(value)):continue
            if value.startswith('{'):
                require(kind=='V_DRM36K_E1' and pin in ('DIA','DIB'),
                        'camera net used in an unreviewed vector port')
                bits=flat_data_bus(value)
                for i,token in enumerate(bits):
                    require(token!=base or net==base, 'camera bit hidden in whole-bus binding')
                    if token==net:result.add((name,f'{pin}[{i}]'))
            else:
                token=scalar(value)
                require(token!=base or net==base, 'camera bit hidden in whole-bus binding')
                if token==net:result.add((name,pin))
        cache[net]=result
        return result
    return refs


def audit(g):
    require(not re.search(r'\b(?:assign|always|initial|function|task|generate|tran|buf|not)\b',
                          g.g['ModuleDeclarations']), 'unparsed native aliases or procedural logic')
    delays = {n:c for n,c in g.cells.items() if c['Primitive']=='V_ZEROHOLDDELAY'}
    require(len(delays)==8, 'exactly eight native camera delay cells required')
    refs_for=references(g)
    used, rows, all_sinks = set(), [], set()
    for bit in range(8):
        pad=f'cam_data[{bit}]'
        buffer=one([n for n,c in g.cells.items() if c['Primitive']=='V_IBUF' and c['Ports'].get('I')==pad], pad+' buffer')
        bc=g.cells[buffer];intermediate=bc['Ports'].get('O')
        require(set(bc['Ports'])=={'I','O'} and intermediate, 'input buffer ports differ')
        require(bc['Parameters']=={'IOSTANDARD':'"LVCMOS33"','TERM_DDR':'"ON"'}, 'input buffer electrical parameters differ')
        delay=one([n for n,c in delays.items() if c['Ports'].get('DI')==intermediate], pad+' delay')
        dc=delays[delay];output=dc['Ports'].get('DO')
        require(set(dc['Ports'])=={'DI','DO'} and output and dc['Parameters']=={'ZHOLD_SET':'"1500ps"'}, 'input delay setting or ports differ')
        require(delay.startswith(f'camera_data_delay/data_bit[{bit}].') or delay.startswith(f'camera_data_delay/data_bit[{bit}]/'), 'camera delay bit hierarchy differs')
        require(refs_for(pad)=={(buffer,'I')}, 'camera pad bypasses input buffer')
        require(refs_for(intermediate)=={(buffer,'O'),(delay,'DI')}, 'camera input buffer bypasses delay')
        require(len({pad,intermediate,output})==3, 'delay nets alias')
        require(buffer not in used and delay not in used, 'delay resources shared across data bits')
        used.update((buffer,delay))
        seen, active, sinks, logic, unused = set(), set(), set(), set(), set()

        def visit(net, driver, allow_unused=False):
            net=scalar(net)
            require(net not in active, 'combinational input fanout cycle')
            if net in seen:return
            active.add(net)
            refs=refs_for(net);require(driver in refs, 'fanout driver absent')
            consumers=refs-{driver}
            require(consumers or allow_unused, 'delayed data has no consumer')
            if not consumers:unused.add((driver[0],driver[1],net))
            # A recognized second output driver cannot silently become a sink.
            for name,pin in consumers:
                c=g.cells[name];kind=c['Primitive']
                if kind in cdc.FF_TYPES:
                    require(pin=='D' and name.startswith(cdc.CAP), 'delayed camera data reaches non-capture or control FF pin')
                    require(g.clock(c['Ports']['CK'])['Domain']=='camera_pclk', 'camera data sampled in wrong domain')
                    sinks.add((name,pin,kind,'CK'));continue
                if kind=='V_DRM36K_E1':
                    match=re.fullmatch(r'(DIA|DIB)\[(\d+)\]',pin)
                    require(match and name.startswith(cdc.CAP+'pixels/'),
                            'camera data reaches non-capture or control DRM pin')
                    require(all(c['Parameters'].get(k)==v for k,v in DRM_PARAMETERS.items()),
                            'unreviewed camera DRM mode/width/ECC/cascade')
                    index=int(match[2]);require(index in range(36) and index%9!=8,
                            'camera data reaches an unused SDP64 parity bit')
                    require(g.clock(c['Ports']['CLKA'])['Domain']=='camera_pclk',
                            'camera DRM write data sampled in wrong domain')
                    sinks.add((name,pin,kind,'CLKA'));continue
                require(kind in COMBINATIONAL and pin in COMBINATIONAL[kind][0], 'unreviewed delayed fanout primitive/pin: '+name+'/'+pin)
                require(name.startswith(cdc.CAP), 'camera combinational fanout escaped capture hierarchy')
                logic.add(name)
                outputs=[(p,c['Ports'][p]) for p in COMBINATIONAL[kind][1] if c['Ports'].get(p)]
                require(outputs, 'camera combinational consumer has no output')
                for p,value in outputs:visit(value,(name,p),allow_unused=True)
            active.remove(net);seen.add(net)

        visit(output,(delay,'DO'))
        require(sinks, 'delayed data never reaches a first sequential sink')
        all_sinks.update(sinks)
        rows.append({'Bit':bit,'Pad':pad,'InputBuffer':buffer,'Intermediate':intermediate,
            'DelayCell':delay,'Output':output,'DelaySetting':'1500ps','NoBypass':True,
            'FirstSequentialSinks':[{'Cell':n,'Pin':p,'Primitive':kind,'Clock':'camera_pclk',
                'ClockPin':ck,'SamplingEdge':'rising'} for n,p,kind,ck in sorted(sinks)],
            'CombinationalFanoutCells':sorted(logic),'EnumeratedFanoutNets':len(seen),
            'UnusedCombinationalOutputs':[{'Cell':n,'Pin':p,'Net':v} for n,p,v in sorted(unused)]})
    return {'Passed':True,'NativeDelayCells':8,'Bits':rows,'UniqueFirstSequentialSinkCount':len(all_sinks),
        'UniqueFFSinkCount':sum(kind in cdc.FF_TYPES for _,_,kind,_ in all_sinks),
        'UniqueDRMDataBitSinkCount':sum(kind=='V_DRM36K_E1' for _,_,kind,_ in all_sinks),
        'DRMModelReference':DRM_MODEL_REFERENCE,
        'NominalDelayPS':1500,'AllPadConsumersTraverseTheirOwnDelay':True,
        'FanoutIsStructuralOverapproximation':True,'BooleanSensitizationProved':False,
        'ActualPVTDelayFromSettingAloneProven':False,'ExternalACTimingAccepted':False}
