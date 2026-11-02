"""Pure candidate-specific IO/CDC adapter for the isolated statistics build.

No native execution, receipt trust, historical timing, or release authority is
provided here. The caller must bind fresh stats-target export, route, constraints
and reports, and must re-derive after any netlist or routing change.
"""
from collections import Counter, defaultdict
from pathlib import Path
import re

import camera720_calibrated_io_adapter as video
import camera720_calibrated_cdc as cdc
import camera720_calibrated_cdc_proof as grouped

TARGET = 'camera720_calibrated_stats_top'
SCHEMA = 'camera720-calibrated-stats-io-cdc-structure-v1'
UART = 'uart_txd'
PREFIX = 'core_statistics/'
CORE = 'ddrphy_sysclk'
UART_ATTRIBUTES = dict(LOC='C24', VCCIO='3.3', STANDARD='LVCMOS33', DRIVE='4', SLEW='SLOW')
structure, native_io = video.structure, video.native_io
io = structure.io
require = structure.require


def module_as(text, name):
    clean = io.pin_parser.clean_verilog(text)
    require(re.findall(r'\bmodule\s+(\w+)', clean) == [TARGET], 'one exact statistics module required')
    value, count = re.subn(r'(\bmodule\s+)'+TARGET+r'\b', r'\g<1>'+name, text)
    require(count == 1, 'ambiguous statistics module token')
    return value


def source_ports(top):
    text = module_as(top, 'camera_vga_output_top')
    text, count = re.subn(r'module\s+camera_vga_output_top\s*#\(.*?\)\s*\(',
                          'module board1080_top(', text, count=1, flags=re.S)
    require(count == 1, 'statistics top parameter declaration differs')
    return io.pin_parser.top_ports(text)


def declared_inventory(top, fdc):
    ports = source_ports(top)
    declared = io.pin_parser.fdc_pins(fdc)
    require(len(ports) == 129 and set(ports) == set(declared), 'all 129 statistics source/FDC ports required')
    require(ports.get(UART) == 'OUTPUT', 'UART must be an output')
    uart = declared[UART]
    require({k:v for k,v in uart.items() if k != 'DIRECTION'} == UART_ATTRIBUTES,
            'exact C24 UART electrical attributes required')
    require('DIRECTION' not in uart or uart['DIRECTION'] == 'OUTPUT', 'UART FDC direction differs')
    for port, direction in ports.items():
        if port != UART:
            require(declared[port].get('DIRECTION') == direction, 'source/FDC direction differs: '+port)
    require(len({row['LOC'] for row in declared.values()}) == len(declared), 'duplicate package pin')
    return ports, declared


def source_inventory(top, fdc):
    ports, declared = declared_inventory(top, fdc)
    commands = [line.strip() for line in fdc.splitlines() if line.strip() and not line.lstrip().startswith('#')]
    require(all(ports.get(p) == 'INPUT' for p in native_io.PORTS), 'DVP interface differs')
    require(all(ports.get(p) == 'OUTPUT' for p in native_io.tx.PORTS), 'TX interface differs')
    require('create_clock -name camera_pclk -period 20.833 [get_ports cam_pclk]' in commands,
            'provisional camera clock differs')
    require(not any(c.startswith('set_output_delay') for c in commands), 'unreviewed external output budget')
    return {'Schema':SCHEMA, 'Target':TARGET, 'PortCount':len(ports), 'Ports':dict(sorted(ports.items())),
        'DVPInputs':sorted(native_io.PORTS), 'TXOutputs':sorted(native_io.tx.PORTS),
        'UART':{'Port':UART, 'Attributes':declared[UART], 'SourceDirection':'OUTPUT',
                'FDCDirectionExplicit':'DIRECTION' in declared[UART], 'ExternalACAccepted':False},
        'PhysicalEvidenceVerified':False, 'TimingAccepted':False, 'HardwareReleaseAllowed':False}


def graph(netlist):
    return video.graph(module_as(netlist, video.TARGET))


