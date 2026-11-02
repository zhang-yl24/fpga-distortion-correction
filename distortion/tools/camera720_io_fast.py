"""Recompute 720p IO evidence using an explicitly anchored inspection proof.

The original IO parser and checks are reused without monkeypatching globals.
Only expensive native source-chain binding is replaced by the exact completed
inspection seed. Actual graph, pad/site, DVP and TX checks run on current bytes.
Pure audit() does not write files or start a process.
"""
import argparse
from datetime import datetime, timezone
import importlib
import json
from pathlib import Path
import re

import camera720_io_evidence as source
import camera720_stage_fast as fast

prep, inspect = source.prep, source.inspect
require, sha, watch = source.require, source.sha, source.watch
SELF = Path(__file__).resolve()


def binding(path):
    path = Path(path).absolute()
    return {'Path':str(path),'SHA256':sha(path)}


def derive(export_path, receipt, watched):
    """Same actual IO graph checks; receipt binding is supplied separately."""
    require(receipt.get('NativeNetlistWithFFloc') is True, 'placed native IO export required')
    netlist = watch(watched, receipt['Netlist']['Path'], receipt['Netlist']['SHA256'])
    text = netlist.read_text(encoding='utf-8-sig')
    graph = source.structure.monitor.Graph(source.structure.functional(text))
    build = Path(receipt['BuildPlan']).parent
    paths = {'top':prep.PROJECT/prep.TOP, 'fdc':build/'compiled'/prep.FDC,
        'pcf':build/'device_map'/(prep.TARGET+'.pcf'),
        'prt':build/'place_route'/(prep.TARGET+'_prr_route_optimize.prt'),
        'official':prep.PROJECT/'platform/video_base/HDMI_IN_DDR3_HDMI_OUT_top.fdc',
        'cam_reference':prep.PROJECT/'board/raw_camera_capture_cam2_ref.fdc',
        'cam_pins':prep.PROJECT/'board/raw_camera_capture_cam2_ref-pins.json'}
    texts = {key:watch(watched,path).read_text(encoding='utf-8-sig') for key,path in paths.items()}
    pins = source.structure.io.pin_audit(source.structure.io_syntax(texts['top']),texts['fdc'],texts['pcf'],texts['prt'],
        source.structure.io_syntax(text),texts['official'],texts['cam_reference'],json.loads(texts['cam_pins']))
    delays = source.structure.delay.audit(graph)
    commands = [line.strip() for line in texts['fdc'].splitlines() if line.strip() and not line.lstrip().startswith('#')]
    require('create_clock -name camera_pclk -period 20.833 [get_ports cam_pclk]' in commands,
            'provisional camera clock differs')
    require(not any(line.startswith('set_output_delay') for line in commands), 'unexpected TX external budget')
    return pins,delays


