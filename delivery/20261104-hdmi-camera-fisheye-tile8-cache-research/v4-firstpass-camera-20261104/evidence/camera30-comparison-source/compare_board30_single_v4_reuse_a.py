"""Summarize one actual V4 30-second saved review; no 600-second input or hardware access."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path

LAB=Path(__file__).resolve().parent
REPO=LAB.parents[2]
WORK=REPO/'distortion/work/hdmi-camera-fisheye-assoc2way256-fastpipe-20261104-a'
CORE=LAB/'compare_board30_results_a.py'
CORE_SHA='ac8d8bb632146232f9f6d9e5ad7587bda733dc40deeac2d5defca7a920ad5064'
if hashlib.sha256(CORE.read_bytes()).hexdigest()!=CORE_SHA:
    raise ValueError('reviewed rate comparison core changed')
spec=importlib.util.spec_from_file_location('saved_board30_comparison_core',CORE)
c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)


def load_short(review_path,baseline):
    review_path=Path(review_path).resolve();review=c.read(review_path)
    c.require(review.get('Schema')=='fastpipe-independent-board-fps-review-v4' and
              review.get('Passed') is True and review.get('InputDrift')==[], 'completed actual V4 independent review required')
    bound=review['Measurement'];measurement_path=Path(bound['Path']).resolve()
    c.require(measurement_path==WORK/'fps-corrected-v4-reuse-a/receipt.json' and c.ref(measurement_path)==bound and
              review.get('InputSHA256',{}).get(str(measurement_path))==bound['SHA256'], 'actual short measurement identity differs')
    receipt=c.read(measurement_path)
    c.require(receipt.get('schema')=='hdmi-camera-fisheye-host-timed-fps-v1' and
              review['Identity']['Bitstream']==receipt['bitstream'], 'actual measurement and reviewed bitstream differ')
    c.require(review['Identity'].get('FirstPassPhysicalProofReused') is True and
              review['Identity'].get('OriginalSecondPassExitCode')==-1 and
              review['Identity'].get('SecondPassSuccessClaimed') is False, 'transparent saved first-pass identity required')
    summary=c.summarize(receipt);c.compare_analysis(summary,review['Analysis'],30)
    old=baseline['HardwareBaseline30Seconds']
    summary.update({'Review':c.ref(review_path),'Measurement':bound,'Bitstream':receipt['bitstream'],'AcquisitionSeconds':30,
       'DecoderTargetFPSNotAssertedPreserved':review['Analysis']['TargetFPSNotAsserted'],
       'BaselineComparison':{'BaselineReceipt':old['Receipt'],'BaselineBitSHA256':baseline['OldBoardBitSHA256'],
          'BaselineNominalRates':old['NominalRates'],'BaselineHostRates':old['HostRates'],'BaselineProcessMS':old['ProcessMS'],
          'ObservedNominalUniqueThroughputRatio':summary['NominalRates']['unique_presented_frames']/old['NominalRates']['unique_presented_frames'],
          'SameSceneOrControlledWorkloadNotEstablished':True,'SimulationNotSubstitutedForBoardMeasurement':True},
       'CounterFollowUpSuggestions':c.suggestions(summary)})
    return summary


def markdown(report):
    s=report['Short30Seconds'];a=s['Assessment'];p=s['ProcessMS'];b=s['BaselineComparison']
    lines=['# Actual V4 30-second board measurement','',
      'Requested counter criteria: **'+('MET' if a['MeetsRequested30FPSCriteria'] else 'NOT MET')+'**.',
      'Only this 30-second acquisition is assessed. No 600-second stability or visual confirmation is claimed.','',
      f"Samples: {s['SampleCount']}; nominal counter window: {s['NominalCounterWindowSeconds']:.6f} s; host window: {s['HostCounterWindowSeconds']:.6f} s.",'',
      '| Counter | Nominal /s | Host /s | Old nominal /s |','|---|---:|---:|---:|']
    for key in c.COUNTERS:
        lines.append(f"| {c.LABELS[key]} | {s['NominalRates'][key]:.6f} | {s['HostRates'][key]:.6f} | {b['BaselineNominalRates'][key]:.6f} |")
    lines+=['',f"Last-process snapshots, ms: min {p['Min']:.6f}; median {p['Median']:.6f}; p95 {p['P95NearestRank']:.6f}; max {p['Max']:.6f}.",
      s['ProcessStatisticsBasis'],
      f"Continuous telemetry: {a['ContinuousTelemetryCadence']}; no observed errors: {a['NoObservedErrors']}.",
      f"Capture/source ratio: {s['CaptureSourceRatio']}; unique/scan ratio: {s['UniqueScanRatio']}; repeat/scan ratio: {s['RepeatScanRatio']}.",'',
      'Nominal capture/process/unique/scan must be 30 +/-1%; host rates 30 +/-3%; source 60 +/-3%. Adjacent sequence/core tick/host cadence and existing clean counters must pass. Repeated scans are not new frames.','',
      'Diagnostic follow-up, not a proven root cause:','']
    lines+=['- '+value for value in s['CounterFollowUpSuggestions']]
    lines+=['','The old baseline is an observed comparison; identical scene or controlled workload is not established.',
      'Review: '+s['Review']['Path'],'Measurement: '+s['Measurement']['Path'],'']
    return '\n'.join(lines)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--review',type=Path,default=LAB/'board-fps30-independent-review-v4-reuse-a.json')
    p.add_argument('--baseline',type=Path,default=LAB/'board30-baseline-comparison-a.json')
    p.add_argument('--output-prefix',type=Path,default=LAB/'board30-short-measured-comparison-v4-reuse-a')
    a=p.parse_args()
    for path in (a.review,a.baseline):c.require(path.is_file(),'completed actual saved input missing: '+str(path))
    out_json=Path(str(a.output_prefix)+'.json');out_md=Path(str(a.output_prefix)+'.md')
    c.require(not out_json.exists() and not out_md.exists(),'fresh short report output required')
    baseline=c.read(a.baseline)
    c.require(baseline.get('Schema')=='fastpipe-board30-local-baseline-comparison-v1','known saved hardware baseline required')
    short=load_short(a.review,baseline)
    report={'Schema':'fastpipe-board30-single-window-comparison-v4','ReportGenerated':True,
       'CreatedUTC':datetime.now(timezone.utc).isoformat(),'Source':c.ref(Path(__file__)),
       'ComparisonCore':c.ref(CORE),'Baseline':c.ref(a.baseline),'Short30Seconds':short,
       'Assessment':{**short['Assessment'],'Only30SecondsNot600':True,'NoVisual':True,
          'ReleaseAuthorizedByThisReport':False},
       'HardwareAccessed':False,'UARTOpened':False,'FullClosureRehashed':False,
       'Only30SecondsNot600':True,'NoVisual':True}
    with out_json.open('x',encoding='utf-8')as f:json.dump(report,f,indent=2,ensure_ascii=False,allow_nan=False);f.write('\n')
    with out_md.open('x',encoding='utf-8')as f:f.write(markdown(report))
    print(json.dumps({'Report':c.ref(out_json),'Markdown':c.ref(out_md),
       'Assessment':report['Assessment'],'NominalRates':short['NominalRates'],'HostRates':short['HostRates'],
       'ProcessMS':short['ProcessMS'],'Samples':short['SampleCount'],
       'CounterFollowUpSuggestions':short['CounterFollowUpSuggestions']},ensure_ascii=False))
    return 0


if __name__=='__main__':raise SystemExit(main())