def stats_domain(current):
    """Check actual new FF cones and fanout, not a source-level CDC promise."""
    names = sorted(n for n in current.ff if n.startswith(PREFIX))
    require(names, 'actual statistics FFs absent')
    rows = []
    for name in names:
        ports = current.ff[name]['Ports']
        require(current.clock(ports['CK'])['Domain'] == CORE, 'statistics FF clock differs: '+name)
        support = {}
        for pin in ('D','CE','SR'):
            if pin not in ports:
                continue
            leaves = structure.monitor.support(current, ports[pin])
            require(all(kind == 'ff' and current.clock(current.ff[n]['Ports']['CK'])['Domain'] == CORE
                        for kind,n in leaves), 'statistics data/enable/reset cone crosses a clock or primary input')
            support[pin] = sorted(n for _,n in leaves)
        rows.append({'FF':name, 'Clock':CORE, 'SequentialSupport':support})
    # Follow Boolean-relevant outputs only: a packed LUT may also implement an
    # unrelated video function, which must not count as telemetry feedback.
    visited, terminals = set(), set()
    pending = [current.ff[n]['Ports']['Q'] for n in names]
    while pending:
        net = pending.pop()
        if net in visited:
            continue
        visited.add(net)
        for name,pin in current.refs.get(net, []):
            if (name,pin) in current.outputs.get(net, []):
                continue
            cell = current.cells[name]
            kind, ports = cell['Primitive'], cell['Ports']
            if name in current.ff:
                require(name.startswith(PREFIX) and pin in ('D','CE','SR'), 'statistics feeds video or clock control')
                terminals.add((name,pin))
            elif kind in ('V_OBUF','V_OBUFT'):
                require(pin == 'I' and structure.cdc.canon(ports['O']) == UART
                        and (kind == 'V_OBUF' or ports.get('T') == "1'b0"), 'statistics feeds unrelated pad')
                terminals.add((name,pin))
            elif kind in ('V_BUF','V_INV'):
                require(pin == 'I', 'statistics buffer pin differs')
                pending.append(ports['Z'])
            else:
                require(kind == 'V_LUT6CARRY', 'unreviewed statistics fanout primitive: '+kind)
                for output in ('Z','Z5','COUT'):
                    if ports.get(output) and net in structure.monitor.immediate_support(cell,output)[0]:
                        pending.append(ports[output])
    return {'ActualStatisticsFFs':len(names), 'Clock':CORE, 'Registers':rows,
        'FanoutTerminalCount':len(terminals), 'AllStatisticsSequentialInputsSameCoreDomain':True,
        'NoStatisticsFeedbackToVideoRegistersOrOtherPads':True, 'TimingAccepted':False}


def uart_launches(current):
    buffers = [n for n,c in current.cells.items() if c['Primitive'] in ('V_OBUF','V_OBUFT')
               and structure.cdc.canon(c['Ports'].get('O','')) == UART]
    require(len(buffers) == 1, 'one actual UART output buffer required')
    cell = current.cells[buffers[0]]
    require(cell['Primitive'] == 'V_OBUF' or cell['Ports'].get('T') == "1'b0", 'UART tristate must be inactive')
    leaves = structure.monitor.support(current,cell['Ports']['I'])
    require(leaves and all(kind == 'ff' and n.startswith(PREFIX)
            and current.clock(current.ff[n]['Ports']['CK'])['Domain'] == CORE for kind,n in leaves),
            'UART launch is not an actual core statistics register')
    return sorted({structure.cdc.native_parent(n)+'/CLK' for _,n in leaves})


def cdc_inputs(current, netlist):
    """Fresh logical inventory plus parents needed by the native route parser."""
    logical, internal, _ = cdc.endpoints.logical_relationships(current)
    placements = cdc.clm.placed_luts(netlist,current)
    parents = {cdc.endpoints.base.native_parent(r[k]) for r in logical+internal for k in ('SourceFF','DestinationFF')}
    parents.update(n.rsplit('/',2)[0] for n in placements)
    return logical, internal, placements, parents


def map_cdc(current, route, logical, internal, placements, constraints, candidate, build_plan_sha):
    require(isinstance(candidate,dict) and re.fullmatch('[0-9a-f]{64}',candidate.get('SHA256',''))
            and re.fullmatch('[0-9a-f]{64}',build_plan_sha), 'explicit current candidate/build identity required')
    mapper = cdc.clm.Mapper(current,route,placements)
    mapped = [mapper.map(row) for row in logical]
    supplement = cdc.sameble.derive(current,route,{'Schema':'camera720-native-endpoints-v1',
        'SameBLEInterstageInventory':internal, 'LogicalRelationships':mapped, 'Queries':[],
        'CandidateADF':candidate, 'BuildPlanSHA256':build_plan_sha}) if internal else {
        'LogicalRelationships':[], 'DirectInternalRows':[], 'Queries':[]}
    mapped.extend(mapper.map(row) for row in supplement['LogicalRelationships'])
    queries = cdc.make_queries(mapped,constraints)
    return {'Schema':SCHEMA, 'Target':TARGET, 'CandidateADF':candidate, 'BuildPlanSHA256':build_plan_sha,
        'ActualCells':len(current.cells), 'ActualFFs':len(current.ff),
        'LogicalRelationships':mapped, 'SameBLESupplement':supplement, 'Queries':queries,
        'NativeLUTBindings':cdc.endpoints.native_lut_bindings(current,route,mapped),
        'InternalCarryLinks':mapper.carry_links, 'StatisticsDomain':stats_domain(current),
        'TimingAccepted':False, 'HardwareReleaseAllowed':False}


