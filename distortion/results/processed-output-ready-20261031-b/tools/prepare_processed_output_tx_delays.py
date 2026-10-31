"""Prepare/read native pad-delay queries without adding timing constraints.

Separate PLL-to-FF-clock and FF-clock-to-pad segments share a named physical
boundary. Their conservative min/max sums are relative to the same PLL node as
the forwarded clock. Unmeasured package/PCB skew and TX mode remain explicit.
"""
from pathlib import Path
import argparse
import hashlib
import json
import math
import re

import audit_processed_output_tx as tx

PLL = 'video_pll/u_gpll/gpll_inst/CLKOUT0'
EVIDENCE = tx.PROJECT / 'results/processed-output-tx-20261031/tx-evidence.json'
require, sha = tx.require, tx.sha
NUMBER = r'[-+]?\d+(?:\.\d+)?'
ROW = re.compile(r'^\s*(\S+)\s+(' + NUMBER + r')\s+(' + NUMBER + r')\s+([rf])\s+(.+?)\s*$')


def prepare(output):
    output = Path(output).absolute()
    require(output.resolve() == output and output.parent == tx.BUILD and not output.exists(),
            'fresh canonical direct processed-output directory required')
    evidence = json.loads(EVIDENCE.read_text())
    require(evidence['CandidateADFSHA256'] == tx.ADF_SHA and evidence['NativePadPathCount'] == 56,
            'bound output evidence differs')
    for path, digest in evidence['InputSHA256'].items():
        require(sha(path) == digest, 'TX evidence input changed')
    sources = {}
    for row in evidence['NativeUnconstrainedMaximumPaths']:
        if row['Port'] == 'pix_clk':
            continue
        require(row['Port'] not in sources or sources[row['Port']] == row['Source'],
                'output FF identity differs across corners')
        sources[row['Port']] = row['Source']
    require(set(sources) == tx.PORTS - {'pix_clk'}, '27 actual data/control ports required')
    jobs, lines = [], []
    def add(role, port, start, end, first, last, corner, condition):
        number = len(jobs)
        marker = f'TX_DELAY_{number:04d}'
        command = (f'get_path_delay -{first}_from {{{start}}} -{last}_to {{{end}}}'
                   + (' -min' if condition == 'min' else '')
                   + (' -fast' if corner == 'fast' else '') + ' -max_path 8')
        jobs.append({'Index': number, 'Marker': marker, 'Role': role, 'Port': port,
                     'Start': start, 'End': end, 'StartEdge': first, 'EndEdge': last,
                     'Corner': corner, 'Condition': condition, 'Command': command})
        lines.extend([f'puts {{{marker}_BEGIN}}', command, f'puts {{{marker}_END}}'])
    for corner in ('slow', 'fast'):
        for condition in ('min', 'max'):
            for port, clock in sorted(sources.items()):
                add('launch_clock', port, PLL, clock, 'rise', 'rise', corner, condition)
                for edge in ('rise', 'fall'):
                    add('clock_to_data', port, clock, port, 'rise', edge, corner, condition)
            for edge in ('rise', 'fall'):
                add('forwarded_clock', 'pix_clk', PLL, 'pix_clk', edge, edge, corner, condition)
    output.mkdir()
    body = output / 'query-body.tcl'
    body.write_text('\n'.join(lines)+'\n', encoding='ascii')
    plan = {'Schema': 'processed-output-pad-delay-query-v1', 'ADF': str(tx.NATIVE/'input.adf'),
            'ADFSHA256': tx.ADF_SHA, 'Jobs': jobs, 'QueryCount': len(jobs),
            'PLLReference': PLL, 'TXEvidence': str(EVIDENCE), 'TXEvidenceSHA256': sha(EVIDENCE),
            'BodySHA256': sha(body), 'ToolSHA256': sha(__file__),
            'HardwareAccessed': False, 'ConstraintsChanged': False,
            'EndpointScope': 'Native get_path_delay pad endpoint; FPGA package and PCB skew remain outside this measurement.'}
    (output/'plan.json').write_text(json.dumps(plan, indent=2)+'\n', encoding='utf-8')
    return plan


