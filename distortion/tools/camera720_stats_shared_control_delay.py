"""Ten native input delays; capture and monitor share delayed controls.

Each control IBUF has only its own delay as consumer. The fixed delay is a
nominal primitive setting; native PVT timing is separate evidence.
"""
import re

import audit_calibrated_camera_input_delay as data
import audit_camera720_monitor as monitor

SCHEMA='camera720-shared-control-input-delay-v1'
require,one=data.require,data.one
CAP,MONITOR=monitor.base.CAP,monitor.PREFIX
CONTROL_SIGNALS={'cam_href':0,'cam_vsync':1}


def audit(graph):
    require(not re.search(r'\b(?:assign|always|initial|function|task|generate|tran|buf|not)\b',
                          graph.g['ModuleDeclarations']),'unparsed native aliases or logic')
    delays={n:c for n,c in graph.cells.items() if c['Primitive']=='V_ZEROHOLDDELAY'}
    require(len(delays)==10,'exactly ten native camera input delay cells required')
    references=data.references(graph);controls={};rows=[]
    for pad,index in CONTROL_SIGNALS.items():
        buffer=one([n for n,c in graph.cells.items() if c['Primitive']=='V_IBUF' and c['Ports'].get('I')==pad],pad+' IBUF')
        bc=graph.cells[buffer];raw=bc['Ports'].get('O')
        require(set(bc['Ports'])=={'I','O'} and raw and
                bc['Parameters']=={'IOSTANDARD':'"LVCMOS33"','TERM_DDR':'"ON"'},'control input buffer differs')
        name=one([n for n,c in delays.items() if c['Ports'].get('DI')==raw],pad+' delay')
        delay=delays[name];delayed=delay['Ports'].get('DO')
        require(set(delay['Ports'])=={'DI','DO'} and delayed and delay['Parameters']=={'ZHOLD_SET':'"1500ps"'},
                'control delay ports or setting differ')
        require(name.startswith(f'camera_control_delay/control_bit[{index}].') or
                name.startswith(f'camera_control_delay/control_bit[{index}]/'),'control delay bit hierarchy differs')
        require(len({pad,raw,delayed})==3 and references(pad)=={(buffer,'I')},'control input aliases or pad bypass')
        require(references(raw)=={(buffer,'O'),(name,'DI')},'pre-delay IBUF output must exclusively drive its delay')
        require(name not in controls,'controls share a delay primitive')
        controls[name]=pad
        seen,active,sinks,logic=set(),set(),{'capture':set(),'monitor':set()},set()

        def visit(net,origin):
            net=data.scalar(net)
            require(net not in active,'control fanout combinational cycle')
            if net in seen:return
            active.add(net);refs=references(net)
            require(origin in refs,'control driver absent from actual graph')
            for cellname,pin in sorted(refs-{origin}):
                cell=graph.cells[cellname];kind,p=cell['Primitive'],cell['Ports']
                if cellname in graph.ff:
                    role='capture' if cellname.startswith(CAP) else 'monitor' if cellname.startswith(MONITOR) else None
                    require(role is not None and pin in ('D','CE','SR'),'delayed control reaches noncapture/nonmonitor FF or clock')
                    require(graph.clock(p['CK'])['Domain']=='camera_pclk','control sampled outside camera domain')
                    sinks[role].add((cellname,pin,kind,'CK'));continue
                if kind=='V_DRM36K_E1':
                    require(cellname.startswith(CAP+'pixels/') and pin in ('WEA','CSA'),'unreviewed delayed control memory sink')
                    require(all(cell['Parameters'].get(k)==v for k,v in data.DRM_PARAMETERS.items())
                            and graph.clock(p['CLKA'])['Domain']=='camera_pclk','control memory mode/clock differs')
                    sinks['capture'].add((cellname,pin,kind,'CLKA'));continue
                require(kind in data.COMBINATIONAL and pin in data.COMBINATIONAL[kind][0],
                        'unreviewed delayed control primitive: '+cellname+'/'+pin)
                logic.add(cellname)
                for output in sorted(data.COMBINATIONAL[kind][1]):
                    if p.get(output) and net in {data.scalar(n) for n in monitor.immediate_support(cell,output)[0]}:
                        visit(p[output],(cellname,output))
            active.remove(net);seen.add(net)

        visit(delayed,(name,'DO'))
        require(sinks['capture'] and sinks['monitor'],'both delayed capture and delayed monitor sinks required')
        inventory=lambda role:{'FirstSequentialSinks':[{'Cell':n,'Pin':p,'Primitive':k,'ClockPin':ck,
            'Clock':'camera_pclk','SamplingEdge':'rising'} for n,p,k,ck in sorted(sinks[role])]}
        rows.append({'Pad':pad,'Bit':index,'InputBuffer':buffer,'RawNet':raw,'DelayCell':name,
            'DelayedNet':delayed,'DelaySetting':'1500ps','PreDelayConsumerIsOnlyOwnDelay':True,
            'DelayedMonitor':inventory('monitor'),'DelayedCapture':inventory('capture'),
            'CombinationalCells':sorted(logic),'EnumeratedNets':len(seen),'NoControlBypass':True})
    projected={**graph.g,'Cells':{n:c for n,c in graph.cells.items() if n not in controls}}
    data_proof=data.audit(monitor.Graph(projected))
    data_names={row['DelayCell'] for row in data_proof['Bits']}
    require(len(data_names)==8 and data_names.isdisjoint(controls) and data_names|set(controls)==set(delays),
            'data/control proofs do not partition all ten actual delay cells')
    return {'Schema':SCHEMA,'Passed':True,'ExpectedControlSignals':2,'NativeDelayCells':len(delays),
        'ControlDelayCells':len(controls),'DataDelayCells':len(data_names),'NominalDelayPS':1500,
        'Signals':sorted(rows,key=lambda r:r['Bit']),'AllCaptureControlConsumersTraverseOwnDelay':True,
        'MonitorAfterControlDelay':True,'AllControlConsumersDelayed':True,'RawMonitorPathPreserved':False,
        'ControlFanoutUsesExactCombinationalOutputSupport':True,'DataDelayProof':data_proof,
        'DataScopeProjection':{'ExcludedIndependentlyVerifiedControlCells':sorted(controls),
            'AllOtherCellsPreserved':True,'OriginalGraphMutated':False},
        'ActualPVTDelayFromSettingAloneProven':False,'ExternalACTimingAccepted':False,
        'TimingAccepted':False,'HardwareReleaseAllowed':False}
