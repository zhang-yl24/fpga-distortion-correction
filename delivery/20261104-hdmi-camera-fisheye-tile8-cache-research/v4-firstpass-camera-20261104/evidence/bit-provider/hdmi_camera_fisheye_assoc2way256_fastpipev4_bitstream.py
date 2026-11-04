"""C fisheye authority: current DDR physical proof, C profile and RTL simulations.

Prepare never runs PDS. Execution requires fresh STA and a saved-firstpass gate,
and explicit UNUSED bit generation. Hardware/image/optical acceptance is separate.
Native1080 system evidence executes source RTL in XSim, not a post-route netlist.
"""
import argparse
from collections import Counter
import copy
from datetime import datetime, timezone
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

SITE=Path(__file__).resolve().parents[2]/'.venv/Lib/site-packages'
sys.path.insert(0,str(SITE))
import hdmi_camera_fisheye_assoc2way256_fastpipe_build as build
import hdmi_camera_fisheye_assoc2way256_fastpipev2_scoped_native as native


SELF = Path(__file__).resolve()
TARGET, ROOT, WORK = build.TARGET, build.ROOT, build.WORK
PYTHON = Path('D:/anaconda3/python.exe')
REQUEST_SCHEMA = 'hdmi-camera-fisheye-assoc2way256fastpipev4-bitstream-request-v1'
PLAN_SCHEMA = 'hdmi-camera-fisheye-assoc2way256fastpipev4-bitstream-plan-v1'
EXEC_SCHEMA = 'hdmi-camera-fisheye-assoc2way256fastpipev4-bitstream-execution-v1'
PROOF_SCHEMA = 'hdmi-camera-fisheye-assoc2way256fastpipev2-final-physical-proof-v1'
GATE_SCHEMA = 'hdmi-camera-fisheye-assoc2way256fastpipev4-pre-bit-gate-v1'
GATE = 'HDMI_CAMERA_FISHEYE_ASSOC2WAY256FASTPIPEV4_PRE_BIT_GATE_PASS'
COMPLETE = 'HDMI_CAMERA_FISHEYE_ASSOC2WAY256FASTPIPEV4_BITSTREAM_COMPLETE'
FIELDS = {'Schema', 'Target', 'PhysicalProof', 'MapperSimulation', 'SystemSimulation', 'IOSimulation', 'Profile','Authority'}
SIMULATIONS = {'MapperSimulation': 'run_hdmi_camera_fisheye_mapper_sim',
               'SystemSimulation': 'run_hdmi_camera_fisheye_assoc2way256_fastpipe_system_sim',
               'IOSimulation': 'run_hdmi_camera_fisheye_io_sim'}
REPORT = 'report_timing/' + TARGET + '.rtr'
EXCEPTIONS = 'report_timing/' + TARGET + '_exception.rtr'
BIT = 'generate_bitstream/' + TARGET + '.sbit'
BGR = 'generate_bitstream/' + TARGET + '.bgr'
STAGES = ['Report Timing', 'Generate Bitstream']
EXPECTED_BIT_BYTES = 3791112
require, sha, read, write = build.require, build.sha, build.read, build.write
_AUTHORITY_CACHE = {}
_SHA_IDENTITIES = {}
_SAVED_BUILDS = {}
AUTHORITY_SCHEMA='fastpipe-saved-firstpass-release-authority-v4'
WITNESS_SCHEMA='fastpipe-saved-firstpass-closure-sha-witness-v4'
FIRST_PROOF_SHA='4e331eb3b6bf21e12b5f9446e03e477156fefeeeddaeb760ab5eb3224a3b85e0'


def file_identity(path):
    stat=build.local_io(path).stat()
    return [stat.st_size,stat.st_mtime_ns,stat.st_ctime_ns,stat.st_ino]


def sha(path):
    """Reuse an exact SHA only while its four-field local file identity is unchanged."""
    path=Path(path).resolve();key=str(path);identity=file_identity(path)
    prior=_SHA_IDENTITIES.get(key)
    if prior is not None and prior[0]==identity:return prior[1]
    digest=build.sha(path)
    require(file_identity(path)==identity,'file changed during SHA read: '+key)
    _SHA_IDENTITIES[key]=(identity,digest)
    return digest


def saved_build(record):
    require(isinstance(record,dict)and set(record)=={'Path','SHA256'},'saved build reference required')
    path=Path(record['Path']).resolve();require(sha(path)==record['SHA256'],'saved build SHA differs')
    require(str(path)in _SAVED_BUILDS,'build must come from current once-checked authority')
    return copy.deepcopy(_SAVED_BUILDS[str(path)])


def bind_saved_closure(authority_path,request_path,inputs):
    """First use hashes every input; later uses reject any saved identity change.

    This is an explicit local saved-evidence optimization, not a second full
    physical/simulation derivation or a cryptographic claim about hostile mtime edits.
    """
    witness_path=request_path.with_name(request_path.stem+'-closure-sha-witness.json')
    if witness_path.exists():
        witness=read(witness_path)
        require(witness.get('Schema')==WITNESS_SCHEMA and witness.get('Authority')==ref(authority_path)and
                witness.get('Request')==ref(request_path)and witness.get('InputSHA256')==inputs and
                witness.get('AllSHA256VerifiedOnce')is True,'saved SHA witness authority differs')
        states=witness.get('FileIdentity',{})
        require(set(states)==set(inputs),'saved SHA witness omitted file identities')
        for name,digest in inputs.items():
            require(file_identity(name)==states[name],'saved authority file identity changed: '+name)
            _SHA_IDENTITIES[name]=(states[name],digest)
    else:
        states={}
        for name,digest in inputs.items():
            require(Path(name).is_absolute()and str(Path(name).resolve())==name and
                    re.fullmatch('[0-9a-f]{64}',digest)is not None,'canonical SHA closure required')
            require(sha(name)==digest,'saved closure SHA differs: '+name)
            states[name]=file_identity(name)
        require(all(file_identity(name)==state for name,state in states.items()),'closure changed during initial SHA pass')
        witness={'Schema':WITNESS_SCHEMA,'Authority':ref(authority_path),'Request':ref(request_path),
                 'InputSHA256':inputs,'FileIdentity':states,'AllSHA256VerifiedOnce':True,
                 'SubsequentValidation':'Exact size/mtime_ns/ctime_ns/inode; SHA rechecked for new or changed files.',
                 'FullPhysicalOrSimulationRederived':False,'CheckedUTC':utc()}
        write(witness_path,witness)
    return ref(witness_path)


