"""Summarize and optionally seal today's finite physical optical evidence."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,csv,hashlib,json,shutil
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from native_optical_audit import analyze,sha,read,ROOT

def main():
    p=argparse.ArgumentParser();p.add_argument('--date',required=True)
    p.add_argument('--seal',action='store_true');args=p.parse_args()
    date=datetime.strptime(args.date,'%Y%m%d').strftime('%Y%m%d')
    out=ROOT/'results'/('lab-'+date);rows=[];audits=[];capture_dirs=[]
    for pose in ('center','left','left-adjusted','right','upper','lower'):
        folder=ROOT/'captures/gamma-triplets'/f'grid-{pose}-{date}'
        if not (folder/'summary.json').exists():continue
        report=analyze(folder/'group-00000001','grid',out/f'grid-{pose}.json')
        audits.append(report);capture_dirs.append(folder)
        complete=report['measurement_complete']
        rows.append({'pose':pose,'complete':complete,
            'raw_rms_px':report['grid']['raw'].get('equal_line_rms_px'),
            'corrected_rms_px':report['grid']['before'].get('equal_line_rms_px'),
            'pixel_rms_reduction_percent':report.get('equal_line_rms_px_reduction_percent'),
            'span_normalized_rms_reduction_percent':report.get('equal_line_rms_fraction_of_span_reduction_percent'),
            'source_crc32':report['source_crc32']})
    if not rows:raise ValueError('No fresh grid evidence')
    neutral_dir=ROOT/'captures/gamma-triplets'/f'neutral-paper-{date}'
    neutral=analyze(neutral_dir/'group-00000001','neutral',out/'neutral-color.json')
    capture_dirs.append(neutral_dir)
    baseline=read(out/'baseline-check.json');transaction=read(out/'baseline-transaction.json')
    if not baseline['passed'] or not transaction['acknowledged']:
        raise ValueError('Baseline evidence failed')
    status=read(ROOT/'status.json')
    if status['current_sram_target']!='heartbeat':raise ValueError('Board must be recorded idle')
    transfers=sorted((ROOT/'build/heartbeat').glob('program-evidence-*/transfer.json'),key=lambda f:f.stat().st_mtime)
    idle=read(transfers[-1])
    if not idle['Done'] or idle['CheckedOn']!=status['current_connection']['checked_on']:
        raise ValueError('Current recorded idle lacks actual matching transfer')
    manifests={};inputs=[]
    for target in ('corrected_gamma_d5','gamma_capture_settled_d5','heartbeat'):
        path=ROOT/'build'/target/'validated-build.json';m=read(path)
        if sha(Path(m['Bitstream']))!=m['SHA256']:
            raise ValueError('Bitstream fingerprint changed')
        if target!='heartbeat' and ('TimingReport' not in m or 'SourceSHA256' not in m):
            raise ValueError('Video/capture build lacks final timing/source proof')
        if 'TimingReport' in m and sha(Path(m['TimingReport']))!=m['TimingSHA256']:
            raise ValueError('Timing fingerprint changed')
        for name,digest in m.get('SourceSHA256',{}).items():
            if sha(ROOT/name)!=digest:raise ValueError('Build source fingerprint changed: '+name)
            inputs.append(ROOT/name)
        manifests[target]={'bitstream_sha256':m['SHA256'],'timing_sha256':m.get('TimingSHA256'),
            'source_manifest_available':'SourceSHA256' in m}
        inputs.extend((path,Path(m['Bitstream'])))
        if 'TimingReport' in m:inputs.append(Path(m['TimingReport']))
    with (out/'grid-results.csv').open('w',newline='',encoding='utf-8-sig') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    complete=[r for r in rows if r['complete']]
    fig,axes=plt.subplots(1,2,figsize=(10,3.8),layout='constrained')
    x=list(range(len(complete)));labels=[r['pose'] for r in complete]
    axes[0].bar([v-.18 for v in x],[r['raw_rms_px'] for r in complete],.36,label='Raw')
    axes[0].bar([v+.18 for v in x],[r['corrected_rms_px'] for r in complete],.36,label='FPGA corrected')
    axes[0].set_ylabel('Grid line RMS residual (pixels)');axes[0].legend()
    axes[1].bar(x,[r['span_normalized_rms_reduction_percent'] for r in complete],.5,color='#356ca5')
    axes[1].axhline(0,color='black',lw=.8);axes[1].set_ylabel('Span-normalized RMS reduction (%)')
    for ax in axes:ax.set_xticks(x,labels);ax.tick_params(colors='black')
    fig.suptitle('Independent grid observations: no lens refit; one capture per pose')
    fig.savefig(out/'grid-results.png',dpi=180);plt.close(fig)
    result={'recorded_utc':datetime.now(timezone.utc).isoformat(),'date':date,
        'baseline':baseline,'baseline_visual_observation':read(out/'baseline-user-observation.json'),
        'grid_poses':rows,'neutral_center':neutral['statistics']['raw'],
        'builds':manifests,'last_actual_idle_transfer':idle,
        'full_optical_acceptance':False,
        'limits':'One captured source per pose; no repetition statistics, full-field acceptance, MTF or color accuracy claim. HDMI refresh differs from newly corrected frame rate. ADC is an estimate. SRAM recovery is not Flash autonomous boot.',
        'source_sha256':{name:sha(ROOT/name) for name in (
            'tools/native_optical_audit.py','tools/record_optical_session.py','tests/test_native_optical_audit.py')}}
    (out/'optical-session.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    if args.seal:
        inputs.extend(f for folder in capture_dirs for f in folder.rglob('*') if f.is_file())
        inputs.extend(f for f in out.iterdir() if f.is_file())
        inputs.extend(ROOT/name for name in result['source_sha256'])
        inputs.extend(ROOT/name for name in ('tools/check-grid-straightness.py','tools/capture-gamma-triplets.py',
            'tools/frozen_gamma_analysis.py','tools/evaluate-tone-pair.py','tools/frame_protocol.py',
            'tools/gamma_triplets.py','tools/program-heartbeat.ps1','tools/host-angle.py','model/reference.py',
            'status.json','README.md','output/project/成果记录.md',
            'build/gamma_frozen_native_20261008_sim/reference.json'))
        inputs.append(transfers[-1])
        archive=ROOT/'results/verified'/('optical-session-'+datetime.now().strftime('%Y%m%d-%H%M%S-%f'))
        archive.mkdir();hashes={}
        for source in sorted(set(inputs)):
            source=source.resolve()
            if not source.is_relative_to(ROOT):raise ValueError('Archive source outside workspace')
            name=source.relative_to(ROOT);dest=archive/name
            dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,dest)
            digest=sha(source)
            if sha(dest)!=digest:raise ValueError('Archive copy differs')
            hashes[name.as_posix()]=digest
        (archive/'files-sha256.json').write_text(json.dumps(hashes,indent=2)+'\n')
        if not all(sha(archive/name)==digest for name,digest in hashes.items()):raise ValueError('Archive hash failure')
        result['archive']={'path':str(archive),'verified_files':len(hashes)}
    print(json.dumps({'grid_poses':rows,'idle_confirmed':idle['CheckedOn'],'archive':result.get('archive')}))

if __name__=='__main__':main()
