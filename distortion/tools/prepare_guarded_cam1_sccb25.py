"""Exact offline single-parameter CAM1 SCCB speed trial; never hardware."""
from pathlib import Path
import argparse
import copy
import hashlib
import json
import re
import prepare_guarded_cam1 as inherited

ROOT = inherited.ROOT
APPROVED = inherited.APPROVED
ORIGINAL = inherited.TARGET
TARGET = 'raw_camera_capture_cam1_guarded_sccb25'
BUILD_TAG = 0x52473125
CAMERA_ID = 0x43414D31
CAMERA_SLOT = 1
BASE_PREPARED_SHA256 = '1be75999ef7225e41824fdc32b54faaada69a219b982ff4a2ed1dd3379645bb8'
BASE_BUILD = APPROVED/'cam1-guarded-board-20261025-183856-600/validated-build.json'
BASE_BUILD_SHA256 = 'd541e2e425865c53b0c45bf25cc6977e4d792d0a8b3b375b8dfa6403cfc745a8'
SCCB_TRIAL_CONTRACT = {
    'parameter': 'I2C_QUARTER_CYCLES', 'quarter_cycles': 270,
    'reference_quarter_cycles': 68, 'input_clock_hz': 27000000,
    'nominal_scl_hz': 25000, 'nominal_frequency_only': True,
    'pad_mask': '0x7FF0', 'timeout_cycles': 1350000,
    'initialization_and_readback_policy_unchanged': True,
    'hardware_acceptance_inferred_from_parameter': False,
}
sha = inherited.sha
load = inherited.load
OWN = [f'board/{ORIGINAL}.v', f'board/{ORIGINAL}.fdc',
       f'board/{ORIGINAL}-pins.json', f'board/build-{ORIGINAL}.tcl']


def clone_top(data):
    pairs = [(b'module '+ORIGINAL.encode()+b'(', b'module '+TARGET.encode()+b'('),
             (b"GUARDED_BUILD_TAG=32'h52473101", b"GUARDED_BUILD_TAG=32'h52473125"),
             (b'ov5640_cadence_trial_init #(.DYNAMIC_PAD_MASK(1))',
              b'ov5640_cadence_trial_init #(.DYNAMIC_PAD_MASK(1),.I2C_QUARTER_CYCLES(270))')]
    for old, new in pairs:
        if data.count(old) != 1:
            raise ValueError('CAM1 exact module/tag/SCCB parameter anchor differs')
        data = data.replace(old, new, 1)
    if (data.count(b'.I2C_QUARTER_CYCLES(270)') != 1 or
            data.count(b".trial_pad_mask(16'h7ff0)") != 1):
        raise ValueError('SCCB quarter or complete 7FF0 pad mask differs')
    return data


def expected_files():
    parent = inherited.verify_clone()
    parent_path = ROOT/f'board/{ORIGINAL}-sources.json'
    if sha(parent_path) != BASE_PREPARED_SHA256 or sha(BASE_BUILD) != BASE_BUILD_SHA256:
        raise ValueError('sealed CAM1 prepared/validated artifact differs')
    build = load(BASE_BUILD)
    if (build.get('Target') != ORIGINAL or build.get('ProcessExitCode') != 0 or
            build.get('HardwareAccessed') is not False or build.get('SourceSHA256') != parent['SourceSHA256']):
        raise ValueError('validated CAM1 source binding differs')
    for path_key, hash_key in [('Bitstream','SHA256'),('TimingReport','TimingSHA256'),('PinReport','PinReportSHA256')]:
        if sha(Path(build[path_key])).upper() != build[hash_key].upper():
            raise ValueError('sealed CAM1 final artifact changed: '+path_key)
    if not Path(build['TimingReport']).read_text(encoding='utf-8').startswith('Design Summary : All Constraints Met.'):
        raise ValueError('CAM1 parent final timing is not accepted')
    sources = parent['source_files']
    if len(sources) != 107 or set(sources) != set(parent['SourceSHA256']):
        raise ValueError('parent CAM1 source107 closure differs')
    files = {}
    for name in OWN:
        data = (ROOT/name).read_bytes()
        if name.endswith('.v'):
            data = clone_top(data)
        elif name.endswith('.tcl'):
            # Exact target paths/module change; every compile/route option stays.
            if data.count(ORIGINAL.encode()) != 3:
                raise ValueError('CAM1 Tcl must have exactly top/FDC/compile target sites')
            data = data.replace(ORIGINAL.encode(), TARGET.encode())
        files[name.replace(ORIGINAL,TARGET)] = data
    new_sources = [name.replace(ORIGINAL,TARGET) if name in OWN else name for name in sources]
    shared = {name:parent['SourceSHA256'][name] for name in sources if name not in OWN}
    if len(shared) != 103:
        raise ValueError('SCCB trial must inherit exactly103 unchanged dependencies')
    manifest = copy.deepcopy(parent)
    manifest.update(target=TARGET, source_files=new_sources,
        SourceSHA256={name:hashlib.sha256(files[name]).hexdigest().upper() if name in files else shared[name]
                      for name in new_sources}, SCCBTrialContract=copy.deepcopy(SCCB_TRIAL_CONTRACT))
    manifest['GuardedControlContract']['build_tag']=BUILD_TAG
    manifest['SCCBSpeedTrialVerification']={'OriginalTarget':ORIGINAL,
        'OriginalPreparedManifestSHA256':BASE_PREPARED_SHA256.upper(),
        'OriginalValidatedBuild':str(BASE_BUILD),'OriginalValidatedBuildSHA256':BASE_BUILD_SHA256.upper(),
        'UnchangedSharedDependencyCount':103,'SharedSourceSHA256':shared,
        'ChangedSourceParameterOnly':'camera.I2C_QUARTER_CYCLES=270',
        'PhysicalEye':None,'CauseOfPrevious3018NackEstablished':False}
    manifest['limits']='Offline single-parameter SCCB speed trial. Complete7FF0 mask, PLL, initialization and all readbacks remain. CAM1 is a connector slot. A nominal25kHz parameter is not a measured bus frequency, a diagnosis or a verified hardware fix. No physical-eye, stereo, optics or unattended acceptance.'
    files[f'board/{TARGET}-sources.json']=(json.dumps(manifest,indent=2)+'\n').encode('utf-8')
    return files, manifest