def stop_identity(observed,launch,ended,proof_ref):
    require(observed.get('Schema')=='fastpipe-firstpass-proof-root-observation-v4'and
            observed.get('PhysicalProof')==proof_ref and observed.get('FirstPassCompleted')is True and
            observed.get('SecondVerificationInterrupted')is True and
            all(observed.get(k)is True for k in ('WorkerAbsent','PDSAbsent','PDriveReleased')),
            'actual saved-firstpass and stopped second pass observation required')
    require(type(observed.get('ExitCode'))is int and observed['ExitCode']!=0 and
            type(ended.get('ExitCode'))is int and ended['ExitCode']==observed['ExitCode'] and
            type(launch.get('PID'))is int and launch['PID']>0 and
            launch['PID']==ended.get('PID')==observed.get('PID') and
            launch.get('CreationUTC')==ended.get('CreationUTC')==observed.get('CreationUTC') and
            isinstance(launch.get('CreationUTC'),str)and bool(launch['CreationUTC']) and
            launch.get('ProcessHandleRetained')is True and ended.get('ProcessHandleRetained')is True,
            'interrupted second-pass actual nonzero exit identity required')
    return True


def saved_native_flags(value):
    require(value.get('ExecutionPassed')is True and type(value.get('ExitCode'))is int and value['ExitCode']==0 and
            value.get('TimedOut')is False and value.get('InputDrift')==[] and not value.get('Error')and
            value.get('Cleanup',{}).get('Complete')is True,'completed saved native stage required')


def utc():
    return datetime.now(timezone.utc).isoformat()


def ref(path):
    path = Path(path).resolve()
    return {'Path': str(path), 'SHA256': sha(path)}


def add(watched, path, expected=None):
    path = Path(path).absolute()
    require(path == path.resolve() and build.local_io(path).is_file(), 'canonical existing input required: ' + str(path))
    digest = sha(path)
    require(expected is None or isinstance(expected, str) and re.fullmatch('[0-9a-f]{64}', expected)
            and digest == expected, 'input SHA differs: ' + str(path))
    require(str(path) not in watched or watched[str(path)] == digest, 'conflicting input SHA')
    watched[str(path)] = digest
    return path


def merge(watched, inputs):
    for path, digest in inputs.items():
        add(watched, path, digest)


def binding(value, watched):
    require(isinstance(value, dict) and set(value) == {'Path', 'SHA256'}, 'exact Path/SHA256 reference required')
    return add(watched, value['Path'], value['SHA256'])


def drift(watched):
    return [str(p) for p, h in watched.items() if not build.local_io(p).is_file() or sha(p) != h]


def physical_provider():
    module = importlib.import_module('hdmi_camera_fisheye_assoc2way256_fastpipev2_final')
    require(Path(module.__file__).resolve() == SELF.with_name('hdmi_camera_fisheye_assoc2way256_fastpipev2_final.py'), 'physical provider location differs')
    return module


def physical_flags(proof):
    require(proof.get('Schema')==PROOF_SCHEMA and proof.get('Target')==TARGET,'current fisheye physical proof required')
    for name in ('Passed','STAAllTenPassed','NativeWarningsReviewed','SourceDiagnosticReviewPassed','NetlistEquivalent',
                 'AllFFPlacementsEquivalent','RoutesUnchanged','ResetAccepted','SourceSamplingIsolatedVerified',
                 'VendorDDRClockResetAccepted','FrameBoundaryViewSelectionAccepted','FisheyeProfileAccepted','UserCDCAccepted',
                 'ActualNativeCacheRAMMappingPassed'):
        require(proof.get(name)is True,'fisheye physical proof incomplete: '+name)
    pins=proof.get('Pins',{});active=pins.get('NativeActivePorts');unused=pins.get('UnusedPads')
    require(type(pins.get('DeclaredTopPorts'))is int and pins['DeclaredTopPorts']==144 and
        type(pins.get('NativeRoutedPorts'))is int and pins['NativeRoutedPorts']==144 and
        type(active)is int and active==144 and unused==[]and
        pins.get('NativeElectricalParametersVerified')is True,'complete current144-pin fisheye disposition required')
    cdc=proof.get('DataCDC',{})
    require(cdc.get('InterstageTimingAccepted')is True and cdc.get('Missing')==[]and cdc.get('Violations')==[],
        'complete actual fisheye user CDC/interstage acceptance required')
    acceptance=proof.get('NativeAcceptance');partitions=proof.get('SourcePartitions')
    require(isinstance(acceptance,dict)and acceptance and isinstance(partitions,dict)and partitions,
        'current native DDR/reset/CDC/source partitions required')
    ram=proof.get('CacheRAMMapping',{})
    require(ram.get('Passed')is True and ram.get('LogicalPixelBytes')==262144 and
        ram.get('Ways')==2 and ram.get('Sets')==512 and ram.get('PixelDRM36Count')==64 and
        ram.get('TrueDualPortAndReadBeforeWrite')is True and ram.get('ActualSynthesisMappingAndNetlistChecked')is True,
        'actual two-way 256 KiB FAST pixel RAM mapping required')


def simulation_provider(kind):
    require(kind in SIMULATIONS,'unknown fisheye simulation role')
    name=SIMULATIONS[kind]
    module=importlib.import_module(name)
    require(Path(module.__file__).resolve()==SELF.with_name(name+'.py'),
            'fisheye simulation provider location differs: '+kind)
    return module



def directfill_frame_counts(frames):
    """Validate the counters parsed from actual DUT events, not predictions."""
    require(isinstance(frames,list) and len(frames)==2,'two actual direct-fill frames required')
    for row in frames:
        counts={}
        for name in ('fills','scatter_cycles','cache_ram_write_cycles','cache_fill_valid_commits'):
            value=row.get(name)
            require(type(value)is int and value>=0 or type(value)is str and
                re.fullmatch(r'0|[1-9][0-9]*',value) is not None,
                'canonical actual direct-fill counter required: '+name)
            counts[name]=int(value)
        require(counts['scatter_cycles']==0 and counts['cache_ram_write_cycles']==8*counts['fills'] and
            counts['cache_fill_valid_commits']==counts['fills'],
            'each actual direct-fill frame must bind zero scatter, eight RAM writes and one valid commit per fill')


