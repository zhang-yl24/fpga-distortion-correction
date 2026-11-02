"""Exact V_MUX2 support for the actual statistics sequential-cone audit.

The parsed functional graph is unchanged. Only the local driver index adds
this vendor primitive's Z output. No LUT placement or timing arc is invented.
"""
from pathlib import Path

import camera720_stats_io_cdc as base

require = base.require
MODEL = Path('D:/pango/PDS_2023.2/arch/vendor/pango/verilog/bsim/V_MUX2.v')
MODEL_SHA = '77540b86085dc742e5a5102578cb3f0a8753989b3b800d6a75f23e6d46515b95'


class Graph(base.structure.monitor.Graph):
    def __init__(self, parsed):
        super().__init__(parsed)
        for name,cell in self.cells.items():
            if cell['Primitive'] == 'V_MUX2':
                require(set(cell['Ports']) == {'I0','I1','SEL','Z'} and cell['Parameters']=={},
                        'V_MUX2 port/parameter contract differs')
                self.outputs[cell['Ports']['Z']].append((name,'Z'))


def inputs(cell, output):
    if cell['Primitive'] != 'V_MUX2':
        return base.structure.monitor.immediate_support(cell,output)[0]
    require(output == 'Z', 'V_MUX2 output differs')
    ports = cell['Ports']
    if ports['SEL'] in ("1'b0","1'b1"):
        return {ports['I'+ports['SEL'][-1]]}
    if ports['I0'] == ports['I1']:
        return {ports['I0']}
    return {ports['I0'],ports['I1'],ports['SEL']}


def support(graph, net, active=()):
    require(net not in active, 'cycle in statistics cone')
    if net in ("1'b0","1'b1"):
        return set()
    drivers = graph.outputs.get(net,[])
    if not drivers:
        return {('primary',net)}
    name,pin = base.structure.cdc.one(drivers,'statistics driver '+net)
    cell = graph.cells[name]
    if name in graph.ff:
        require(pin == 'Q','statistics sequential source is not Q')
        return {('ff',name)}
    require(cell['Primitive'] in ('V_MUX2','V_LUT6CARRY','V_BUF','V_INV'),
            'unreviewed statistics cone primitive: '+cell['Primitive'])
    result = set()
    for source in inputs(cell,pin):
        result |= support(graph,source,active+(net,))
    return result


def audit(parsed):
    require(base.cdc.sha(MODEL) == MODEL_SHA,'V_MUX2 vendor Boolean model differs')
    graph = Graph(parsed)
    names = sorted(n for n in graph.ff if n.startswith(base.PREFIX))
    require(names,'actual statistics FFs absent')
    rows=[]
    for name in names:
        p=graph.ff[name]['Ports']
        require(graph.clock(p['CK'])['Domain'] == base.CORE,'statistics FF clock differs')
        sources={}
        for pin in ('D','CE','SR'):
            if pin not in p:continue
            leaves=support(graph,p[pin])
            require(all(kind=='ff' and graph.clock(graph.ff[n]['Ports']['CK'])['Domain']==base.CORE
                        for kind,n in leaves),'statistics cone has foreign clock or primary input: '+name+'/'+pin)
            sources[pin]=sorted(n for _,n in leaves)
        rows.append({'FF':name,'Clock':base.CORE,'SequentialSupport':sources})
    pending=[graph.ff[n]['Ports']['Q'] for n in names];seen=set();terminals=set();muxes=set()
    while pending:
        net=pending.pop()
        if net in seen:continue
        seen.add(net)
        for name,pin in graph.refs.get(net,[]):
            if (name,pin) in graph.outputs.get(net,[]):continue
            cell=graph.cells[name];kind,p=cell['Primitive'],cell['Ports']
            if name in graph.ff:
                require(name.startswith(base.PREFIX) and pin in ('D','CE','SR'),'statistics feeds video or clock control')
                terminals.add((name,pin))
            elif kind in ('V_OBUF','V_OBUFT'):
                require(pin=='I' and base.structure.cdc.canon(p['O'])==base.UART
                        and (kind=='V_OBUF' or p.get('T')=="1'b0"),'statistics feeds unrelated pad')
                terminals.add((name,pin))
            else:
                require(kind in ('V_MUX2','V_LUT6CARRY','V_BUF','V_INV'),'unreviewed statistics fanout: '+kind)
                outputs=('Z','Z5','COUT') if kind=='V_LUT6CARRY' else ('Z',)
                for output in outputs:
                    if p.get(output) and net in inputs(cell,output):pending.append(p[output])
                if kind=='V_MUX2':muxes.add(name)
    return {'ActualStatisticsFFs':len(names),'Clock':base.CORE,'Registers':rows,
        'FanoutTerminalCount':len(terminals),'AllStatisticsSequentialInputsSameCoreDomain':True,
        'NoStatisticsFeedbackToVideoRegistersOrOtherPads':True,'TimingAccepted':False,
        'MUX2BooleanModel':{'Path':str(MODEL),'SHA256':MODEL_SHA},
        'StatisticsFanoutMUX2Cells':sorted(muxes),'NativeCellsAndPlacementUnchanged':True}
