"""Isolated tile8/dual-stripe engine in the actual selected S3 system closure.

New fixture and work outputs only. Existing RTL and simulation helpers remain
unchanged. Native runs require this exact source closure's completed small run.
"""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
import tempfile
from pathlib import Path
import re
import time

import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'.venv/Lib/site-packages'))

import numpy as np
import cv2
import generate_hdmi_fisheye_profile as fish
from hdmi_camera_direct_audit import static_helpers

import generate_1080_core_vectors as cpu
import run_board1080_rowpipe_system_sim as rowpipe
from simulation_tools import prepare_compile_sources, resolve_vivado_bin, verify_compile_sources

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'work/hdmi-camera-fisheye-tile8df8-20261103-a'
SELF = 'tools/run_hdmi_camera_fisheye_tile8df8_sustained_sim.py'
BENCH = 'tests/tb_hdmi_camera_fisheye_tile8df8_sustained.sv'
SAMPLER = 'rtl/experimental/hdmi_camera_pixel_sampler.v'
CANDIDATE_CACHE = 'rtl/experimental/ddr_neighbour_cache_scatter16_rowpipe_directfill.v'
ORIGINAL_CACHE = 'rtl/experimental/ddr_neighbour_cache_scatter16_rowpipe_fill8r3.v'
ORIGINAL_CACHE_SHA256 = 'ccddbc0293698184a3695744d7fca88350969ccc5f69cb1762b39eac84a0d294'
CACHE_INDEX_BITS = 8
CANDIDATE_ENGINE = 'rtl/experimental/hdmi_camera_fisheye_engine_tile8df8.v'
CANDIDATE_CACHE_SHA256 = 'd4730a733bc8f84886d268fcc90bb702db035a41867c812d6119694fbbf35b1e'
TOP = 'tb_hdmi_camera_fisheye_tile8df8_sustained'
MARKER = 'PASS hdmi_camera_fisheye_tile8df8_sustained:'
SCHEMA = 'hdmi-camera-fisheye-tile8df8-sustained-simulation-v1'
REPORT = 'simulation.json'


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'),
        parse_constant=lambda value: (_ for _ in ()).throw(ValueError('nonfinite JSON ' + value)))


