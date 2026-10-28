"""Exact offline CAM1 trial: sink the other connector reset after configuration."""
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
TARGET = 'raw_camera_capture_cam1_guarded_isolated'
BUILD_TAG = 0x52473149
CAMERA_ID = 0x43414D31
CAMERA_SLOT = 1
BASE_PREPARED_SHA256 = '1be75999ef7225e41824fdc32b54faaada69a219b982ff4a2ed1dd3379645bb8'
BASE_BUILD = APPROVED/'cam1-guarded-board-20261025-183856-600/validated-build.json'
BASE_BUILD_SHA256 = 'd541e2e425865c53b0c45bf25cc6977e4d792d0a8b3b375b8dfa6403cfc745a8'
RESET_REFERENCES = {
    'board/raw_camera_capture_cam2_guarded-pins.json': '7d4d158411d319fc7a5b6b4e9262deef414ad353a441608c08eae5bd9798bd98',
    'board/raw_camera_capture_cam2_guarded.fdc': '016c5f4b44bfa6edd2ee0490632c8572e2165abdb9ec8a0c18960b08cd04a52b',
    'board/corrected_gamma_d5-pins.json': '63e059c7126fbcf07fbb61e10a77981ab04cb350077a82c5151a8b4ae3c6e7a4',
    'build/offline-20261024/raw-guarded-board-20261025-183203-296/place_route/raw_camera_capture_cam2_guarded_prr.prt': 'b233d4f571944432b4445265f9fd827a53e027823419e39f7a146067fc7e5b25',
}
OTHER_SENSOR_RESET_TRIAL_CONTRACT = {
    'controlled_connector_slot': 'CAM2', 'port': 'cam2_hold_rst_n', 'pad': 'Y20',
    'direction': 'inout', 'drive_policy': 'constant_zero_sink_only',
    'drives_high': False, 'released_during_configured_run': False,
    'scope': 'configured_FPGA_runtime_only',
    'before_configuration_and_after_heartbeat_hold_guaranteed': False,
    'reference_reset_port': 'cam_rst_n',
    'reference_source_sha256': dict(RESET_REFERENCES),
    'active_camera_connector_slot': 'CAM1', 'active_camera_quarter_cycles': 68,
    'active_camera_pad_mask': '0x7FF0',
    'active_camera_initialization_and_readbacks_unchanged': True,
    'physical_reset_independence_verified': False,
    'other_sensor_inactivity_verified': False,
    'hardware_fix_or_cause_established': False,
}
sha = inherited.sha
load = inherited.load
OWN = [f'board/{ORIGINAL}.v', f'board/{ORIGINAL}.fdc',
       f'board/{ORIGINAL}-pins.json', f'board/build-{ORIGINAL}.tcl']
HOLD_ASSIGNMENT = b"    assign cam2_hold_rst_n=1'b0;\r\n"


def clone_top(data):
    pairs = [(b'module '+ORIGINAL.encode()+b'(', b'module '+TARGET.encode()+b'('),
             (b"GUARDED_BUILD_TAG=32'h52473101", b"GUARDED_BUILD_TAG=32'h52473149"),
             (b'inout cam_rst_n,cam_scl,cam_sda, inout hd_scl,hd_sda,',
              b'inout cam_rst_n,cam_scl,cam_sda,cam2_hold_rst_n, inout hd_scl,hd_sda,'),
             (b'    // Connector slot only; no physical left/right or stereo-sync claim.\r\n',
              HOLD_ASSIGNMENT+b'    // Connector slot only; no physical left/right or stereo-sync claim.\r\n')]
    for old, new in pairs:
        if data.count(old) != 1:
            raise ValueError('CAM1 exact module/tag/reset-port/assignment anchor differs')
        data = data.replace(old, new, 1)
    if (data.count(b'cam2_hold_rst_n') != 2 or data.count(HOLD_ASSIGNMENT) != 1 or
            data.count(b'ov5640_cadence_trial_init #(.DYNAMIC_PAD_MASK(1))') != 1 or
            data.count(b".trial_pad_mask(16'h7ff0)") != 1 or b'I2C_QUARTER_CYCLES' in data):
        raise ValueError('constant sink or unchanged default68/full7FF0 init differs')
    return data


