"""Read native HDMI diagnostic build reports; no EDA or programming."""
from pathlib import Path
import argparse
import hashlib
import json
import math
import re

ROOT=Path(__file__).resolve().parents[1]


def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def fdc_directions(path, pins):
    """Require one explicit direction for every planned diagnostic port."""
    directions={}
    pattern=r'define_attribute\s+\{p:([^{}]+)\}\s+\{PAP_IO_DIRECTION\}\s+\{(INPUT|OUTPUT|INOUT)\}\s*(?:#.*)?'
    for line in Path(path).read_text(encoding='utf-8').splitlines():
        line=line.strip()
        if not line or line.startswith('#') or 'PAP_IO_DIRECTION' not in line:
            continue
        match=re.fullmatch(pattern,line)
        if match is None:
            raise ValueError('unsupported or malformed diagnostic FDC direction')
        port,direction=match.groups()
        if port in directions:
            raise ValueError('duplicate FDC direction for '+port)
        directions[port]=direction.lower()
    if set(directions)!=set(pins):
        raise ValueError('an explicit FDC direction is required for every planned port')
    return directions


def audit(work):
    work=Path(work).resolve()
    plan=json.loads((work/'build-plan.json').read_text(encoding='utf-8'))
    execution=json.loads((work/'execution.json').read_text(encoding='utf-8'))
    target=plan.get('Target','hdmi_uart_diag')
    native=work/'report_timing'/(target+'.rtr')
    text=native.read_text(encoding='utf-8',errors='replace')
    pattern=r'(?m)^(Setup|Hold|Recovery|Removal|Minimum Pulse Width) Summary\((Slow|Fast) Corner\):'
    matches=list(re.finditer(pattern,text))
    if len(matches)!=10 or len({m.groups() for m in matches})!=10:
        raise ValueError('all five timing types in both corners required')
    summaries=[]
    for i,m in enumerate(matches):
        section=text[m.end():matches[i+1].start() if i+1<len(matches) else len(text)]
        # The first equal-rule closes the summary table; path reports follow.
        section=section.split('\n====',1)[0]
        rows=[];clock_groups=set()
        for line in section.splitlines():
            fields=line.split()
            if len(fields) not in (5,6):continue
            try:slack,total=float(fields[-4]),float(fields[-3]); failing,count=int(fields[-2]),int(fields[-1])
            except ValueError:continue
            if not math.isfinite(slack) or not math.isfinite(total):
                raise ValueError('native timing slack and total must be finite')
            if count<=0 or not 0<=failing<=count or total>0:
                raise ValueError('invalid native endpoint counts or positive total negative slack')
            # Native decimal values may round a tiny failing slack/TNS to
            # zero, but never to a positive value. A zero-failure row must
            # have nonnegative worst slack and exactly zero negative total.
            if (failing==0 and (slack<0 or total!=0)) or (failing>0 and slack>0):
                raise ValueError('native slack/total/failing endpoint relationship disagrees')
            clocks=tuple(fields[:-4])
            expected_clocks=1 if m[1]=='Minimum Pulse Width' else 2
            if len(clocks)!=expected_clocks or clocks in clock_groups:
                raise ValueError('duplicate or malformed native timing clock row')
            clock_groups.add(clocks)
            rows.append({'Clocks':fields[:-4],'WorstSlackNS':slack,'TotalNegativeSlackNS':total,
                         'FailingEndpoints':failing,'TotalEndpoints':count})
        if not rows:raise ValueError('missing native timing rows')
        summaries.append({'Type':m[1],'Corner':m[2],'Rows':rows,
                          'FailingEndpoints':sum(r['FailingEndpoints'] for r in rows),
                          'WorstSlackNS':min(r['WorstSlackNS'] for r in rows)})
    report_pin=work/'place_route'/(target+'_prr_route_optimize.prt')
    actual={};directions={}
    for line in report_pin.read_text(encoding='utf-8').splitlines():
        fields=line.split('|')
        if len(fields)>=7 and fields[4]:
            if fields[4] in actual or fields[6]!='YES':raise ValueError('duplicate/inactive routed port')
            actual[fields[4]]=fields[0];directions[fields[4]]=fields[5]
    fdc=Path(plan.get('FDC',work/(target+'.fdc')))
    expected_directions=fdc_directions(fdc,plan['Pins'])
    pins_ok=actual==plan['Pins'] and len(set(actual.values()))==len(actual)
    pins_ok &= directions==expected_directions
    pins_ok &= directions.get('uart_txd')=='output' and directions.get('hd_scl')=='inout' and directions.get('hd_sda')=='inout'
    drift=[s for s,h in plan['InputSHA256'].items() if sha(ROOT/s)!=h]
    if sha(work/'build.tcl')!=plan['TclSHA256']:drift.append('build.tcl')
    if sha(fdc)!=plan['FDCSHA256']:drift.append('candidate.fdc')
    all_met=all(row['FailingEndpoints']==0 and row['WorstSlackNS']>=0 and
                row['TotalNegativeSlackNS']==0 for summary in summaries for row in summary['Rows'])
    declared=bool(re.search(r'(?m)^Design Summary\s*:\s*All Constraints Met\.\s*$',text))
    if all_met!=declared:raise ValueError('native summary/detail disagree')
    paths=[work/'build-plan.json',work/'execution.json',native,report_pin,fdc,work/'build.tcl',
           work/'place_route'/(target+'_pnr.adf'),work/'report_timing'/(target+'_rtp.adf'),
           work/'native-stdout.log',work/'native-stderr.log']
    native_log=(work/'native-stdout.log').read_text(encoding='utf-8',errors='replace')
    errors=bool(re.search(r'(?m)^[EF]:',native_log)) or bool((work/'native-stderr.log').read_bytes())
    return {'Schema':'hdmi-diagnostic-native-audit-v1','Target':target,
            'BuildCompleted':execution['ReturnCode']==0 and not errors,
            'NativeTimingPassed':all_met,'AllTenTimingTypesChecked':True,'TimingSummaries':summaries,
            'PinMapPassed':bool(pins_ok),'ActualPinCount':len(actual),'ActualDirections':directions,
            'ExpectedDirections':expected_directions,'AllPinDirectionsChecked':True,
            'SourceDrift':drift,'AuditPassed':execution['ReturnCode']==0 and not errors and all_met and pins_ok and not drift,
            'BuildPlan':str(work/'build-plan.json'),'InputsSHA256':{str(p):sha(p) for p in paths},
            'HardwareAccessed':False,'HardwareReleaseAllowed':False,
            'Limits':'Native reported timing and routed pins only. External I/O AC, physical CDC protocol, analog rise time and real video remain separate.'}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--workdir',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    result=audit(a.workdir)
    with a.output.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2);f.write('\n')
    print(json.dumps({k:result[k] for k in ('AuditPassed','NativeTimingPassed','PinMapPassed','ActualPinCount','SourceDrift')}))
    raise SystemExit(0 if result['AuditPassed'] else 1)
