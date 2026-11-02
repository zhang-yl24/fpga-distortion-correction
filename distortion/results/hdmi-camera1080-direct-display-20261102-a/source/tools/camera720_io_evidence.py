"""Current 720p pad parameters and conditional DVP/TX evidence; CPU only.

The native ADIF cell parameters are inspected separately from functional-model
defaults. Reported DVP coverage is per input/corner/kind, not every fanout path;
full internal STA is a separate gate. External AC and board voltages are unmeasured.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib
import json
from pathlib import Path
import re

import audit_camera720_io_cdc as structure
import audit_camera_vga_routes as adif
import audit_processed_output_tx as tx

inspect, prep = structure.inspect, structure.prep
require, sha = prep.require, prep.sha
SELF = Path(__file__).resolve()
SCHEMA = 'camera720-io-evidence-v1'
PORTS = {*(f'cam_data[{i}]' for i in range(8)), 'cam_href', 'cam_vsync'}
SINK_PREFIXES = ('system/input_link/input_dma/capture/', 'camera_configuration/monitor/')
NUMBER = r'[-+]?\d+(?:\.\d+)?'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def watch(watched, path, expected=None):
    path = Path(path).absolute()
    require(path == path.resolve() and path.is_file(), 'canonical existing IO evidence required')
    actual = sha(path)
    require(expected is None or actual == expected, 'IO evidence identity differs: '+str(path))
    require(path not in watched or watched[path] == actual, 'IO evidence drift while binding')
    watched[path] = actual
    return path


def bind_native(path, mode, watched, candidate=None, build_sha=None):
    path = watch(watched, path)
    schema = read(path).get('Schema')
    modules = {'camera720-output-readonly-inspection-v1': 'camera720_inspect',
               'camera720-derived-readonly-inspection-v1': 'camera720_derived_inspect',
               'camera720-reset-derived-inspection-v1': 'camera720_reset_inspect'}
    require(schema in modules, 'unsupported current IO receipt schema')
    module = importlib.import_module(modules[schema])
    if schema == 'camera720-reset-derived-inspection-v1':
        value = module.bind_receipt(path, watched)
    else:
        value, bound = module.bind_receipt(path)
        for source, digest in bound.items():
            # External native rules have already passed the strict inspector;
            # preserve those exact bindings, never broaden its path policy.
            watch(watched, source, digest)
    require(value['Mode'] == mode and value['Target'] == prep.TARGET, 'IO receipt mode/target differs')
    if candidate is not None:
        require(value['SourceADFSHA256'] == candidate['SHA256'] and
                Path(value['SourceADF']).resolve() == Path(candidate['Path']).resolve(),
                'IO receipt belongs to another actual candidate')
    if build_sha is not None:
        require(value['BuildPlanSHA256'] == build_sha, 'IO receipt belongs to another build')
    for helper in structure.local_helpers((module, structure, tx, adif)):
        watch(watched, helper)
    watch(watched, SELF)
    return value


def artifact(receipt_path, receipt, name, watched):
    names = [n for n in receipt['Artifacts'] if Path(n).name == name and
             'report_path_timing' not in Path(n).parts]
    require(len(names) == 1, 'one exact bound IO artifact required: '+name)
    path = Path(receipt_path).absolute().parent/names[0]
    require(path.resolve().is_relative_to(Path(receipt_path).absolute().parent), 'IO artifact escaped stage')
    return watch(watched, path, receipt['Artifacts'][names[0]])


def derive(export_path, watched):
    receipt = bind_native(export_path, 'export', watched)
    require(receipt.get('NativeNetlistWithFFloc') is True, 'placed native IO export required')
    netlist = watch(watched, receipt['Netlist']['Path'], receipt['Netlist']['SHA256'])
    text = netlist.read_text(encoding='utf-8-sig')
    graph = structure.monitor.Graph(structure.functional(text))
    build = Path(receipt['BuildPlan']).parent
    paths = {'top': prep.PROJECT/prep.TOP, 'fdc': build/'compiled'/prep.FDC,
             'pcf': build/'device_map'/(prep.TARGET+'.pcf'),
             'prt': build/'place_route'/(prep.TARGET+'_prr_route_optimize.prt'),
             'official': prep.PROJECT/'platform/video_base/HDMI_IN_DDR3_HDMI_OUT_top.fdc',
             'cam_reference': prep.PROJECT/'board/raw_camera_capture_cam2_ref.fdc',
             'cam_pins': prep.PROJECT/'board/raw_camera_capture_cam2_ref-pins.json'}
    texts = {k: watch(watched, p).read_text(encoding='utf-8-sig') for k,p in paths.items()}
    pins = structure.io.pin_audit(structure.io_syntax(texts['top']), texts['fdc'], texts['pcf'], texts['prt'],
        structure.io_syntax(text), texts['official'], texts['cam_reference'], json.loads(texts['cam_pins']))
    delays = structure.delay.audit(graph)
    commands = [l.strip() for l in texts['fdc'].splitlines() if l.strip() and not l.lstrip().startswith('#')]
    require('create_clock -name camera_pclk -period 20.833 [get_ports cam_pclk]' in commands,
            'provisional camera clock differs')
    require(not any(l.startswith('set_output_delay') for l in commands), 'unexpected TX external budget')
    return receipt, pins, delays


def io_parameters(path, pins):
    """Select native IO instances and their concrete cell definitions, no defaults."""
    wanted = {c['NativeInstance'] for row in pins['PinInventory'] for c in row['FinalPrimitiveConnections']}
    cells, instances = {}, {}
    depth, active, held = 0, None, []
    for line in Path(path).open(encoding='utf-8-sig'):
        tokens = adif.TOKEN.findall(line)
        require(not adif.TOKEN.sub('', line).strip(), 'unparsed native IO tokens')
        start = depth
        depth += tokens.count('(')-tokens.count(')')
        require(depth >= 0, 'unbalanced native IO dump')
        if active is None and tokens[:2] == ['(', 'CELL'] and tokens[2].startswith(('gopIBUF','gopOBUF','gopIOBUF')):
            active, held = ('cell', tokens[2], start), []
        elif active is None and tokens[:2] == ['(', 'INSTANCE'] and tokens[2].lstrip('\\') in wanted:
            active, held = ('instance', tokens[2].lstrip('\\'), start), []
        if active is not None:
            held.extend(tokens)
            if depth == active[2]:
                table = cells if active[0] == 'cell' else instances
                require(active[1] not in table, 'duplicate native IO object')
                table[active[1]] = adif.expression(held)
                active = None
    require(depth == 0 and active is None and set(instances) == wanted, 'incomplete native IO dump/instance coverage')
    def atom(value):
        require(isinstance(value,str) and re.fullmatch(r'"?[A-Za-z0-9_.-]+"?', value) is not None,
                'unreviewed native IO parameter value')
        return value.strip('"')
    rows = []
    for pin in pins['PinInventory']:
        for name in sorted({c['NativeInstance'] for c in pin['FinalPrimitiveConnections']}):
            inst = instances[name]
            require(inst[0] == 'INSTANCE' and len(inst) >= 4 and inst[2][:2] == ['VIEWREF','OPER'], 'unreviewed IO instance view')
            ref = inst[2][2]
            require(len(inst[2]) == 3 and len(ref) == 3 and ref[0] == 'CELLREF' and
                    ref[2][0] == 'OPERAREF' and ref[2][2] == ['LIBRARYREF','pango_lib'], 'unreviewed IO cell reference')
            require(ref[1] in cells, 'native IO cell definition missing')
            cell = cells[ref[1]]
            require(cell[:2] == ['CELL', ref[1]] and cell[2] == ['OPERAREF',ref[2][1]], 'IO cell operator differs')
            params = {}
            for item in cell[3:]:
                if item[0] != 'PARAMETER':
                    continue
                require(len(item) == 4 and item[2] == ['DATATYPE','STRING'] and
                        item[3][0] == 'STRING' and len(item[3]) == 2 and item[1] not in params,
                        'ambiguous native IO parameter')
                params[item[1]] = atom(item[3][1])
            attrs = {}
            for item in inst[3:]:
                require(item[0] != 'PARAMETER', 'native IO instance parameter override unreviewed')
                if item[0] == 'ATTRIBUTE' and item[1].startswith('PAP_IO_'):
                    require(len(item) == 3 and item[2][0] == 'STRING' and len(item[2]) == 2,
                            'unreviewed IO attribute')
                    key = item[1][7:]
                    require(key not in attrs, 'duplicate native IO attribute')
                    attrs[key] = atom(item[2][1])
            for key, value in attrs.items():
                if key in pin:
                    require(value == pin[key], 'native declared IO attribute differs: '+pin['Port']+'/'+key)
            for field, parameter in (('VCCIO','VCCIO'),('STANDARD','IOSTANDARD'),('DRIVE','DRV_CURR_VAL'),('SLEW','SLEW_MODE')):
                if field in pin:
                    expected = {'FAST':'F','SLOW':'S'}.get(pin[field], pin[field])
                    require(params.get(parameter) == expected, 'native electrical parameter differs: '+pin['Port']+'/'+field)
            if pin.get('PULLUP') == 'TRUE':
                require(params.get('TERMINATED') == 'PULLUP', 'native pullup differs')
            rows.append({'Port':pin['Port'], 'Instance':name, 'Cell':ref[1], 'Operator':ref[2][1],
                         'Parameters':params, 'ExplicitNativeAttributes':attrs})
    require({r['Port'] for r in rows} == {r['Port'] for r in pins['PinInventory']}, 'native pad parameter coverage differs')
    return {'Passed':True,'Ports':len(pins['PinInventory']),'NativeInstances':len(wanted),'Rows':rows,
            'VerifiedFields':['VCCIO','IOSTANDARD','explicit DRIVE/SLEW','explicit PULLUP'],
            'ActualBoardVoltagesMeasured':False,'HardwareElectricalAcceptance':False}


def dvp_records(reports):
    records = []
    for path in reports:
        block, first = [], 0
        def finish():
            if not block:return
            text = ''.join(block)
            src = re.search(r'^Startpoint\s*:\s*(\S+) \(port\)\s*$', text, re.M)
            if src is None or src[1] not in PORTS:return
            def field(pattern):
                matches = re.findall(pattern, text, re.M)
                require(len(matches) == 1, 'incomplete/ambiguous DVP native path')
                return matches[0]
            kind, corner = field(r'^Path Type\s*:\s*(min|max) \((slow|fast) corner\)\s*$')
            endpoint = field(r'^Endpoint\s*:\s*(\S+)\s*$')
            require(endpoint.startswith(SINK_PREFIXES), 'DVP endpoint escaped reviewed hierarchy')
            require(field(r'^Path Class\s*:\s*(.+?)\s*$') == 'sequential timing path', 'DVP path is not sequential')
            require(not re.search(r'^Timing Exception\s*:',text,re.M), 'DVP path unexpectedly excepted')
            require(re.findall(r'^ Clock (\S+) \((rising|falling) edge\)',text,re.M) ==
                    [('camera_pclk','rising'),('camera_pclk','rising')], 'DVP sampling clock/edge differs')
            external = field(r'^ Input external delay\s+('+NUMBER+r')\s+')
            require(float(external) == (5. if kind == 'max' else 0.), 'DVP provisional external budget differs')
            state, slack = field(r'^ Slack \((MET|VIOLATED)\)\s+('+NUMBER+r')\s*$')
            require(state == 'MET' and float(slack) >= 0, 'DVP conditional timing violation')
            records.append({'Port':src[1], 'Endpoint':endpoint, 'DelayType':kind,'Corner':corner,
                            'SlackNS':float(slack),'InputExternalDelayNS':float(external),
                            'Report':str(path),'ReportLine':first,
                            'PathSHA256':hashlib.sha256(text.encode()).hexdigest()})
        for number,line in enumerate(Path(path).open(encoding='ascii'),1):
            if line.startswith('Startpoint'):
                finish(); block, first = [line], number
            elif block:block.append(line)
        finish()
    return records


def dvp_summary(records):
    expected = {(p,t,c) for p in PORTS for t in ('min','max') for c in ('slow','fast')}
    groups = {}
    for row in records:
        key = row['Port'],row['DelayType'],row['Corner']
        require(key in expected, 'unexpected DVP record')
        if key not in groups or row['SlackNS'] < groups[key]['SlackNS']:groups[key]=row
    return {'ReportedBudgetCoverageComplete':set(groups)==expected, 'ExpectedPortCornerKindCases':40,
            'CoveredCases':len(groups),'MissingCases':[dict(zip(('Port','DelayType','Corner'),k)) for k in sorted(expected-set(groups))],
            'WorstReportedPaths':[groups[k] for k in sorted(groups)],
            'AllFanoutPathsEnumerated':False, 'ExternalTimingAccepted':False,
            'Scope':'At least one native detail per 10 inputs x two corners x setup/hold; full internal STA independently required.'}


def prepare(export_path, output):
    watched = {};receipt, pins, delays = derive(export_path,watched)
    report = artifact(export_path,receipt,prep.TARGET+'.rtr',watched)
    records = dvp_records([report]); queries=[]
    for port in sorted(PORTS):
        values = [r for r in records if r['Port']==port and r['DelayType']=='max']
        require(values, 'no actual native setup endpoint for DVP query')
        row = min(values,key=lambda r:r['SlackNS'])
        require(re.fullmatch(r'[A-Za-z0-9_./\[\]-]+',row['Endpoint']), 'unsafe actual DVP endpoint')
        queries.append({'Source':port,'Endpoint':row['Endpoint']})
    body = '# Current actual DVP endpoints; per-port conditional min/max details.\n'+'\n'.join(
        'report_path_timing -delay_type min_max -max_path 100 -nworst 8 -report_exception TRUE -from {'+
        q['Source']+'} -to {'+q['Endpoint']+'}' for q in queries)+'\n'
    inspect.query_commands(body)
    require(not inspect.drift(watched),'IO preparation input drift')
    output = prep.work_path(output); require(not output.exists(),'fresh IO preparation directory required'); output.mkdir()
    (output/'query-body.tcl').write_text(body,encoding='ascii',newline='\n')
    value = {'Schema':'camera720-io-query-plan-v1','Target':prep.TARGET,
             'CandidateADF':{'Path':receipt['SourceADF'],'SHA256':receipt['SourceADFSHA256']},
             'BuildPlanSHA256':receipt['BuildPlanSHA256'],
             'ExportReceipt':{'Path':str(Path(export_path).absolute()),'SHA256':sha(export_path)},
             'Queries':queries,'QueryBodySHA256':sha(output/'query-body.tcl'),
             'InitialDVPCoverage':dvp_summary(records),'InputSHA256':{str(p):h for p,h in watched.items()},
             'HardwareAccessed':False,'EDAExecuted':False,'HardwareReleaseAllowed':False}
    inspect.diagnostic.write(output/'plan.json',value)
    return value


def audit(export_path, query_receipts):
    """Pure CPU replay; query_receipts may be a path or a list of actual receipts."""
    if isinstance(query_receipts,(str,Path)):query_receipts=[query_receipts]
    require(query_receipts and len(set(map(str,query_receipts)))==len(query_receipts),'distinct native query receipts required')
    watched = {};receipt,pins,delays=derive(export_path,watched)
    candidate={'Path':receipt['SourceADF'],'SHA256':receipt['SourceADFSHA256']}
    report=artifact(export_path,receipt,prep.TARGET+'.rtr',watched)
    reports=[report];site_logs=[];dumps=[];refs=[]
    for path in query_receipts:
        value=bind_native(path,'query',watched,candidate,receipt['BuildPlanSHA256'])
        log=artifact(path,value,'stdout.log',watched)
        text=log.read_text(encoding='gb18030')
        if re.search(r'^Site \S+ \(\d+\) :',text,re.M):site_logs.append(text)
        if 'route-dump.txt' in value['Artifacts']:dumps.append(artifact(path,value,'route-dump.txt',watched))
        for name,digest in value['Artifacts'].items():
            if name.endswith('.rtr') and not name.endswith('_exception.rtr'):
                reports.append(watch(watched,Path(path).absolute().parent/name,digest))
        refs.append({'Path':str(Path(path).absolute()),'SHA256':sha(path)})
    require(len(site_logs)==1 and dumps and len({sha(p) for p in dumps})==1,'one complete site log and consistent native dump required')
    structure.io.apply_native_sites(pins,site_logs[0])
    electrical=io_parameters(dumps[0],pins)
    tx_rows=tx.pad_paths(report)
    table=tx.commands(watch(watched,prep.PROJECT/'board/ms7210_commands.vh').read_text(),
                      watch(watched,prep.PROJECT/'platform/video_base/source/hdmi/ms7210_ctl.v').read_text())
    dvp=dvp_summary(dvp_records(list(dict.fromkeys(reports))))
    require(dvp['ReportedBudgetCoverageComplete'],'DVP per-port/corner/kind detail missing')
    require(not inspect.drift(watched),'IO audit input drift')
    return {'Schema':SCHEMA,'Target':prep.TARGET,'CreatedUTC':datetime.now(timezone.utc).isoformat(),
            'CandidateADF':candidate,'BuildPlanSHA256':receipt['BuildPlanSHA256'],
            'ExportReceipt':{'Path':str(Path(export_path).absolute()),'SHA256':sha(export_path)},
            'QueryReceipts':refs,'InputSHA256':{str(p):h for p,h in watched.items()},
            'AuditPassed':True,'PinDeclarationsVerified':True,'NativePadElectricalParametersVerified':True,
            'NativePinSitesVerified':True,'InputDelayStructureVerified':True,'TXMaximumPathsVerified':True,
            'DVPReportedBudgetCoverageComplete':True,'Pins':pins,'NativeElectricalParameters':electrical,
            'InputDelays':delays,'TX':{'Vendor49CommandsIdentical':True,'Commands':table,
                'NativeMaximumPaths':tx_rows,'NativeMaximumPathCount':len(tx_rows),
                'NativeMinimumDelaysObtained':False,'RegisterSamplingInterpretationVerified':False},
            'DVP':dvp,'HardwareAccessed':False,'EDAExecuted':False,'HardwareReleaseAllowed':False,
            'ExternalACAccepted':False,'AnalogMTBFProven':False,'BoardVoltagesMeasured':False,
            'Limits':'Native declared pad parameters, sites, eight input-delay structures and conditional DVP/native TX maximum paths only. No external sampling, PCB skew, measured clock/fps, optical or universal CDC acceptance.'}


def output_file(value):
    path=Path(value).absolute()
    require(path==path.resolve() and path.is_relative_to(prep.WORK) and
            path.parent.is_dir() and not path.exists(),'fresh IO output file within 720 workspace required')
    return path


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('mode',choices=('prepare','audit'))
    p.add_argument('--export-receipt',type=Path,required=True);p.add_argument('--query-receipt',type=Path,action='append')
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    if a.mode=='prepare':value=prepare(a.export_receipt,a.output)
    else:
        require(a.query_receipt,'actual query receipts required');value=audit(a.export_receipt,a.query_receipt)
        output=output_file(a.output)
        inspect.diagnostic.write(output,value)
    print(json.dumps({k:value[k] for k in ('Schema','CandidateADF','AuditPassed','DVPReportedBudgetCoverageComplete') if k in value}))


if __name__=='__main__':main()