def reset_attributes():
    for name, digest in RESET_REFERENCES.items():
        if sha(ROOT/name) != digest:
            raise ValueError('sealed CAM2 reset reference changed: '+name)
    for name in ('board/raw_camera_capture_cam2_guarded-pins.json','board/corrected_gamma_d5-pins.json'):
        if load(ROOT/name).get('cam_rst_n') != 'Y20':
            raise ValueError('CAM2 reset reference pad differs')
    fdc = (ROOT/'board/raw_camera_capture_cam2_guarded.fdc').read_bytes()
    lines = [line for line in fdc.splitlines(keepends=True) if b'{p:cam_rst_n}' in line]
    expected = [('PAP_IO_LOC','Y20'),('PAP_IO_VCCIO','3.3'),('PAP_IO_STANDARD','LVCMOS33'),
                ('PAP_IO_DRIVE','4'),('PAP_IO_SLEW','SLOW')]
    if len(lines) != 5 or [line.strip() for line in lines] != [
            ('define_attribute {p:cam_rst_n} {'+key+'} {'+value+'}').encode() for key,value in expected]:
        raise ValueError('CAM2 reset exact electrical attributes differ')
    routed = (ROOT/next(name for name in RESET_REFERENCES if name.endswith('.prt'))).read_text()
    rows = [line.split('|') for line in routed.splitlines() if '|cam_rst_n|' in line]
    if len(rows)!=1 or rows[0][0]!='Y20' or rows[0][5:7]!=['inout','YES']:
        raise ValueError('verified CAM2 routed reset reference differs')
    return b''.join(lines).replace(b'{p:cam_rst_n}',b'{p:cam2_hold_rst_n}')


def board_stubs(top):
    """Inert vendor DDR/PLL/ADC models; actual complete board top is elaborated."""
    text=top.decode(); blocks=[]
    for module, instance in [('GTP_INBUFGDS','u_gtp'),('ddr3_test','u_ddr3_test_h'),('bringup_pll','video_pll')]:
        match=re.search(r'\b'+module+r'\b(.*?)\b'+instance+r'\s*\((.*?)\);',text,re.S)
        if not match: raise ValueError('board peripheral stub anchor differs: '+module)
        params=re.findall(r'\.(\w+)\s*\(',match.group(1))
        ports=list(dict.fromkeys(re.findall(r'\.(\w+)\s*\(',re.sub(r'//[^\n]*','',match.group(2)))))
        parameter=' #('+','.join('parameter '+name+'=0' for name in params)+')' if params else ''
        blocks.append('module '+module+parameter+'('+','.join('input wire [255:0] '+name for name in ports)+'); endmodule')
    adc=(ROOT/'rtl/logos2_temperature_monitor.v').read_text()
    params=list(dict.fromkeys(re.findall(r'\.(CREG_\w+)\(',adc)))
    ports=['VA','VAUX','DCLK','RST_N','DEN','SECEN','DWE','DADDR','DI','CONVST','LOADSC_N','DO','DRDY','LOGIC_DONE_A','LOGIC_DONE_B','ADC_CLK_OUT','DMODIFIED','OVER_TEMP','ALARM']
    blocks.append('module GTP_ADC_E2 #('+','.join('parameter '+name+'=0' for name in params)+')('+','.join('input wire [255:0] '+name for name in ports)+'); endmodule')
    return ('// TEST ONLY. Inert vendor blocks deliberately do not model DDR/PLL/ADC behavior.\n'
            '// Real board top, camera init, reset sink and all shared digital RTL are compiled.\n'
            '// These input-only stubs create no drivers; only camera/reset lifecycle is asserted.\n'+'\n'.join(blocks)+'\n').encode()


