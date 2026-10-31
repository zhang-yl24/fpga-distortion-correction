"""Bind the three nonlocal scalar synchronizers to native min/max reports.

Reports ordinary interstage timing budgets, not analog metastability MTBF.
Does not run EDA, change the design or access hardware.
"""
from collections import Counter
from pathlib import Path
import argparse
import hashlib
import json
import re

import audit_ddr_final_timing as native

FINAL_SHA = '1d19936ede917ea1268a17a11fb3b0b34ff84753abefb062ae26d8a2c7c7550b'
P0 = 'ddr_ready_ref[0]/opit_0_L6Q_perm'
P1 = 'system_failed_ref[0]/opit_0_L6Q_LUT6DQL5Q_perm'
T0 = 'system_failed_ref[1]/opit_0_L6Q_LUT6DQL5Q_perm'
T1 = 'processed_bit_ref[1]/opit_0_L6Q_LUT6DQL5Q_perm'
WANTED = {(P0+'/CLK',T0+'/I2'):'ddr_ready_ref[0]',
          (P1+'/CLK',T0+'/I4'):'system_failed_ref[0]',
          (P1+'/CLK',T1+'/I4'):'processed_bit_ref[0]'}
require, sha, NUM = native.require, native.sha, native.NUM


def records(report):
    text = Path(report).read_text(encoding='ascii')
    rows=[]
    for match in re.finditer(r'(?ms)^Startpoint\s*:.*?(?=^Startpoint\s*:|\Z)', text):
        block=match.group()
        if not re.search(r'(?m)^Endpoint\s*:\s*(?:'+ '|'.join(re.escape(p[1]) for p in WANTED)+r')\s*$',block):
            continue
        end=re.search(r'(?m)^ Slack \((MET|VIOLATED)\)\s+('+NUM+r')\s*$',block)
        require(end is not None,'target interstage path has no slack')
        block=block[:end.end()]+'\n'
        row=native.path_record(block.splitlines(keepends=True))
        pair=(row['Source'],row['Endpoint'])
        require(pair in WANTED,'unexpected source to an interstage target')
        require(row['PathClass']=='sequential timing path' and
                row['LaunchClock']==row['CaptureClock']=='board27' and
                row['LaunchEdge']==row['CaptureEdge']=='rising',
                'target must be a normal rising board27 register check')
        def number(pattern,label):
            values=re.findall(pattern,block,re.M)
            require(len(values)==1,'missing/ambiguous interstage '+label)
            return float(values[0])
        kind=re.findall(r'^Path Type\s*:\s*(max|min) ',block,re.M)[0]
        arrival=number(r'^ Data arrival time\s+('+NUM+r')\s+Logic Levels:', 'arrival')
        launch=number(r'^  Launch Clock Delay\s*:\s*('+NUM+r')\s*$', 'launch delay')
        timing_label='Setup' if kind=='max' else 'Hold'
        check=number(r'^ '+timing_label+r' time\s+('+NUM+r')\s+'+NUM+r'\s*$', 'check value')
        transition=re.findall(r'^ \S+\s+tco\s+'+NUM+r'\s+'+NUM+r'\s+([rf])\s+\S+',block,re.M)
        require(len(transition)==1,'one source-Q transition required')
        slack=float(end[2])
        require(end[1]=='MET' and slack>=0,'interstage timing failed')
        row.update(Label=WANTED[pair],Kind='setup' if kind=='max' else 'hold',
                   LaunchDataTransition=transition[0],SlackNS=slack,
                   DataArrivalNS=arrival,LaunchClockDelayNS=launch,
                   ClockToTargetInputNS=round(arrival-launch,3),
                   SignedLibraryCheckNS=check,
                   NativeReportLine=text.count('\n',0,match.start())+1,
                   NativePathSHA256=hashlib.sha256('\n'.join(
                       line.rstrip() for line in block.splitlines() if line.strip()).encode('ascii')).hexdigest())
        require(row['ClockToTargetInputNS']>=0,'negative interstage datapath')
        rows.append(row)
    wanted={(label,corner,kind) for label in WANTED.values()
            for corner in ('slow','fast') for kind in ('setup','hold')}
    actual=Counter((r['Label'],r['Corner'],r['Kind']) for r in rows)
    require(set(actual)==wanted,'all three paths need both corners and setup/hold')
    require(len({r['NativePathSHA256'] for r in rows})==len(rows),'duplicate native path')
    return rows


def audit(receipt_path,structure_path):
    receipt_path=Path(receipt_path).resolve()
    structure_path=Path(structure_path).resolve()
    receipt=json.loads(receipt_path.read_text())
    work=receipt_path.parent
    require(receipt['ExecutionPassed'] is True and receipt['InputDrift']==[]
            and receipt['HardwareAccessed'] is False
            and receipt['SourceADFSHA256']==receipt['ResultADFSHA256']==FINAL_SHA
            and receipt['PreSTAEqualsResultADF'] is True
            and sha(work/'input.adf')==sha(work/'pre-sta.adf')==FINAL_SHA,
            'native receipt/final ADF binding differs')
    reports=[work/name for name in receipt['Artifacts']
             if name.endswith('.rtr') and not name.endswith('_exception.rtr')]
    require(len(reports)==1,'one normal native timing report required')
    report=reports[0]
    require(sha(report)==receipt['Artifacts'][str(report.relative_to(work))], 'native report drift')
    structural=json.loads(structure_path.read_text())
    require(structural['AuditPassed'] is True and
            {r['Label'] for r in structural['ScalarSynchronizers'] if not r['SameSite']}==set(WANTED.values()),
            'nonlocal synchronizer inventory differs')
    require(all(sha(p)==h for p,h in structural['InputSHA256'].items()),'structural evidence drift')
    rows=records(report)
    bounds=[]
    for label in WANTED.values():
        for corner in ('slow','fast'):
            subset=[r for r in rows if r['Label']==label and r['Corner']==corner]
            bounds.append({'Label':label,'Corner':corner,
                           'SetupSlackNS':min(r['SlackNS'] for r in subset if r['Kind']=='setup'),
                           'HoldSlackNS':min(r['SlackNS'] for r in subset if r['Kind']=='hold'),
                           'MaxClockToTargetInputNS':max(r['ClockToTargetInputNS'] for r in subset),
                           'NativeVariants':len(subset)})
    inputs=[receipt_path,structure_path,report,work/'input.adf',work/'pre-sta.adf',
            Path(__file__).resolve(),Path(native.__file__).resolve()]
    return {'Schema':'processed-output-scalar-interstage-v1','AuditPassed':True,
            'ClockPeriodNS':37.037,'Bounds':bounds,'Paths':rows,
            'InputSHA256':{str(p):sha(p) for p in inputs},
            'Scope':'Three nonlocal second-stage input paths; native setup includes the packed LUT/FF library check.',
            'AnalogMTBFProven':False,'AllCDCUniversallyProven':False,'HardwareAccessed':False,
            'Limitations':['Positive setup slack is the reported digital timing budget, not a measured metastability resolution probability.',
                           'This supplements, and does not replace, the bounded structural/Gray/mailbox audit.']}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--receipt',type=Path,required=True)
    p.add_argument('--structure',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    result=audit(a.receipt,a.structure)
    with a.output.open('x',encoding='utf-8') as stream:
        json.dump(result,stream,indent=2); stream.write('\n')
    print(json.dumps({'AuditPassed':True,'Bounds':result['Bounds']}))


if __name__=='__main__':
    main()
