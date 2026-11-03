"""Inventory this output candidate's TX mode evidence and native pad paths.

No IO-delay values or sampling-edge claims are invented. Unconstrained native
maximum paths are not minimum-delay or external hold-time acceptance.
"""
from pathlib import Path
from collections import Counter
import argparse
import hashlib
import json
import re

PROJECT = Path(__file__).resolve().parents[1]
BUILD = PROJECT / 'build/processed-output'
NATIVE = BUILD / 'physical-final-report-20261031-a'
ADF_SHA = '1d19936ede917ea1268a17a11fb3b0b34ff84753abefb062ae26d8a2c7c7550b'
PORTS = {*(f'{color}_out[{bit}]' for color in 'rgb' for bit in range(8)),
         'hs_out', 'vs_out', 'de_out', 'pix_clk'}
PDF = PROJECT / 'build/research/ms72xx-ac-20261029/ms7210-lcsc.pdf'
PDF_SHA = 'be817ef43ceafac1178a734c21081295fef005a783e99a6f52ef666c146931d2'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def commands(header, vendor):
    actual = [(int(i), int(value,16)) for i,value in re.findall(
        r"6'd(\d+):\s*hdmi_command=24'h([0-9a-fA-F]{6});", header)]
    reference = [(int(i), (int(address,16)<<8)|int(value,16)) for i,address,value in re.findall(
        r"6'd(\d+)\s*:\s*cmd_data\s*=\s*\{16'h([0-9a-fA-F]{4}),8'h([0-9a-fA-F]{2})\};", vendor)]
    require(len(actual) == len(reference) == 49 and [i for i,v in actual] == list(range(49)),
            'complete ordered 49-command tables required')
    require(actual == reference, 'independent TX register table differs from vendor')
    return [{'Index':i,'Address':f'{v>>8:04X}','Data':f'{v&255:02X}'} for i,v in actual]


def pad_paths(report):
    records, block, first_line = [], [], 0
    def finish():
        if not block:
            return
        text = ''.join(block)
        endpoint = re.findall(r'(?m)^Endpoint\s*:\s*(\S+) \(port\)\s*$', text)
        if len(endpoint) != 1 or endpoint[0] not in PORTS:
            return
        def one(pattern, what):
            found = re.findall(pattern, text, re.M)
            require(len(found) == 1, 'missing or ambiguous ' + what)
            return found[0]
        port = endpoint[0]
        typ, corner = one(r'^Path Type\s*:\s*(min|max) \((slow|fast) corner\)\s*$', 'path type')
        require(one(r'^Path Class\s*:\s*(.+?)\s*$', 'path class') == 'combinational timing path',
                'expected current unconstrained output path')
        arrival = one(r'^ Data arrival time\s+([-+]?\d+\.\d+)\s+Logic Levels:', 'pad arrival')
        source = one(r'^Startpoint\s*:\s*(.+?)\s*$', 'source')
        launch = re.findall(r'^ Clock (\S+) \((rising|falling) edge\)', text, re.M)
        if port != 'pix_clk':
            require(launch == [('pixel_clk','rising')], 'data/control launch edge differs')
            require(source.startswith('system/output_video/'), 'unexpected output logic source')
        else:
            require(source == 'clk_27m (port)' and not launch, 'forwarded clock source differs')
        require('video_pll/u_gpll/gpll_inst/CLKOUT0' in text, 'output bypasses expected PLL')
        records.append({'Port':port,'Corner':corner,'DelayType':typ,'Source':source,
                        'LaunchClockAndEdge':launch, 'ReportedPadArrivalNS':float(arrival),
                        'ReportLine':first_line,
                        'NativeBodySHA256':hashlib.sha256(text.encode()).hexdigest()})
    with Path(report).open(encoding='ascii') as stream:
        for lineno,line in enumerate(stream,1):
            if line.startswith('Startpoint'):
                finish(); block, first_line = [line],lineno
            elif block:
                block.append(line)
    finish()
    require(Counter((r['Port'],r['Corner'],r['DelayType']) for r in records) ==
            Counter((p,c,'max') for p in PORTS for c in ('slow','fast')),
            'expected exactly one native maximum path per 28 outputs per corner')
    return records