def expected_files():
    parent = inherited.verify_clone()
    if sha(ROOT/f'board/{ORIGINAL}-sources.json')!=BASE_PREPARED_SHA256 or sha(BASE_BUILD)!=BASE_BUILD_SHA256:
        raise ValueError('sealed CAM1 prepared/validated artifact differs')
    build = load(BASE_BUILD)
    if (build.get('Target')!=ORIGINAL or build.get('ProcessExitCode')!=0 or
            build.get('HardwareAccessed') is not False or build.get('SourceSHA256')!=parent['SourceSHA256']):
        raise ValueError('validated CAM1 source binding differs')
    for path_key,hash_key in [('Bitstream','SHA256'),('TimingReport','TimingSHA256'),('PinReport','PinReportSHA256')]:
        if sha(Path(build[path_key])).upper()!=build[hash_key].upper():
            raise ValueError('sealed CAM1 final artifact changed: '+path_key)
    if not Path(build['TimingReport']).read_text().startswith('Design Summary : All Constraints Met.'):
        raise ValueError('CAM1 parent final timing is not accepted')
    sources = parent['source_files']
    if len(sources)!=107 or set(sources)!=set(parent['SourceSHA256']):
        raise ValueError('parent CAM1 exact107 source closure differs')
    old_pins = load(ROOT/f'board/{ORIGINAL}-pins.json')
    if len(old_pins)!=129 or len(set(old_pins.values()))!=129 or 'Y20' in old_pins.values():
        raise ValueError('parent129 map collides with reviewed Y20 reset')
    attributes = reset_attributes()
    files = {}
    for name in OWN:
        data = (ROOT/name).read_bytes()
        if name.endswith('.v'):
            data = clone_top(data)
        elif name.endswith('.fdc'):
            data += b'\r\n'+attributes
        elif name.endswith('-pins.json'):
            pins = dict(old_pins); pins['cam2_hold_rst_n']='Y20'
            data = (json.dumps(pins,indent=2)+'\n').encode()
        else:
            if data.count(ORIGINAL.encode())!=3:
                raise ValueError('CAM1 Tcl must have exactly top/FDC/compile target sites')
            data = data.replace(ORIGINAL.encode(),TARGET.encode())
        files[name.replace(ORIGINAL,TARGET)] = data
    new_sources = [name.replace(ORIGINAL,TARGET) if name in OWN else name for name in sources]
    shared = {name:parent['SourceSHA256'][name] for name in sources if name not in OWN}
    if len(shared)!=103:
        raise ValueError('isolation trial must inherit exactly103 unchanged sources')
    manifest = copy.deepcopy(parent)
    manifest.update(target=TARGET,source_files=new_sources,
        SourceSHA256={name:hashlib.sha256(files[name]).hexdigest().upper() if name in files else shared[name] for name in new_sources},
        OtherSensorResetTrialContract=copy.deepcopy(OTHER_SENSOR_RESET_TRIAL_CONTRACT))
    manifest['GuardedControlContract']['build_tag']=BUILD_TAG
    manifest['OtherSensorResetTrialVerification']={'OriginalTarget':ORIGINAL,
        'OriginalPreparedManifestSHA256':BASE_PREPARED_SHA256.upper(),
        'OriginalValidatedBuild':str(BASE_BUILD),'OriginalValidatedBuildSHA256':BASE_BUILD_SHA256.upper(),
        'UnchangedSharedDependencyCount':103,'SharedSourceSHA256':shared,
        'Original129PinsUnchanged':True,'NewPort':'cam2_hold_rst_n','NewPad':'Y20','ActivePinCount':130,
        'PhysicalEye':None,'PhysicalResetIndependenceVerified':False}
    manifest['limits']='Offline FPGA-side other-connector reset sink trial only. Default68/full7FF0/PLL/init/readbacks and original129 pins unchanged. Sink low only after configuration, not before configuration or after heartbeat replacement. The module/cable reset independence and actual other-sensor inactivity are unmeasured. No cause, hardware fix, physical-eye, stereo, optics, thermal or unattended acceptance.'
    files[f'board/{TARGET}-sources.json']=(json.dumps(manifest,indent=2)+'\n').encode()
    files['tests/cam1_isolated_board_stubs.v']=board_stubs(files[f'board/{TARGET}.v'])
    data = (ROOT/'tests/tb_guarded_cam1_pipeline.sv').read_bytes()
    for old,new in [(b'tb_guarded_cam1_pipeline',b'tb_guarded_cam1_isolated_pipeline'),
                    (b"32'h52473101",b"32'h52473149"),
                    (b'guarded-cam1-mixed-stream.bin',b'guarded-cam1-isolated-mixed-stream.bin')]:
        if data.count(old)<1: raise ValueError('inherited CAM1 pipeline anchor differs')
        data=data.replace(old,new)
    files['tests/tb_guarded_cam1_isolated_pipeline.sv']=data
    return files,manifest


