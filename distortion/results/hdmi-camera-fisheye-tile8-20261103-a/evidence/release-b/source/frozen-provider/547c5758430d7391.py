"""CPU-only camera candidate pad, DVP and TX evidence audit.

This audits current source/native evidence. Provisional DVP input budgets and
functional export electrical parameters never become measured external AC
acceptance. Read-only native queries must be executed separately by the owner.
"""
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
import argparse
import hashlib
import json
import re

import audit_board1080_pin_contract as pin_parser
import audit_ddr_entry_reset_netlist as net_parser
import audit_processed_output_tx as tx_parser
import prepare_camera_vga_output as candidate

PROJECT = Path(__file__).resolve().parents[1]
ROOT = PROJECT / 'work/camera-vga-output'
FINAL = ROOT / 'physical-final-report-20261031-a'
EXPORT = ROOT / 'export-final-20261031-a'
BUILD = ROOT / 'pds-20261031-a'
ADF_SHA = 'daa2a9221238d09398ba325acef561b604dcb5643571301ba8831f76736dfd9f'
CAM_DATA = {*(f'cam_data[{i}]' for i in range(8)), 'cam_vsync', 'cam_href'}
CAM_PORTS = CAM_DATA | {'cam_pclk', 'cam_rst_n', 'cam_scl', 'cam_sda'}
require = pin_parser.require


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def bind(watched, path, digest=None):
    path = Path(path).resolve()
    actual = sha(path)
    require(digest is None or actual == digest, 'input hash differs: ' + str(path))
    require(str(path) not in watched or watched[str(path)] == actual, 'conflicting evidence hash')
    watched[str(path)] = actual
    return path


def load_receipt(path, schema, watched):
    path = bind(watched, path)
    r = json.loads(path.read_text())
    require(r.get('Schema') == schema and r.get('ExecutionPassed') is True and
            r.get('ExitCode') == 0 and r.get('InputDrift') == [] and r.get('Diagnostics') == [] and
            r.get('HardwareAccessed') is False and r.get('BitstreamRequested') is False and
            r.get('SourceADFSHA256') == r.get('ResultADFSHA256') == ADF_SHA and
            r.get('InputADFUnchanged') is True, 'clean current final-ADF receipt required')
    bind(watched, r['SourceADF'], ADF_SHA)
    bind(watched, path.parent / 'input.adf', ADF_SHA)
    for name, digest in r['InputSHA256'].items():
        bind(watched, name, digest)
    for name, digest in r['Artifacts'].items():
        artifact = (path.parent / name).resolve()
        require(artifact.is_relative_to(path.parent), 'native artifact escaped stage')
        bind(watched, artifact, digest)
    return r


def netlist_ports(text):
    header = net_parser.parse(text.replace('module camera_vga_output_top', 'module board1080_top', 1))[0]
    ports = {}
    for kind, hi, lo, name in re.findall(r'(?m)^\s*(input|output|inout)\s+(?:\[(\d+):(\d+)\]\s+)?(\w+);', header):
        for port in ([name] if not hi else [f'{name}[{i}]' for i in range(int(lo), int(hi) + 1)]):
            require(port not in ports, 'duplicate final top port')
            ports[port] = kind.upper()
    return ports


