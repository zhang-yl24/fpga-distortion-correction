"""Freeze an independent fill8r2 HDMI fisheye candidate; build only, no hardware.

The checked source manifest supplies the unchanged DDR/rowpipe bodies.
New exact-fisheye modules and frame-boundary view selection replace the old
Brown/rotation/gamma chain. Source roles are derived and checked explicitly. Canonical RTL/IP stays untouched; legacy includes and the
selected digital timing flag change only in this candidate's frozen copies.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import importlib
import copy
import json
import os
from pathlib import Path
import re
import subprocess
import time
import xml.etree.ElementTree as ET

import audit_board1080_pin_contract as pins
import prepare_board1080_timing as paths
import run_camera_vga_output_diagnostic as cleanup
import hdmi_raw_status as raw_status

ROOT=Path(__file__).resolve().parents[1]
SELF=Path(__file__).resolve()
WORK=ROOT/'work/hdmi-camera-fisheye-tile8-20261103-a'
C_WORK=ROOT/'work/hdmi-camera-fisheye-20261103-a'
RAW_WORK=ROOT/'work/hdmi-camera1080-raw-20261102-a'
TARGET='hdmi_camera_fisheye_top'
TOP='board/'+TARGET+'.v'
SAMPLER='rtl/experimental/hdmi_camera_pixel_sampler.v'
BASE_MANIFEST='board/board1080-checked-build-sources.json'
BASE_MANIFEST_SHA='95d2abbf1da3066e5ca69cf4243a83cf5d44c45a0fadb8032fcfc47756353a14'
BASE_FDC='board/board1080-checked-i2c.fdc'
BASE_FDC_SHA='4fd34ebc9d39642e2539610211fe20778971bf9870b53e8f479bcf164c3cf37c'
MANIFEST='board/hdmi-camera-fisheye-tile8-build-sources.json'
FDC='board/hdmi-camera-fisheye-tile8-internal.fdc'
RCF='board/board1080-ddr-ioclk-priority.rcf'
RCF_SHA='981934688d526e8d686635859d811070752570a34738548154d544e41be48516'
IP='platform/video_base/ipcore/ddr3_test'
IDF=IP+'/ddr3_test.idf'
PROFILE=RAW_WORK/'input-timing-profile-v2-a.json'
REARM_PLAN=RAW_WORK/'build-d/plan.json'
FISHEYE_PROFILE=C_WORK/'profile-a/profile.json'
_FISHEYE_PROFILE_CACHE={}
SCHEMA='hdmi-camera-fisheye-tile8-build-v1'
MANIFEST_SCHEMA='hdmi-camera-fisheye-tile8-source-closure-v1'
STAGES=['Compile','Synthesize','Device Map','Place','Route','Route Optimize','Report Timing']
REPLACEMENTS={'board/board1080_checked_top.v':TOP,
    'rtl/experimental/ms72xx_checked_ctl.v':'rtl/experimental/ms72xx_rearm_observed_ctl.v',
    'rtl/experimental/ms7200_1080p30_ctl.v':'rtl/experimental/ms7200_1080p30_rearm_ctl.v',BASE_FDC:FDC,
    'rtl/experimental/hdmi1080_video_system_cdc_reset.v':'rtl/experimental/hdmi_camera_fisheye_system_c.v',
    'rtl/experimental/hdmi1080_input_write_link.v':'rtl/experimental/hdmi_camera_fisheye_input_link.v',
    'rtl/experimental/lens1080_bank_core.v':'rtl/experimental/hdmi_camera_fisheye_bank_tile8.v',
    'rtl/experimental/pipeline_gamma_frame_engine_1080_scatter4.v':'rtl/experimental/hdmi_camera_fisheye_engine_tile8.v',
    'rtl/experimental/rotated_remap_core_gamma_scatter4.v':'rtl/experimental/hdmi_camera_fisheye_core.v',
    'rtl/experimental/ddr_neighbour_cache_scatter4_rowpipe.v':'rtl/experimental/ddr_neighbour_cache_scatter16_rowpipe_fill8r3.v',
    'rtl/experimental/ddr_remap_sample_scatter4_rowpipe.v':'rtl/experimental/ddr_remap_sample_scatter16_rowpipe.v',
    'rtl/ddr_read_arbiter.v':'rtl/experimental/ddr_read_arbiter_fill8r2.v'}
REPLACEMENTS['rtl/experimental/ddr_adaptive_result_writer.v']='rtl/experimental/ddr_adaptive_result_writer_dualstripe.v'
REMOVED=('rtl/experimental/dvp_mode_admission_monitor.v','rtl/experimental/hdmi1080_input_status.v',
    'board/board1080-synthetic.vh','rtl/pixel_inverse_rotation.v','rtl/bounded_brown_inverse_mapper.v',
    'rtl/experimental/adaptive_gamma_stream.v','rtl/experimental/adaptive_gamma_tagged.v',
    'rtl/experimental/gamma_curves.vh')
MAPPER='rtl/experimental/hdmi_camera_fisheye_mapper.v'
ROM='rtl/experimental/hdmi_camera_fisheye_rom.v'
QUANTIZER='rtl/experimental/hdmi_camera_rgb565_quantizer.v'
VIEW_CONTROL='rtl/experimental/camera720_view_control.v'
STATUS_UART='rtl/experimental/hdmi_camera_fisheye_status_uart.v'
UART='rtl/uart_tx.v'
PROFILE_HEADER='board/hdmi-camera-fisheye-profile.vh'
RADIAL_HEADER='board/hdmi-camera-fisheye-radial-table.vh'
ADDED=(SAMPLER,MAPPER,ROM,QUANTIZER,VIEW_CONTROL,STATUS_UART,UART,PROFILE_HEADER,RADIAL_HEADER)
HEADERS={'rtl/video_crc32.vh',PROFILE_HEADER,RADIAL_HEADER}
INCLUDE_BINDINGS={name:binding for name,binding in paths.INCLUDE_BINDINGS.items()
    if name in ('rtl/ddr_video_reader.v','rtl/experimental/ddr_adaptive_result_writer.v',
        'rtl/experimental/ddr_video_output_1080_board.v')}
INCLUDE_BINDINGS.update({MAPPER:('D:/English/FPGA/distortion/'+PROFILE_HEADER,PROFILE_HEADER),
    ROM:('D:/English/FPGA/distortion/'+RADIAL_HEADER,RADIAL_HEADER)})
INCLUDE_BINDINGS.pop('rtl/experimental/ddr_adaptive_result_writer.v',None)
INCLUDE_BINDINGS['rtl/experimental/ddr_adaptive_result_writer_dualstripe.v']=("D:/English/FPGA/distortion/rtl/video_crc32.vh",'rtl/video_crc32.vh')
USER_CLOCKS={'board27','cfg_clk','input_pixel','pixel_clk','ddrphy_sysclk'}
REQUIRED_MODULES={name: 'rtl/experimental/'+name+'.v'for name in (
    'hdmi_camera_fisheye_system','hdmi_camera_fisheye_bank','hdmi_camera_fisheye_engine',
    'hdmi_camera_fisheye_core','hdmi_camera_fisheye_mapper','hdmi_camera_fisheye_rom','hdmi_camera_rgb565_quantizer')}
REQUIRED_MODULES['ddr_read_arbiter']='rtl/experimental/ddr_read_arbiter_fill8r2.v'
REQUIRED_MODULES['hdmi_camera_fisheye_system']='rtl/experimental/hdmi_camera_fisheye_system_c.v'
REQUIRED_MODULES['hdmi_camera_fisheye_input_link']='rtl/experimental/hdmi_camera_fisheye_input_link.v'
REQUIRED_MODULES.update({'ddr_remap_sample_scatter4':'rtl/experimental/ddr_remap_sample_scatter16_rowpipe.v',
    'ddr_neighbour_cache_scatter16_rowpipe':'rtl/experimental/ddr_neighbour_cache_scatter16_rowpipe_fill8r3.v',
    'camera720_view_control':VIEW_CONTROL,'hdmi_camera_fisheye_status_uart':STATUS_UART,'uart_tx':UART,TARGET:TOP,'hdmi_camera_pixel_sampler':SAMPLER})
REQUIRED_MODULES.pop('hdmi_camera_fisheye_engine')
REQUIRED_MODULES['hdmi_camera_fisheye_engine_tile8']='rtl/experimental/hdmi_camera_fisheye_engine_tile8.v'
REQUIRED_MODULES['hdmi_camera_fisheye_bank']='rtl/experimental/hdmi_camera_fisheye_bank_tile8.v'
REQUIRED_MODULES['ddr_adaptive_result_writer_dualstripe']='rtl/experimental/ddr_adaptive_result_writer_dualstripe.v'

def sha(path):return hashlib.sha256(local_io(path).read_bytes()).hexdigest()
C_MANIFEST='board/hdmi-camera-fisheye-c-build-sources.json'
C_MANIFEST_SHA='2a02ceee984cc84a15d6854f2a3651d937abe2b7c3508915d5d8c8a616093bb7'
C_FDC='board/hdmi-camera-fisheye-c-internal.fdc'
C_FDC_SHA='e27a18c4a5f228ac8543e50c9b50a145f14bf1d4e640ff34361422d32f1bf78a'
TILE8_SOURCE_REPLACEMENTS={
    'rtl/experimental/ddr_neighbour_cache_scatter4_rowpipe.v':'rtl/experimental/ddr_neighbour_cache_scatter16_rowpipe_fill8r3.v',
    'rtl/experimental/ddr_remap_sample_scatter4_rowpipe.v':'rtl/experimental/ddr_remap_sample_scatter16_rowpipe.v',
    'rtl/ddr_read_arbiter.v':'rtl/experimental/ddr_read_arbiter_fill8r2.v'}


TILE8_SOURCE_REPLACEMENTS.update({'rtl/experimental/hdmi_camera_fisheye_engine.v': 'rtl/experimental/hdmi_camera_fisheye_engine_tile8.v', 'rtl/experimental/hdmi_camera_fisheye_bank.v': 'rtl/experimental/hdmi_camera_fisheye_bank_tile8.v', 'rtl/experimental/ddr_adaptive_result_writer.v': 'rtl/experimental/ddr_adaptive_result_writer_dualstripe.v'})

def require(ok,message):
    if not ok:raise ValueError(message)


def local_io(path):
    path=Path(path).absolute()
    return Path('\\\\?\\'+str(path)) if os.name=='nt' else path


def read(path):return json.loads(local_io(path).read_text(encoding='utf-8-sig'))
def utc():return datetime.now(timezone.utc).isoformat()
def digest(data):return hashlib.sha256(data).hexdigest()
def ref(path):return {'Path':str(Path(path).resolve()),'SHA256':sha(path)}


def write(path,value):
    with local_io(path).open('x',encoding='utf-8',newline='\n') as out:
        json.dump(value,out,indent=2,allow_nan=False);out.write('\n')


def add(watched,path,expected=None):
    path=Path(path).absolute();require(path==path.resolve() and local_io(path).is_file(),'canonical build input required: '+str(path))
    actual=sha(path);require(expected is None or actual==expected,'fisheye input SHA differs: '+str(path))
    require(str(path) not in watched or watched[str(path)]==actual,'conflicting fisheye input SHA')
    watched[str(path)]=actual;return path


def work_path(value):
    path=Path(value).absolute()
    require(path==path.resolve() and path.parent==WORK.resolve() and re.fullmatch(r'[A-Za-z0-9_-]+',path.name),
            'canonical direct pixel work child required')
    return path


def source_names(base):
    names=base.get('source_files')
    require(base.get('Schema')=='board1080-checked-build-closure-v1'and base.get('Target')=='board1080_top'
        and isinstance(names,list)and len(names)==len(set(names))and
        set(base.get('SourceSHA256',{}))==set(names),'complete checked source manifest required')
    require(all(names.count(n)==1 for n in (*REPLACEMENTS,*REMOVED)),
        'source replacement/drop roles missing')
    result=[REPLACEMENTS.get(n,n)for n in names if n not in REMOVED]
    for name in ADDED:
        require(name not in result,'new design already exists in retained source closure');result.append(name)
    require(len(result)==len({n.casefold()for n in result}),'duplicate/case-colliding fisheye source')
    for name in result:paths.relative_name(name)
    return result


def render_constraints(data):
    """Keep exact pin/DDR clauses, remove only the old40 approximate CDC bounds."""
    kept=[];removed=[];input_clock=0
    for raw in data.splitlines(keepends=True):
        line=raw.decode('ascii').strip()
        if not line or line.startswith('#'):continue
        if line.startswith(('set_max_delay ','set_min_delay ')):
            match=re.fullmatch(r'set_(max|min)_delay( -datapath_only)? -from \[get_clocks \{(\w+)\}\] '
                               r'-to \[get_clocks \{(\w+)\}\] (8\.0|0\.0)',line)
            require(match is not None and match[3] in USER_CLOCKS and match[4] in USER_CLOCKS
                    and match[3]!=match[4] and ((match[1]=='max' and match[2]==' -datapath_only' and match[5]=='8.0')
                    or (match[1]=='min' and match[2] is None and match[5]=='0.0')),'unreviewed legacy CDC constraint')
            removed.append(line);continue
        require(line.startswith(('create_clock ','create_generated_clock ','set_multicycle_path ',
                                 'set_clock_uncertainty ','define_attribute ')),'unreviewed pixel constraint command: '+line)
        if line=='create_clock -name input_pixel -period 13.315579 [get_ports pixclk_in]':
            raw=raw.replace(b'13.315579',b'6.6667',1);input_clock+=1
        kept.append(raw if raw.endswith((b'\n',b'\r')) else raw+b'\n')
    require(input_clock==1 and len(removed)==40 and len(set(removed))==40,'exact input clock and40 old CDC bounds required')
    text=(b'# Independent pixel diagnostic:150MHz input /74.25MHz output internal envelope.\n'
          b'# Actual RGB/progressive mode, source capture phase, PCB skew and external AC are not accepted.\n'
          b'# Retain DDR IP electrical/clock/placement/multicycle clauses; new graph still needs full physical review.\n'
          b'# No old broad user-domain max/min/false-path or clock-group exception is imported.\n'+b''.join(kept))
    require(pins.fdc_pins(text.decode('ascii'))==pins.fdc_pins(data.decode('ascii')),'retained pin/electrical attributes changed')
    require(b'{C23}'not in text and b'key1_n'not in text and b'{C24}'not in text and b'p:uart_tx}'not in text,
        'KEY1 or UART pad is already occupied')
    text+=b'\n# KEY1 active low; only its exact first synchronizer input may receive a later async exception.\n'
    for key,value in (('DIRECTION','INPUT'),('LOC','C23'),('VCCIO','3.3'),('STANDARD','LVCMOS33'),('PULLUP','TRUE')):
        text+=('define_attribute {p:key1_n} {PAP_IO_'+key+'} {'+value+'}\n').encode('ascii')
    for key,value in (('DIRECTION','OUTPUT'),('LOC','C24'),('VCCIO','3.3'),('STANDARD','LVCMOS33'),('DRIVE','4'),('SLEW','SLOW')):
        text+=('define_attribute {p:uart_tx} {PAP_IO_'+key+'} {'+value+'}\n').encode('ascii')
    return text,removed


def profile_binding(path=None):
    watched={};path=add(watched,PROFILE if path is None else path);profile=read(path)
    require(profile.get('Schema')=='hdmi-camera-observed-digital-timing-v1','observed v2 digital profile required')
    source=profile['Source'];live_path=add(watched,source['Path'],source['SHA256']);live=read(live_path)
    require(live_path.parent==RAW_WORK.resolve() and live.get('passed') is True
            and live.get('protocol')=='PGHRAW01' and live.get('packet_bytes')==128
            and live.get('uart_transmit_bytes')==0 and live.get('rejected_packets')==0,'successful receive-only v2 timing evidence required')
    wire=add(watched,live['raw_path'],live['wire_sha256'])
    require(wire.parent==RAW_WORK.resolve() and wire.stat().st_size<=raw_status.MAX_BYTES,'bound raw wire role differs')
    parser=raw_status.FrameParser();frames=parser.feed(wire.read_bytes())
    require(frames==live['frames'] and parser.accepted==live['accepted_packets']==20 and parser.rejected==0,
            'raw v2 wire/decoded packet inventory differs')
    summary=raw_status.summarize(frames)
    require(summary==live['summary'] and summary['valid_counter_windows']==19
            and summary['unavailable_reasons']=={} and summary['edge_conservation_failure_windows']==0,
            'raw v2 timing/edge conservation recomputation failed')
    require(all(f['build_tag']==0x48445202 and not f['semantic_issues'] and f['cfg_error']==0 for f in frames),
            'wrong raw sampler generation or configuration/semantic issue')
    expected={'BuildTags':['0x48445202'],'TransportPassed':True,'RejectedPackets':0,'UARTTransmitBytes':0,
        'ValidWindows':19,'UnavailableReasons':{},'EstimatedPCLKHz':summary['pclk_hz_estimate'],
        'EstimatedVSRisingHz':summary['raw_vs_rising_hz_estimate'],'EstimatedVSFallingHz':summary['raw_vs_falling_hz_estimate'],
        'VSPeriodPCLK':sorted({f['raw']['vs_period_pclk'] for f in frames}),
        'HSPeriodPCLK':sorted({f['raw']['hs_period_pclk'] for f in frames}),
        'DEHighWidthPCLK':sorted({f['raw']['de_high_width_pclk'] for f in frames}),
        'VSHighWidthPCLK':sorted({f['raw']['vs_high_width_pclk'] for f in frames}),
        'VSLowWidthPCLK':sorted({f['raw']['vs_low_width_pclk'] for f in frames}),
        'ActiveLinesPerVS':sorted({f['raw']['de_rises_per_vs_period'] for f in frames}),
        'ConfigurationErrorCodes':[0],'SemanticIssues':[],'VSActiveHighSelectedForNextPrototype':True,
        'DEActiveHighSelectedForNextPrototype':True,'RGBPixelsVerified':False,'ExternalACAccepted':False}
    require(all(profile.get(k)==v for k,v in expected.items()),'digital profile differs from source measurement/selection')
    require(expected['VSPeriodPCLK']==[2475000] and expected['HSPeriodPCLK']==[2200]
            and expected['DEHighWidthPCLK']==[1920] and expected['ActiveLinesPerVS']==[1080]
            and expected['VSHighWidthPCLK']==[11000] and expected['VSLowWidthPCLK']==[2464000]
            and 148000000<expected['EstimatedPCLKHz']<150000000,'selected150MHz envelope no longer covers observed profile')
    add(watched,raw_status.__file__)
    return {'Profile':ref(path),'Source':ref(live_path),'Wire':ref(wire),'RecomputedValidWindows':19,
        'DigitalTimingConfigured':True,'SelectedVSActiveLevel':1,'SelectedDEActiveLevel':1,
        'MeasuredPCLKHzEstimate':summary['pclk_hz_estimate'],'ProgressiveSourceVerified':False,
        'RGBPixelsVerified':False,'CapturePhaseVerified':False,'ExternalACAccepted':False},watched



def fisheye_profile_binding(path=None):
    path=Path(FISHEYE_PROFILE if path is None else path).resolve();value=read(path);watched={}
    key=(str(path),sha(path));cached=_FISHEYE_PROFILE_CACHE.get(key)
    if cached is not None:
        saved,inputs=cached
        require(all(local_io(p).is_file()and sha(p)==h for p,h in inputs.items()),'cached exact-fisheye profile input drift')
        return copy.deepcopy((saved,inputs))
    add(watched,path)
    require(value.get('Schema')=='hdmi-camera-fisheye-r2-profile-v1'and value.get('Passed')is True,
        'source-bound exact-fisheye r2 profile required')
    generator=value['Generator'];require(Path(generator['Path']).resolve()==SELF.with_name('generate_hdmi_fisheye_profile.py'),
        'exact-fisheye profile generator location differs')
    add(watched,generator['Path'],generator['SHA256'])
    calibration=value['Calibration'];add(watched,calibration['Path'],calibration['SHA256'])
    source=value['SourceFit'];add(watched,source['path'],source['sha256'])
    expected={str((ROOT/n).resolve())for n in (PROFILE_HEADER,RADIAL_HEADER)}
    require(set(value['GeneratedFiles'])==expected,'exact two generated fisheye headers required')
    for name,h in value['GeneratedFiles'].items():add(watched,name,h)
    provider=importlib.import_module('generate_hdmi_fisheye_profile')
    require(Path(provider.__file__).resolve()==Path(generator['Path']).resolve(),'loaded profile generator differs')
    require(value['SourceFit']==provider.read_calibration(calibration['Path'])[0]['source_fit'],
        'profile source fit differs from calibration provenance')
    cfg=provider.config(calibration['Path'])
    require((ROOT/PROFILE_HEADER).read_bytes()==provider.header_bytes(cfg)
        and (ROOT/RADIAL_HEADER).read_bytes()==provider.table_bytes(cfg),'fisheye source calibration/header/table differs')
    require(value['FullGridError']==provider.metrics(calibration['Path'])and
        value.get('IdentityCoordinatesExact')is True,'complete native fisheye coordinate oracle differs')
    require(value['Format']=={'NormalizedFractionBits':22,'RadialScaleFractionBits':30,'PixelFractionBits':8,
        'R2Domain':[0,8],'Nodes':1025,'Segments':1024,'SegmentFractionBits':15,
        'ROMWord':'{signedDeltaQ30[31:0],baseQ30[31:0]}','SynchronousWordBits':64,'Expected18KHalves':4,
        'MemoryResourceClaim':'four18K halves by1024x64 capacity; actual mapped usage requires native build'},
        'fisheye bounded synchronous ROM format differs')
    require(value['OpenCVVersion']==provider.cv2.__version__ and value['NumPyVersion']==provider.np.__version__,
        'profile coordinate oracle runtime differs')
    result={'Profile':ref(path),'Calibration':calibration,'SourceFit':source,'Generator':generator,
        'GeneratedFiles':value['GeneratedFiles'],'FullGridError':value['FullGridError'],'Format':value['Format'],
        'IdentityCoordinatesExact':True,'PriorLensParametersReused':False,'PhysicalROMModeStillRequiresNativeAudit':True}
    require(all(local_io(p).is_file()and sha(p)==h for p,h in watched.items()),'fisheye profile input drift')
    _FISHEYE_PROFILE_CACHE[key]=copy.deepcopy((result,watched));return result,watched


def c_source_difference(names,hashes,fdc):
    require(sha(ROOT/C_MANIFEST)==C_MANIFEST_SHA and sha(ROOT/C_FDC)==C_FDC_SHA,
        'frozen C source manifest or constraint changed')
    prior=read(ROOT/C_MANIFEST)
    require(prior.get('Schema')=='hdmi-camera-fisheye-source-closure-v1' and prior.get('Target')==TARGET,
        'current frozen C source closure required')
    changes={**TILE8_SOURCE_REPLACEMENTS,C_FDC:FDC}
    require(names==[changes.get(n,n)for n in prior['source_files']],
        'fill8r2 closure must differ from C only by cache/sampler/arbiter/FDC names')
    require(fdc==(ROOT/C_FDC).read_bytes(),'fill8r2 FDC bytes must equal frozen C')
    for old in prior['source_files']:
        new=changes.get(old,old)
        if old not in TILE8_SOURCE_REPLACEMENTS:
            require(hashes[new]==prior['SourceSHA256'][old],'retained C source changed: '+old)
    return {'BaselineManifest':ref(ROOT/C_MANIFEST),'BaselineFDC':ref(ROOT/C_FDC),
        'RTLReplacements':TILE8_SOURCE_REPLACEMENTS,'ConstraintBytesEqual':True,
        'RetainedSourceHashesEqual':True,'PhysicalProofInherited':False,
        'CachePixelsPerScatterCycle':16,'ScatterCyclesPer256ByteFill':8}


def expected_manifest(fdc_bytes=None):
    base_path=ROOT/BASE_MANIFEST;require(sha(base_path)==BASE_MANIFEST_SHA,'checked base source manifest changed')
    base=read(base_path);names=source_names(base);fdc,removed=render_constraints((ROOT/BASE_FDC).read_bytes())
    require(sha(ROOT/BASE_FDC)==BASE_FDC_SHA,'checked baseline FDC changed')
    hashes={}
    for name in names:
        if name==FDC and fdc_bytes is not None:
            require(fdc_bytes==fdc,'new pixel FDC creation differs from exact derivation');hashes[name]=digest(fdc_bytes);continue
        path=paths.inside(ROOT,name);actual=sha(path)
        if name==FDC:require(path.read_bytes()==fdc,'new pixel FDC differs from exact derivation')
        elif name not in ADDED and name!=TOP and name not in REPLACEMENTS.values():
            require(actual==base['SourceSHA256'][name],'retained checked source changed: '+name)
        hashes[name]=actual
    require(sha(ROOT/RCF)==RCF_SHA,'retained DDR priority RCF changed')
    profile,watched=profile_binding();optical,_=fisheye_profile_binding();rearm=read(REARM_PLAN)
    require(rearm.get('Schema')=='hdmi-camera-raw-build-v1' and rearm.get('Target')=='hdmi_camera_raw_diag',
            'current v2 rearm reference plan required')
    rearm_refs=[]
    for name in (REPLACEMENTS['rtl/experimental/ms72xx_checked_ctl.v'],REPLACEMENTS['rtl/experimental/ms7200_1080p30_ctl.v']):
        frozen=REARM_PLAN.parent/'frozen-inputs'/name
        require(sha(frozen)==hashes[name]==rearm['PreparedSHA256'][str(frozen.resolve())], 'RX rearm bytes differ from v2 baseline')
        rearm_refs.append(ref(frozen))
    difference=c_source_difference(names,hashes,fdc)
    return {'Schema':MANIFEST_SCHEMA,'Target':TARGET,'CSourceDifferenceReview':difference,'BaseManifest':ref(base_path),'source_files':names,
        'SourceSHA256':hashes,'Replacements':REPLACEMENTS,'Removed':list(REMOVED),'Added':list(ADDED),
        'Constraint':FDC,'RouteConstraint':RCF,'RouteConstraintSHA256':RCF_SHA,
        'InputTiming':profile,'FisheyeProfile':optical,'RearmReferencePlan':ref(REARM_PLAN),'RetainedRearmFrozenSources':rearm_refs,
        'FrozenTopParameterOverride':{'Parameter':'INPUT_TIMING_CONFIGURED','Original':0,'Compiled':1},
        'InputPixelPeriodNS':6.6667,'OutputPixelMHz':74.25,'ConfigurationMHz':10.0,
        'RemovedLegacyApproximateCDCCommands':removed,'HardwareAccessed':False,'BitstreamRequested':False,
        'HardwareReleaseAllowed':False,'ExternalACAccepted':False,'PriorPhysicalProofCountsInherited':False}


def write_manifest():
    require(not (ROOT/MANIFEST).exists() and not (ROOT/FDC).exists(),'fresh pixel source/constraint manifests required')
    require(sha(ROOT/BASE_FDC)==BASE_FDC_SHA,'checked FDC changed')
    fdc,_=render_constraints((ROOT/BASE_FDC).read_bytes())
    # All source roles must exist before creating either artifact.
    for name in source_names(read(ROOT/BASE_MANIFEST)):
        if name!=FDC:paths.inside(ROOT,name)
    value=expected_manifest(fdc_bytes=fdc);source_roles(value)
    (ROOT/FDC).write_bytes(fdc)
    write(ROOT/MANIFEST,value)
    return ROOT/MANIFEST



def instantiated_types(text):
    """Inventory conventional line-start named instances, including parameters."""
    clean=pins.clean_verilog(text)
    keywords={'module','input','output','inout','wire','reg','integer','parameter','localparam',
        'function','task','if','else','for','while','case','casex','casez','assign','always','initial',
        'begin','end','generate','endgenerate','endcase','endfunction','endtask','endmodule'}
    pattern=r'(?m)^[ \t]*([A-Za-z_$][\w$]*)[ \t]+(?:(#)\s*\(|([A-Za-z_$][\w$]*)\s*\()'
    result=[]
    for m in re.finditer(pattern,clean):
        kind=m[1]
        if kind in keywords:continue
        if m[2]:
            depth=1;index=m.end()
            while index<len(clean)and depth:
                if clean[index]=='(':depth+=1
                elif clean[index]==')':depth-=1
                index+=1
            require(depth==0,'unbalanced module instance parameters')
            instance=re.match(r'\s*([A-Za-z_$][\w$]*)\s*\(',clean[index:])
            require(instance is not None,'parameterized instance name missing: '+kind)
            name=instance[1]
        else:name=m[3]
        result.append({'Module':kind,'Instance':name})
    return result


def source_roles(manifest):
    names=manifest['source_files'];source=ET.parse(ROOT/IDF).getroot().find('file_list/source')
    require(source is not None,'DDR IDF source section missing')
    entries=[paths.relative_name(e.get('pathname')) for e in source.findall('file')]
    require(len(entries)==len(set(entries))==74 and Counter(Path(n).suffix for n in entries)=={'.vp':71,'.v':3},
            'complete74-body DDR IDF closure required')
    expanded=[IP+'/'+n for n in entries]
    require({n for n in names if n.startswith(IP+'/')}==set(expanded)|{IDF},'unowned/missing DDR IP body')
    headers={n for n in names if Path(n).suffix=='.vh'};require(headers==HEADERS,'only bound CRC and exact-fisheye profile/table headers required')
    explicit=[n for n in names if n not in set(expanded)|headers|{FDC}]
    require(explicit and sum(Path(n).suffix=='.idf'for n in explicit)==1
        and all(Path(n).suffix in('.v','.idf')for n in explicit),'explicit fisheye source roles differ')
    modules={};design_texts={}
    for name in explicit+sorted(headers):
        if name==IDF:continue
        data=(ROOT/name).read_bytes();found=paths.INCLUDE.findall(data);expected=INCLUDE_BINDINGS.get(name)
        require(len(paths.INCLUDE_DIRECTIVE.findall(data))==len(found)
                and found==([] if expected is None else [expected[0].encode('ascii')]),'unbound pixel include: '+name)
        if name in headers:continue
        design_texts[name]=data.decode('utf-8-sig')
        for module in re.findall(r'\bmodule\s+(\w+)',pins.clean_verilog(data.decode('utf-8-sig'))):
            require(module not in modules,'same-module alternate design selected: '+module);modules[module]=name
    require(all(modules.get(m)==n for m,n in REQUIRED_MODULES.items()),'production CDC/system/engine/cache module selection differs')
    instances={name:instantiated_types(text)for name,text in design_texts.items()}
    allowed=set(modules)|{'ddr3_test','GTP_GPLL','GTP_INBUFGDS'}
    require(all(r['Module']in allowed for rows in instances.values()for r in rows),
        'unresolved design module in actual fisheye closure')
    require(not any(name in modules for name in ('bounded_brown_inverse_mapper','pixel_inverse_rotation',
        'adaptive_gamma_stream','adaptive_gamma_tagged','hdmi1080_video_system')),
        'old Brown/rotation/gamma/system alternative entered fisheye closure')
    return {'ExplicitDesigns':explicit,'IDFExpandedSources':expanded,'Headers':sorted(headers),
        'Modules':modules,'InstancesBySource':instances,'UnresolvedModuleInstances':[]}


def top_ports(text):
    adapted,count=re.subn(r'\bmodule\s+'+TARGET+r'\s*#\(.*?\)\s*\(','module board1080_top(',text,count=1,flags=re.S)
    require(count==1,'one parameterized current pixel top required')
    return pins.top_ports(adapted)


def pin_contract(top_text,fdc_text,baseline_top,baseline_fdc):
    actual=top_ports(top_text);previous=pins.top_ports(baseline_top)
    attributes=pins.fdc_pins(fdc_text);old_attributes=pins.fdc_pins(baseline_fdc)
    extra={'key1_n':'INPUT','uart_tx':'OUTPUT'}
    require(actual=={**previous,**extra}and set(attributes)==set(actual)and
        {k:v for k,v in attributes.items()if k not in extra}==old_attributes,
        'fisheye retained pins/current electrical/DDR contract differs')
    require(attributes['key1_n']=={'DIRECTION':'INPUT','LOC':'C23','VCCIO':'3.3','STANDARD':'LVCMOS33','PULLUP':'TRUE'},
        'KEY1 source-bound electrical contract differs')
    require(attributes['uart_tx']=={'DIRECTION':'OUTPUT','LOC':'C24','VCCIO':'3.3','STANDARD':'LVCMOS33','DRIVE':'4','SLEW':'SLOW'},
        'UART TX source-bound electrical contract differs')
    require(all(attributes[n]['DIRECTION']==direction for n,direction in actual.items()),'pixel pin direction differs')
    require(len({r['LOC'] for r in attributes.values()})==len(actual),'duplicate fisheye pad location')
    for name in ('hd_scl','hd_sda'):
        require(actual[name]=='INOUT','I2C bidirectional declaration differs')
    def ddr_wiring(text):
        clean=pins.clean_verilog(text);matches=re.findall(r'\bddr3_test\s+u_ddr3_test_h\s*\((.*?)\)\s*;',clean,re.S)
        require(len(matches)==1,'exactly one actual DDR wrapper instance required')
        connections=re.findall(r'\.(\w+)\s*\(([^()]*)\)',matches[0]);require(connections,'DDR connections missing')
        require(len({n for n,v in connections})==len(connections),'duplicate DDR named connection')
        return {n:re.sub(r'\s+','',v) for n,v in connections}
    require(ddr_wiring(top_text)==ddr_wiring(baseline_top),'actual DDR port wiring/tie-offs differ from checked top')
    return {'TopPortCount':len(actual),'DDRAttributePorts':sum(n.startswith('mem_') or n in ('clk_p','clk_n') for n in actual),
        'PinInventory':attributes,'DeclaredPinsAndElectricalPreserved':True,'DDRWrapperConnections':ddr_wiring(top_text),
        'NativePinMappingVerified':False,'NativeElectricalParametersVerified':False,'ExternalACAccepted':False}


def pll_clocks():
    rows=[]
    for name,expected in (('board/bringup_pll.v',74.25),('platform/video_base/ipcore/cfg_pll/cfg_pll.v',10.0)):
        text=(ROOT/name).read_text(encoding='utf-8');values={}
        for key in ('CLKIN_FREQ','STATIC_RATIOI','STATIC_RATIOM','STATIC_RATIO0','STATIC_RATIOF'):
            matches=re.findall(r'localparam\s+(?:real|integer)\s+'+key+r'\s*=\s*([0-9.]+)\s*;',text)
            require(len(matches)==1,'ambiguous PLL ratio '+name+':'+key);values[key]=float(matches[0])
        mhz=values['CLKIN_FREQ']*values['STATIC_RATIOM']*values['STATIC_RATIOF']/values['STATIC_RATIOI']/values['STATIC_RATIO0']
        require(values['CLKIN_FREQ']==27.0 and abs(mhz-expected)<1e-9,'pixel/configuration PLL frequency differs')
        rows.append({'Source':name,'Parameters':values,'ComputedOutputMHz':mhz})
    return rows


def compiled_source(name,data,work,alias):
    changes=[];expected=INCLUDE_BINDINGS.get(name)
    if expected:
        matches=list(paths.INCLUDE.finditer(data));require(len(matches)==1 and matches[0][1]==expected[0].encode('ascii'),'legacy include identity differs')
        header=expected[1];target=paths.alias_path(ROOT,alias,work/'compiled'/header)
        match=matches[0];data=data[:match.start(1)]+target.encode('ascii')+data[match.end(1):]
        changes.append({'Kind':'BoundHeaderIncludeRelocation','Original':expected[0],'Compiled':target,
                        'Header':header,'HeaderSHA256':sha(ROOT/header),'ReplacementCount':1})
    if name==TOP:
        for parameter in ('RX_VS_ACTIVE_LEVEL','RX_DE_ACTIVE_LEVEL'):
            require(len(re.findall(rb'parameter[ \t]+integer[ \t]+'+parameter.encode('ascii')+rb'[ \t]*=[ \t]*1(?=[ \t]*[,\r\n])',data))==1,
                    'pixel top does not use the selected active-high digital input profile')
        pattern=rb'(parameter[ \t]+integer[ \t]+INPUT_TIMING_CONFIGURED[ \t]*=[ \t]*)0(?=[ \t]*[,\r\n])'
        require(len(re.findall(pattern,data))==1,'one unconfigured digital timing parameter default required')
        data,count=re.subn(pattern,rb'\g<1>1',data,count=1)
        changes.append({'Kind':'SelectedDigitalTimingOnly','Parameter':'INPUT_TIMING_CONFIGURED','Original':0,'Compiled':1,'ReplacementCount':count,
                        'RGBPixelsVerified':False,'CapturePhaseVerified':False,'ExternalACAccepted':False})
    return data,changes


def render_tcl(explicit,work,alias):
    compiled=lambda n:paths.tcl_path(paths.alias_path(ROOT,alias,work/'compiled'/n))
    return ('set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676\n'+
        '\n'.join('add_design '+compiled(n) for n in explicit)+'\n'+
        'add_constraint '+compiled(FDC)+'\nadd_constraint '+compiled(RCF)+'\n'
        'compile -top_module '+TARGET+'\nsynthesize -ads -selected_syn_tool_opt 2\ndev_map\n'
        'pnr -force_to_run -gplace_seed 3 -optimize_multi_corner_timing -fix_hold_violation -fix_hold_violation_iterations 50 '
        '-fix_hold_violation_threshold 100 -fix_hold_violation_in_route TRUE\n'
        'report_timing -force_to_run -delay_type min_max -max_path 10000 -nworst 4 -report_exception TRUE\n')


def recipe(work,alias='P:/',maximum=1800,require_alias=False):
    work=work_path(work);alias=paths.alias_format(alias)
    require(type(maximum) is int and 60<=maximum<=1800,'bounded60..1800 second fisheye build required')
    if require_alias:paths.validate_repo_alias(ROOT,alias)
    saved=read(ROOT/MANIFEST);expected=expected_manifest();require(saved==expected,'pixel source/constraint manifest differs')
    roles=source_roles(saved);profile,watched=profile_binding()
    optical,inputs=fisheye_profile_binding()
    for path,h in inputs.items():add(watched,path,h)
    for name,h in saved['SourceSHA256'].items():add(watched,ROOT/name,h)
    for name in (BASE_MANIFEST,BASE_FDC,MANIFEST,RCF,C_MANIFEST,C_FDC,'board/board1080_checked_top.v'):
        add(watched,ROOT/name)
    add(watched,REARM_PLAN,saved['RearmReferencePlan']['SHA256'])
    for source in saved['RetainedRearmFrozenSources']:add(watched,source['Path'],source['SHA256'])
    pin_review=pin_contract((ROOT/TOP).read_text(encoding='utf-8-sig'),(ROOT/FDC).read_text(encoding='ascii'),
                           (ROOT/'board/board1080_checked_top.v').read_text(encoding='utf-8-sig'),(ROOT/BASE_FDC).read_text(encoding='ascii'))
    payloads={};copies=[]
    for name in saved['source_files']:
        original=(ROOT/name).read_bytes();compiled,changes=compiled_source(name,original,work,alias)
        payloads[work/'compiled'/name]=compiled
        copies.append({'Source':name,'OriginalSHA256':digest(original),'CompiledPath':str(work/'compiled'/name),
                       'NativeCompiledPath':paths.alias_path(ROOT,alias,work/'compiled'/name),
                       'CompiledSHA256':digest(compiled),'Changes':changes})
    payloads[work/'compiled'/RCF]=(ROOT/RCF).read_bytes()
    payloads[work/'build.tcl']=render_tcl(roles['ExplicitDesigns'],work,alias).encode('ascii')
    config=ROOT.parent/'team-config.local.json';pds=Path(read(config)['pds_bin'])/'pds_shell.exe'
    require(pds.is_file(),'configured PDS executable missing')
    for module in (pins,paths,cleanup,raw_status):add(watched,module.__file__)
    for p in (SELF,config,pds,Path('D:/anaconda3/python.exe')):add(watched,p)
    native_work=paths.alias_path(ROOT,alias,work)
    value={'Schema':SCHEMA,'Target':TARGET,'ProjectRoot':str(ROOT),'WorkDirectory':str(work),
        'RepoAlias':alias,'AliasExpectedRepository':str(ROOT.parent.resolve()),
        'AliasRequiredForNativeExecutionOnly':True,'Manifest':ref(ROOT/MANIFEST),'SourceFiles':saved['source_files'],
        'SourceRoles':roles,'CSourceDifferenceReview':saved['CSourceDifferenceReview'],'CompiledInputs':copies,'InputTiming':profile,'FisheyeProfile':optical,'Pins':pin_review,'PLLClocks':pll_clocks(),
        'InputPixelPeriodNS':6.6667,'OutputPixelMHz':74.25,'ConfigurationMHz':10.0,
        'InputSHA256':watched,'PreparedSHA256':{str(p):digest(data) for p,data in payloads.items()},
        'ExpectedStages':STAGES,'MaximumSeconds':maximum,
        'Command':[str(pds),'-file',native_work+'/build.tcl','-work_dir',native_work,'-project_name',TARGET],
        'HardwareAccessed':False,'BitstreamRequested':False,'HardwareReleaseAllowed':False,'TimingAccepted':False,
        'ExternalACAccepted':False,'NativePinsVerified':False,'RGBPixelsVerified':False,'CapturePhaseVerified':False,
        'DigitalInputGeometryConfigured':True,'ExactFisheyeConfiguredInProductionEngine':True,
        'FrameBoundaryViewSelection':True,'RawModeIsExactRGB565Identity':True,'NoBrownRotationOrGammaChain':True,'DDRIncluded':True,
        'UserCDCExceptionsImported':False,'RetainedDDRVendorTimingClausesUnchanged':True,'PriorPhysicalProofCountsInherited':False,
        'InitialSTAADFBeforeAfterVerified':False,
        'Limits':'Independent first pixel-display diagnostic build only.150MHz input/74.25MHz output and measured digital framing do not establish progressive RGB, external AC, capture phase, pixel identity, throughput or hardware acceptance.'}
    return value,payloads


def prepare(work,alias='P:/',maximum=1800):
    work=work_path(work);require(not work.exists(),'fresh fisheye build directory required')
    value,payloads=recipe(work,alias,maximum,require_alias=True);work.mkdir(parents=True)
    for p,data in payloads.items():
        native=Path(paths.alias_path(ROOT,alias,p))
        native.parent.mkdir(parents=True,exist_ok=True);native.write_bytes(data)
    value['PreparedUTC']=utc();write(work/'plan.json',value);return value


def validate(path,require_alias=False):
    path=Path(path).absolute();work=work_path(path.parent);saved=read(path)
    require(path.name=='plan.json','exact fisheye build plan filename required')
    expected,payloads=recipe(work,saved['RepoAlias'],saved['MaximumSeconds'],require_alias=require_alias)
    require(set(saved)==set(expected)|{'PreparedUTC'} and {k:v for k,v in saved.items() if k!='PreparedUTC'}==expected,
            'fisheye build plan differs from exact current recipe')
    require({p for p in (work/'compiled').rglob('*') if local_io(p).is_file()}=={p for p in payloads if p.is_relative_to(work/'compiled')},
            'pixel compiled inventory differs')
    for p,data in payloads.items():require(local_io(p).is_file() and local_io(p).read_bytes()==data,'frozen pixel source/Tcl/FDC differs: '+str(p))
    for name,h in saved['InputSHA256'].items():require(sha(name)==h,'fisheye build input drift: '+name)
    return saved


def diagnostics(work):
    return [p.relative_to(work).as_posix()+': '+line.strip() for p in sorted(Path(work).rglob('*.log'))
            for line in p.read_text(encoding='gb18030',errors='replace').splitlines()
            if re.match(r'\s*(C:|E:|F:|CRITICAL:|ERROR:|FATAL:|Traceback)',line)]



def diagnostic_errors(rows,plan):
    """Only the five source-bound, already identified width notifications."""
    work=Path(plan['WorkDirectory']);prefix=paths.alias_path(ROOT,plan['RepoAlias'],work)+'/compiled/'
    top=(work/'compiled'/TOP).read_text(encoding='utf-8-sig').splitlines()
    def process_line(signal,clock):
        declaration=next(i for i,line in enumerate(top)if re.search(r'\breg\b.*\b'+signal+r'\b',line))
        return next(i+1 for i in range(declaration+1,len(top))if 'always @(posedge '+clock in top[i])
    specs=[(TOP,process_line('cfg_wait_count','clk_27m'),'cfg_wait_count',32,22),
        (TOP,process_line('pclk_age','clk_27m'),'pclk_age',32,22),
        ('rtl/experimental/iic_dri_checked.v',93,'watchdog',32,17),
        (IP+'/rtl/ddrphy/ips2l_ddrphy_data_slice_wrcal_v1_10.vp',614,'delay_cnt',4,2),
        (IP+'/rtl/mcdq_ctrl/ips2l_mcdq_dcp_buf_v1_2.vp',541,'cnt',7,6)]
    allowed=set()
    for source,line,name,old,new in specs:
        allowed.add('C: Sdm-3003: ['+prefix+source+'(line number: '+str(line)+')] Reduce accumulator '+name+
            ' size from '+str(old)+' to '+str(new)+'. If this is not intended behavior, please drive '+name+' with valid values.')
    return [row for row in rows if row.split(': ',1)[-1]not in allowed]


def events(text):return [list(row) for row in re.findall(r'^Process "([^"]+)" (started|done)\.',text,re.M)]


def execute(path):
    path=Path(path).absolute();plan=validate(path,require_alias=True);work=path.parent
    require(os.name=='nt' and not (work/'execution-start.json').exists(),'fresh Windows fisheye build execution required')
    watched={**plan['InputSHA256'],**plan['PreparedSHA256'],str(path):sha(path)}
    result={'Schema':'hdmi-camera-fisheye-tile8-build-execution-v1','Target':TARGET,'PlanSHA256':sha(path),
        'StartedUTC':utc(),'Command':plan['Command'],'HardwareAccessed':False,'BitstreamRequested':False,
        'EDAExecuted':False,'TimedOut':False,'StoppedForUnexpectedStage':False,'ExitCode':None,
        'TimingAccepted':False,'HardwareReleaseAllowed':False,'ExternalACAccepted':False}
    write(work/'execution-start.json',result);process=None;start=time.monotonic()
    expected=[[stage,event] for stage in STAGES for event in ('started','done')]
    try:
        with (work/'stdout.log').open('xb') as out,(work/'stderr.log').open('xb') as err:
            process=subprocess.Popen(plan['Command'],cwd=work,stdout=out,stderr=err,shell=False,
                creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0));result.update(EDAExecuted=True,OwnedPID=process.pid)
            while process.poll() is None:
                remaining=plan['MaximumSeconds']-(time.monotonic()-start)
                if remaining<=0:result['TimedOut']=True;break
                try:process.wait(timeout=min(3,remaining))
                except subprocess.TimeoutExpired:pass
                current=events((work/'stdout.log').read_text(encoding='gb18030',errors='replace'))
                if current!=expected[:len(current)]:result['StoppedForUnexpectedStage']=True;break
    except BaseException as error:result['Error']=type(error).__name__+': '+str(error)
    finally:
        result['Cleanup']=(cleanup.stop_owned_tree(process,work,'bounded independent fisheye build')
                           if process is not None and process.poll() is None else {'Complete':True,'ParentExited':True})
        if process is not None:result['ExitCode']=process.poll()
        adf=work/'place_route'/(TARGET+'_pnr.adf');report=work/'report_timing'/(TARGET+'.rtr')
        result.update(ElapsedSeconds=round(time.monotonic()-start,3),FinishedUTC=utc(),
            InputDrift=[name for name,h in watched.items() if not local_io(name).is_file() or sha(name)!=h],
            ActualEvents=events((work/'stdout.log').read_text(encoding='gb18030',errors='replace')),
            Diagnostics=diagnostics(work),ADF=str(adf),ADFSHA256=sha(adf) if adf.is_file() else None,
            TimingReport=ref(report) if report.is_file() else None,InitialSTAADFBeforeAfterVerified=False,
            NativeLogSHA256={p.relative_to(work).as_posix():sha(p) for p in work.rglob('*.log')})
        result['NativeErrors']=diagnostic_errors(result['Diagnostics'],plan)
        result['BuildCompleted']=(result['ExitCode']==0 and result['EDAExecuted'] and not result['TimedOut']
            and not result.get('Error') and not result['StoppedForUnexpectedStage'] and result['ActualEvents']==expected
            and result['InputDrift']==[] and adf.is_file() and report.is_file() and result['NativeErrors']==[] and result['Cleanup']['Complete'])
        result['DiagnosticsReviewed']=False;result['DiagnosticsCleared']=result['Diagnostics']==[]
        write(work/'execution-result.json',result)
    return result


def verify_execution(path):
    path=Path(path).absolute();work=work_path(path.parent);saved=read(path)
    require(path.name=='execution-result.json' and saved.get('Schema')=='hdmi-camera-fisheye-tile8-build-execution-v1'
            and saved.get('Target')==TARGET and saved.get('BuildCompleted') is True,
            'completed current fisheye build receipt required')
    plan=validate(work/'plan.json')
    require(saved['PlanSHA256']==sha(work/'plan.json') and saved['Command']==plan['Command']
            and saved['ExitCode']==0 and saved['EDAExecuted'] is True and saved['TimedOut'] is False
            and saved['StoppedForUnexpectedStage'] is False and not saved.get('Error')
            and saved['InputDrift']==[] and saved['NativeErrors']==[] and saved['Cleanup']['Complete'],
            'fisheye native receipt did not complete cleanly')
    actual_logs={p.relative_to(work).as_posix():sha(p) for p in work.rglob('*.log')}
    log=(work/'stdout.log').read_text(encoding='gb18030',errors='strict')
    require(saved['NativeErrors']==diagnostic_errors(saved['Diagnostics'],plan)
            and saved['NativeLogSHA256']==actual_logs and saved['Diagnostics']==diagnostics(work)
            and saved['ActualEvents']==events(log)==[[s,e] for s in STAGES for e in ('started','done')],
            'fisheye native logs/events differ')
    adf=work/'place_route'/(TARGET+'_pnr.adf');report=work/'report_timing'/(TARGET+'.rtr')
    require(saved['ADF']==str(adf) and saved['ADFSHA256']==sha(adf) and saved['TimingReport']==ref(report),
            'fisheye native ADF/report binding differs')
    require(all(saved.get(k) is False for k in ('HardwareAccessed','BitstreamRequested','HardwareReleaseAllowed',
                                              'TimingAccepted','ExternalACAccepted')),'pixel receipt overclaims release')
    return saved


def main():
    p=argparse.ArgumentParser(description=__doc__);m=p.add_mutually_exclusive_group(required=True)
    m.add_argument('--write-manifest',action='store_true');m.add_argument('--prepare',type=Path)
    m.add_argument('--validate',type=Path);m.add_argument('--execute',type=Path)
    m.add_argument('--verify-result',type=Path)
    p.add_argument('--repo-alias',default='P:/');p.add_argument('--maximum-seconds',type=int,default=1800);a=p.parse_args()
    if a.write_manifest:print(json.dumps({'Created':str(write_manifest())}));return 0
    if a.prepare:v=prepare(a.prepare,a.repo_alias,a.maximum_seconds);print(json.dumps({'Prepared':True,'Plan':str(Path(v['WorkDirectory'])/'plan.json')}));return 0
    if a.validate:validate(a.validate);print('{"Validated":true,"HardwareAccessed":false}');return 0
    if a.verify_result:verify_execution(a.verify_result);print('{"Verified":true,"HardwareAccessed":false}');return 0
    v=execute(a.execute);print(json.dumps({k:v.get(k) for k in ('BuildCompleted','ExitCode','ElapsedSeconds','Error')}));return 0 if v['BuildCompleted'] else 1


if __name__=='__main__':raise SystemExit(main())