def bind_simulation(kind,path,plan,watched):
    provider=simulation_provider(kind);value,inputs=provider.verify(path)
    require(value==read(path)and value.get('Passed')is True and value.get('HardwareAccessed')is False and
        value.get('PDSAccessed')is False and not value.get('Error'),'clean actual simulation required: '+kind)
    merge(watched,inputs);add(watched,path);add(watched,provider.__file__)
    names={'MapperSimulation':(build.MAPPER,build.ROM,build.PROFILE_HEADER,build.RADIAL_HEADER,'rtl/mul32_pipe.v'),
        'SystemSimulation':(build.SAMPLER,build.MAPPER,build.ROM,build.PROFILE_HEADER,build.RADIAL_HEADER,build.VIEW_CONTROL,
            *[build.REQUIRED_MODULES[n]for n in ('hdmi_camera_fisheye_system','hdmi_camera_fisheye_bank',
                'hdmi_camera_fisheye_engine_tile8','hdmi_camera_fisheye_core','hdmi_camera_fisheye_input_link',
                'ddr_neighbour_cache_scatter16_rowpipe','ddr_remap_sample_scatter4','ddr_read_arbiter',
                'ddr_adaptive_result_writer_dualstripe')]),
        'IOSimulation':(build.QUANTIZER,build.STATUS_UART,build.UART)}[kind]
    sources=value.get('SourceSHA256',{})
    for name in names:
        original=str((ROOT/name).resolve());observed=sources.get(name)if kind=='SystemSimulation'else sources.get(original)
        require(original in plan['InputSHA256']and observed==plan['InputSHA256'][original],
            'fisheye regression compiled different build-plan RTL/header: '+kind+' '+name)
    if kind=='MapperSimulation':
        require(value.get('Mode')=='native'and value.get('SmallGate')and value.get('SourceDrift')==[]and
            value.get('ActualMapperROMAndMultipliersExecuted')is True,'actual same-source native mapper required')
        summary=value.get('Summary',{});error=value.get('FullNativeCPUError',{})
        require(summary.get('CorrectedCoordinates')==2073600 and summary.get('ExactIdentityCoordinates')==4096 and
            summary.get('DomainCoordinates')==1024 and summary.get('TotalCoordinatesMatched')==2078720 and
            summary.get('InitiationInterval')==1 and summary.get('PipelineEnabledStages')==23 and
            error.get('NativeCoordinatesChecked')==2073600 and error.get('ArithmeticMaskedCoordinates')==0 and
            error.get('Passed')is True and 0<=error.get('FixedVsOpenCVMaxNativePixels',1)<=.125,
            'full native fisheye/error/identity/throughput oracle required')
    elif kind=='SystemSimulation':
        require(value.get('Mode')=='native'and value.get('SmallGate')and value.get('FunctionalPassed')is True and
            value.get('InputClockHz')==148500000 and value.get('OutputClockHz')==74250000 and
            value.get('SystemClockHz')==125000000 and value.get('ActualPixelSamplerInstantiated')is True and
            value.get('InputDDRPreloaded')is False and value.get('RealOutputAsyncFIFO')is True and
            value.get('ActualDERGBScanned')is True,'actual complete raw-to-DDR-fisheye/identity scan required')
        require(value.get('DirectFillCache')is True and value.get('CacheIndexBits')==10 and
            value.get('CacheWays')==2 and value.get('CacheSets')==512 and value.get('CacheLogicalBytes')==262144 and
            value.get('CacheKind')=='assoc2way256-fastpipe' and
            value.get('ScatterCyclesPerFill')==0 and value.get('CacheRAMWriteCyclesPerFill')==8 and
            value.get('CandidateCache')==build.REQUIRED_MODULES['ddr_neighbour_cache_scatter16_rowpipe'],
            'actual FAST two-way INDEX10 cache system evidence required')
        require(value.get('CandidateArbiter')==build.REQUIRED_MODULES['ddr_read_arbiter'],
            'current r2 arbiter system evidence required')
        require(value.get('CandidateEngine')==build.REQUIRED_MODULES['hdmi_camera_fisheye_engine_tile8'] and
            value.get('CandidateWriter')==build.REQUIRED_MODULES['ddr_adaptive_result_writer_dualstripe'] and
            value.get('CorrectedCoordinatesTiled8x8')is True and value.get('RawCoordinatesRaster')is True,
            'actual tile8 corrected/raw engine and dual-stripe writer evidence required')
        # Bind every executed production RTL/header, including bank, writer,
        # arbitration and display, not just the changed three role names.
        compiled={row['Source']:row for row in plan['CompiledInputs']}
        production,headers,_,_=provider.closure()
        for name in (*production,*headers):
            if name==provider.BENCH:continue
            original=str((ROOT/name).resolve());observed=sources[name];row=compiled.get(name)
            require(plan['InputSHA256'].get(original)==observed and row is not None and
                row['OriginalSHA256']==observed and sha(row['CompiledPath'])==row['CompiledSHA256'] and
                plan['PreparedSHA256'].get(row['CompiledPath'])==row['CompiledSHA256'],
                'tile8 entire executed production source/header differs from built closure: '+name)
            add(watched,row['CompiledPath'],row['CompiledSHA256'])
        directfill_frame_counts(value.get('Frames'))
        summary=value.get('Summary',{})
        for field,expected in {'frames_input':2,'frames_committed':2,'frames_processed':2,'frames_published':2,
            'frames_unique_scanned':2,'unique_scanned_pixels':4147200,'key_toggles':3,
            'mode_changes_while_processing':3,'frame_mode_latches':2,'output_underflows':0,'output_crc_mismatches':0,
            'dropped_frames':0,'overflow_frames':0,'no_free_frames':0,'final_drain':True}.items():
            require(summary.get(field)==expected,'actual system/frame-lock coverage differs: '+field)
        require(len(value.get('Frames',[]))==2 and len(value.get('Fixture',{}).get('Frames',[]))>=2 and
            value['Fixture']['Frames'][0].get('Corrected')is True and value['Fixture']['Frames'][1].get('Corrected')is False and
            value['Fixture']['Frames'][1].get('ChangedPixels')==0,
            'two fully drained corrected/bit-exact identity output frames required')
    else:
        require(value.get('SourceDrift')==[]and value.get('ActualUARTPinDecodePassed')is True and
            value.get('ActualQuantizerAll256ValuesAndTimingPassed')is True and
            value.get('AtomicSnapshotUnaffectedByLaterCounterAndFaultChanges')is True and
            value.get('Bytes')==96 and value.get('BitCycles')==(125000000+115200//2)//115200,
            'actual PGHFPS02 UART and matched quantizer regression required')
    return value


def bind_sustained(plan,watched):
    """Require this run's separate four-corrected-frame contention evidence."""
    import run_hdmi_camera_fisheye_assoc2way256_fastpipe_continuation_sustained_sim as provider
    require(Path(provider.__file__).resolve()==SELF.with_name('run_hdmi_camera_fisheye_assoc2way256_fastpipe_continuation_sustained_sim.py'),
        'selected sustained simulation provider location differs')
    path=WORK/'system-sustained-continuation-native-a/simulation.json'
    value,inputs=provider.verify(path)
    require(value==read(path) and value.get('Schema')=='hdmi-camera-fisheye-assoc2way256fastpipe-sustained-simulation-v1' and
        value.get('Mode')=='native' and value.get('Passed')is True and value.get('FunctionalPassed')is True and
        value.get('ActualDERGBScanned')is True and value.get('HardwareAccessed')is False and
        value.get('PDSAccessed')is False and value.get('InputDrift')==[] and not value.get('Error'),
        'actual completed selected native sustained simulation required')
    exact={'SourceFrames':16,'AcceptedCompleteFrames':4,'DDRFirstBeatLatencyCycles':40,
        'AdmissionDisabledOnlyAfterCompleteSources':4,'CacheIndexBits':10,'CacheWays':2,'CacheSets':512,
        'CacheLogicalBytes':262144,'ScatterCyclesPerFill':0,
        'CacheRAMWriteCyclesPerFill':8,'InputClockHz':148500000,'OutputClockHz':74250000,'SystemClockHz':125000000}
    require(all(type(value.get(k))is int and value[k]==v for k,v in exact.items()) and
        value.get('ContinuousUnthrottledInput')is True and value.get('ActualPixelSamplerInstantiated')is True and
        value.get('DirectFillCache')is True and value.get('CacheKind')=='assoc2way256-fastpipe' and
        value.get('InputDDRPreloaded')is False and value.get('RealOutputAsyncFIFO')is True and
        value.get('CorrectedCoordinatesTiled8x8')is True and
        all(value.get(field)==build.REQUIRED_MODULES[module]for field,module in (
            ('CandidateEngine','hdmi_camera_fisheye_engine_tile8'),
            ('CandidateWriter','ddr_adaptive_result_writer_dualstripe'),
            ('CandidateCache','ddr_neighbour_cache_scatter16_rowpipe'),('CandidateArbiter','ddr_read_arbiter'))),
        'sustained FAST INDEX10 two-way/16-source/4-accepted/40-cycle model differs')
    fixture=value.get('Fixture',{})
    require(fixture.get('Width')==1920 and fixture.get('Height')==1080 and fixture.get('InputSourceFrames')==16 and
        len(fixture.get('Frames',[]))==3 and all(row.get('Corrected')is True for row in fixture['Frames']),
        'native sustained source textures must all use the corrected oracle')
    summary=value.get('Summary',{})
    expected={'passed':True,'frames_input':16,'frames_committed':4,'frames_processed':4,'frames_published':4,
        'frames_unique_scanned':4,'unique_scanned_pixels':8294400,'source_beats':518400,'result_beats':518400,
        'output_underflows':0,'output_crc_mismatches':0,'dropped_frames':0,'overflow_frames':0,
        'final_drain':True,'key_toggles':0,'mode_changes_while_processing':0,'frame_mode_latches':4}
    require(all(type(summary.get(k))is type(v) and summary[k]==v for k,v in expected.items()),
        'four distinct complete corrected scans and final drain required')
    require(all(type(summary.get(k))is int and summary[k]>0 for k in
        ('aw_stall','w_stall','physical_ar_stall','read_contention','write_contention','no_free_frames')) and
        value.get('ActualDDRReadContentionExercised')is True and value.get('ActualDDRWriteContentionExercised')is True,
        'actual sustained read/write contention and source admission backpressure required')
    def count(row,name):
        require(isinstance(row,dict),'actual sustained counter row required')
        number=row.get(name)
        require(type(number)is int and number>=0 or type(number)is str and
            re.fullmatch(r'0|[1-9][0-9]*',number)is not None,'canonical actual sustained counter required: '+name)
        return int(number)
    frames=value.get('Frames');metrics=value.get('PerformanceBreakdown')
    require(isinstance(frames,list) and isinstance(metrics,list) and len(frames)==len(metrics)==4 and
        [count(row,'frame_id')for row in frames]==[1,2,3,4],
        'four ordered distinct actual sustained frame IDs required')
    overlap=0;previous_source=-1
    for index,(row,metric)in enumerate(zip(frames,metrics)):
        fills=count(row,'fills');source=count(row,'input_source_index')
        require(previous_source<source<16,'sustained accepted source IDs must be increasing within sixteen rasters')
        previous_source=source
        require(fills>0 and count(row,'scatter_cycles')==0 and count(row,'cache_ram_write_cycles')==8*fills and
            count(row,'cache_fill_valid_commits')==fills,
            'each sustained frame needs zero scatter, eight actual RAM writes and one valid commit per fill')
        require(count(row,'input_pixels')==2073600 and count(row,'source_beats')==count(row,'result_beats')==129600 and
            all(count(row,k)==1 for k in ('commits','releases','publishes','unique_scans')),
            'actual per-ID sustained pixels/ownership differs')
        require(count(metric,'frame_id')==index+1 and count(metric,'corrected')==1 and
            count(metric,'coordinates_issued')==2073600 and all(count(metric,k)==count(row,k)for k in
                ('scatter_cycles','hardware_process_cycles','cache_ram_write_cycles','cache_fill_valid_commits')),
            'sustained per-ID corrected performance evidence differs')
        overlap+=count(row,'future_capture_write_overlap_cycles')
    require(type(value.get('FutureSourceWriteOverlapCycles'))is int and
        value['FutureSourceWriteOverlapCycles']==overlap and overlap>0,
        'actual future-source DDR writes must overlap active corrected processing')
    compiled={row['Source']:row for row in plan['CompiledInputs']}
    production,headers,_,_=provider.closure()
    for name in (*production,*headers):
        if name==provider.BENCH:continue
        original=str((ROOT/name).resolve());observed=value.get('SourceSHA256',{}).get(name);row=compiled.get(name)
        require(plan['InputSHA256'].get(original)==observed and row is not None and
            row['OriginalSHA256']==observed and sha(row['CompiledPath'])==row['CompiledSHA256'] and
            plan['PreparedSHA256'].get(row['CompiledPath'])==row['CompiledSHA256'],
            'sustained executed production RTL/header differs from actual built closure: '+name)
        add(watched,row['CompiledPath'],row['CompiledSHA256'])
    merge(watched,inputs);add(watched,path);add(watched,provider.__file__)
    return value


def bind_profile(path,plan,watched):
    bound,inputs=build.fisheye_profile_binding(path);merge(watched,inputs)
    require(bound==plan.get('FisheyeProfile'),'bit profile differs from fully rederived build profile')
    error=bound['FullGridError'];require(error['Passed']is True and error['NativeCoordinatesChecked']==2073600 and
        error['ArithmeticMaskedCoordinates']==0 and error['FixedVsOpenCVMaxNativePixels']<=.125,
        'actual C full-native OpenCV profile error gate required')
    for name in (build.PROFILE_HEADER,build.RADIAL_HEADER):
        original=str((ROOT/name).resolve());require(bound['GeneratedFiles'][original]==plan['InputSHA256'][original],
            'generated profile header differs from built mapper source')
    return bound


def bind_physical_core(proof, verified_inputs, proof_path, watched):
    """Retain the complete saved proof core, independently of importing callers.

    The provider already rederived all facts and verified its full current
    closure. Additional caller modules must not change an otherwise identical
    bit recipe; every saved core input and the proof itself remain mandatory.
    """
    core = proof.get('InputSHA256')
    require(isinstance(core, dict) and core, 'physical proof input core required')
    verified = {}
    for name, digest in verified_inputs.items():
        path = Path(name).absolute()
        require(path == path.resolve() and
                (str(path) not in verified or verified[str(path)] == digest),
                'ambiguous verified physical input')
        verified[str(path)] = digest
    require(all(verified.get(name) == digest for name, digest in core.items()),
            'verified physical inputs omit or change saved proof core')
    proof_path = Path(proof_path).resolve()
    require(verified.get(str(proof_path)) == sha(proof_path), 'verified physical proof file unbound')
    merge(watched, core)
    add(watched, proof_path, verified[str(proof_path)])


def bind_log_group(path, hashes, watched):
    require(isinstance(hashes, dict) and 'simulation.log' in hashes, 'simulation log closure required')
    for name, digest in hashes.items():
        p = path.parent / name
        require(p.resolve().is_relative_to(path.parent), 'simulation artifact path escapes directory')
        add(watched, p, digest)
    text = (path.parent / 'simulation.log').read_text(encoding='utf-8', errors='replace')
    require('$finish called' in text and not re.search(r'(?im)^\s*(?:fatal|error):', text), 'simulation did not finish cleanly')
    return text


def audit_request(path, *, use_cache=True):
    path=Path(path).resolve();require(path.parent==WORK.resolve(),'bit request must be in fisheye work root')
    request=read(path);require(set(request)==FIELDS and request.get('Schema')==REQUEST_SCHEMA and
                             request.get('Target')==TARGET,'exact saved-authority v4 request required')
    cache_key=(str(path),sha(path));cached=_AUTHORITY_CACHE.get(cache_key) if use_cache else None
    if cached is not None:
        require(not drift(cached['Watched']),'saved authority input drift')
        return cached
    authority_path=Path(request['Authority']['Path']).resolve()
    require(authority_path.parent==WORK.resolve()and ref(authority_path)==request['Authority'],'exact local authority required')
    authority=read(authority_path)
    require(authority.get('Schema')==AUTHORITY_SCHEMA and authority.get('Target')==TARGET and
            authority.get('FirstPassCompleted')is True and authority.get('FullFinalReevaluationSkippedAtUserRequest')is True and
            authority.get('FlashAuthorized')is False and
            all(authority.get('RootHandoff',{}).get(k)is True for k in ('UserAuthorizedVolatileSRAM','UserNotifiedBeforeExecution')),
            'explicit saved-firstpass volatile release authority required')
    selected={k:request[k]for k in FIELDS-{'Schema','Target','Authority'}}
    require(authority.get('SelectedReleaseInputs')==selected and authority.get('PhysicalProof')==request['PhysicalProof'] and
            request['PhysicalProof']['SHA256']==FIRST_PROOF_SHA,'exact completed firstpass and selected roles required')
    watched=dict(authority['InputSHA256'])
    require(watched,'nonempty saved source closure required')
    for p in (authority_path,path):
        key=str(p);digest=sha(p);require(key not in watched or watched[key]==digest,'authority self binding differs');watched[key]=digest
    witness=bind_saved_closure(authority_path,path,watched)
    def bound(record):
        require(isinstance(record,dict)and set(record)=={'Path','SHA256'}and
                watched.get(record['Path'])==record['SHA256']and sha(record['Path'])==record['SHA256'],
                'saved authority role absent or changed: '+str(record))
        return read(record['Path'])
    def covered(mapping,label):
        require(isinstance(mapping,dict)and mapping and all(watched.get(str(p))==h for p,h in mapping.items()),
                'saved authority omitted '+label)
    observed=bound(authority['RootObservation']);launch=bound(observed['ActualLaunchReceipt']);ended=bound(observed['ActualExitReceipt'])
    stop_identity(observed,launch,ended,request['PhysicalProof'])
    require(ended.get('LaunchReceiptSHA256')==observed['ActualLaunchReceipt']['SHA256']and
            ended.get('LauncherSHA256')==launch.get('LauncherSHA256'),'actual interrupted launch source differs')
    first=bound(observed['FirstPassObservation']);stop=bound(observed['OriginalStopObservation'])
    require(first.get('FirstPassProofComplete')is True and first.get('FirstPassProof')==request['PhysicalProof']and
            first.get('NativeResultsAllActualExitZero')is True and stop.get('FirstPassProof')==request['PhysicalProof']and
            stop.get('ActualExitCode')==ended['ExitCode']and stop.get('SecondPassPassed')is False and
            stop.get('SecondPassIntentionallyInterrupted')is True and stop.get('FirstPassProofPreserved')is True,
            'first proof and deliberate nonzero second-pass stop must remain separate')
    proof=bound(request['PhysicalProof']);physical_flags(proof);covered(proof['InputSHA256'],'full firstpass proof closure')
    require(proof['BuildPlan']['Path']==str(WORK/'build-a/plan.json'),'exact original build required')
    plan=bound(proof['BuildPlan']);plan_path=Path(proof['BuildPlan']['Path'])
    for key in ('InputSHA256','PreparedSHA256'):covered(plan[key],'saved build '+key)
    for record in (proof['Application'],proof['FinalExport'],proof['FinalRoute'],*proof['FinalQueries']):
        result=bound(record);saved_native_flags(result);covered(result['InputSHA256'],'actual native stage closure')
        if record!=proof['Application']:require(result.get('SourceProof')==proof['Application'],'native stage changed application')
    require(first.get('Application')==proof['Application']and first.get('FinalExport')==proof['FinalExport']and
            first.get('FinalRoute')==proof['FinalRoute']and first.get('FinalQueries')==proof['FinalQueries']and
            first.get('FinalADF')==proof['FinalADF'],'root firstpass exact native roles differ')
    for record in (proof['FinalADF'],proof['FreshSTAReport'],proof['FreshSTAExceptions']):
        require(watched.get(record['Path'])==record['SHA256']and sha(record['Path'])==record['SHA256'],'firstpass ADF/STA bytes differ')
    adf=Path(proof['FinalADF']['Path']);require(adf.suffix=='.adf'and adf.is_relative_to(WORK.resolve()),'final candidate ADF required')
    require(proof['Pins']['DeclaredTopPorts']==len(plan['Pins']['PinInventory'])and native.MAX_PATHS==10000,'physical pin/report contract differs')
    simulations={kind:bound(request[kind])for kind in SIMULATIONS}
    for kind,value in simulations.items():
        require(value.get('Passed')is True and value.get('HardwareAccessed')is False and value.get('PDSAccessed')is False and
                not value.get('Error'),'saved native simulation failed: '+kind)
        if value.get('InputSHA256'):covered(value['InputSHA256'],'saved '+kind)
        if value.get('SourceSHA256'):
            for source,digest in value['SourceSHA256'].items():
                original=str((ROOT/source).resolve())if not Path(source).is_absolute()else str(Path(source).resolve())
                if original in plan['InputSHA256']:require(plan['InputSHA256'][original]==digest,'saved simulation/build source differs')
    directfill_frame_counts(simulations['SystemSimulation'].get('Frames'))
    sustained_path=WORK/'system-sustained-continuation-native-a/simulation.json'
    require(str(sustained_path)in watched,'saved sustained role missing')
    sustained=read(sustained_path)
    require(sustained.get('Passed')is True and sustained.get('FunctionalPassed')is True and sustained.get('HDLRunReexecuted')is False and
            sustained.get('SourceFrames')==16 and sustained.get('AcceptedCompleteFrames')==4 and
            sustained.get('DDRFirstBeatLatencyCycles')==40 and sustained.get('SimulatorNaturalExitCodes')=={'xsim':0,'xsimk':0},
            'saved finite four-frame natural completion required')
    covered(sustained['InputSHA256'],'saved sustained closure')
    completion=bound(sustained['Completion'])
    require(completion.get('Passed')is True and completion.get('OriginalTimeoutConvertedToSuccess')is False and
            completion.get('OriginalOuterRun',{}).get('ActualExitCode')==1 and
            completion.get('Summary',{}).get('unique_scanned_pixels')==8294400 and
            completion.get('Summary',{}).get('final_drain')is True,'saved full pixel/CRC completion identity differs')
    profile=plan['FisheyeProfile'];require(profile.get('FullGridError',{}).get('Passed')is True,'saved profile acceptance required')
    bound(request['Profile'])
    for p in (SELF,PYTHON,Path(physical_provider().__file__),Path(build.__file__),Path(native.__file__),Path(build.cleanup.__file__),Path(plan['Command'][0])):
        require(watched.get(str(p.resolve()))==sha(p),'current runtime source not frozen: '+str(p))
    watched[str(Path(witness['Path']))]=witness['SHA256']
    _SAVED_BUILDS[str(plan_path)]=plan
    context={'Request':request,'RequestPath':path,'Proof':proof,'BuildPlan':plan_path,'Build':plan,
             'FinalADF':adf,'FinalADFSHA256':proof['FinalADF']['SHA256'],'Watched':watched,
             'Simulations':simulations,'Profile':profile,'SustainedSimulation':sustained,
             'SavedAuthority':request['Authority'],'ClosureWitness':witness}
    _AUTHORITY_CACHE[cache_key]=context
    return context


def context_prefix(plan_path):
    return native.context_prefix(plan_path)


def tcl_path(path):
    value = Path(path).resolve().as_posix()
    require(not any(c in value for c in '{}\r\n'), 'unsafe Tcl path')
    return '{' + value + '}'


def native_work(path):
    # Stable textual alias; only native execution requires its live mapping.
    return build.paths.alias_path(ROOT, 'P:/', Path(path))


def native_tcl(path):
    value=path if isinstance(path,str) else native_work(path)
    require(not any(c in value for c in '{}\r\n'), 'unsafe native Tcl path')
    return '{'+value+'}'


def render(context,work):
    w=Path(work)
    return (context_prefix(context['BuildPlan'])+'report_timing -force_to_run -input_db_file '+
        native_tcl(w/'audited-final.adf')+' -delay_type min_max -max_path 10000 -nworst 4 -report_exception TRUE\n'
        'if {[info script] ne {}} {\n    set checked [exec '+tcl_path(PYTHON)+' -B '+tcl_path(SELF)+
        ' --gate '+tcl_path(w)+']\n    puts $checked\n    if {[string first {'+GATE+' '+
        context['FinalADFSHA256']+'} $checked] < 0} {error {Missing exact fisheye pre-bit gate}}\n'
        '    gen_bit_stream -force_to_run -input_db_file '+native_tcl(w/'audited-final.adf')+
        ' -scbv {High Voltage} -unused_io_status UNUSED\n    puts {'+COMPLETE+'}\n    flush stdout\n}\n')


def recipe(request, work, maximum=10800, *, fresh_authority=False):
    work = build.work_path(work)
    require(work.name.startswith('bit-') and type(maximum) is int and 60 <= maximum <= 10800, 'bit-* stage and60..10800s limit required')
    context = audit_request(request, use_cache=not fresh_authority)
    tcl = render(context, work)
    plan = {'Schema': PLAN_SCHEMA, 'Target': TARGET, 'Request': ref(request), 'WorkDirectory': str(work),
            'BuildPlan': ref(context['BuildPlan']), 'PhysicalProof': context['Request']['PhysicalProof'],
            **{kind:context['Request'][kind]for kind in SIMULATIONS},'Profile':context['Request']['Profile'],
            'SimulationLimits':{kind:context['Simulations'][kind].get('Limits',
                'Source RTL simulation only; coverage is limited to the provider checks, and physical implementation is a separate proof.')
                for kind in SIMULATIONS},
            'SimulationEvidenceKind':{'MapperSimulation':'Full-native coordinate RTL and CPU oracle',
                'SystemSimulation':'Two-frame native1080 source RTL in XSim; not post-route netlist simulation',
                'IOSimulation':'Quantizer and UART source RTL with actual pin-waveform decode'},
            'PostRouteGateLevelSimulationClaimed':False,'HardwareFPSMeasured':False,
            'FinalADF': ref(context['FinalADF']), 'FinalADFSHA256': context['FinalADFSHA256'],
            'InputSHA256': context['Watched'], 'MaximumSeconds': maximum, 'ExpectedStages': STAGES,
            'TclSHA256': hashlib.sha256(tcl.encode('ascii')).hexdigest(),
            'Command': [context['Build']['Command'][0], '-file', native_work(work / 'bitstream.tcl'),
                        '-work_dir', native_work(work), '-project_name', TARGET],
            'HardwareAccessed': False, 'BitstreamRequested': True, 'EDAExecutedByPreparer': False,
            'HardwareReleaseAllowed': False, 'ExternalACAccepted': False, 'PixelsVerified': False,
            'SavedAuthority':context['SavedAuthority'],'ClosureWitness':context['ClosureWitness'],
            'FullPhysicalOrSimulationRederived':False,'FirstPassReusedAtUserRequest':True}
    return plan, tcl, context


def prepare(request, work, maximum=10800):
    build.paths.validate_repo_alias(ROOT,'P:/')
    plan, tcl, context = recipe(request, work, maximum)
    work = Path(plan['WorkDirectory'])
    require(not work.exists(), 'fresh bit directory required')
    work.mkdir()
    shutil.copyfile(context['FinalADF'], work / 'audited-final.adf')
    shutil.copyfile(SELF, work / 'tool-fisheye.py')
    (work / 'bitstream.tcl').write_text(tcl, encoding='ascii', newline='\n')
    write(work / 'bitstream-plan.json', plan)
    return plan


def validate(work, *, fresh_authority=False):
    work = build.work_path(work)
    plan = read(work / 'bitstream-plan.json')
    require(plan.get('Schema') == PLAN_SCHEMA and plan.get('Target') == TARGET, 'exact fisheye bit plan required')
    expected, tcl, context = recipe(plan['Request']['Path'], work, plan['MaximumSeconds'],
                                    fresh_authority=fresh_authority)
    require(plan == expected, 'fisheye bit plan differs from full recipe')
    require((work / 'bitstream.tcl').read_bytes() == tcl.encode('ascii')
            and sha(work / 'audited-final.adf') == context['FinalADFSHA256']
            and sha(work / 'tool-fisheye.py') == sha(SELF), 'prepared bit input drift')
    return plan, context


def compare_fresh(context, report, exceptions):
    value = physical_provider().compare_fresh_sta(context['Proof'], Path(report), Path(exceptions))
    require(all(value.get(k) is True for k in ('STAAllTenPassed', 'ClockAndSummaryIdentityPreserved',
                                              'AllExceptionPathsPreserved')), 'fresh physical STA or exceptions differ')
    return value


def gate(work):
    # A cold child binds the saved firstpass SHA witness and unchanged file
    # identities. Fresh native STA and exact exceptions are still checked here.
    plan, context = validate(work, fresh_authority=True)
    work = Path(work)
    require(build.diagnostics(work) == [], 'native critical/error diagnostics before bit')
    before = {name: sha(work / name) for name in ('bitstream-plan.json', 'audited-final.adf', 'bitstream.tcl', REPORT, EXCEPTIONS)}
    checks = compare_fresh(context, work / REPORT, work / EXCEPTIONS)
    require(not drift(plan['InputSHA256']) and before == {n: sha(work / n) for n in before}, 'pre-bit gate evidence drift')
    result = {'Schema': GATE_SCHEMA, 'Target': TARGET, 'GatePassed': True, 'FinalADFSHA256': context['FinalADFSHA256'],
              'CheckedUTC': utc(), 'Checks': checks, 'EvidenceSHA256': before, 'HardwareAccessed': False}
    write(work / 'pre-bit-audit.json', result)
    return result


def actual_events(text, digest):
    rows = []
    for line in text.splitlines():
        line = line.strip()
        match = re.fullmatch(r'Process "([^"]+)" (started|done)\.', line)
        if match:
            rows.append(list(match.groups()))
        elif line.startswith(GATE):
            require(line == GATE + ' ' + digest, 'wrong runtime gate ADF')
            rows.append(['Runtime gate', 'passed'])
        elif line == COMPLETE:
            rows.append(['Bitstream', 'complete'])
    require(rows == [['Report Timing', 'started'], ['Report Timing', 'done'], ['Runtime gate', 'passed'],
                     ['Generate Bitstream', 'started'], ['Generate Bitstream', 'done'], ['Bitstream', 'complete']],
            'fresh STA/gate/generation event order differs')
    return rows


def bit_header(data):
    require(len(data) == EXPECTED_BIT_BYTES, 'exact PG2L100H fisheye diagnostic programming length required')
    prefix = bytes.fromhex('00090ff00ff00ff00ff000') + b'PANGO MICROSYSTEMS, INC.\0\1'
    require(data.startswith(prefix), 'invalid native bit prefix')
    offset, fields = len(prefix), {}
    for tag, name in zip(b'abcdef', ('Design', 'Device', 'Date', 'Time', 'Generator', 'Version')):
        require(offset + 3 <= len(data) and data[offset] == tag, 'missing native bit header field')
        length = int.from_bytes(data[offset + 1:offset + 3], 'big')
        value = data[offset + 3:offset + 3 + length]
        require(length > 0 and len(value) == length and value[-1:] == b'\0' and b'\0' not in value[:-1], 'invalid native header string')
        fields[name] = value[:-1].decode('ascii')
        offset += 3 + length
    require(data[offset:offset + 3] == b'ghi' and len(data) > 1000000, 'truncated native payload')
    for k, v in {'Design': TARGET, 'Device': 'Logos2-PG2L100H--6-FBG676',
                 'Generator': 'Fabric Compiler', 'Version': '2023.2-SP3<154097>'}.items():
        require(fields[k] == v, 'wrong bit identity: ' + k)
    return fields


def verify_generation_evidence(work, text, digest, receipt, gate_proof):
    """Bind actual command/order, native BGR defaults and generation times."""
    work = Path(work)
    expected_command = ('gen_bit_stream -force_to_run -input_db_file ' + native_work(work / 'audited-final.adf')
                        + ' -scbv {High Voltage} -unused_io_status UNUSED')
    launches = [(m.start(), m.group(1).rstrip()) for m in re.finditer(r'(?m)^Executing : (gen_bit_stream .+)$', text)
                if not m.group(1).rstrip().endswith(' successfully.')]
    require(len(launches) == 1 and launches[0][1] == expected_command, 'native bit generation command differs')
    markers = list(re.finditer(r'(?m)^' + re.escape(GATE + ' ' + digest) + r'\s*$', text))
    starts = list(re.finditer(r'(?m)^Process "Generate Bitstream" started\.\s*$', text))
    require(len(markers) == len(starts) == 1 and markers[0].start() < launches[0][0] < starts[0].start(),
            'actual generation command must follow runtime gate and precede native start')
    report = (work / BGR).read_text(encoding='gb18030')
    require('Generating Programming File done.' in report, 'native programming report incomplete')
    flow = re.findall(r'(?m)^Flow Command:\s*(.+?)\s*$', report)
    base_command = ('gen_bit_stream -force_to_run -input_db_file {' +
                    native_work(work / 'audited-final.adf') + '} -scbv {High Voltage}')
    require(flow in ([base_command], [base_command + ' -unused_io_status UNUSED']), 'native BGR flow command differs')
    actual_input = re.findall(r'(?m)^\| Input\s*\|\s*(.*?)\s*$', report)
    require(actual_input == [native_work(work / 'audited-final.adf')], 'native BGR input role differs')
    output = re.findall(r'^The bitstream file is "([^"]+)"\s*$', report, re.M)
    require(output == [native_work(work / BIT)], 'native BGR output role differs')
    script = (work / 'bitstream.tcl').read_text(encoding='ascii')
    emitted = re.findall(r'(?m)^\s*(gen_bit_stream .+)$', script)
    expected_tcl = ('gen_bit_stream -force_to_run -input_db_file {' +
                    native_work(work / 'audited-final.adf') + '} -scbv {High Voltage} -unused_io_status UNUSED')
    require(emitted == [expected_tcl], 'bound Tcl generation controls differ')
    try:
        started, finished, checked = (datetime.fromisoformat(s) for s in
                                    (receipt['StartedUTC'], receipt['FinishedUTC'], gate_proof['CheckedUTC']))
    except (ValueError, TypeError, KeyError) as error:
        raise ValueError('valid execution/gate UTC timestamps required') from error
    require(all(t.tzinfo is not None and t.utcoffset() is not None for t in (started, finished, checked))
            and started <= checked <= finished, 'runtime gate is outside this execution window')
    bit_mtime = (work / BIT).stat().st_mtime
    gate_mtime = (work / 'pre-bit-audit.json').stat().st_mtime
    require(started.timestamp() <= gate_mtime <= bit_mtime <= finished.timestamp(),
            'gate/bit artifact timestamps do not follow this execution')
    return {'ActualGenerationCommand': expected_command, 'ActualCommandAfterGateBeforeNativeStart': True,
            'BGRInputAndOutputRolesVerified': True, 'BGRHighVoltageVerified': True,
            'NativeBGROmittedDefaultUnused': flow == [base_command], 'UnusedIOExplicitInTclAndStdout': True,
            'RuntimeGateWithinExecutionWindow': True, 'BitArtifactNotOlderThanGate': True}


def artifacts(work):
    return {p.relative_to(work).as_posix(): sha(p) for p in Path(work).rglob('*') if p.is_file()
            and p.suffix in ('.log', '.rtr', '.sbit', '.bgr', '.tcl')}


def verify(work):
    plan, context = validate(work)
    work = Path(work)
    receipt_sha = sha(work / 'execution-result.json')
    receipt = read(work / 'execution-result.json')
    require(receipt.get('Schema') == EXEC_SCHEMA and receipt.get('Target') == TARGET
            and receipt.get('PlanSHA256') == sha(work / 'bitstream-plan.json') and receipt.get('ExecutorSHA256') == sha(SELF)
            and receipt.get('Command') == plan['Command'] and receipt.get('FinalADFSHA256') == context['FinalADFSHA256']
            and receipt.get('ExitCode') == 0 and receipt.get('TimedOut') is False and not receipt.get('Error')
            and receipt.get('EDAExecuted') is True and receipt.get('HardwareAccessed') is False
            and receipt.get('StoppedForUnexpectedStage') is False and receipt.get('InputDrift') == []
            and receipt.get('Diagnostics') == [] and receipt.get('Cleanup', {}).get('Complete') is True,
            'unclean native fisheye bit execution')
    expected = artifacts(work)
    require(receipt['Artifacts'] == expected and {'stdout.log', 'stderr.log', REPORT, EXCEPTIONS, BIT, BGR, 'bitstream.tcl'} <= set(expected),
            'native bit artifact inventory differs')
    require(build.diagnostics(work) == [], 'native bit diagnostic failure')
    text = (work / 'stdout.log').read_text(encoding='gb18030', errors='replace')
    events = actual_events(text, context['FinalADFSHA256'])
    checks = compare_fresh(context, work / REPORT, work / EXCEPTIONS)
    proof = read(work / 'pre-bit-audit.json')
    gate_sha = sha(work / 'pre-bit-audit.json')
    generation = verify_generation_evidence(work, text, context['FinalADFSHA256'], receipt, proof)
    evidence = {n: sha(work / n) for n in ('bitstream-plan.json', 'audited-final.adf', 'bitstream.tcl', REPORT, EXCEPTIONS)}
    require(proof.get('Schema') == GATE_SCHEMA and proof.get('Target') == TARGET and proof.get('GatePassed') is True
            and proof.get('FinalADFSHA256') == context['FinalADFSHA256'] and proof['Checks'] == checks
            and proof['EvidenceSHA256'] == evidence, 'actual runtime gate differs')
    data = (work / BIT).read_bytes()
    header = bit_header(data)
    require(not drift(plan['InputSHA256']) and artifacts(work) == expected
            and sha(work / 'execution-result.json') == receipt_sha
            and sha(work / 'pre-bit-audit.json') == gate_sha, 'bit verification input/artifact drift')
    return {'Schema': 'hdmi-camera-fisheye-assoc2way256fastpipev4-bitstream-verification-v1', 'Verified': True, 'Target': TARGET,
            'FinalADFSHA256': context['FinalADFSHA256'], 'Bitstream': {**ref(work / BIT), 'Bytes': len(data), 'Header': header},
            'FreshSTA': checks, 'ActualEvents': events, 'GenerationEvidence': generation, 'CheckedUTC': utc(),
            'EvidenceSHA256': {n: sha(work / n) for n in ('bitstream-plan.json', 'audited-final.adf', 'tool-fisheye.py',
                'execution-result.json', 'pre-bit-audit.json', *sorted(expected))},
            'HardwareAccessed': False, 'ExternalACAccepted': False, 'PixelsVerified': False, 'HardwareReleaseAllowed': False}


def execute(work):
    plan, context = validate(work)
    work = Path(work)
    build.paths.validate_repo_alias(ROOT,'P:/')
    require(os.name == 'nt' and {p.name for p in work.iterdir()} ==
            {'bitstream-plan.json', 'bitstream.tcl', 'audited-final.adf', 'tool-fisheye.py'}, 'fresh Windows bit stage required')
    watched = {**plan['InputSHA256'], **{str(p): sha(p) for p in work.iterdir()}}
    value = {'Schema': EXEC_SCHEMA, 'Target': TARGET, 'PlanSHA256': sha(work / 'bitstream-plan.json'),
             'ExecutorSHA256': sha(SELF), 'Command': plan['Command'], 'FinalADFSHA256': context['FinalADFSHA256'],
             'StartedUTC': utc(), 'EDAExecuted': False, 'HardwareAccessed': False, 'ExitCode': None,
             'TimedOut': False, 'StoppedForUnexpectedStage': False}
    write(work / 'execution-claim.json', value)
    process, start = None, time.monotonic()
    try:
        with (work / 'stdout.log').open('xb') as out, (work / 'stderr.log').open('xb') as err:
            process = subprocess.Popen(plan['Command'], cwd=work, stdout=out, stderr=err, shell=False,
                                       creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            value.update(EDAExecuted=True, OwnedPID=process.pid)
            expected = [[s, e] for s in STAGES for e in ('started', 'done')]
            while process.poll() is None:
                left = plan['MaximumSeconds'] - (time.monotonic() - start)
                if left <= 0:
                    value['TimedOut'] = True
                    break
                try:
                    process.wait(timeout=min(3, left))
                except subprocess.TimeoutExpired:
                    pass
                current = build.events((work / 'stdout.log').read_text(encoding='gb18030', errors='replace'))
                if current != expected[:len(current)]:
                    value['StoppedForUnexpectedStage'] = True
                    break
    except BaseException as error:
        value['Error'] = type(error).__name__ + ': ' + str(error)
    finally:
        if process is not None and process.poll() is None:
            value['Cleanup'] = build.cleanup.stop_owned_tree(process, work, 'bounded fisheye bit generation')
        else:
            value['Cleanup'] = {'Complete': True, 'ParentExited': process is not None}
        value.update(ExitCode=process.poll() if process is not None else None, FinishedUTC=utc(),
                     ElapsedSeconds=round(time.monotonic() - start, 3), InputDrift=drift(watched),
                     Diagnostics=build.diagnostics(work), Artifacts=artifacts(work))
        write(work / 'execution-result.json', value)
    checked = verify(work)
    write(work / 'verification.json', checked)
    return checked


def main():
    p = argparse.ArgumentParser(description=__doc__)
    mode = p.add_mutually_exclusive_group(required=True)
    for name in ('prepare', 'validate', 'execute', 'verify', 'gate', 'audit-request'):
        mode.add_argument('--' + name, type=Path)
    p.add_argument('--request', type=Path)
    p.add_argument('--maximum-seconds', type=int, default=10800)
    a = p.parse_args()
    if a.audit_request:
        c = audit_request(a.audit_request)
        print(json.dumps({'AuthorityPassed': True, 'FinalADFSHA256': c['FinalADFSHA256'], 'Inputs': len(c['Watched']), 'HardwareAccessed': False}))
    elif a.prepare:
        require(a.request is not None, '--prepare requires --request')
        value = prepare(a.request, a.prepare, a.maximum_seconds)
        print(json.dumps({'Prepared': True, 'Plan': str(Path(value['WorkDirectory']) / 'bitstream-plan.json')}))
    elif a.validate:
        validate(a.validate)
        print('{"Validated":true,"HardwareAccessed":false}')
    elif a.gate:
        value = gate(a.gate)
        print(GATE + ' ' + value['FinalADFSHA256'])
    else:
        print(json.dumps(execute(a.execute) if a.execute else verify(a.verify)))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