def pin_audit(top, fdc, pcf, prt, exported, official, cam_reference, cam_pins):
    normalized, substitutions = re.subn(r'module\s+camera_vga_output_top\s*#\(.*?\)\s*\(',
                                        'module board1080_top(', top, count=1, flags=re.S)
    require(substitutions == 1, 'camera top parameter declaration differs')
    ports = pin_parser.top_ports(normalized)
    declared, generated = pin_parser.fdc_pins(fdc), pin_parser.pcf_pins(pcf)
    pads, routed = pin_parser.routed_pads(prt)
    require(len(ports) == 128 and set(ports) == set(declared) == set(generated) == set(routed),
            'all 128 current ports must match FDC, PCF and routed table')
    require(netlist_ports(exported) == ports, 'final functional top ports differ')
    require(len({r['LOC'] for r in declared.values()}) == len(declared), 'duplicate package pin')
    scalar_attributes = {}
    for body, direction, port in re.findall(r'\(\*([^*]+)\*\)\s*(input|output|inout)\s+(\w+);', exported):
        attrs = dict(re.findall(r'PAP_IO_(\w+)="([^"]+)"', body))
        require(port in declared and port not in scalar_attributes, 'duplicate/unexpected final scalar attributes')
        require(all(attrs.get(k) == v for k,v in declared[port].items()), 'final scalar pad attrs differ: ' + port)
        require(direction.upper() == ports[port], 'final scalar direction differs')
        scalar_attributes[port] = attrs
    _, cells = net_parser.parse(exported.replace('module camera_vga_output_top', 'module board1080_top', 1))
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
        require(attrs['DIRECTION'] == direction == routed[port]['Direction'], 'pin direction differs: ' + port)
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
        inventory.append({'Port':port, **attrs, 'Site':routed[port]['Site'], 'Bank':routed[port]['Bank'],
                          'NativeFunction':routed[port]['Function'], 'FinalPrimitiveConnections':connections[port]})
    bank_summary = {}
    for bank, names in banks.items():
        volts = {declared[n]['VCCIO'] for n in names}
        require(len(volts) == 1, 'mixed declared bank voltages')
        bank_summary[bank] = {'Ports':len(names), 'DeclaredVCCIO':next(iter(volts)),
                              'Standards':dict(Counter(declared[n]['STANDARD'] for n in names))}
    reference = pin_parser.fdc_pins(official)
    ddr = {n for n in ports if n.startswith('mem_')}
    require(len(ddr) == 71 and all(declared[n] == reference[n] for n in ddr), '71 DDR reference attrs differ')
    require(all(declared[n] == reference[n] for n in ('clk_p','clk_n')), 'DDR reference clock attrs differ')
    raw = pin_parser.fdc_pins(cam_reference)
    require(len(CAM_PORTS) == 14 and all({k:v for k,v in declared[n].items() if k != 'DIRECTION'} == raw[n]
            and declared[n]['LOC'] == cam_pins[n] for n in CAM_PORTS), '14 CAM2 reference attrs differ')
    require(declared['cam_data[5]']['LOC'] == 'AA23', 'corrected CAM2 D5 pad required')
    return {'DeclarationAndSourceBuildMappingPassed':True, 'TopPortCount':len(ports),
            'OriginalRoutedPorts':len(routed), 'DDRMemoryPins':len(ddr), 'DDRReferenceClockPins':2,
            'CAM2Pins':len(CAM_PORTS), 'FinalFunctionalPortConnectionsPassed':True,
            'FinalScalarAttributePortsVerified':len(scalar_attributes),
            'FinalFunctionalPadSiteCommentPortCount':sum(any(c['PhysicalSiteComment'] for c in v) for v in connections.values()),
            'FinalFunctionalPadSiteMappingPassed':False, 'FinalNativeSiteMappingPassed':False,
            'FinalNativeElectricalAttributesVerified':False,
            'FunctionalLibraryParameterDifferences':parameter_deltas, 'Banks':bank_summary,
            'PinInventory':sorted(inventory,key=lambda r:r['Port']),
            'ActualBoardRevisionVerified':False,'MeasuredBankVoltagesVerified':False,
            'Limit':'Functional library DRIVE/SLEW defaults are not accepted as actual native electrical settings.'}


def apply_native_sites(pins, log):
    blocks = re.findall(r'(?ms)^Site (\S+) \((\d+)\) :\r?\n(.*?)(?=^Site |^Executing :|\Z)', log)
    sites = {}
    for site, count, body in blocks:
        require(site not in sites, 'duplicate native site block')
        names = re.findall(r'(?m)^\t(\S+) \(', body)
        require(len(names) == int(count), 'native site instance count differs')
        sites[site] = names
    expected = {r['Site'] for r in pins['PinInventory']}
    require(set(sites) == expected, 'native IO site coverage differs')
    for row in pins['PinInventory']:
        native = {c['NativeInstance'] for c in row['FinalPrimitiveConnections']}
        require(native == set(sites[row['Site']]), 'native IO instance/site differs: ' + row['Port'])
        row['FinalNativeSiteInstances'] = sites[row['Site']]
    pins['FinalNativeSiteMappingPassed'] = True
    pins['FinalFunctionalPadSiteMappingPassed'] = True
    pins['FinalNativeSiteCount'] = len(sites)