def audit():
    receipt = json.loads((NATIVE/'result.json').read_text())
    require(receipt['ExecutionPassed'] and receipt['InputDrift'] == [] and receipt['Diagnostics'] == []
            and receipt['ResultADFSHA256'] == ADF_SHA and receipt['PreSTAEqualsResultADF'],
            'completed stable native report required')
    require(sha(NATIVE/'input.adf') == sha(NATIVE/'pre-sta.adf') == ADF_SHA, 'ADF mismatch')
    report = NATIVE/'processed_output_top.rtr'
    require(sha(report) == receipt['Artifacts']['processed_output_top.rtr'], 'native report changed')
    files = [report,NATIVE/'result.json',NATIVE/'input.adf',NATIVE/'pre-sta.adf',
             PROJECT/'board/ms7210_commands.vh',PROJECT/'board/hdmi_tx_init.v',
             PROJECT/'platform/video_base/source/hdmi/ms7210_ctl.v',
             PROJECT/'board/processed_output_top.v',PROJECT/'board/processed-output-diagnostic.fdc',
             PROJECT/'rtl/experimental/ddr_video_output_1080_board.v',PDF,Path(__file__).resolve()]
    watched = {str(p):sha(p) for p in files}
    require(watched[str(PDF)] == PDF_SHA, 'reviewed MS7210 document changed')
    table = commands(files[4].read_text(),files[6].read_text())
    records = pad_paths(report)
    corners = {}
    for corner in ('slow','fast'):
        data = [r for r in records if r['Corner'] == corner and r['Port'] != 'pix_clk']
        clock = [r for r in records if r['Corner'] == corner and r['Port'] == 'pix_clk'][0]
        slowest = max(data,key=lambda r:r['ReportedPadArrivalNS'])
        fastest_max = min(data,key=lambda r:r['ReportedPadArrivalNS'])
        corners[corner] = {'SlowestReportedMaximum':slowest,
                           'SmallestOfReportedMaximaNotMinimumDelay':fastest_max,
                           'ForwardedClockReportedMaximum':clock}
    require(all(sha(p)==digest for p,digest in watched.items()), 'input changed during audit')
    return {'Schema':'processed-output-tx-evidence-v1','AuditCompleted':True,
            'CandidateADFSHA256':ADF_SHA,'Vendor49CommandsIdentical':True,'Commands':table,
            'PhysicalCaptureEdgeFromCurrentRegistersProven':False,
            'NominalPixelPeriodNS':1000/74.25,'NativePadPathCount':len(records),
            'NativeUnconstrainedMaximumPaths':records,'CornerInventory':corners,
            'Document':{'SHA256':PDF_SHA,'LocalPath':str(PDF),'VisuallyReviewedPages':[13,14],
                        'SDRDiagramCaptureEdge':'rising','SetupNS':0.879,'HoldNS':0.22,
                        'DutyCycleRange':[0.4,0.6],'NumbersFromSimulationNotMeasurement':True,
                        'CurrentRegisterSamplingModeDefined':False,'BoardSkewProvided':False},
            'Diagnosis':['RTL/native data and control paths launch on the pixel clock rising edge.',
                         'The same PLL output is forwarded to pix_clk; mode interpretation remains conditional.',
                         'The complete native report contains only maximum output paths, so it does not bound external hold.',
                         '1281=04 belongs to the TX; no MS7200 bit definitions are imported.'],
            'NextNativeReadOnlyProbe':['report_path_timing -help','get_path_delay -help',
                'get_path_delay -from {system/output_video/g[0]/opit_0_L8Q_perm/CLK} -to {g_out[0]} -min -fast -max_path 8',
                'get_path_delay -from {video_pll/u_gpll/gpll_inst/CLKOUT0} -to {pix_clk} -min -fast -max_path 8'],
            'ProbeStatus':'Syntax/objects require native confirmation; no EDA executed by this helper.',
            'IOConstraintsApplied':False,'ExternalTimingAccepted':False,'HardwareAccessed':False,
            'InputSHA256':watched}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args(); require(not args.output.exists(),'output must be new')
    result=audit(); args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(result,stream,indent=2); stream.write('\n')
    print(json.dumps({'AuditCompleted':True,'NativePadPathCount':result['NativePadPathCount'],
                      'Vendor49CommandsIdentical':True,'ExternalTimingAccepted':False}))


if __name__ == '__main__':
    main()