def collect(queries, reports):
    """Strict stats report header, then the existing exact Q-qualified parser."""
    lookup = {cdc.timing.identity(q):q for q in queries}
    require(len(lookup) == len(queries), 'duplicate statistics query identity')
    pairs = {(q['Source'],q['Endpoint']) for q in queries}
    rows, violations, other, seen = [], [], Counter(), set()
    for report in sorted({Path(p).resolve() for p in reports}):
        with report.open(encoding='gb18030') as stream:
            head = ''.join(next(stream,'') for _ in range(18))
        require('2023.2-SP3 <build 154097>' in head and re.search(r'^\| Design\s*:\s*'+TARGET+r'\s*$',head,re.M),
                'statistics report target/version differs')
        for lines,line in cdc.timing.native.blocks(report):
            text = ''.join(lines)
            source = cdc.timing.field(r'^Startpoint\s*:\s*(.+?)\s*$',text,'source')
            endpoint = cdc.timing.field(r'^Endpoint\s*:\s*(.+?)\s*$',text,'endpoint')
            if (source,endpoint) not in pairs:
                continue
            try:
                key = (source,cdc.timing.launch_row(text)['LaunchOutput'],endpoint)
                if key not in lookup:
                    other[key] += 1
                    continue
                value = cdc.timing.parse_record(lines,report,line,lookup[key])
            except ValueError as error:
                violations.append({'Source':source,'Endpoint':endpoint,'Report':str(report),'ReportLine':line,'Error':str(error)})
                continue
            if value['PathSHA256'] not in seen:
                seen.add(value['PathSHA256']); rows.append(value)
    return rows, violations, [dict(zip(cdc.timing.IDENTITY,k),ObservedVariants=n) for k,n in sorted(other.items())]


def cdc_query_bodies(queries, missing, per_body=8):
    # Group only actual fresh identities; complete coverage is checked later.
    groups = grouped.groups(queries,missing)
    return groups, cdc.bodies(groups,per_body)


def io_query_body(pins, dvp_pairs, video_launches, uart_sources):
    ports = {r['Port'] for r in pins['PinInventory']}
    require(pins['TopPortCount'] == len(pins['PinInventory']) == len(ports) == 129
            and ports >= native_io.PORTS | native_io.tx.PORTS | {UART},
            'fresh 129-port native inventory required')
    require(uart_sources and len(uart_sources) == len(set(uart_sources))
            and all(cdc.SAFE.fullmatch(s) and s.startswith(PREFIX) and s.endswith('/CLK') for s in uart_sources),
            'actual UART core native launch required')
    body = video.query_body(pins,dvp_pairs,video_launches)
    return body+'# UART pad propagation observation only; no external AC threshold.\n'+(
        'report_path_timing -delay_type min_max -max_path 1000 -nworst 8 -report_exception TRUE -from {'+
        ' '.join(sorted(uart_sources))+'} -to {uart_txd}\n')


