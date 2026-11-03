"""Extract routed startup-reset delay bounds without treating slack as delay.

The caller separately proves the actual physical reset consumers, source and
clock-stop/startup contract. This module binds the current C native reports and
retains their actual recovery/removal paths, including their physical pins.
It does not authorize a constraint or establish a vendor startup contract.
"""
import hashlib
import json
import math
from pathlib import Path
import re

import hdmi_camera_fisheye_tile8_build as build
import hdmi_camera_fisheye_tile8_native as native

SELF=Path(__file__).resolve()
NUM=r'[-+]?\d+(?:\.\d+)?'
require=build.require


def extract(report,physical_pins,source):
    require(isinstance(physical_pins,list)and physical_pins and physical_pins==sorted(set(physical_pins))
        and all(re.fullmatch(r'CLM[AS]_\d+_\d+/RS',p)for p in physical_pins),
        'complete sorted actual startup reset physical-pin inventory required')
    require(all(isinstance(source.get(k),str)and source[k]for k in
        ('SourceFF','SourcePhysicalQ','SourceNativeOutputPin','LaunchClock','CaptureClock')),
        'independently verified startup launch identity required')
    report_ref=native.ref(report)
    required=set(physical_pins);rows=[];block=[];first_line=0
    def finish():
        if not block:return
        text=''.join(block)
        check=re.findall(r'^ (Recovery|Removal) time\s+('+NUM+r')\s+('+NUM+r')\s*$',text,re.M)
        if not check:return
        require(len(check)==1,'ambiguous native reset check')
        launch=re.findall(r'^\s+(\S+)\s+tco\s+('+NUM+r')\s+('+NUM+r')\s+([rf])\s+(\S+)\s*$',text,re.M)
        if len(launch)!=1 or launch[0][4]!=source['SourceNativeOutputPin']:return
        endpoint=re.findall(r'^Endpoint\s*:\s*(\S+)\s*$',text,re.M)
        require(len(endpoint)==1,'native startup reset endpoint missing')
        targets=re.findall(r'^\s+(\S+/RS)\s+(?:'+NUM+r'\s+'+NUM+r'\s+)?([rf])\s+'
            +re.escape(endpoint[0])+r'\s*$',text,re.M)
        if len(targets)!=1 or targets[0][0]not in required:return
        require(launch[0][0]==source['SourcePhysicalQ'],'startup native launch physical Q differs')
        clocks=re.findall(r'^ Clock (\S+) \((rising|falling) edge\)\s+('+NUM+r')',text,re.M)
        require(len(clocks)==2 and clocks[0][0]==source['LaunchClock']and clocks[1][0]==source['CaptureClock'],
            'startup-reset path has an unreviewed actual launch/capture clock')
        corner=re.findall(r'^Path Type\s*:\s*(max|min) \((slow|fast) corner\)\s*$',text,re.M)
        require(len(corner)==1 and corner[0][0]==('max'if check[0][0]=='Recovery'else'min'),
            'startup reset check and native delay corner differ')
        arrivals=re.findall(r'^ Data arrival time\s+('+NUM+r')\b',text,re.M)
        uncertainty=re.findall(r'^ clock uncertainty\s+('+NUM+r')\s+'+NUM+r'\s*$',text,re.M)
        require(arrivals and len(set(arrivals))==1 and len(uncertainty)==1,
            'startup reset needs actual data arrival and clock uncertainty, not slack')
        tco=float(launch[0][1]);tco_arrival=float(launch[0][2]);arrival=float(arrivals[0])
        propagation=round(tco+arrival-tco_arrival,6)
        recovery=abs(float(check[0][1]));uncertainty=abs(float(uncertainty[0]))
        require(all(math.isfinite(v)and v>=0 for v in(tco,propagation,recovery,uncertainty))
            and arrival>=tco_arrival,'negative/nonfinite native startup delay bound')
        body='\n'.join(' '.join(l.split())for l in block if l.strip()and not set(l.strip())<=set('-='))
        rows.append({**source,'Endpoint':endpoint[0],'PhysicalEndpoint':targets[0][0],
            'Corner':corner[0][1],'Check':check[0][0],'LaunchEdge':clocks[0][1],'CaptureEdge':clocks[1][1],
            'LaunchDataTransition':launch[0][3],'EndpointTransition':targets[0][1],
            'TCOIncrementNS':tco,'TCOArrivalNS':tco_arrival,'DataArrivalNS':arrival,
            'PostQPropagationNS':round(arrival-tco_arrival,6),'PropagationNS':propagation,
            'RequiredRecoveryNS':recovery,'ClockUncertaintyNS':uncertainty,
            'PrintedPrecisionRoundingAllowanceNS':0.003,
            'TotalRequiredNS':round(propagation+recovery+uncertainty+0.003,6),
            'PathSHA256':hashlib.sha256(body.encode('utf-8')).hexdigest(),
            'Report':report_ref,'NativeReportLine':first_line})
    with Path(report).open(encoding='gb18030',errors='strict')as stream:
        for line_number,line in enumerate(stream,1):
            if line.startswith('Startpoint'):finish();block=[line];first_line=line_number
            elif block:
                block.append(line)
                if line.startswith(' Slack'):finish();block=[]
    finish()
    found={(r['PhysicalEndpoint'],r['Corner'],r['Check'])for r in rows}
    expected={(p,c,k)for p in required for c in('slow','fast')for k in('Recovery','Removal')}
    require(len({(r['PathSHA256'],r['Report']['Path'])for r in rows})==len(rows),
        'duplicate literal startup reset path')
    return rows,sorted(expected-found)