def parse_jobs(log, jobs):
    records = []
    for job in jobs:
        begin, end = job['Marker']+'_BEGIN', job['Marker']+'_END'
        parts = re.findall(r'(?ms)^' + re.escape(begin) + r'\r?\n(.*?)^' + re.escape(end) + r'\r?$', log)
        require(len(parts) == 1, 'missing/duplicate query marker: ' + job['Marker'])
        bodies = re.findall(r'(?ms)^Path start\.\.\.\r?\n(.*?)^Path end\.\.\.\r?$', parts[0])
        require(bodies, 'no native paths: ' + job['Marker'])
        require(len(bodies) == len(re.findall(r'(?m)^Path start\.\.\.\r?$', parts[0]))
                == len(re.findall(r'(?m)^Path end\.\.\.\r?$', parts[0])),
                'incomplete native path variant: ' + job['Marker'])
        paths = []
        for body in bodies:
            rows = [ROW.fullmatch(line) for line in body.splitlines()]
            rows = [m for m in rows if m is not None]
            require(len(rows) >= 2, 'incomplete native path')
            first, last = rows[0], rows[-1]
            require(first[5] == job['Start'] and last[5] == job['End'], 'native path boundary differs')
            expected_edges = {'rise':'r', 'fall':'f'}
            require(first[4] == expected_edges[job['StartEdge']]
                    and last[4] == expected_edges[job['EndEdge']], 'native selected edge differs')
            require(float(first[3]) == 0 and float(last[3]) > 0, 'native path origin/arrival invalid')
            require(all(math.isfinite(float(row[3])) for row in rows), 'nonfinite native path')
            paths.append({'DelayNS':float(last[3]), 'Rows':len(rows),
                          'NativeBodySHA256':hashlib.sha256(body.encode()).hexdigest()})
        # Preserve every report variant and conservatively take the extreme.
        delay = (min if job['Condition'] == 'min' else max)(p['DelayNS'] for p in paths)
        records.append({**job, 'DelayNS':delay, 'NativePaths':paths})
    require(len(records) == len(jobs), 'incomplete query inventory')
    return records