def prepare():
    files,manifest = expected_files()
    for name,data in files.items():
        if (ROOT/name).exists() and (ROOT/name).read_bytes()!=data:
            raise ValueError('refusing to overwrite differing reset trial candidate: '+name)
    for name,data in files.items():
        if not (ROOT/name).exists():
            with (ROOT/name).open('xb') as stream:stream.write(data)
    return verify_clone()


def verify_clone():
    files,manifest = expected_files()
    for name,data in files.items():
        if (ROOT/name).read_bytes()!=data:
            raise ValueError('reset trial differs beyond exact identity/new constant sink130pins: '+name)
    return manifest


def validate_simulation(path):
    manifest=verify_clone();path=Path(path).resolve()
    if not path.is_relative_to(APPROVED.resolve()):raise ValueError('isolation simulation must be below approved scratch')
    sim=load(path)
    if (sim.get('Passed') is not True or sim.get('HardwareAccessed') is not False or sim.get('Target')!=TARGET or
            sim.get('OtherSensorResetTrialContract')!=OTHER_SENSOR_RESET_TRIAL_CONTRACT or
            sim.get('PreparedSourceManifestSHA256','').lower()!=sha(ROOT/f'board/{TARGET}-sources.json') or
            sim.get('MeasuredConsecutiveBitPeriodCoreCycles')!=274 or
            sim.get('RegressionTops')!=['tb_cam1_isolated_init','tb_guarded_cam1_isolated_pipeline']):
        raise ValueError('fresh constant-sink lifecycle/default68 bus plus pipeline simulation required')
    required={'rtl/reg16_i2c.v','rtl/experimental/ov5640_cadence_trial_init.v','board/ov5640_cadence_trial_commands.vh',
        'tests/tb_cam1_isolated_init.sv','tests/cam1_isolated_board_stubs.v','tests/tb_guarded_cam1_isolated_pipeline.sv',
        f'board/{TARGET}.v','tools/run-guarded-cam1-isolated-sim.ps1'}
    hashes={name.replace('\\','/'):digest for name,digest in sim.get('SourceSHA256',{}).items()}
    if not required.issubset(hashes):raise ValueError('reset trial simulation omitted source/bench binding')
    for name,digest in hashes.items():
        if sha(inherited._inside(name)).upper()!=digest.upper():raise ValueError('reset trial simulation source changed: '+name)
    for name,digest in sim['LogSHA256'].items():
        log=path.parent/name
        if log.parent!=path.parent or sha(log).upper()!=digest.upper():raise ValueError('reset trial simulation log changed')
    wire=Path(sim['MixedStream']).resolve()
    if wire.parent!=path.parent or sha(wire).upper()!=sim['MixedStreamSHA256'].upper():
        raise ValueError('reset trial mixed stream changed/escaped')
    return sim


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--stage',action='store_true');args=parser.parse_args()
    manifest=prepare() if args.stage else verify_clone()
    print(json.dumps({'target':TARGET,'source_files':len(manifest['source_files']),'active_pins':130,
        'hardware_accessed':False,'other_sensor_reset_trial_contract':OTHER_SENSOR_RESET_TRIAL_CONTRACT}))


if __name__=='__main__':main()