def dvp_paths(report):
    groups, block, line_number = {}, [], 0
    def finish():
        if not block:return
        text = ''.join(block)
        source = re.search(r'^Startpoint\s*:\s*(\S+) \(port\)\s*$',text,re.M)
        if not source or source[1] not in CAM_DATA:return
        typ = re.search(r'^Path Type\s*:\s*(min|max) \((slow|fast) corner\)\s*$',text,re.M)
        slack = re.search(r'^ Slack \((MET|VIOLATED)\)\s+([-+]?\d+\.\d+)',text,re.M)
        require(typ and slack, 'DVP input path missing timing result')
        clocks = re.findall(r'^ Clock (\S+) \((rising|falling) edge\)',text,re.M)
        require(clocks == [('camera_pclk','rising'),('camera_pclk','rising')], 'DVP capture clock/edge differs')
        external = re.findall(r'^ Input external delay\s+([-+]?\d+\.\d+)',text,re.M)
        require(external == (['5.000'] if typ[1]=='max' else ['0.000']), 'provisional DVP budget differs')
        endpoint = re.search(r'^Endpoint\s*:\s*(\S+)',text,re.M)[1]
        require(endpoint.startswith('system/input_link/input_dma/capture/'), 'DVP input leaves capture hierarchy')
        key = (source[1],typ[1],typ[2]); value = float(slack[2])
        row = groups.setdefault(key,{'Port':source[1],'DelayType':typ[1],'Corner':typ[2],'ReportedPathCount':0,
                                    'ConditionalWorstSlackNS':value,'WorstPath':None})
        row['ReportedPathCount'] += 1
        if row['WorstPath'] is None or value < row['ConditionalWorstSlackNS']:
            row['ConditionalWorstSlackNS'] = value
            row['WorstPath'] = {'Endpoint':endpoint,'ReportLine':line_number,
                                'NativeBodySHA256':hashlib.sha256(text.encode()).hexdigest()}
    with Path(report).open(encoding='ascii') as stream:
        for line, value in enumerate(stream,1):
            if value.startswith('Startpoint'):finish();block=[value];line_number=line
            elif block:block.append(value)
    finish()
    require(set(groups) == {(p,t,c) for p in CAM_DATA for t in ('min','max') for c in ('slow','fast')},
            'all ten DVP inputs need both timing types and corners')
    return [groups[k] for k in sorted(groups)]


