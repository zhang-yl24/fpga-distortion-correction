"""All native timing types and unsafe interactions; diagnostic, never release."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,sys,xml.etree.ElementTree as ET
B=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()

def table(tree,name,recursive=False):
    t=tree.find('.//table[@id="'+name+'"]')
    if t is None:raise ValueError('missing native table '+name)
    h=[x.text or '' for x in t.find('column_headers').findall('data')]
    out=[]
    for r in t.findall('.//row' if recursive else 'row'):
        values=[x.text or '' for x in r.findall('data')]
        if len(values)!=len(h):raise ValueError('native row schema mismatch '+name)
        out.append(dict(zip(h,values)))
    return out

def negative(row,kind):
    column='WPWS' if kind.endswith('mpw') else 'WHS(ns)' if kind.endswith(('hold','removal')) else 'WNS(ns)'
    count='Failing End Point' if kind.endswith('mpw') else 'Failing Endpoints'
    return float(row[column])<0 or int(row[count])>0

def gate(groups,interactions,missing):
    # No passing setup-only result can override a recovery or unsafe failure.
    expected={c+'_'+k for c in ('slow','fast') for k in ('setup','hold','recovery','removal','mpw')}
    if set(groups)!=expected or any(not rows for rows in groups.values()):raise ValueError('incomplete native timing coverage')
    return not any(negative(r,k) for k,v in groups.items() for r in v) and not any('unsafe' in r['Inter-Clock Constrains'].lower() for r in interactions) and not missing

def selftest():
    base={c+'_'+k:[{'WNS(ns)':'1','WHS(ns)':'1','WPWS':'1','Failing Endpoints':'0','Failing End Point':'0'}] for c in ('slow','fast') for k in ('setup','hold','recovery','removal','mpw')}
    assert gate(base,[],[])
    for kind in ('slow_setup','slow_recovery','fast_recovery','fast_hold','slow_removal','slow_mpw'):
        g={k:[dict(r) for r in v] for k,v in base.items()}
        field='WPWS' if kind.endswith('mpw') else 'WHS(ns)' if kind.endswith(('hold','removal')) else 'WNS(ns)'
        g[kind][0][field]='-0.001';assert not gate(g,[],[])
    assert not gate(base,[{'Inter-Clock Constrains':'Timed(unsafe)'}],[])
    assert not gate(base,[],['clock-domain-uncovered'])
    bad=dict(base);bad.pop('fast_recovery')
    try:gate(bad,[],[])
    except ValueError:pass
    else:raise AssertionError('missing recovery accepted')
    return 10

def run(xml,db,expected,output):
    if Path(db).suffix.lower()!='.adf' or sha(db)!=expected:raise ValueError('exact routed ADF hash required, not PRR index')
    tree=ET.parse(xml)
    groups={c+'_'+k:table(tree,'report_timing_'+c+'_'+k) for c in ('slow','fast') for k in ('setup','hold','recovery','removal','mpw')}
    clocks=table(tree,'report_timing_clock_summary',True);inter=table(tree,'report_clock_interaction')
    counts={r['Check']:int(r['Number of Issues']) for r in table(tree,'check_timing_summary')}
    same={}
    for k,v in groups.items():
        if not k.endswith(('setup','hold')):continue
        for r in v:
            if r['Launch Clock']==r['Capture Clock']:same.setdefault(r['Launch Clock'],{})[k]=r
    uncovered=[r['Clock Name'] for r in clocks if r['Clock Name'] not in same]
    missing=uncovered+['native:'+k for k in ('no_clock','no_input_delay','no_output_delay','unexpandable_clocks') if counts.get(k,1)]
    neg={k:[r for r in v if negative(r,k)] for k,v in groups.items()}
    sums={k:{'FailingGroups':len(v),'FailedChecks':sum(int(r.get('Failing Endpoints',r.get('Failing End Point',0))) for r in v)} for k,v in neg.items()}
    details={c+'_'+k:table(tree,'report_timing_'+c+'_path_'+k) for c in ('slow','fast') for k in ('setup','hold','recovery','removal')}
    result={'Marker':'FPGA-1031-CDC-RESET-ONE','DiagnosticOnly':True,'ObservedUtc':datetime.now(timezone.utc).isoformat(),
        'FinalRoutedADF':{'Path':str(db),'SHA256':sha(db)},'NativeXML':{'Path':str(xml),'SHA256':sha(xml)},
        'Units':'All slack/period/delay values in native table columns are ns. Endpoints are per-check/per-corner, not unique FF counts.',
        'ClockSummaryAll':clocks,'ClockInteractionAll':inter,'CornerSummariesAll':groups,'DetailedPathsAllTypes':details,
        'NegativeByCheckAndCorner':neg,'FailureCounts':sums,
        'UnsafeInteractions':[r for r in inter if 'unsafe' in r['Inter-Clock Constrains'].lower()],
        'SameClockSetupHold':same,'ClocksWithoutObservedSameClockSetupHold':uncovered,
        'NoSameClockRowIsNotPass':True,'CheckTimingCounts':counts,'CoverageNotAccepted':missing,
        'AllInternalTimingChecksNonNegative':not any(neg.values()),'FullCoverageAndTimingGate':gate(groups,inter,missing),
        'ExceptionsAndSkewTables':[ET.tostring(t,encoding='unicode') for t in tree.findall('.//table') if any(x in t.attrib.get('id','').lower() for x in ('exception','skew'))],
        'CDCProtocolAndGrayBusSkewAccepted':False,'ExternalIOAccepted':False,'HardwareReleaseAllowed':False,
        'NativeCheckDetailTables':[ET.tostring(tree.find('.//table[@id="'+n+'"]'),encoding='unicode') for n in ('no_clock_detailed_report','unexpandable_clocks_detailed_report','no_input_delay_detailed_report','no_output_delay_detailed_report')]}
    with Path(output).open('x',encoding='utf-8') as f:json.dump(result,f,indent=2);f.write('\n')
    return result

if __name__ == '__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--selftest-only',action='store_true')
    parser.add_argument('--xml',type=Path)
    parser.add_argument('--final-adf',type=Path)
    parser.add_argument('--expected-sha256')
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    passed=selftest()
    if args.selftest_only:
        print(json.dumps({'SelfTestsPassed':passed,'HardwareAccessed':False}))
    else:
        if not all((args.xml,args.final_adf,args.expected_sha256,args.output)):
            parser.error('explicit XML, final ADF, expected SHA256 and new output are required')
        result=run(args.xml,args.final_adf,args.expected_sha256,args.output)
        print(json.dumps({'FailureCounts':result['FailureCounts'],'FullGate':result['FullCoverageAndTimingGate']}))