def audit(export_path, query_receipts, inspection_seed, inspection_seed_sha256):
    if isinstance(query_receipts,(str,Path)):
        query_receipts=[query_receipts]
    require(query_receipts and len(set(map(str,query_receipts)))==len(query_receipts),
            'distinct actual native query receipts required')
    group = importlib.import_module('camera720_cdc_grouped')
    seed_context = fast.bind_seed(inspection_seed,inspection_seed_sha256)
    _,original,bound = seed_context
    watched = {}
    for path,digest in bound.items():watch(watched,path,digest)
    for helper in source.structure.local_helpers((source,fast,group)):
        watch(watched,helper)
    watch(watched,SELF)
    seed_ref = {'Path':str(Path(inspection_seed).absolute()),'SHA256':inspection_seed_sha256}
    candidate = {'Path':original['SourceADF'],'SHA256':original['SourceADFSHA256']}
    receipt = group.bind_native_fast(export_path,'export',watched,candidate,original['BuildPlanSHA256'],seed_ref,seed_context)
    pins,delays=derive(export_path,receipt,watched)
    report=source.artifact(export_path,receipt,prep.TARGET+'.rtr',watched)
    reports=[report];site_logs=[];dumps=[];refs=[]
    for path in query_receipts:
        value=group.bind_native_fast(path,'query',watched,candidate,receipt['BuildPlanSHA256'],seed_ref,seed_context)
        log=source.artifact(path,value,'stdout.log',watched)
        text=log.read_text(encoding='gb18030')
        if re.search(r'^Site \S+ \(\d+\) :',text,re.M):site_logs.append(text)
        if 'route-dump.txt' in value['Artifacts']:
            dumps.append(source.artifact(path,value,'route-dump.txt',watched))
        for name,digest in value['Artifacts'].items():
            if name.endswith('.rtr') and not name.endswith('_exception.rtr'):
                reports.append(watch(watched,Path(path).absolute().parent/name,digest))
        refs.append(binding(path))
    require(len(site_logs)==1 and dumps and len({sha(path) for path in dumps})==1,
            'one complete site log and consistent native dump required')
    source.structure.io.apply_native_sites(pins,site_logs[0])
    electrical=source.io_parameters(dumps[0],pins)
    tx_rows=source.tx.pad_paths(report)
    table=source.tx.commands(watch(watched,prep.PROJECT/'board/ms7210_commands.vh').read_text(),
        watch(watched,prep.PROJECT/'platform/video_base/source/hdmi/ms7210_ctl.v').read_text())
    dvp=source.dvp_summary(source.dvp_records(list(dict.fromkeys(reports))))
    require(dvp['ReportedBudgetCoverageComplete'],'DVP per-port/corner/kind detail missing')
    for helper in source.structure.local_helpers((source,fast,group)):
        watch(watched,helper)
    watch(watched,SELF)
    require(not inspect.drift(watched),'fast IO audit input drift')
    return {'Schema':source.SCHEMA,'Target':prep.TARGET,'CreatedUTC':datetime.now(timezone.utc).isoformat(),
        'CandidateADF':candidate,'BuildPlanSHA256':receipt['BuildPlanSHA256'],
        'ExportReceipt':binding(export_path),'QueryReceipts':refs,
        'Producer':binding(SELF),'InspectionSeed':seed_ref,
        'NativeSourceProofReused':True,'ActualIOChecksRecomputed':True,
        'InputSHA256':{str(path):digest for path,digest in watched.items()},
        'AuditPassed':True,'PinDeclarationsVerified':True,'NativePadElectricalParametersVerified':True,
        'NativePinSitesVerified':True,'InputDelayStructureVerified':True,'TXMaximumPathsVerified':True,
        'DVPReportedBudgetCoverageComplete':True,'Pins':pins,'NativeElectricalParameters':electrical,
        'InputDelays':delays,'TX':{'Vendor49CommandsIdentical':True,'Commands':table,
            'NativeMaximumPaths':tx_rows,'NativeMaximumPathCount':len(tx_rows),
            'NativeMinimumDelaysObtained':False,'RegisterSamplingInterpretationVerified':False},
        'DVP':dvp,'HardwareAccessed':False,'EDAExecuted':False,'HardwareReleaseAllowed':False,
        'ExternalACAccepted':False,'AnalogMTBFProven':False,'BoardVoltagesMeasured':False,
        'Limits':'Native declared pad parameters, sites, eight input-delay structures and conditional DVP/native TX maximum paths only. No external sampling, PCB skew, measured clock/fps, optical or universal CDC acceptance.'}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--export-receipt',type=Path,required=True)
    parser.add_argument('--query-receipt',type=Path,action='append',required=True)
    parser.add_argument('--inspection-seed',type=Path,required=True)
    parser.add_argument('--inspection-seed-sha256',required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    output=source.output_file(args.output)
    value=audit(args.export_receipt,args.query_receipt,args.inspection_seed,args.inspection_seed_sha256)
    inspect.diagnostic.write(output,value)
    print(json.dumps({key:value[key] for key in ('Schema','CandidateADF','AuditPassed','DVPReportedBudgetCoverageComplete')}))


if __name__=='__main__':main()