def analyze(plan_path, receipt_path, output):
    plan_path, receipt_path, output = map(Path, (plan_path, receipt_path, output))
    require(not output.exists(), 'output must be new')
    plan = json.loads(plan_path.read_text())
    receipt = json.loads(receipt_path.read_text())
    work = receipt_path.parent
    require(receipt.get('ExecutionPassed') is True and receipt.get('ExitCode') == 0
            and receipt.get('InputDrift') == [] and receipt.get('Diagnostics') == []
            and receipt.get('SourceADFSHA256') == receipt.get('ResultADFSHA256') == tx.ADF_SHA,
            'completed unchanged final-ADF query required')
    require(plan['ADFSHA256'] == tx.ADF_SHA and sha(plan['ADF']) == tx.ADF_SHA,
            'authority ADF differs')
    require(sha(work/'input.adf') == tx.ADF_SHA, 'executed ADF drift')
    require(sha(plan['TXEvidence']) == plan['TXEvidenceSHA256'], 'TX evidence drift')
    evidence = json.loads(Path(plan['TXEvidence']).read_text())
    require(all(sha(p) == digest for p, digest in evidence['InputSHA256'].items()),
            'TX authority input drift')
    require(sha(plan_path.parent/'query-body.tcl') == plan['BodySHA256'], 'query body changed')
    require(receipt['InputSHA256'].get(str((plan_path.parent/'query-body.tcl').resolve()))
            == plan['BodySHA256'], 'receipt did not use prepared body')
    log_path = work/'stdout.log'
    require(receipt['Artifacts']['stdout.log'] == sha(log_path), 'native log drift')
    watched = {str(p.resolve()):sha(p) for p in
               (plan_path, receipt_path, log_path, work/'input.adf', Path(__file__),
                Path(plan['TXEvidence']), Path(tx.__file__))}
    records = parse_jobs(log_path.read_text(encoding='gb18030', errors='strict'), plan['Jobs'])
    values = {(r['Role'],r['Port'],r['EndEdge'],r['Corner'],r['Condition']):r['DelayNS'] for r in records}
    require(len(values) == len(records), 'duplicate semantic queries')
    by_port = []
    for corner in ('slow','fast'):
        for port in sorted(tx.PORTS-{'pix_clk'}):
            clock_min = values['launch_clock',port,'rise',corner,'min']
            clock_max = values['launch_clock',port,'rise',corner,'max']
            data_min = clock_min + min(values['clock_to_data',port,e,corner,'min'] for e in ('rise','fall'))
            data_max = clock_max + max(values['clock_to_data',port,e,corner,'max'] for e in ('rise','fall'))
            require(data_min <= data_max, 'min/max data bounds reversed')
            for edge in ('rise','fall'):
                forwarded_min = values['forwarded_clock','pix_clk',edge,corner,'min']
                forwarded_max = values['forwarded_clock','pix_clk',edge,corner,'max']
                require(forwarded_min <= forwarded_max, 'clock min/max reversed')
                by_port.append({'Port':port,'Corner':corner,'SamplingEdgeHypothesis':edge,
                    'DataMinFromPLLNS':data_min,'DataMaxFromPLLNS':data_max,
                    'ForwardClockMinFromPLLNS':forwarded_min,'ForwardClockMaxFromPLLNS':forwarded_max,
                    'DataMinusClockMinimumNS':data_min-forwarded_max,
                    'DataMinusClockMaximumNS':data_max-forwarded_min})
    period, setup, hold = 1000/74.25, .879, .22
    scenarios = []
    for edge in ('rise','fall'):
        rows = [r for r in by_port if r['SamplingEdgeHypothesis'] == edge]
        dmin = min(r['DataMinusClockMinimumNS'] for r in rows)
        dmax = max(r['DataMinusClockMaximumNS'] for r in rows)
        # Delta = external data/package delay minus external clock/package delay.
        # Rising captures prior pixel at phase0; next data transition must hold.
        # Falling captures current pixel at phase0.4..0.6*T (unverified mode).
        phase_min, phase_max, sample = (0.,0.,'prior_pixel') if edge == 'rise' else (.4*period,.6*period,'current_pixel')
        lower = phase_max + hold - (dmin if sample == 'prior_pixel' else period+dmin)
        upper = phase_min - setup - (dmax-period if sample == 'prior_pixel' else dmax)
        scenarios.append({'SamplingEdgeHypothesis':edge,'PixelAssociation':sample,
                          'AssumedPLLPhaseMinNS':phase_min,'AssumedPLLPhaseMaxNS':phase_max,
                          'DataMinusClockMinNS':dmin,'DataMinusClockMaxNS':dmax,
                          'AllowedExternalDataMinusClockSkewMinNS':lower,
                          'AllowedExternalDataMinusClockSkewMaxNS':upper,
                          'NonemptyConditionalWindow':lower<=upper,
                          'ZeroExternalSkewInsideWindow':lower<=0<=upper})
    require(all(sha(p)==digest for p,digest in watched.items()), 'query evidence changed')
    result = {'Schema':'processed-output-pad-delay-analysis-v1','AnalysisCompleted':True,
              'CandidateADFSHA256':tx.ADF_SHA,'NativeQueries':len(records),'Paths':records,
              'PortCornerEdgeBounds':by_port,'ConservativeScenarios':scenarios,
              'CommonReference':PLL,'NominalPeriodNS':period,
              'TXSetupNS':setup,'TXHoldNS':hold,
              'SamplingModeFromRegistersVerified':False,'ExternalSkewMeasured':False,
              'ExternalTimingAccepted':False,'HardwareAccessed':False,'ConstraintsChanged':False,
              'InputSHA256':watched,
              'Limits':['All calculations are conditional on the stated sampling edge and pixel association.',
                        'Unmeasured FPGA package/PCB data-minus-clock skew must lie inside the stated interval.',
                        'No phase/jitter/PVT guarantee beyond native delay estimates and the cited simulation-only TX numbers.',
                        'The 40%-60% falling-edge phase is a scenario assumption, not a measured PLL/clock duty guarantee.',
                        'The actual 1281=04 sampling interpretation remains unverified; diagnostic display is separate evidence.']}
    output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--prepare',type=Path)
    p.add_argument('--plan',type=Path); p.add_argument('--receipt',type=Path); p.add_argument('--output',type=Path)
    a=p.parse_args()
    if a.prepare:
        result=prepare(a.prepare)
        print(json.dumps({'QueryCount':result['QueryCount'],'Body':str(a.prepare/'query-body.tcl')}))
    else:
        require(all((a.plan,a.receipt,a.output)), 'plan/receipt/output required')
        result=analyze(a.plan,a.receipt,a.output)
        print(json.dumps({'NativeQueries':result['NativeQueries'],'Scenarios':result['ConservativeScenarios']}))


if __name__=='__main__':
    main()
