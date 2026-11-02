"""CPU-only inspection of a fresh KEY1 view-toggle physical candidate.

This does not execute PDS, alter constraints, accept old physical evidence or
authorize hardware. Query files are requests; only supplied native path reports
can fill their coverage. The original native target bytes are never changed.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import tempfile

import audit_ddr_final_timing as summaries
import camera720_stats_io_cdc as base
import camera720_stats_cdc_proof as mapping
import camera720_stats_native_mux as mux
import camera720_stats_shared_control_delay as controls

ROOT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()
TARGET = 'camera720_view_toggle_top'
CORE = 'ddrphy_sysclk'
TOP = 'board/'+TARGET+'.v'
FDC = 'board/camera720-view-toggle.fdc'
KEY_ATTRIBUTES = dict(DIRECTION='INPUT', LOC='C23', VCCIO='3.3', STANDARD='LVCMOS33', PULLUP='TRUE')
require, io, cdc = base.require, base.io, base.cdc


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def ref(path):
    path = Path(path).resolve()
    return {'Path':str(path), 'SHA256':sha(path)}


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def module_as(text, name):
    clean = io.pin_parser.clean_verilog(text)
    require(re.findall(r'\bmodule\s+(\w+)',clean)==[TARGET], 'one exact view-toggle module required')
    value, count = re.subn(r'(\bmodule\s+)'+TARGET+r'\b', r'\g<1>'+name, text)
    require(count==1, 'ambiguous target module token')
    return value


def declared_inventory(top, fdc):
    normalized = module_as(top, 'board1080_top')
    normalized, count = re.subn(r'module\s+board1080_top\s*#\(.*?\)\s*\(',
                                'module board1080_top(', normalized, count=1, flags=re.S)
    require(count==1, 'view-toggle top parameter declaration differs')
    ports = io.pin_parser.top_ports(normalized)
    declared = io.pin_parser.fdc_pins(fdc)
    require(len(ports)==130 and set(ports)==set(declared), 'all 130 source/FDC ports required')
    require(declared['key1_n']==KEY_ATTRIBUTES and ports['key1_n']=='INPUT', 'KEY1 C23 electrical contract differs')
    require(declared['reset_n']['LOC']=='C22', 'KEY0 C22 must remain reset')
    require(ports['uart_txd']=='OUTPUT' and
            {k:v for k,v in declared['uart_txd'].items() if k!='DIRECTION'}==base.UART_ATTRIBUTES,
            'UART C24 contract differs')
    require(len({p['LOC'] for p in declared.values()})==130, 'duplicate package pin')
    for port, direction in ports.items():
        require(declared[port].get('DIRECTION', direction if port=='uart_txd' else None)==direction,
                'source/FDC direction differs: '+port)
    commands = [l.strip() for l in fdc.splitlines() if l.strip() and not l.lstrip().startswith('#')]
    key_exceptions = [l for l in commands if l.startswith('set_false_path') and 'key1_n' in l]
    require(key_exceptions==['set_false_path -from [get_ports {key1_n}]'], 'only asynchronous KEY1 pad exception expected')
    require(not any(l.startswith('set_false_path') and 'view_control' in l for l in commands),
            'KEY1 synchronizer interstage must remain timed')
    require('create_clock -name camera_pclk -period 20.833 [get_ports cam_pclk]' in commands,
            'camera clock declaration changed')
    require(not any(l.startswith('set_output_delay') for l in commands), 'external output assumption changed')
    return ports, declared


def pin_audit(top, fdc, pcf, prt, exported, official, cam_reference, cam_pins):
    """All 130 pins participate; KEY1 is not projected out for an old count."""
    ports, declared = declared_inventory(top, fdc)
    generated = io.pin_parser.pcf_pins(pcf)
    _, routed = io.pin_parser.routed_pads(prt)
    require(set(ports)==set(generated)==set(routed), 'source/PCF/routed complete pin sets differ')
    exported = module_as(exported,'camera_vga_output_top')
    require(io.netlist_ports(exported)==ports, 'native functional top ports differ')
    scalar_attributes = {}
    for body, direction, port in re.findall(r'\(\*([^*]+)\*\)\s*(input|output|inout)\s+(\w+);',exported):
        attrs = dict(re.findall(r'PAP_IO_(\w+)="([^"]+)"',body))
        require(port in declared and port not in scalar_attributes, 'duplicate/unexpected scalar attributes')
        require(all(attrs.get(k)==v for k,v in declared[port].items()), 'native scalar attributes differ: '+port)
        require(direction.upper()==ports[port], 'native scalar direction differs')
        scalar_attributes[port] = attrs
    _, cells = io.net_parser.parse(exported.replace('module camera_vga_output_top','module board1080_top',1))
    sites = {m[3].lstrip('\\'):m[2].strip() for m in re.finditer(
        r'(?ms)^\s*(V_\w+)\s*/\* ([^*]+) \*/\s*(?:#\s*\(.*?\)\s*)?(\\\S+|[A-Za-z_$][\w$]*)\s*\(',exported)}
    connections = defaultdict(list)
    for cell in cells:
        for pin, value in cell.ports.items():
            if value in ports:
                connections[value].append({'Cell':cell.name,'Primitive':cell.primitive,'Pin':pin,
                    'NativeInstance':cell.name.rsplit('/',1)[0], 'PhysicalSiteComment':sites.get(cell.name),
                    'FunctionalParameters':cell.parameters,'FunctionalPorts':cell.ports})
    require(set(connections)==set(ports), 'functional export leaves port disconnected')
    banks, inventory, differences = defaultdict(list), [], []
    for port, direction in ports.items():
        attrs = declared[port]
        require(direction==routed[port]['Direction'], 'routed direction differs: '+port)
        require(generated[port]=={k:v for k,v in attrs.items() if k!='DIRECTION'}, 'PCF attributes differ: '+port)
        require(attrs['LOC']==routed[port]['Pad'], 'routed package pin differs: '+port)
        for conn in connections[port]:
            if conn['PhysicalSiteComment']:
                require(conn['PhysicalSiteComment']==routed[port]['Site'], 'functional pad site differs: '+port)
            for field, parameter in (('STANDARD','IOSTANDARD'),('DRIVE','DRIVE_STRENGTH'),('SLEW','SLEW_RATE')):
                value = conn['FunctionalParameters'].get(parameter,'').strip('"')
                require(field!='STANDARD' or not value or value==attrs[field], 'functional IO standard differs')
                if value and field in attrs and value!=attrs[field]:
                    differences.append({'Port':port,'Cell':conn['Cell'],'Attribute':field,
                        'FDCAndPCF':attrs[field],'FunctionalLibraryParameter':value})
        banks[routed[port]['Bank']].append(port)
        inventory.append({'Port':port,**attrs,'DIRECTION':direction,'Site':routed[port]['Site'],
            'Bank':routed[port]['Bank'],'NativeFunction':routed[port]['Function'],
            'FinalPrimitiveConnections':connections[port]})
    bank_summary = {}
    for bank, names in banks.items():
        volts = {declared[n]['VCCIO'] for n in names}
        require(len(volts)==1, 'mixed declared bank voltage')
        bank_summary[bank] = {'Ports':len(names),'DeclaredVCCIO':next(iter(volts)),
            'Standards':dict(Counter(declared[n]['STANDARD'] for n in names))}
    reference = io.pin_parser.fdc_pins(official)
    ddr = {n for n in ports if n.startswith('mem_')}
    require(len(ddr)==71 and all(declared[n]==reference[n] for n in ddr), 'DDR reference attributes differ')
    require(all(declared[n]==reference[n] for n in ('clk_p','clk_n')), 'DDR reference clock attributes differ')
    raw = io.pin_parser.fdc_pins(cam_reference)
    require(len(io.CAM_PORTS)==14 and all({k:v for k,v in declared[n].items() if k!='DIRECTION'}==raw[n]
            and declared[n]['LOC']==cam_pins[n] for n in io.CAM_PORTS), 'CAM2 reference mapping differs')
    require(declared['cam_data[5]']['LOC']=='AA23', 'CAM2 D5 differs')
    for port in ('key1_n','uart_txd'):
        require(port in scalar_attributes and len(connections[port])==1,
                'native key/UART pad connection count differs')
        pad_connection(port,connections[port][0])
    return {'Target':TARGET,'TopPortCount':len(ports),'PinInventory':sorted(inventory,key=lambda r:r['Port']),
        'DDRMemoryPins':len(ddr),'CAM2Pins':len(io.CAM_PORTS),'Banks':bank_summary,
        'DeclarationAndSourceBuildMappingPassed':True,'FinalFunctionalPortConnectionsPassed':True,
        'FinalScalarAttributePortsVerified':len(scalar_attributes),'FunctionalLibraryParameterDifferences':differences,
        'FinalNativeElectricalAttributesVerified':False,'FinalNativeSiteMappingPassed':False,
        'Limit':'Functional library DRIVE/SLEW defaults do not establish actual native electrical settings.'}


def pad_connection(port, connection):
    if port=='key1_n':
        require(connection['Primitive']=='V_IBUF' and connection['Pin']=='I',
                'native KEY1 input pad connection differs')
    else:
        require(port=='uart_txd' and connection['Primitive'] in ('V_OBUF','V_OBUFT')
                and connection['Pin']=='O' and (connection['Primitive']=='V_OBUF'
                or connection['FunctionalPorts'].get('T')=="1'b0"),
                'native UART output pad must remain enabled')


def graph(text):
    # Keep original graph names, wires, placements and primitive parameters;
    # adapt only the unique top token expected by the reused flat parser.
    return mux.Graph(base.structure.functional(module_as(text,base.structure.prep.TARGET)))


def support(g, net, active=()):
    require(net not in active, 'cycle in view-control cone')
    if net in ("1'b0","1'b1"):
        return set()
    drivers = g.outputs.get(net,[])
    if not drivers:
        return {('primary',net)}
    require(len(drivers)==1, 'view-control net has ambiguous driver')
    name, pin = drivers[0]
    cell = g.cells[name]
    if name in g.ff:
        require(pin=='Q', 'view-control sequential launch is not Q')
        return {('ff',name)}
    if cell['Primitive']=='V_IBUF':
        require(pin=='O', 'view input buffer pin differs')
        return support(g,cell['Ports']['I'],active+(net,))
    require(cell['Primitive'] in ('V_MUX2','V_LUT6CARRY','V_BUF','V_INV'), 'unsupported view-control cone primitive')
    result = set()
    for source in mux.inputs(cell,pin):
        result |= support(g,source,active+(net,))
    return result


def terminals(g, start):
    """Exact relevant Boolean fanout, stopping at sequential/pad consumers."""
    seen, ends, pending = set(), set(), [start]
    while pending:
        net = pending.pop()
        if net in seen:
            continue
        seen.add(net)
        for name, pin in g.refs.get(net,[]):
            if (name,pin) in g.outputs.get(net,[]):
                continue
            c = g.cells[name]
            if name in g.ff or c['Primitive'] in ('V_OBUF','V_OBUFT'):
                ends.add((name,pin))
                continue
            require(c['Primitive'] in ('V_IBUF','V_MUX2','V_LUT6CARRY','V_BUF','V_INV'),
                    'unreviewed view-control fanout primitive: '+name)
            if c['Primitive']=='V_IBUF':
                require(pin=='I', 'wrong key IBUF input')
                pending.append(c['Ports']['O'])
            else:
                for output in (('Z','Z5','COUT') if c['Primitive']=='V_LUT6CARRY' else ('Z',)):
                    if c['Ports'].get(output) and net in mux.inputs(c,output):
                        pending.append(c['Ports'][output])
    return ends


def key_audit(g):
    raw_ends=terminals(g,'key1_n')
    require(len(raw_ends)==1, 'raw KEY1 has ambiguous first sequential consumer')
    first,first_pin=next(iter(raw_ends))
    require(first in g.ff and first_pin=='D' and first.startswith('view_control/key_sync[0]/'),
            'raw KEY1 first consumer is not the declared first synchronizer')
    stage_ends=terminals(g,g.ff[first]['Ports']['Q'])
    require(len(stage_ends)==1, 'KEY1 first stage has ambiguous second consumer')
    second,second_pin=next(iter(stage_ends))
    require(second in g.ff and second_pin=='D' and second!=first
            and second.startswith(('view_control/key_sync[0]/','view_control/key_sync[1]/')),
            'KEY1 second stage is not the declared packed or separate synchronizer')
    names = sorted(n for n in g.ff if n.startswith('view_control/'))
    require(names, 'view controller physical FFs absent')
    rows = []
    for name in names:
        ports = g.ff[name]['Ports']
        require(g.clock(ports['CK'])['Domain']==CORE, 'view controller clock differs')
        cones = {}
        for pin in ('D','CE','SR'):
            if pin not in ports:
                continue
            leaves = support(g,ports[pin])
            primaries = {n for kind,n in leaves if kind=='primary'}
            require(primaries==({'key1_n'} if name==first and pin=='D' else set()),
                    'view-control primary input bypass: '+name+'/'+pin)
            require(all(kind=='primary' or g.clock(g.ff[n]['Ports']['CK'])['Domain']==CORE for kind,n in leaves),
                    'view-control sequential input crosses a clock')
            cones[pin] = sorted([kind,n] for kind,n in leaves)
        rows.append({'FF':name,'Clock':CORE,'SequentialSupport':cones})
    require(terminals(g,'key1_n')=={(first,'D')}, 'raw KEY1 must only reach first synchronizer D')
    require(terminals(g,g.ff[first]['Ports']['Q'])=={(second,'D')}, 'first stage fanout escapes second D')
    require(('ff',first) in support(g,g.ff[second]['Ports']['D']), 'second stage misses first Q')
    release = g.by_q('core_reset[1]')
    chain = g.chain(first,second,'KEY1 view request synchronizer',g.ff[release]['Ports']['Q'])
    modes = [n for n in g.ff if n.startswith('view_control/corrected_requested/')]
    require(len(modes)==1 and modes[0].startswith('view_control/'), 'one registered requested mode required')
    ends = terminals(g,g.ff[modes[0]]['Ports']['Q'])
    require(ends, 'requested mode has no physical consumer')
    mode_rows, mapper_sinks, led_sinks = [], [], []
    for name,pin in sorted(ends):
        c = g.cells[name]
        if name in g.ff:
            require(pin in ('D','CE','SR') and g.clock(c['Ports']['CK'])['Domain']==CORE,
                    'requested mode drives clock or foreign-domain register')
            require(name.startswith(('view_control/','system/bank_core/engine/core/mapper/')),
                    'requested mode escapes controller or frame-latched mapper config: '+name)
            if name.startswith('system/'):
                mapper_sinks.append(name)
        else:
            require(pin=='I' and base.structure.cdc.canon(c['Ports'].get('O',''))=='led[0]',
                    'requested mode feeds unexpected pad')
            led_sinks.append(name)
        mode_rows.append({'Cell':name,'Pin':pin})
    require(mapper_sinks and len(led_sinks)==1, 'mode must feed mapper configuration and requested-mode LED0')
    return {'Passed':True,'InputPort':'key1_n','Clock':CORE,'First':first,'Second':second,
        'Chain':chain,'ControllerRegisters':rows,'ModeFF':modes[0],'ModeTerminals':mode_rows,
        'RawPadOnlyFeedsFirstD':True,'FirstOnlyFeedsSecondD':True,
        'FirstStageExternalSetupHoldAccepted':False,'InterstageTimingAccepted':False,
        'LEDMeaning':'requested mode, not presentation confirmation'}


def header_check(path):
    with Path(path).open(encoding='gb18030') as f:
        head = ''.join(next(f,'') for _ in range(18))
    require('2023.2-SP3 <build 154097>' in head and
            re.search(r'^\| Design\s*:\s*'+TARGET+r'\s*$',head,re.M), 'native timing target/version differs')
    for label,value in (('Device','PG2L100H'),('Speed Grade','-6'),('Package','FBG676')):
        require(re.search(r'^\| '+label+r'\s*:\s*'+re.escape(value)+r'\s*$',head,re.M),
                'native timing device differs: '+label)
    return head


def timing_summary(path):
    header_check(path)
    with Path(path).open(encoding='gb18030') as f:
        tables, clocks = summaries.parse_summaries(f)
    rows = []
    for (corner,kind), table in sorted(tables.items()):
        for names, value in sorted(table.items()):
            rows.append({'Corner':corner,'Kind':kind,'Clocks':list(names),**value})
    passed = all(r['WorstSlackNS']>=0 and r['TotalNegativeSlackNS']==0 and r['FailingChecks']==0 for r in rows)
    return {'Report':ref(path),'AllTenTablesPresent':True,'Rows':rows,'Clocks':clocks,
            'AllSummaryChecksPassed':passed,'ExternalACTimingAccepted':False}


def collect(queries,reports):
    lookup = {cdc.timing.identity(q):q for q in queries}
    require(len(lookup)==len(queries),'duplicate CDC query identity')
    pairs = {(q['Source'],q['Endpoint']) for q in queries}
    rows, violations, other, seen = [], [], Counter(), set()
    for report in sorted({Path(p).resolve() for p in reports}):
        header_check(report)
        for lines,line in cdc.timing.native.blocks(report):
            text = ''.join(lines)
            source = cdc.timing.field(r'^Startpoint\s*:\s*(.+?)\s*$',text,'source')
            endpoint = cdc.timing.field(r'^Endpoint\s*:\s*(.+?)\s*$',text,'endpoint')
            if (source,endpoint) not in pairs:
                continue
            try:
                key = source,cdc.timing.launch_row(text)['LaunchOutput'],endpoint
                if key not in lookup:
                    other[key] += 1
                    continue
                value = cdc.timing.parse_record(lines,report,line,lookup[key])
            except ValueError as exc:
                violations.append({'Source':source,'Endpoint':endpoint,'Report':str(report),'ReportLine':line,'Error':str(exc)})
                continue
            if value['PathSHA256'] not in seen:
                seen.add(value['PathSHA256'])
                rows.append(value)
    return rows, violations, [dict(zip(cdc.timing.IDENTITY,k),ObservedVariants=n) for k,n in sorted(other.items())]


def append_key_relationship(key,logical,internal):
    chain = key['Chain']
    if chain['SameBLE']:
        internal.append({'SourceFF':key['First'],'DestinationFF':key['Second'],'DestinationPin':'D',
            'Label':chain['Label'],'Placement':chain['FirstPlacement'],
            'Reason':'New KEY1 first-to-second same-BLE pair requires current native reclassification.'})
    else:
        logical.append({'SourceFF':key['First'],'DestinationFF':key['Second'],'DestinationPin':'D',
            'SourceClock':CORE,'DestinationClock':CORE,'Labels':[chain['Label']],
            'Purposes':['ordinary KEY1 interstage timing'],
            'OriginalEndpoints':[q['Endpoint'] for q in chain['NativeQueries']]})


def derive(build,export,route,extra_reports=()):
    build, export, route = (Path(p).resolve() for p in (build,export,route))
    paths = {'plan':build/'plan.json','top':build/'compiled'/TOP,'fdc':build/'compiled'/FDC,
        'pcf':build/'device_map'/(TARGET+'.pcf'),
        'prt':build/'place_route'/(TARGET+'_prr_route_optimize.prt'),
        'netlist':export/'generate_netlist'/(TARGET+'_sim.v'),
        'report':export/'report_timing'/(TARGET+'.rtr'),
        'adf':export/'input.adf','route_adf':route/'input.adf','route':route/'route-dump.txt',
        'official':ROOT/'platform/video_base/HDMI_IN_DDR3_HDMI_OUT_top.fdc',
        'camref':ROOT/'board/raw_camera_capture_cam2_ref.fdc',
        'campins':ROOT/'board/raw_camera_capture_cam2_ref-pins.json'}
    require(all(p.is_file() for p in paths.values()), 'missing actual physical input: '+str([str(p) for p in paths.values() if not p.is_file()]))
    bindings = {str(p):sha(p) for p in paths.values()}
    plan = read(paths['plan'])
    require(plan['Schema']=='camera720-view-toggle-build-v1' and plan['Target']==TARGET,
            'wrong fresh build plan')
    for name,digest in {**plan['InputSHA256'],**plan['PreparedSHA256']}.items():
        require(sha(name)==digest, 'fresh build source drift: '+name)
        bindings[name] = digest
    require(sha(paths['adf'])==sha(paths['route_adf']), 'export and route derive from different candidates')
    text = {k:paths[k].read_text(encoding='utf-8-sig') for k in ('top','fdc','pcf','prt','netlist','official','camref')}
    pins = pin_audit(text['top'],text['fdc'],text['pcf'],text['prt'],text['netlist'],
                     text['official'],text['camref'],read(paths['campins']))
    g = graph(text['netlist'])
    key = key_audit(g)
    control = controls.audit(g)
    telemetry = mux.audit(g.g)
    logical,internal,placements,parents = base.cdc_inputs(g,text['netlist'])
    append_key_relationship(key,logical,internal)
    parents.update(cdc.endpoints.base.native_parent(key[k]) for k in ('First','Second'))
    parents.update(s.rsplit('/',1)[0] for s in base.uart_launches(g))
    with tempfile.TemporaryDirectory(prefix='view-toggle-route-') as tmp:
        normalized = Path(tmp)/'normalized.adif'
        normalization = cdc.normalize_source_locations(paths['route'],normalized)
        native = cdc.endpoints.route_objects(normalized,parents)
    constraints,_ = cdc.endpoints.base.constraint_inventory(paths['fdc'])
    inventory = mapping.mapped_inventory(g,native,logical,internal,placements,constraints,
        ref(paths['adf']),sha(paths['plan']),telemetry)
    inventory['Target'] = TARGET
    reports = [paths['report'],*map(Path,extra_reports)]
    for p in reports:
        bindings[str(p.resolve())] = sha(p)
    records,violations,other = collect(inventory['Queries'],reports)
    coverage = cdc.timing.coverage(inventory['Queries'],records,violations)
    groups,bodies = base.cdc_query_bodies(inventory['Queries'],coverage['MissingCases'])
    pairs,pair_sources = mapping.dvp_query_pairs(paths['report'])
    io_body = mapping.uart_query_body(pins,pairs,base.video.tx_launches(g),inventory['UARTSourceOutputs'])
    for p in base.structure.local_helpers((base,mapping,mux,controls,summaries)):
        bindings[str(p)] = sha(p)
    bindings[str(SELF)] = sha(SELF)
    bindings[str(mux.MODEL)] = sha(mux.MODEL)
    require(all(sha(n)==h for n,h in bindings.items()), 'input drift during physical audit')
    result = {'Schema':'camera720-view-toggle-physical-audit-v1','Target':TARGET,
        'CandidateADF':ref(paths['adf']),'BuildPlan':ref(paths['plan']),'InputSHA256':bindings,
        'Pins':pins,'Key':key,'InputDelays':control,'Telemetry':telemetry,
        'TimingSummary':timing_summary(paths['report']),'CDC':inventory,
        'NativeRouteNormalization':normalization,'Constraints':constraints,
        'CDCRecords':records,'CDCViolations':violations,'OtherLaunches':other,'CDCCoverage':coverage,
        'MissingQueryGroups':groups,'DVPQuerySources':pair_sources,
        'NativeElectricalParametersVerified':False,'NativeQueryReceiptBindingPerformed':False,
        'HardwareReleaseAllowed':False,'InheritedPhysicalAcceptance':False,
        'Limits':'Pure parsers inspect supplied candidate artifacts. Native execution/ADF provenance, targeted query receipt binding, actual pad electrical settings and reset/data timing closure remain separate requirements.'}
    return result,bodies,io_body


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--build-dir',type=Path,required=True)
    p.add_argument('--export-dir',type=Path,required=True)
    p.add_argument('--route-dir',type=Path,required=True)
    p.add_argument('--report',type=Path,action='append',default=[])
    p.add_argument('--output',type=Path,required=True)
    a = p.parse_args()
    output = a.output.resolve()
    require(not output.exists() and output.parent.is_dir(), 'fresh output JSON required')
    result,bodies,io_body = derive(a.build_dir,a.export_dir,a.route_dir,a.report)
    query_dir = output.with_suffix('')
    require(not query_dir.exists(), 'fresh query directory required')
    query_dir.mkdir()
    for name,body in bodies.items():
        (query_dir/name).write_text(body,encoding='ascii',newline='\n')
    (query_dir/'io.tcl').write_text(io_body,encoding='ascii',newline='\n')
    result['QueryFiles'] = [ref(q) for q in sorted(query_dir.iterdir())]
    with output.open('x',encoding='utf-8',newline='\n') as f:
        json.dump(result,f,indent=2)
        f.write('\n')
    print(json.dumps({'Output':str(output),'Pins':result['Pins']['TopPortCount'],
        'SummaryPassed':result['TimingSummary']['AllSummaryChecksPassed'],
        'CDCCoverage':{k:v for k,v in result['CDCCoverage'].items() if k not in ('CaseCoverage','MissingCases')},
        'MissingCases':len(result['CDCCoverage']['MissingCases']),'QueryFiles':len(result['QueryFiles'])}))


if __name__=='__main__':
    main()