def pin_audit(top, fdc, pcf, prt, exported, official, cam_reference, cam_pins):
    ports, declared = declared_inventory(top,fdc)
    source_inventory(top,fdc)
    generated = io.pin_parser.pcf_pins(pcf)
    _, routed = io.pin_parser.routed_pads(prt)
    require(set(ports) == set(generated) == set(routed), 'all 129 current ports must match PCF and routed table')
    exported = module_as(exported,'camera_vga_output_top')
    require(io.netlist_ports(exported) == ports, 'statistics native functional top ports differ')
    scalar_attributes = {}
    for body, direction, port in re.findall(r'\(\*([^*]+)\*\)\s*(input|output|inout)\s+(\w+);', exported):
        attrs = dict(re.findall(r'PAP_IO_(\w+)="([^"]+)"', body))
        require(port in declared and port not in scalar_attributes, 'duplicate/unexpected final scalar attributes')
        require(all(attrs.get(k) == v for k,v in declared[port].items()), 'final scalar pad attrs differ: ' + port)
        require(direction.upper() == ports[port], 'final scalar direction differs')
        scalar_attributes[port] = attrs
    _, cells = io.net_parser.parse(exported.replace('module camera_vga_output_top', 'module board1080_top', 1))
    sites = {m[3].lstrip('\\'): m[2].strip() for m in re.finditer(
        r'(?ms)^\s*(V_\w+)\s*/\* ([^*]+) \*/\s*(?:#\s*\(.*?\)\s*)?(\\\S+|[A-Za-z_$][\w$]*)\s*\(', exported)}
    connections = defaultdict(list)
    for cell in cells:
        for pin, value in cell.ports.items():
            if value in ports:
                connections[value].append({'Cell': cell.name, 'Primitive': cell.primitive, 'Pin': pin,
                                           'NativeInstance': cell.name.rsplit('/', 1)[0],
                                           'PhysicalSiteComment': sites.get(cell.name),
                                           'FunctionalParameters': cell.parameters})
    require(set(connections) == set(ports), 'final export leaves a port without a primitive connection')
    banks, inventory, parameter_deltas = defaultdict(list), [], []
    for port, direction in ports.items():
        attrs = declared[port]
        require(attrs.get('DIRECTION', direction if port == UART else None) == direction == routed[port]['Direction'], 'pin direction differs: ' + port)
        require(generated[port] == {k:v for k,v in attrs.items() if k != 'DIRECTION'}, 'PCF electrical attrs differ: ' + port)
        require(attrs['LOC'] == routed[port]['Pad'], 'native package mapping differs: ' + port)
        for conn in connections[port]:
            if conn['PhysicalSiteComment']:
                require(conn['PhysicalSiteComment'] == routed[port]['Site'], 'functional pad site differs: ' + port)
            for field, parameter in (('STANDARD','IOSTANDARD'), ('DRIVE','DRIVE_STRENGTH'), ('SLEW','SLEW_RATE')):
                value = conn['FunctionalParameters'].get(parameter, '').strip('"')
                require(field != 'STANDARD' or not value or value == attrs[field], 'functional IO standard differs: ' + port)
                if value and field in attrs and value != attrs[field]:
                    parameter_deltas.append({'Port':port, 'Cell':conn['Cell'], 'Attribute':field,
                                             'FDCAndPCF':attrs[field], 'FunctionalLibraryParameter':value})
        banks[routed[port]['Bank']].append(port)
        inventory.append({'Port':port, **attrs, 'DIRECTION':direction, 'Site':routed[port]['Site'], 'Bank':routed[port]['Bank'],
                          'NativeFunction':routed[port]['Function'], 'FinalPrimitiveConnections':connections[port]})
    bank_summary = {}
    for bank, names in banks.items():
        volts = {declared[n]['VCCIO'] for n in names}
        require(len(volts) == 1, 'mixed declared bank voltages')
        bank_summary[bank] = {'Ports':len(names), 'DeclaredVCCIO':next(iter(volts)),
                              'Standards':dict(Counter(declared[n]['STANDARD'] for n in names))}
    reference = io.pin_parser.fdc_pins(official)
    ddr = {n for n in ports if n.startswith('mem_')}
    require(len(ddr) == 71 and all(declared[n] == reference[n] for n in ddr), '71 DDR reference attrs differ')
    require(all(declared[n] == reference[n] for n in ('clk_p','clk_n')), 'DDR reference clock attrs differ')
    raw = io.pin_parser.fdc_pins(cam_reference)
    require(len(io.CAM_PORTS) == 14 and all({k:v for k,v in declared[n].items() if k != 'DIRECTION'} == raw[n]
            and declared[n]['LOC'] == cam_pins[n] for n in io.CAM_PORTS), '14 CAM2 reference attrs differ')
    require(declared['cam_data[5]']['LOC'] == 'AA23', 'corrected CAM2 D5 pad required')
    require(UART in scalar_attributes, 'actual UART scalar pad attributes absent')
    require(len(connections[UART]) == 1 and connections[UART][0]['Primitive'] in ('V_OBUF','V_OBUFT')
            and connections[UART][0]['Pin'] == 'O', 'actual UART output pad connection differs')
    return {'Target':TARGET, 'DeclarationAndSourceBuildMappingPassed':True,
            'UARTDirectionEvidence':['generated top output', 'native export output', 'routed pad OUTPUT'],
            'UARTFDCDirectionExplicit':'DIRECTION' in declared[UART], 'UARTExternalACAccepted':False, 'TopPortCount':len(ports),
            'OriginalRoutedPorts':len(routed), 'DDRMemoryPins':len(ddr), 'DDRReferenceClockPins':2,
            'CAM2Pins':len(io.CAM_PORTS), 'FinalFunctionalPortConnectionsPassed':True,
            'FinalScalarAttributePortsVerified':len(scalar_attributes),
            'FinalFunctionalPadSiteCommentPortCount':sum(any(c['PhysicalSiteComment'] for c in v) for v in connections.values()),
            'FinalFunctionalPadSiteMappingPassed':False, 'FinalNativeSiteMappingPassed':False,
            'FinalNativeElectricalAttributesVerified':False,
            'FunctionalLibraryParameterDifferences':parameter_deltas, 'Banks':bank_summary,
            'PinInventory':sorted(inventory,key=lambda r:r['Port']),
            'ActualBoardRevisionVerified':False,'MeasuredBankVoltagesVerified':False,
            'Limit':'Functional library DRIVE/SLEW defaults are not accepted as actual native electrical settings.'}