def prepare():
    files, manifest = expected_files()
    for name, data in files.items():
        path=ROOT/name
        if path.exists() and path.read_bytes()!=data:
            raise ValueError('refusing to overwrite differing SCCB trial candidate: '+name)
    for name, data in files.items():
        path=ROOT/name
        if not path.exists():
            with path.open('xb') as stream:stream.write(data)
    return verify_clone()


def verify_clone():
    files, manifest = expected_files()
    for name, data in files.items():
        if (ROOT/name).read_bytes()!=data:
            raise ValueError('SCCB trial differs beyond exact target/tag/270 parameter: '+name)
    return manifest


def validate_simulation(path):
    manifest=verify_clone();path=Path(path).resolve()
    if not path.is_relative_to(APPROVED.resolve()):
        raise ValueError('SCCB simulation must be below approved scratch')
    sim=load(path)
    if (sim.get('Passed') is not True or sim.get('HardwareAccessed') is not False or
            sim.get('Target')!=TARGET or sim.get('SCCBTrialContract')!=SCCB_TRIAL_CONTRACT or
            sim.get('PreparedSourceManifestSHA256','').lower()!=sha(ROOT/f'board/{TARGET}-sources.json') or
            sim.get('MeasuredConsecutiveBitPeriodCoreCycles')!=1082 or
            sim.get('RegressionTops')!=['tb_cam1_sccb25_init','tb_guarded_cam1_sccb25_pipeline']):
        raise ValueError('fresh SCCB270 bus and parameterized pipeline simulation required')
    required={'rtl/reg16_i2c.v','rtl/experimental/ov5640_cadence_trial_init.v','board/ov5640_cadence_trial_commands.vh',
        'tests/tb_cam1_sccb25_init.sv','tests/tb_guarded_cam1_sccb25_pipeline.sv',f'board/{TARGET}.v',
        'tools/run-guarded-cam1-sccb25-sim.ps1'}
    hashes={name.replace('\\','/'):digest for name,digest in sim.get('SourceSHA256',{}).items()}
    if not required.issubset(hashes):raise ValueError('SCCB simulation omitted required source/bench binding')
    for name,digest in hashes.items():
        if sha(inherited._inside(name)).upper()!=digest.upper():raise ValueError('SCCB simulation source changed: '+name)
    for name,digest in sim['LogSHA256'].items():
        log=path.parent/name
        if log.parent!=path.parent or sha(log).upper()!=digest.upper():raise ValueError('SCCB simulation log changed')
    return sim


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--stage',action='store_true');args=parser.parse_args()
    manifest=prepare() if args.stage else verify_clone()
    print(json.dumps({'target':TARGET,'source_files':len(manifest['source_files']),
        'hardware_accessed':False,'sccb_trial_contract':SCCB_TRIAL_CONTRACT}))


if __name__=='__main__':main()