def closure(cache_kind='directfill'):
    require(cache_kind in ('directfill','original'), 'explicit selected cache kind required')
    cache = CANDIDATE_CACHE if cache_kind=='directfill' else ORIGINAL_CACHE
    cache_sha = CANDIDATE_CACHE_SHA256 if cache_kind=='directfill' else ORIGINAL_CACHE_SHA256
    require(isinstance(cache_sha,str) and len(cache_sha)==64 and sha(ROOT/cache)==cache_sha,
        'selected cache must be frozen before any system run')
    old = rowpipe.system
    configured = rowpipe.configuration(ROOT, old.COMPILE, old.fixtures.previous.FROZEN, old.HELPERS)
    replace = {'tests/tb_board1080_system.sv': BENCH,
        'rtl/experimental/hdmi1080_video_system_cdc_reset.v': 'rtl/experimental/hdmi_camera_fisheye_system_c.v',
        'rtl/experimental/hdmi1080_input_write_link.v': 'rtl/experimental/hdmi_camera_fisheye_input_link.v',
        'rtl/experimental/lens1080_bank_core.v': 'rtl/experimental/hdmi_camera_fisheye_bank_tile8.v',
        'rtl/experimental/pipeline_gamma_frame_engine_1080_scatter4.v': CANDIDATE_ENGINE,
        'rtl/experimental/rotated_remap_core_gamma_scatter4.v': 'rtl/experimental/hdmi_camera_fisheye_core.v',
        'rtl/experimental/ddr_neighbour_cache_scatter4_rowpipe.v': cache,
        'rtl/experimental/ddr_remap_sample_scatter4_rowpipe.v': 'rtl/experimental/ddr_remap_sample_scatter16_rowpipe.v',
        'rtl/ddr_read_arbiter.v': 'rtl/experimental/ddr_read_arbiter_fill8r2.v',
        'rtl/experimental/ddr_adaptive_result_writer.v': 'rtl/experimental/ddr_adaptive_result_writer_dualstripe.v'}
    removed = {'rtl/pixel_inverse_rotation.v','rtl/bounded_brown_inverse_mapper.v',
        'rtl/ddr_remap_sample.v','rtl/experimental/ddr_compact_neighbour_cache.v',
        'rtl/experimental/rotated_remap_core_gamma.v','rtl/experimental/adaptive_gamma_stream.v',
        'rtl/experimental/adaptive_gamma_tagged.v'}
    names = tuple(replace.get(n,n) for n in configured['COMPILE'] if n not in removed) + (SAMPLER,
        'rtl/experimental/hdmi_camera_fisheye_mapper.v','rtl/experimental/hdmi_camera_fisheye_rom.v',
        'rtl/experimental/camera720_view_control.v')
    require(len(names)==len(set(names)), 'duplicate fisheye source module')
    headers = ('rtl/video_crc32.vh',fish.PROFILE_HEADER,fish.TABLE_HEADER)
    helpers = tuple(dict.fromkeys((*configured['HELPERS'],SELF,'tools/generate_1080_core_vectors.py',
        'tools/generate-brown-vectors.py','model/reference.py','tools/generate_hdmi_fisheye_profile.py',
        'tools/run_board1080_rowpipe_system_sim.py','tools/hdmi_camera_direct_audit.py',
        'tools/run_hdmi_camera_fisheye_system_c_sim.py','tests/tb_hdmi_camera_fisheye_system_c.sv',
        'rtl/experimental/ddr_remap_sample_scatter4_rowpipe.v',
        'tools/run_hdmi_camera_fisheye_fill8_system_sim.py','tests/tb_hdmi_camera_fisheye_fill8_system.sv','rtl/ddr_read_arbiter.v',
        'tools/run_hdmi_camera_fisheye_fill8r2_system_sim.py','tests/tb_hdmi_camera_fisheye_fill8r2_system.sv',
        'rtl/experimental/ddr_neighbour_cache_scatter16_rowpipe.v')))
    frozen = {n:h for n,h in configured['FROZEN'].items() if n not in removed and n not in replace}
    reference=read(ROOT/'work/hdmi-camera-fisheye-fill8r3-20261103-a/system-native-a/simulation.json')
    require(reference['Passed'] is True and reference['Mode']=='native', 'completed selected R3 native reference required')
    selected=reference['SourceSHA256']
    for name in (*names,*headers):
        if name in selected:
            require(sha(ROOT/name)==selected[name], 'selected S3/R3 core/cache/mapper/profile bytes differ: '+name)
    return names,headers,helpers,frozen



def identity_config(width, height):
    require(type(width) is type(height) is int and width >= 16 and height >= 8
        and width % 16 == 0 and height % 8 == 0, 'aligned identity geometry required')
    cx, cy = (width - 1) * 128, (height - 1) * 128
    return [cx, cy, cx, cy, 262144, 262144, 1048576, 1048576, 0, 0, 0, 0, 0]


