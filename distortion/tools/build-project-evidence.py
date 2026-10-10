"""Read-only project proof inventory and engineering budgets; no hardware I/O."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,re,csv

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'output/project'
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest().upper()

def bound(path):
    path=Path(path).resolve()
    if not path.is_relative_to(ROOT):raise ValueError('Evidence outside project')
    return path

def verify_sources(obj,key='source_sha256'):
    for name,digest in obj[key].items():
        if sha(bound(ROOT/name))!=digest.upper():raise ValueError('Evidence input changed: '+name)

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    lab=ROOT/'results/lab-20261008';session=read(lab/'session.json')
    release=ROOT/'results/verified/lab-release-20261008-191622-981116'
    hashes=read(release/'files-sha256.json')
    for name,digest in hashes.items():
        if sha(bound(release/name))!=digest:raise ValueError('Sealed release changed: '+name)
    d5=read(lab/'d5-correction.json');video=read(lab/'d5-video-check.json')
    if not d5['physical_restoration_passed'] or not video['passed']:raise ValueError('Corrected physical acceptance missing')
    verify_sources(video);verify_sources(d5,'tools_sha256')
    target='corrected_gamma_d5';build=read(ROOT/f'build/{target}/validated-build.json')
    verify_sources(build,'SourceSHA256')
    if sha(bound(build['Bitstream']))!=build['SHA256'] or sha(bound(build['TimingReport']))!=build['TimingSHA256']:
        raise ValueError('Stable build changed')
    if video['capture_transfer']['SHA256']!=build['SHA256']:raise ValueError('Video not bound to stable build')
    parity=read(lab/'pipeline-parity-regression.json');verify_sources(parity)
    sfr=read(OUT/'sfr-validation.json');verify_sources(sfr)
    records=[
        {'id':'E01','claim':'Camera D5 mapping restored','level':'physical','value':'14400/14400 white pixels FFFF','file':'results/lab-20261008/d5-correction.json','limit':'Remaining color requires a neutral target'},
        {'id':'E02','claim':'Corrected full-frame remap and Gamma match integer oracle','level':'physical','value':'640x480; zero mismatched pixels','file':'captures/gamma-triplets/optical-d5-fixed-20261008/summary.json','limit':'Empty-chair scene; no optical quality acceptance'},
        {'id':'E03','claim':'Corrected stable live 12-angle rotation','level':'physical_serial','value':f"{video['approx_rates_per_second']['CF']:.4f} new fps; video error counters zero",'file':'results/lab-20261008/d5-video-check.json','limit':'38.24-second sampled span; no human visual confirmation'},
        {'id':'E04','claim':'Stable core final timing and source binding','level':'final_route','value':'125 MHz; D5 AA23','file':f'build/{target}/validated-build.json','limit':'SRAM transfer; not repeated autonomous Flash boot'},
        {'id':'E05','claim':'Parity cache matches baseline pixels and cadence','level':'simulation','value':'3686400 pixels; 12 angles; 2322 queries; 161 stream packets','file':'results/lab-20261008/pipeline-parity-regression.json','limit':'Synthetic DDR stalls; historical camera words used as received'},
        {'id':'E06','claim':'Parity cache mapped RAM reduction','level':'mapped_only','value':'DRM 36 to 28','file':'build/corrected_pipeline_parity_cadence/build.log','limit':'Final route timed out; no valid bitstream or board speed claim'},
        {'id':'E07','claim':'Host protocol and evidence gates','level':'host_tests','value':str(sum(x['tests'] for x in session['host_tests']))+' tests passed','file':'results/lab-20261008/session.json','limit':'Separate from hardware and optical acceptance'},
        {'id':'E08','claim':'Slanted-edge diagnostic estimator','level':'synthetic_validation','value':f"{sfr['host_tests']} tests; maximum Gaussian MTF50 error {100*sfr['maximum_relative_error']:.2f}%",'file':'output/project/sfr-validation.json','limit':'No physical edge measurement; not ISO compliance'},
        {'id':'E09','claim':'Historical center grid collinearity','level':'historical_diagnostic','value':'15.87% RMS residual reduction in one complete pair','file':'results/lab-20261008/grid-straightness.json','limit':'Pre-D5 correction; two edge pairs incomplete; fresh acceptance pending'}]
    mapped={}
    for name in ('corrected_pipeline_cadence_seed4','corrected_pipeline_parity_cadence'):
        log=(ROOT/f'build/{name}/build.log').read_bytes()
        text=log.decode('utf-16' if log.startswith((b'\xff\xfe',b'\xfe\xff')) else 'utf-8-sig')
        match=re.search(r'\|\s*DRM\s*\|\s*(\d+)\s*\|',text)
        if not match:raise ValueError('Missing mapped DRM count')
        mapped[name]=int(match[1])
    if list(mapped.values())!=[36,28]:raise ValueError('Unexpected resource comparison')
    for row in records:row['sha256']=sha(bound(ROOT/row['file']))
    rows=[]
    for w,h,fps in ((640,480,30),(1280,720,15),(1280,720,30),(1920,1080,30),(1920,1080,60)):
        pixels=w*h;byte_rate=pixels*fps*2
        stride=1<<(pixels*2-1).bit_length()
        rows.append({'width':w,'height':h,'target_new_fps':fps,'minimum_dvp_rgb565_byte_clock_hz':byte_rate,
            'core_cycles_per_pixel_budget_at_125mhz':125000000/(pixels*fps),
            'rgb565_frame_bytes':pixels*2,'power_of_two_bank_stride_bytes':stride,'four_bank_bytes':stride*4,
            'uncached_four_neighbor_DDR_pixel_traffic_bytes_per_second':pixels*fps*14,
            'current_48mhz_input_constraint_covers_minimum':byte_rate<=48000000})
    status=read(ROOT/'status.json')
    result={'recorded_utc':datetime.now(timezone.utc).isoformat(),'hardware_accessed':False,
        'stable_target':target,'stable_bitstream_sha256':build['SHA256'],'evidence':records,
        'verified_release':str(release),'verified_release_files':len(hashes),
        'last_known_board_target':status['current_sram_target'],'last_actual_idle_confirmation':status['current_connection']['checked_on'],
        'engineering_budgets_not_achieved_performance':rows,
        'budget_assumptions':'125 MHz core; 8-bit RGB565 DVP requires two bytes/pixel; bank stride is in BYTES. Ideal DDR traffic counts 2-byte source write + four 2-byte neighbours + 2-byte result write + 2-byte display read, excludes arbitration/bursts/repeated display/command overhead. Reuse can reduce reads; misses can increase traffic. A timing constraint is not a measured camera clock or sensor maximum.',
        'local_deadline':'2026-10-31','feature_freeze_target':'2026-10-20','rehearsal_release_target':'2026-10-26',
        'published_deadline':{'date':'2026-11-04T18:00:00+08:00','source':'https://jiaowu.buaa.edu.cn/info/1016/9028.htm',
            'scope':'Published university notice; latest organiser and campus deadlines require confirmation. Preserve earlier user deadline.'},
        'awards':{'target':'National first prize; best engineering and enterprise special award as additional targets',
            'source':'https://jiaowu.buaa.edu.cn/info/1016/9028.htm','award_level_established':False},
        'source_sha256':{'tools/build-project-evidence.py':sha(Path(__file__))}}
    (OUT/'evidence-register.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    with (OUT/'evidence-register.csv').open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(records[0]));writer.writeheader();writer.writerows(records)
    print(json.dumps({'evidence_entries':len(records),'sealed_files_verified':len(hashes),'board_last_known':status['current_sram_target'],'hardware_accessed':False}))

if __name__=='__main__':main()