def audit(native_io_receipt=None):
    watched = {};candidate.validate()
    paths = {
        'top':PROJECT/'board/camera_vga_output_top.v','fdc':PROJECT/'board/camera-vga-output-diagnostic.fdc',
        'pcf':BUILD/'device_map/camera_vga_output_top.pcf','prt':BUILD/'place_route/camera_vga_output_top_prr_route_optimize.prt',
        'netlist':EXPORT/'generate_netlist/camera_vga_output_top_sim.v',
        'report':FINAL/'camera_vga_output_top.rtr','official':PROJECT/'platform/video_base/HDMI_IN_DDR3_HDMI_OUT_top.fdc',
        'cam_reference':PROJECT/'board/raw_camera_capture_cam2_ref.fdc','cam_pins':PROJECT/'board/raw_camera_capture_cam2_ref-pins.json',
        'tx_commands':PROJECT/'board/ms7210_commands.vh','tx_reference':PROJECT/'platform/video_base/source/hdmi/ms7210_ctl.v',
        'tx_init':PROJECT/'board/hdmi_tx_init.v','cam_init':PROJECT/'rtl/experimental/ov5640_cadence_trial_init.v',
        'cam_commands':PROJECT/'board/ov5640_cadence_trial_commands.vh','capture':PROJECT/'rtl/experimental/dvp_rgb565_capture_cdc.v',
        'manifest':PROJECT/'board/camera-vga-output-sources.json'}
    for path in paths.values():bind(watched,path)
    export = load_receipt(EXPORT/'result.json','camera-vga-functional-export-v1',watched)
    report = load_receipt(FINAL/'result.json','camera-vga-isolated-query-v1',watched)
    require(export['Netlist']['SHA256'] == sha(paths['netlist']), 'final netlist binding differs')
    original = json.loads(bind(watched,BUILD/'execution-result.json').read_text())
    require(original.get('ExecutionCompletedWithoutError') is True and original['Readback']['InputDrift']==[] and
            original['Readback']['CompiledDrift']==[] and original['DatabaseSnapshotAudit']['UnchangedAcrossSTA'],
            'original source build not stable')
    plan = json.loads(bind(watched,BUILD/'plan.json',original['PlanSHA256']).read_text())
    for key in ('top','fdc'):
        require(plan['InputSHA256'][paths[key].relative_to(PROJECT).as_posix()] == sha(paths[key]), 'source differs from native build')
    archive_path = bind(watched,PROJECT/'results/camera-vga-native-20261031-a/manifest.json')
    archive = json.loads(archive_path.read_text())
    require(any(row['SHA256']==sha(paths['prt']) and Path(row['OriginalPath']).resolve()==paths['prt'] for row in archive['Files']),
            'original routed pad table lacks archive binding')
    texts={k:p.read_text(encoding='utf-8-sig') for k,p in paths.items() if k not in ('report','manifest')}
    pins=pin_audit(**{k:texts[k] for k in ('top','fdc','pcf','prt','official','cam_reference')},
                   exported=texts['netlist'],cam_pins=json.loads(texts['cam_pins']))
    if native_io_receipt:
        r=load_receipt(native_io_receipt,'camera-vga-isolated-query-v1',watched)
        log=Path(native_io_receipt).resolve().parent/'stdout.log'
        require(r['Artifacts'].get('stdout.log')==sha(log),'native IO query log not bound')
        apply_native_sites(pins,log.read_text(encoding='gb18030'))
        pins['NativeSiteReceipt']=str(Path(native_io_receipt).resolve())
    table=tx_parser.commands(texts['tx_commands'],texts['tx_reference'])
    tx=tx_parser.pad_paths(paths['report']);dvp=dvp_paths(paths['report'])
    fdc_commands=[l.strip() for l in texts['fdc'].splitlines() if l.strip() and not l.lstrip().startswith('#')]
    require(not any(l.startswith('set_output_delay') for l in fdc_commands),'unexpected external TX budget')
    require('create_clock -name camera_pclk -period 20.833 [get_ports cam_pclk]' in fdc_commands,'provisional camera period differs')
    top_compact=re.sub(r'\s+','',pin_parser.clean_verilog(texts['top']))
    require('.VSYNC_ACTIVE_HIGH(0),.HREF_ACTIVE_HIGH(0),.HIGH_BYTE_FIRST(0)' in top_compact and
            ".trial_pad_mask(16'h7ff0)" in top_compact,'historical CAM2 mode/pad mask differs')
    capture_compact=re.sub(r'\s+','',pin_parser.clean_verilog(texts['capture']))
    require('always@(posedgecam_clk' in capture_compact and
            'pixel565=HIGH_BYTE_FIRST?{first_byte,cam_data}:{cam_data,first_byte};' in capture_compact,'DVP capture/byte contract differs')
    tools={str(Path(m.__file__).resolve()):sha(m.__file__) for m in (pin_parser,net_parser,tx_parser,candidate)}
    tools[str(Path(__file__).resolve())]=sha(__file__)
    require(all(sha(p)==h for p,h in watched.items()),'input drift during IO audit')
    return {'Schema':'camera-vga-io-evidence-v1','AuditedUTC':datetime.now(timezone.utc).isoformat(),
            'AuditCompleted':True,'CandidateADF':{'Path':str(FINAL/'input.adf'),'SHA256':ADF_SHA},'Pins':pins,
            'TX':{'Vendor49CommandsIdentical':True,'Commands':table,'NativeUnconstrainedMaximumPaths':tx,
                  'NativePadPathCount':len(tx),'DataControlPorts':27,'ForwardClockPorts':1,
                  'NativeMinimumDelaysObtained':False,'PhysicalCaptureEdgeFromCurrentRegistersProven':False,
                  'OutputDelayConstraintsPresent':False,'NominalPixelPeriodNS':1000/74.25,
                  'ExternalTimingAccepted':False,'BoardSkewMeasured':False,
                  'Limitation':'The 56 maximum paths do not bound external hold; 1281=04 capture mode and package/PCB skew remain unverified.'},
            'DVP':{'ConstrainedInputDataControlPorts':10,'CaptureEdge':'rising','VSYNCActiveHigh':False,
                   'HREFActiveHigh':False,'HighByteFirst':False,'CAM2PadMask':'7FF0',
                   'ProvisionalClockPeriodNS':20.833,'ProvisionalInputMinNS':0.0,'ProvisionalInputMaxNS':5.0,
                   'ConditionalSTA':dvp,'ReportedConditionalWorstSetupNS':min(r['ConditionalWorstSlackNS'] for r in dvp if r['DelayType']=='max'),
                   'ReportedConditionalWorstHoldNS':min(r['ConditionalWorstSlackNS'] for r in dvp if r['DelayType']=='min'),
                   'ExternalTimingAccepted':False,'SensorPCLKMeasured':False,'BoardSkewMeasured':False,
                   'Limitation':'Reported slack assumes historical unmeasured input budgets; it is not a sensor/board sampling-margin measurement.'},
            'InputSHA256':watched,'ToolSHA256':tools,'EDAExecutedByAuditor':False,
            'ConstraintsChanged':False,'HardwareAccessed':False,'HardwareReleaseAllowed':False}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--native-io-receipt',type=Path);a=p.parse_args()
    require(not a.output.exists(),'fresh evidence output required')
    result=audit(a.native_io_receipt);a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open('x',encoding='utf-8',newline='\n') as stream:json.dump(result,stream,indent=2);stream.write('\n')
    print(json.dumps({'AuditCompleted':True,'TopPortCount':result['Pins']['TopPortCount'],
                      'FinalNativeSiteMappingPassed':result['Pins']['FinalNativeSiteMappingPassed'],
                      'TXPadPaths':result['TX']['NativePadPathCount'],'DVPConditionalHoldNS':result['DVP']['ReportedConditionalWorstHoldNS'],
                      'ExternalTimingAccepted':False}))


if __name__=='__main__':main()