def identity_fixture(width, height):
    """All coordinates/borders checked by independent integer/bilinear CPU code."""
    config = identity_config(width, height)
    y, x = np.indices((height, width), dtype=np.int64)
    sx, sy, bad, radius = cpu.project_integer(x * 256, y * 256, config)
    require(np.array_equal(sx, x * 256) and np.array_equal(sy, y * 256)
        and not bad.any() and int(radius.max()) <= 8388608,
        'full-frame identity coordinates or radius differ')
    scalar = cpu.scalar_oracle()
    for py in (0, height // 2, height - 1):
        for px in (0, width // 2, width - 1):
            ax, ay, invalid = scalar.project(px * 256, py * 256, config)
            require((ax, ay, bool(invalid)) == (px * 256, py * 256, False),
                    'scalar identity border/center differs')
    source = ((((x + 3 * y) % 32) << 11) | (((2 * x + y) % 64) << 5)
              | ((x ^ y) % 32)).astype(np.uint16)
    frames = [source, source ^ np.uint16(0x5a3c), source ^ np.uint16(0xa5c3)]
    for frame in frames:
        mapped = cpu.remap_fixed(cpu.expand565(frame), sx / 256., sy / 256.)
        expected = cpu.tone(cpu.pack565(mapped), np.zeros(frame.shape, dtype=bool), 0)
        require(np.array_equal(expected, frame), 'identity bilinear/RGB565/gamma0 pixel oracle differs')
    return config, frames


def fixtures(work, mode, cache_kind='directfill'):
    width,height=(32,16) if mode=='small' else (1920,1080)
    _,frames=identity_fixture(width,height)
    yy,xx=np.indices((height,width),dtype=np.int64)
    cfg=fish.config(width=width,height=height)
    (work/'config.vh').write_text(('`define FISHEYE_DIRECT_FILL\n' if cache_kind=='directfill' else '')+f'localparam integer VEC_WIDTH={width},VEC_HEIGHT={height},SIM_CACHE_INDEX_BITS={CACHE_INDEX_BITS},SIM_DIRECT_FILL={int(cache_kind=="directfill")};\n',encoding='ascii')
    hashes={'config.vh':sha(work/'config.vh')};metadata=[]
    for index,frame in enumerate(frames):
        corrected=True
        sx,sy,black=fish.fixed_map(xx*256,yy*256,corrected=corrected,config=cfg,width=width,height=height)
        mask=black | (sx<=-256) | (sy<=-256) | (sx>=width*256) | (sy>=height*256)
        sampled=cpu.remap_fixed(cpu.expand565(frame),sx/256.,sy/256.)
        result=np.where(mask,0,cpu.pack565(sampled)).astype(np.uint16)
        if corrected:require(np.any(result!=frame),'corrected texture must differ from identity')
        else:require(np.array_equal(result,frame) and not mask.any(),'raw RGB565 identity differs')
        cpu.write_mem(work/f'source{index}.mem',frame,4)
        cpu.write_mem(work/f'expected{index}.mem',result,4)
        cpu.write_mem(work/f'masks{index}.mem',mask.astype(np.uint8),1)
        source_crc=cpu.pixel_crc(frame);result_crc=cpu.pixel_crc(result)
        (work/f'sourcecrc{index}.mem').write_text(source_crc+'\n',encoding='ascii')
        (work/f'crc{index}.mem').write_text(result_crc+'\n',encoding='ascii')
        metadata.append({'Texture':index,'Corrected':corrected,'SourceCRC32':source_crc,
            'ExpectedCRC32':result_crc,'MaskedPixels':int(mask.sum()),'ChangedPixels':int((result!=frame).sum())})
        for stem in ('source','expected','masks','crc','sourcecrc'):
            name=f'{stem}{index}.mem';hashes[name]=sha(work/name)
    ht,vt,x0,y0,hs,vs=(80,40,10,3,4,1) if mode=='small' else (2200,1125,192,41,44,5)
    cycles=2000000 if mode=='small' else 60000000
    timing=(f'localparam integer SIM_HT={ht},SIM_VT={vt},SIM_X0={x0},SIM_Y0={y0},SIM_HS={hs},SIM_VS={vs};\n'
        f'localparam integer SIM_FRAMES={8 if mode=="small"else 16},SIM_MAX_CYCLES={cycles},SIM_FAULT_PHASE=0;\n'
        'localparam integer SIM_OUTPUT_PHASE_PS=1733,SIM_DDR_FIRST_R_LATENCY=40;\n')
    (work/'timing.vh').write_text(timing,encoding='ascii');hashes['timing.vh']=sha(work/'timing.vh')
    return {'Width':width,'Height':height,'IntegerConfig':cfg['Constants'],'Frames':metadata,
        'CoordinateModel':'C OpenCV fisheye, 1025-node radial Q30 interpolation; raw exact identity',
        'ProjectionBalance':.5,'GammaMode':0,'InputClockHz':148500000,'OutputClockHz':74250000,
        'HT':ht,'VT':vt,'InputSourceFrames':8 if mode=='small'else 16,'FixtureSHA256':hashes}



def profile(path):
    path = Path(path).resolve()
    value = read(path)
    require(value.get('Schema') == 'hdmi-camera-observed-digital-timing-v1'
        and value.get('TransportPassed') is True and value.get('RejectedPackets') == 0
        and value.get('BuildTags') == ['0x48445202'] and type(value.get('ValidWindows')) is int
        and value['ValidWindows'] > 0 and value.get('UnavailableReasons') == {}
        and value.get('SemanticIssues') == [] and value.get('ConfigurationErrorCodes') == [0]
        and value.get('VSActiveHighSelectedForNextPrototype') is True
        and value.get('DEActiveHighSelectedForNextPrototype') is True
        and value.get('VSPeriodPCLK') == [2475000] and value.get('HSPeriodPCLK') == [2200]
        and value.get('DEHighWidthPCLK') == [1920] and value.get('ActiveLinesPerVS') == [1080],
        'source-bound measured148.5MHz digital input profile required')
    for field, low, high in (('EstimatedPCLKHz', 148000000, 149000000),
            ('EstimatedVSRisingHz', 59, 61), ('EstimatedVSFallingHz', 59, 61)):
        number = value.get(field)
        require(type(number) in (int, float) and math.isfinite(number) and low <= number <= high,
                'measured input clock/cadence differs from148.5/60 model: ' + field)
    source = value['Source']
    require(sha(source['Path']) == source['SHA256'], 'measured input evidence changed')
    return {str(path): sha(path), source['Path']: source['SHA256']}


def verify_small(path, sources, compiled, headers):
    path=Path(path).resolve();value,_=verify(path)
    require(value['Mode']=='small' and value['SourceSHA256']==sources,
        'native requires completed same-source fisheye small report')
    return {'Path':str(path),'SHA256':sha(path)}



def assess(work, fixture, cache_kind='directfill'):
    summary=read(work/'summary.json'); n=fixture['Width']*fixture['Height']
    expected={'passed':True,'frames_input':fixture['InputSourceFrames'],'frames_committed':4,'frames_processed':4,
        'frames_published':4,'frames_unique_scanned':4,'unique_scanned_pixels':4*n,
        'source_beats':4*n//16,'result_beats':4*n//16,'output_underflows':0,
        'output_crc_mismatches':0,'dropped_frames':0,'overflow_frames':0,'final_drain':True,
        'fault_injection_exercised':False,'whole_frame_drop_exercised':False,
        'key_toggles':0,'mode_changes_while_processing':0,'frame_mode_latches':4}
    require(all(type(summary.get(k)) is type(v) and summary[k]==v for k,v in expected.items()),
        'sustained unthrottled source/four actual corrected scans/drain contract failed')
    require(all(type(summary.get(k)) is int and summary[k]>0 for k in
        ('aw_stall','w_stall','physical_ar_stall','no_free_frames')),
        'sustained real arbitration/backpressure/not-granted source coverage absent')
    if fixture['Width']==1920:
        require(summary['read_contention']>0 and summary['write_contention']>0,'native read/write dual-client contention coverage absent')
    with (work/'frames.csv').open(encoding='utf-8-sig',newline='')as f: rows=list(csv.DictReader(f))
    with (work/'performance.csv').open(encoding='utf-8-sig',newline='')as f: metrics=list(csv.DictReader(f))
    require(len(rows)==len(metrics)==4 and [int(r['frame_id'])for r in rows]==[1,2,3,4],
        'four complete distinct source/result/scan identities required')
    require(sum(int(r['future_capture_write_overlap_cycles'])for r in rows)>0,
        'no actual future source write overlapped active correction')
    previous_source=-1
    for i,(r,m)in enumerate(zip(rows,metrics)):
        source=int(r['input_source_index']);require(previous_source<source<fixture['InputSourceFrames'],'source cadence mapping must be ordered')
        previous_source=source; oracle=fixture['Frames'][source%3]
        require(r['source_crc32'].upper()==oracle['SourceCRC32'] and r['scan_crc32'].upper()==oracle['ExpectedCRC32'],
            'actual sustained source/corrected display CRC differs from independent CPU pixels')
        require(int(r['input_pixels'])==n and int(r['source_beats'])==int(r['result_beats'])==n//16 and
            int(r['commits'])==int(r['releases'])==int(r['publishes'])==int(r['unique_scans'])==1,
            'sustained per-ID exact pixels/ownership differs')
        require(int(r['scatter_cycles'])==(0 if cache_kind=='directfill'else 8)*int(r['fills']) and
            int(r['cache_ram_write_cycles'])==8*int(r['fills']) and int(r['cache_fill_valid_commits'])==int(r['fills']),
            'actual cache fill/write/publication observations differ')
        require(int(r['input_first_ps'])<int(r['input_last_ps'])<int(r['commit_ps'])<int(r['source_release_ps'])<=
            int(r['publish_ps'])<=int(r['scan_start_ps'])<int(r['scan_last_pixel_ps'])<=int(r['scan_done_ps']),
            'sustained actual events reordered')
        require(int(m['frame_id'])==i+1 and int(m['corrected'])==1 and int(m['coordinates_issued'])==n and
            int(m['scan_active_cycles'])==n+int(m['coordinate_blocked_cycles']) and
            all(int(m[k])==int(r[k])for k in ('scatter_cycles','hardware_process_cycles','cache_ram_write_cycles','cache_fill_valid_commits')),
            'sustained observed cycle breakdown differs')
    return summary,rows


def run(args):
    work = Path(args.workdir).resolve()
    require(work.parent == WORK.resolve() and not work.exists(), 'fresh direct child of raw-camera work required')
    maximum = (300 if args.mode == 'small' else 3600) if args.maximum_seconds is None else args.maximum_seconds
    require(type(maximum) is int and 1 <= maximum <= (300 if args.mode == 'small' else 3600), 'bounded simulation budget required')
    compiled, headers, helpers, frozen = closure(args.cache_kind)
    sources = {n: sha(ROOT/n) for n in dict.fromkeys((*compiled, *headers, *helpers))}
    for name, digest in frozen.items():
        require(sources.get(name) == digest, 'existing frozen source differs: ' + name)
    inputs = bound_inputs(args.input_profile)
    small = verify_small(args.small_report, sources, compiled, headers) if args.mode == 'native' and args.small_report else None
    require(args.mode == 'small' or small is not None, 'native requires completed same-source small report')
    work.mkdir()
    report = {'Schema': SCHEMA, 'Mode': args.mode, 'Passed': False, 'FunctionalPassed': False,
        'SourceSHA256': sources, 'InputSHA256': inputs, 'InputDrift': [], 'SmallGate': small, 'MaximumSeconds': maximum,
        'InputClockHz': 148500000, 'OutputClockHz': 74250000, 'SystemClockHz': 125000000,
        'SourceFrames':8 if args.mode=='small'else 16,'AcceptedCompleteFrames':4,'ContinuousUnthrottledInput':True,'DDRFirstBeatLatencyCycles':40,'AdmissionDisabledOnlyAfterCompleteSources':4,'ActualPixelSamplerInstantiated':True,
        'CandidateEngine': CANDIDATE_ENGINE,
        'CandidateWriter': 'rtl/experimental/ddr_adaptive_result_writer_dualstripe.v',
        'CorrectedCoordinatesTiled8x8': True, 'RawCoordinatesRaster': True,
        'SelectedR3NativeReference': {'Path':str(ROOT/'work/hdmi-camera-fisheye-fill8r3-20261103-a/system-native-a/simulation.json'),
            'SHA256':sha(ROOT/'work/hdmi-camera-fisheye-fill8r3-20261103-a/system-native-a/simulation.json')},
        'CandidateCache': CANDIDATE_CACHE if args.cache_kind=='directfill' else ORIGINAL_CACHE,
        'CacheKind':args.cache_kind,'DirectFillCache':args.cache_kind=='directfill','CacheIndexBits':CACHE_INDEX_BITS,
        'CacheRAMWriteCyclesPerFill':8,'ScatterCyclesPerFill':0 if args.cache_kind=='directfill' else 8, 'ProductionSourcesModified': False,
        'CandidateArbiter': 'rtl/experimental/ddr_read_arbiter_fill8r2.v',
        'InputDDRPreloaded': False, 'RealOutputAsyncFIFO': True, 'DisplayDDRReadbackOnly': False,
        'FaultInjectionExercised': False, 'WholeFrameDropExercised': False,
        'HardwareAccessed': False, 'PDSAccessed': False, 'HardwareReleaseAllowed': False,
        'StartedUTC': datetime.now(timezone.utc).isoformat(), 'Commands': []}
    fixture = None
    try:
        fixture = fixtures(work, args.mode, args.cache_kind)
        report.update(Fixture=fixture, FixtureSHA256=fixture['FixtureSHA256'])
        paths, report['RelocatedSources'] = prepare_compile_sources(ROOT, compiled, headers, work)
        paths,report['CompileSnapshot']=compile_snapshots(paths,compiled,work)
        tool_dir = resolve_vivado_bin(ROOT.parent)
        deadline = time.monotonic() + maximum
        for executable, argv, stage in (
            ('xvlog.bat', ['--sv', *map(str, paths)], 'compile'),
            ('xelab.bat', [TOP, '-s', 'hdmi_camera_fisheye_tile8df8_sustained'], 'elaborate'),
            ('xsim.bat', ['hdmi_camera_fisheye_tile8df8_sustained', '-runall', '-log', 'simulation.log'], 'simulate')):
            command = {'Stage': stage, 'Argv': [str(tool_dir/executable), *argv], 'ReturnCode': None}
            report['Commands'].append(command)
            rowpipe.system.fixtures.previous.base.tool(tool_dir, executable, argv, work, deadline, stage)
            command['ReturnCode'] = 0
        log = (work/'simulation.log').read_text(encoding='utf-8', errors='replace')
        require(MARKER in log and '$finish called' in log
            and not re.search(r'(?im)^\s*(?:fatal|error):', log), 'pixel-system completion marker absent or RTL error')
        summary, rows = assess(work, fixture, args.cache_kind)
        report.update(Passed=True, FunctionalPassed=True, ActualDERGBScanned=True, Summary=summary, Frames=rows,
            PerformanceBreakdown=list(csv.DictReader((work/'performance.csv').open(encoding='utf-8-sig',newline=''))),
            CResetProbe=reset_probe(log,args.mode),
            ActualDDRReadContentionExercised=summary['read_contention']>0,
            ActualDDRWriteContentionExercised=summary['write_contention']>0,
            FutureSourceWriteOverlapCycles=sum(int(r['future_capture_write_overlap_cycles'])for r in rows))
    except (Exception, KeyboardInterrupt) as error:
        report['Error'] = type(error).__name__ + ': ' + str(error)
    finally:
        report['SourceSHA256After'] = {n: sha(ROOT/n) for n in sources}
        report['InputSHA256After'] = {p: sha(p) for p in inputs}
        report['FixtureSHA256After'] = {n: sha(work/n) if (work/n).is_file() else None
            for n in (fixture or {}).get('FixtureSHA256', {})}
        if (report['SourceSHA256After'] != sources or report['InputSHA256After'] != inputs
                or report.get('FixtureSHA256') != report['FixtureSHA256After']):
            report.update(Passed=False, FunctionalPassed=False, InputDrift=['source, external input or fixture bytes changed'])
        if report.get('RelocatedSources') is not None:
            try:
                verify_compile_sources(ROOT, compiled, headers, work, report['RelocatedSources'])
            except ValueError as error:
                report.update(Passed=False, FunctionalPassed=False, CompiledInputDrift=str(error))
        report['LogSHA256'] = {p.name: sha(p) for p in work.glob('*.log')}
        report['ResultSHA256'] = {p.name: sha(p) for n in ('summary.json', 'frames.csv', 'scans.csv', 'events.csv', 'performance.csv')
            if (p := work/n).is_file()}
        report['EndedUTC'] = datetime.now(timezone.utc).isoformat()
        report['Limits'] = ('Eight small or sixteen native continuous synthetic raw148.5MHz input rasters with four fully accepted corrected frames, actual sampler/DMA; '
            'C-profile corrected pixels, 40cycle modeled DDR first-beat latency and true read/write contention, actual74.25MHz scan; no KEY coverage in this supplemental test. '
            'Four-source admission stops only after full source commit; source raster remains unthrottled. No physical DDR/STA/hardware FPS or indefinite stability proof.')
        (work/REPORT).write_text(json.dumps(report, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    return report



def reset_probe(log,mode):
    marker='PASS C_LOCAL_RESET_PROBE sampled_reset_edges=2 forced_wready=1 core_clock_paused=0'
    if mode=='small':require(log.splitlines().count(marker)==1,'actual C local-reset/WREADY probe absent')
    else:require(marker not in log,'native reset coverage must come from its same-source small gate')
    return {'Exercised':mode=='small','SampledResetEdges':2 if mode=='small'else 0,
        'ForcedWReadyHighDuringLocalReset':mode=='small','CoreClockPaused':False,
        'WarmMidstreamResetExercised':False,'NativeUsesVerifiedSameSourceSmallGate':mode=='native'}


def bound_inputs(input_profile):
    inputs=profile(input_profile)
    calibration,_,_,_=fish.read_calibration()
    paths=[fish.CALIBRATION,Path(calibration['source_fit']['path']),Path('D:/anaconda3/python.exe'),
        ROOT/'work/hdmi-camera-fisheye-fill8r3-20261103-a/system-native-a/simulation.json',
        ROOT/'work/hdmi-camera-fisheye-fill8r3s3-20261103-a/system-binding-selected-b.json',
        Path(np.__file__),Path(cv2.__file__),*static_helpers(ROOT/SELF)]
    inputs.update({str(p.resolve()):sha(p) for p in paths})
    return inputs


def compile_snapshots(paths,names,work):
    copied=[];rows={}
    for name,path in zip(names,paths):
        target=work/'compiled-sources'/name;target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(path.read_bytes());copied.append(target)
        rows[name]={'Path':str(target),'SHA256':sha(target),'TransformedSource':str(path)}
    return copied,rows


def verify(path):
    path=Path(path).resolve();value=read(path);watched={}
    require(value.get('Schema')==SCHEMA and value.get('Passed')is True and value.get('FunctionalPassed')is True
        and value.get('HardwareAccessed')is False and value.get('PDSAccessed')is False,
        'completed no-hardware fisheye system report required')
    require(value.get('CacheIndexBits')==CACHE_INDEX_BITS and value.get('DirectFillCache')==(value.get('CacheKind')=='directfill') and value.get('CacheRAMWriteCyclesPerFill')==8 and value.get('ScatterCyclesPerFill')==(0 if value.get('CacheKind')=='directfill' else 8), 'selected cache capacity/direct-fill report contract differs')
    require(value.get('Mode')in ('small','native') and value.get('InputClockHz')==148500000 and
        value.get('OutputClockHz')==74250000 and value.get('ActualPixelSamplerInstantiated')is True and
        value.get('InputDDRPreloaded')is False and value.get('RealOutputAsyncFIFO')is True and
        value.get('ActualDERGBScanned')is True,'actual input/sampler/DDR/scan evidence required')
    names,headers,helpers,_=closure(value['CacheKind'])
    current={n:sha(ROOT/n)for n in dict.fromkeys((*names,*headers,*helpers))}
    require(value['SourceSHA256']==value['SourceSHA256After']==current,'fisheye source closure changed')
    require(value['InputSHA256']==value['InputSHA256After'],'simulation external input drift')
    watched.update({(ROOT/n).resolve():h for n,h in current.items()})
    for p,h in value['InputSHA256'].items():
        require(sha(p)==h,'simulation external input bytes changed: '+p);watched[Path(p)]=h
    require([c['Stage']for c in value['Commands']]==['compile','elaborate','simulate']and
        all(c['ReturnCode']==0 for c in value['Commands']),'simulation did not complete all stages')
    verify_compile_sources(ROOT,names,headers,path.parent,value['RelocatedSources'])
    bindings=value['RelocatedSources']
    require(set(value['CompileSnapshot'])==set(names),'complete simulator source snapshots required')
    for name,row in value['CompileSnapshot'].items():
        expected=bindings.get(name,{}).get('CompiledSHA256',current[name])
        require(row['SHA256']==expected and sha(row['Path'])==expected,'compiled source snapshot changed: '+name)
        watched[Path(row['Path'])]=expected
    for row in bindings.values():
        watched[Path(row['CompiledPath'])]=row['CompiledSHA256']
        for header in row['IncludePathReplacements']:
            watched[Path(header['CompiledHeaderPath'])]=header['HeaderSHA256']
    for group in ('LogSHA256','ResultSHA256','FixtureSHA256'):
        require(value.get(group),'simulation artifact group absent: '+group)
        for name,h in value[group].items():
            p=path.parent/name;require(p.resolve().is_relative_to(path.parent)and sha(p)==h,
                'simulation artifact changed: '+name);watched[p]=h
    require(value['FixtureSHA256']==value['FixtureSHA256After']==value['Fixture']['FixtureSHA256'],
        'fisheye fixture drift')
    with tempfile.TemporaryDirectory(prefix='fisheye-fixture-rederive-')as tmp:
        expected=fixtures(Path(tmp),value['Mode'],value['CacheKind'])
    require(value['Fixture']==expected,'fisheye profile/geometry/pixel oracle cannot be rederived')
    text=(path.parent/'simulation.log').read_text(encoding='utf-8',errors='replace')
    require(MARKER in text and '$finish called'in text and not re.search(r'(?im)^\s*(?:fatal|error):',text),
        'actual RTL completion marker absent')
    require(value.get('CResetProbe')==reset_probe(text,value['Mode']),'C directed reset probe differs')
    summary,rows=assess(path.parent,value['Fixture'],value['CacheKind'])
    require(value['Summary']==summary and value['Frames']==rows,'saved system summaries differ from actual evidence')
    if value['Mode']=='native':
        small=value['SmallGate'];require(sha(small['Path'])==small['SHA256'],'small gate changed')
        previous,inputs=verify(small['Path']);require(previous['Mode']=='small','native small gate substituted')
        watched.update(inputs)
    watched[path]=sha(path)
    return value,watched


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('small', 'native'), required=True)
    parser.add_argument('--workdir', type=Path, required=True)
    parser.add_argument('--input-profile', type=Path, default=ROOT/'work/hdmi-camera1080-raw-20261102-a/input-timing-profile-v2-a.json')
    parser.add_argument('--small-report', type=Path)
    parser.add_argument('--cache-kind', choices=('directfill','original'), default='directfill')
    parser.add_argument('--maximum-seconds', type=int)
    args = parser.parse_args()
    result = run(args)
    print(json.dumps({k: result.get(k) for k in ('Passed', 'FunctionalPassed', 'Error', 'Summary')}))
    return 0 if result['Passed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
