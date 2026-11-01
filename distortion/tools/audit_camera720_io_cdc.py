"""Bind a real current 720p export and audit application/monitor CDC structure.

This tool is deliberately incomplete for physical approval: held snapshots,
native path results and pad electrical inspection remain explicit pending gates.
It never invokes PDS, applies exceptions or accesses the board.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import types

import camera720_inspect as inspect
import audit_camera720_monitor as monitor
import audit_calibrated_camera_input_delay as delay
import audit_camera_vga_io as io

cdc = monitor.base
prep, require, sha = inspect.prep, inspect.require, inspect.sha
SELF = Path(__file__).resolve()


def io_syntax(text):
    clean = io.pin_parser.clean_verilog(text)
    require(re.findall(r'\bmodule\s+(\w+)', clean) == [prep.TARGET], 'unique current 720 IO module required')
    changed, count = re.subn(r'(\bmodule\s+)'+prep.TARGET+r'\b', r'\1camera_vga_output_top', text)
    require(count == 1, 'module-token IO parser adaptation ambiguous')
    return changed


def sync_pad_sinks(g):
    rows = []
    for pad in ('cam_vsync', 'cam_href'):
        buffer = cdc.one([n for n, c in g.cells.items() if c['Primitive'] == 'V_IBUF'
                          and c['Ports'].get('I') == pad], pad+' buffer')
        seen, active, sinks = set(), set(), set()
        def visit(net, driver):
            require(net not in active, 'sync pad combinational cycle')
            if net in seen:
                return
            active.add(net)
            for name, pin in g.refs[net]:
                if (name, pin) == driver:
                    continue
                cell = g.cells[name]
                if name in g.ff:
                    require(pin in ('D', 'CE', 'SR'), 'sync pad reaches unreviewed FF pin')
                    require(g.clock(cell['Ports']['CK'])['Domain'] == 'camera_pclk', 'raw sync pad reaches non-camera domain')
                    require(name.startswith((cdc.CAP, monitor.PREFIX)), 'sync pad reaches unreviewed hierarchy')
                    sinks.add((name, pin))
                    continue
                if cell['Primitive'] == 'V_DRM36K_E1':
                    require(name.startswith(cdc.CAP+'pixels/') and pin in ('WEA', 'CSA'),
                            'sync pad reaches unreviewed memory control')
                    require(g.clock(cell['Ports']['CLKA'])['Domain'] == 'camera_pclk',
                            'sync pad memory control sampled outside camera clock')
                    sinks.add((name, pin))
                    continue
                kind = cell['Primitive']
                require(kind in delay.COMBINATIONAL and pin in delay.COMBINATIONAL[kind][0],
                        'sync pad unreviewed fanout: '+name+'/'+pin)
                for output in delay.COMBINATIONAL[kind][1]:
                    value = cell['Ports'].get(output)
                    if value:
                        visit(value, (name, output))
            active.remove(net)
            seen.add(net)
        visit(g.cells[buffer]['Ports']['O'], (buffer, 'O'))
        require(sinks, 'sync pad has no sequential sinks')
        rows.append({'Pad': pad, 'Buffer': buffer,
                     'FirstSequentialSinks': [{'Cell': n, 'Pin': pin, 'Clock': 'camera_pclk'} for n, pin in sorted(sinks)],
                     'StructuralFanoutOverapproximation': True, 'ExternalACTimingAccepted': False})
    return rows


def local_helpers(modules):
    """Bind transitive local imported modules without editing their globals."""
    pending, seen = list(modules), set()
    while pending:
        module = pending.pop()
        if module in seen or not getattr(module, '__file__', None):
            continue
        path = Path(module.__file__).resolve()
        if not path.is_relative_to(prep.PROJECT):
            continue
        seen.add(module)
        pending.extend(value for value in vars(module).values() if isinstance(value, types.ModuleType))
        yield path


def functional(text):
    require('2023.2-SP3<build 154097>' in text[:300], 'native 720 export version differs')
    clean = re.sub(r'/\*.*?\*/|//[^\n]*|\(\*.*?\*\)', lambda m: '\n'*m[0].count('\n'), text, flags=re.S)
    require(re.findall(r'(?m)^module\s+(\w+)', clean) == [prep.TARGET]
            and len(re.findall(r'(?m)^endmodule\b', clean)) == 1, 'one flat 720 top required')
    cells = {}
    for match in cdc.physical.dialect.CELL.finditer(clean):
        name = match['name'].lstrip('\\')
        require(name not in cells, 'duplicate native primitive')
        cells[name] = {'Primitive': match['primitive'],
                       'Parameters': cdc.physical.dialect.bindings(match['parameters']),
                       'Ports': cdc.physical.dialect.bindings(match['ports'])}
    require(cells and len(cells) == len(re.findall(r'(?m)^[ \t]*V_\w+\b', clean)), 'incomplete native primitive parse')
    placed = {}
    for match in cdc.physical.FF.finditer(text):
        name = match['name'].lstrip('\\')
        require(name in cells and name not in placed, 'duplicate/unmatched FF placement')
        placed[name] = {'Site': match['site'], 'Attributes': ' '.join((match['attrs'] or '').split())}
    require(set(placed) == {n for n, c in cells.items() if c['Primitive'] in cdc.FF_TYPES}, 'missing placed FF evidence')
    return {'Cells': cells, 'FFPlacement': placed,
            'ModuleDeclarations': ' '.join(cdc.physical.dialect.CELL.sub('', clean).split())}


def audit(receipt_path, output):
    receipt, watched = inspect.bind_receipt(receipt_path)
    require(receipt['Mode'] == 'export' and receipt['NativeNetlistWithFFloc'], 'real placed export required')
    path = Path(receipt['Netlist']['Path'])
    text = path.read_text(encoding='utf-8-sig')
    graph = monitor.Graph(functional(text))
    build = Path(receipt['BuildPlan']).parent
    paths = {'top': prep.PROJECT/prep.TOP, 'fdc': build/'compiled'/prep.FDC,
             'pcf': build/'device_map'/(prep.TARGET+'.pcf'),
             'prt': build/'place_route'/(prep.TARGET+'_prr_route_optimize.prt'),
             'official': prep.PROJECT/'platform/video_base/HDMI_IN_DDR3_HDMI_OUT_top.fdc',
             'cam_reference': prep.PROJECT/'board/raw_camera_capture_cam2_ref.fdc',
             'cam_pins': prep.PROJECT/'board/raw_camera_capture_cam2_ref-pins.json'}
    texts = {}
    for name, source in paths.items():
        source = inspect.canonical(source)
        watched[source] = sha(source)
        texts[name] = source.read_text(encoding='utf-8-sig')
    components, errors = {}, []
    def snapshot():
        result = monitor.held_snapshot(graph)
        result['AllFirstConsumers'] = monitor.held_first_sinks(graph, result)
        result['HeldBusEndpointTraversalComplete'] = True
        return result
    checks = [('Pins', lambda: io.pin_audit(io_syntax(texts['top']), texts['fdc'], texts['pcf'], texts['prt'],
                                         io_syntax(text), texts['official'], texts['cam_reference'], json.loads(texts['cam_pins']))),
              ('SyncPadSinks', lambda: sync_pad_sinks(graph)),
              ('InputDelay', lambda: delay.audit(graph)),
              ('FIFOGray', lambda: cdc.gray_structures(graph)),
              ('ApplicationScalar', lambda: monitor.application_scalars(graph)),
              ('MonitorGray', lambda: monitor.monitor_gray(graph)),
              ('MonitorScalar', lambda: monitor.monitor_scalar(graph)),
              ('ApplicationReset', lambda: monitor.reset_chains(graph)),
              ('MonitorHeldSnapshot', snapshot)]
    for name, check in checks:
        try:
            components[name] = {'Passed': True, 'Value': check()}
        except (ValueError, KeyError, IndexError) as error:
            components[name] = {'Passed': False, 'Error': str(error)}
            errors.append({'Component': name, 'Error': str(error)})
    queries = []
    required = ('FIFOGray', 'MonitorGray', 'ApplicationScalar', 'MonitorScalar', 'ApplicationReset', 'MonitorHeldSnapshot')
    if all(components[name]['Passed'] for name in required):
        queries = monitor.query_pairs(components['FIFOGray']['Value']+components['MonitorGray']['Value'],
                                      components['ApplicationScalar']['Value']+components['MonitorScalar']['Value'],
                                      components['ApplicationReset']['Value'], components['MonitorHeldSnapshot']['Value'])
    for p in local_helpers((inspect, monitor, delay, io)):
        watched[p] = sha(p)
    watched[SELF] = sha(SELF)
    require(not inspect.drift(watched), '720 structure inputs changed')
    output = prep.work_path(output)
    require(not output.exists(), 'fresh 720 structure directory required')
    output.mkdir()
    result = {'Schema': 'camera720-io-cdc-structure-v1', 'Target': prep.TARGET,
              'CreatedUTC': datetime.now(timezone.utc).isoformat(),
              'ExportReceipt': {'Path': str(Path(receipt_path).absolute()), 'SHA256': sha(receipt_path)},
              'CandidateADF': {'Path': receipt['SourceADF'], 'SHA256': receipt['SourceADFSHA256']},
              'BuildPlanSHA256': receipt['BuildPlanSHA256'], 'Netlist': receipt['Netlist'],
              'InputSHA256': {str(p): h for p, h in watched.items()},
              'ComponentChecks': components, 'Errors': errors,
              'EnumeratedComponentChecksPassed': not errors,
              'StructuralAuditPassed': False, 'PhysicalTimingAccepted': False,
              'Pending': ['held snapshot/reset physical timing', 'exact native path timing',
                          'native electrical inspection',
                          'candidate-specific DDR reset scope'],
              'ActualCells': len(graph.cells), 'ActualFFs': len(graph.ff), 'ClockTopology': graph.clock_cache,
              'QueryPairs': queries, 'HardwareAccessed': False, 'EDAExecuted': False,
              'HardwareReleaseAllowed': False,
              'Limits': 'Current exported structure only. No inherited 34/22/7 totals. Pending components prevent overall approval.'}
    inspect.diagnostic.write(output/'structure.json', result)
    # Bound each batch below the read-only inspector's 300-command limit.
    for first in range(0, len(queries), 200):
        lines = ['# Actual current 720p endpoints; timing still pending.']
        for item in queries[first:first+200]:
            lines.append('report_path_timing -delay_type min_max -max_path 100 -nworst 8 -report_exception TRUE -from {'
                         +item['Source']+'} -to {'+item['Endpoint']+'}')
        body = '\n'.join(lines)+'\n'
        inspect.query_commands(body)
        (output/f'query-{first//200:02}.tcl').write_text(body, encoding='ascii', newline='\n')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--export-receipt', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.export_receipt, args.output_dir)
    print(json.dumps({'ComponentChecksPassed': result['EnumeratedComponentChecksPassed'],
                      'Errors': result['Errors'], 'Queries': len(result['QueryPairs']),
                      'StructuralAuditPassed': False, 'HardwareAccessed': False}))
    return 0 if result['EnumeratedComponentChecksPassed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