def review(build_plan,export_receipt,route_receipt,physical_pins,source):
    plan=build.validate(build_plan);exported,watched=native.bind_receipt(export_receipt)
    routed,inputs=native.bind_receipt(route_receipt);native.merge(watched,inputs)
    require(exported['Mode']=='export'and routed['Mode']=='report'
        and exported['BuildPlanSHA256']==routed['BuildPlanSHA256']==build.sha(build_plan)
        and exported['SourceADF']==routed['SourceADF']==str(Path(build_plan).resolve().parent/'place_route'/(build.TARGET+'_pnr.adf'))
        and exported['SourceADFSHA256']==routed['SourceADFSHA256']
        and exported.get('SourceProof')is None and routed.get('SourceProof')is None,
        'startup timing reports must bind this same current C build and ADF')
    report=native.artifact(export_receipt,exported,build.TARGET+'.rtr')
    rows,missing=extract(report,physical_pins,source)
    for path in(SELF,report,Path(build_plan)):native.add(watched,path)
    value={'Schema':'hdmi-camera-fisheye-tile8-vendor-startup-paths-v1','BuildPlan':native.ref(build_plan),
        'ExportReceipt':native.ref(export_receipt),'RouteReceipt':native.ref(route_receipt),
        'Reports':[native.ref(report)],'RequiredPhysicalResetPins':physical_pins,'Source':source,'Rows':rows,
        'CompleteActualResetPathCoverage':not missing,'Missing':[list(v)for v in missing],'Violations':[],
        'MaximumRequiredNS':max((r['TotalRequiredNS']for r in rows),default=None),
        'DelayBasis':'native_tco_increment_plus_actual_data_arrival_minus_native_tco_arrival',
        'SlackUsedAsPropagationDelay':False,'AllUnreportedTransitionsEnumerated':False,
        'PrintedNumericResolutionNS':0.001,'RoundingTerms':5,'RoundingBoundNS':0.003,
        'StartupClockStopContractProven':False,'TimingAccepted':False,'HardwareReleaseAllowed':False,
        'InputSHA256':{str(p):h for p,h in watched.items()}}
    require(not native.drift(watched),'startup timing input drift')
    return value,watched
