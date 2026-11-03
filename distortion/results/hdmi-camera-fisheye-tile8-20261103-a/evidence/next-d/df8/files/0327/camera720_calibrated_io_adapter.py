"""Pure current-candidate IO parsing; no receipt binding, EDA or acceptance.

Callers supply this candidate's generated top, compiled constraints and fresh
placed export/report bytes. Only the unique module token is adapted for the
existing pure parsers; old globals, old physical counts and evidence are unused.
"""
import re

import audit_camera720_io_cdc as structure
import camera720_io_evidence as native_io

TARGET = 'camera720_calibrated_top'
SCHEMA = 'camera720-calibrated-io-structure-v1'
require = structure.require


def module_as(text, name):
    clean = structure.io.pin_parser.clean_verilog(text)
    require(re.findall(r'\bmodule\s+(\w+)', clean) == [TARGET],
            'one exact calibrated720 module required')
    changed, count = re.subn(r'(\bmodule\s+)'+TARGET+r'\b', r'\g<1>'+name, text)
    require(count == 1, 'ambiguous module token replacement')
    return changed


def source_inventory(generated_top, fdc):
    normalized = module_as(generated_top, 'camera_vga_output_top')
    normalized, count = re.subn(r'module\s+camera_vga_output_top\s*#\(.*?\)\s*\(',
                               'module board1080_top(', normalized, count=1, flags=re.S)
    require(count == 1, 'current generated top parameters differ')
    ports = structure.io.pin_parser.top_ports(normalized)
    declared = structure.io.pin_parser.fdc_pins(fdc)
    require(set(ports) == set(declared), 'source/FDC port inventories differ')
    require(all(declared[p]['DIRECTION'] == d for p,d in ports.items()),
            'source/FDC direction differs')
    require(all(ports.get(p) == 'INPUT' for p in native_io.PORTS), 'DVP input interface differs')
    require(all(ports.get(p) == 'OUTPUT' for p in native_io.tx.PORTS), 'TX output interface differs')
    commands = [line.strip() for line in fdc.splitlines() if line.strip() and not line.lstrip().startswith('#')]
    require('create_clock -name camera_pclk -period 20.833 [get_ports cam_pclk]' in commands,
            'provisional camera clock differs')
    require(not any(line.startswith('set_output_delay') for line in commands),
            'TX external timing assumptions changed')
    return {'Target': TARGET, 'PortCount': len(ports), 'Ports': dict(sorted(ports.items())),
            'DVPInputs': sorted(native_io.PORTS), 'TXOutputs': sorted(native_io.tx.PORTS),
            'ClockCommands': [c for c in commands if c.startswith(('create_clock ', 'create_generated_clock '))],
            'InputDelayCommands': [c for c in commands if c.startswith('set_input_delay ')],
            'PhysicalEvidenceVerified': False, 'HardwareReleaseAllowed': False}


def graph(netlist):
    # Functional primitives and FF placement are freshly parsed by the old pure
    # parser; no target/global is mutated and no historical netlist is loaded.
    parsed = structure.functional(module_as(netlist, structure.prep.TARGET))
    return structure.monitor.Graph(parsed)


def derive(generated_top, fdc, pcf, prt, netlist, official_fdc, cam_reference_fdc, cam_pins):
    inventory = source_inventory(generated_top, fdc)
    pins = structure.io.pin_audit(module_as(generated_top, 'camera_vga_output_top'),
        fdc, pcf, prt, module_as(netlist, 'camera_vga_output_top'),
        official_fdc, cam_reference_fdc, cam_pins)
    current = graph(netlist)
    return {'Schema': SCHEMA, 'Target': TARGET, 'SourceInterface': inventory,
            'Pins': pins, 'InputDelay': structure.delay.audit(current),
            'SyncPadFirstSinks': structure.sync_pad_sinks(current),
            'ActualCellCount': len(current.cells), 'ActualFFCount': len(current.ff),
            'NativeElectricalParametersVerified': False, 'NativeSitesVerified': False,
            'TimingAccepted': False, 'ExternalACAccepted': False, 'HardwareReleaseAllowed': False}


def tx_launches(current):
    """Trace current TX output buffers back to actual output-video registers."""
    result = {}
    for port in sorted(native_io.tx.PORTS - {'pix_clk'}):
        buffers = [n for n,c in current.cells.items() if c['Primitive'] in ('V_OBUF','V_OBUFT')
                   and structure.cdc.canon(c['Ports'].get('O', '')) == port]
        require(len(buffers) == 1, 'one current TX output buffer required: '+port)
        cell = current.cells[buffers[0]]
        if cell['Primitive'] == 'V_OBUFT':
            require(cell['Ports']['T'] == "1'b0", 'TX tristate must be inactive')
        leaves = structure.monitor.support(current, cell['Ports']['I'])
        require(leaves and all(kind == 'ff' and name.startswith('system/output_video/') for kind,name in leaves),
                'current TX source escapes output-video register hierarchy')
        result[port] = sorted({structure.cdc.native_parent(name)+'/CLK' for _,name in leaves})
    return result


def query_body(pins, dvp_pairs, launches):
    """Render requests only. DVP endpoints must come from the current native RTR.

    This function does not establish that supplied pairs appeared in a report;
    the caller must bind and compare that report and every actual query receipt.
    """
    require(len(dvp_pairs) == len(native_io.PORTS) and {s for s,e in dvp_pairs} == native_io.PORTS,
            'one current report-derived endpoint per DVP input required')
    require(set(launches) == native_io.tx.PORTS-{'pix_clk'}, 'complete current TX launch inventory required')
    safe = re.compile(r'[A-Za-z0-9_./\[\]-]+')
    for source, endpoint in dvp_pairs:
        require(safe.fullmatch(endpoint) and endpoint.startswith(native_io.SINK_PREFIXES),
                'unsafe or unexpected DVP endpoint')
    outputs = sorted({source for rows in launches.values() for source in rows})
    require(outputs and all(safe.fullmatch(s) and s.startswith('system/output_video/') and s.endswith('/CLK') for s in outputs),
            'unsafe or unexpected TX native launch')
    require(all(rows for rows in launches.values()), 'missing TX launch source')
    sites = sorted({row['Site'] for row in pins['PinInventory']})
    require(sites and all(safe.fullmatch(site) for site in sites), 'unsafe or missing current IO sites')
    def command(sources, endpoints):
        return 'report_path_timing -delay_type min_max -max_path 1000 -nworst 8 -report_exception TRUE -from {'+' '.join(sorted(set(sources)))+'} -to {'+' '.join(sorted(set(endpoints)))+'}'
    commands = ['show -dev_instance {'+site+'}' for site in sites]
    commands += [command([s for s,e in dvp_pairs], [e for s,e in dvp_pairs]),
                 command(outputs, launches), command(['clk_27m'], ['pix_clk'])]
    return '# Current calibrated720 IO requests; not physical acceptance.\n'+'\n'.join(commands)+'\n'
