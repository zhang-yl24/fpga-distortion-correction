"""Combine schematic mapping, old bit loss, and isolated physical correction."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,hashlib,json,importlib.util
ROOT=Path(__file__).resolve().parents[1]
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest().upper()
spec=importlib.util.spec_from_file_location('bits',ROOT/'tools/check-dvp-bitplanes.py')
bits=importlib.util.module_from_spec(spec);spec.loader.exec_module(bits)
def main():
    p=argparse.ArgumentParser();p.add_argument('--pattern',type=Path);p.add_argument('--optical',type=Path);p.add_argument('--video',type=Path);a=p.parse_args()
    lab=ROOT/'results/lab-20261008'
    result={'recorded_utc':datetime.now(timezone.utc).isoformat(),'hardware_accessed_by_recorder':False,
        'proven_mapping_error':{'camera_module_net':'CAM2_D5/MCP','camera_J17_pin':29,'FMC_J2_pin':29,'FPGA_pad':'AA23',
            'old_FPGA_pad':'AA22','old_connector_pin':30,'old_pin_not_connected_on_camera_module':True,
            'sensor_output_enable':'OV5640 D7, 0x3017 bit1; prior physical readback 0x7F enables it'},
        'mapping_sources':[{'path':str(lab/'d5-schematic/source-camera.pdf'),'sha256':sha(lab/'d5-schematic/source-camera.pdf'),'page_1_based':1},
            {'path':str(lab/'d5-schematic/source-fmc.pdf'),'sha256':sha(lab/'d5-schematic/source-fmc.pdf'),'page_1_based':8}],
        'old_data_audit':read(lab/'d5-bitplane-before.json'),
        'physical_restoration_passed':False,'corrected_candidate_builds':{},
        'limits':'Earlier captures and calibration retain the actual received pixels and numerical implementation evidence, but the dropped D5 bit disqualifies their camera color fidelity. Confirm corrected visual behavior and reacquire optical/calibration acceptance data; no retrospective reconstruction of the missing bit.'}
    for target in ('gamma_capture_colorbars_d5','gamma_capture_settled_d5','corrected_gamma_d5'):
        path=ROOT/'build'/target/'validated-build.json'
        if not path.exists():continue
        build=read(path)
        if sha(Path(build['Bitstream']))!=build['SHA256']:raise ValueError('D5 corrected bitstream changed')
        for name,digest in build['SourceSHA256'].items():
            if sha(ROOT/name)!=digest:raise ValueError('D5 corrected source changed')
        if read(ROOT/f'board/{target}-pins.json')['cam_data[5]']!='AA23':raise ValueError('D5 corrected target has wrong pins')
        result['corrected_candidate_builds'][target]={'bitstream_sha256':build['SHA256'],'timing_sha256':build['TimingSHA256'],'timestamp':build['Timestamp']}
    for name,folder in (('pattern',a.pattern),('optical',a.optical)):
        if not folder:continue
        folder=folder.resolve();summary=read(folder/'summary.json')
        if not summary['passed'] or not summary['idle_transfer']['Done'] or summary['idle_transfer']['Target']!='heartbeat':raise ValueError('D5 finite capture incomplete')
        audit=bits.analyze(next(folder.glob('group*/raw.npy')))
        result[name]={'folder':str(folder),'summary_sha256':sha(folder/'summary.json'),'capture_transfer':summary['capture_transfer'],
            'idle_transfer':summary['idle_transfer'],'raw_bitplane_check':audit}
        if name=='pattern':
            if summary['target']!='gamma_capture_colorbars_d5' or summary['input_origin']!='sensor_internal_test_pattern':raise ValueError('Not a corrected sensor pattern')
            result['physical_restoration_passed']=(audit['white_roi']['all_white_FFFF_fraction']>.99
                and audit['one_counts_by_rgb565_bit'][5]>10000 and audit['one_counts_by_rgb565_bit'][13]>10000)
            if (folder/'sensor-colorbars-check.json').exists():result[name]['palette_check']=read(folder/'sensor-colorbars-check.json')
    if a.video:
        video=read(a.video)
        if not video['passed'] or video['canonical_result_angles_deg']!=list(range(0,360,30)):
            raise ValueError('Incomplete corrected video coverage')
        if video['capture_transfer']['SHA256']!=result['corrected_candidate_builds']['corrected_gamma_d5']['bitstream_sha256']:
            raise ValueError('Video transfer not bound to corrected build')
        for name,digest in video['source_sha256'].items():
            if sha(ROOT/name)!=digest:raise ValueError('Video checker changed')
        result['corrected_gamma_video']={'path':str(a.video.resolve()),'sha256':sha(a.video),'telemetry_acceptance':read(a.video),
            'visual_observation_available':False}
    status=read(ROOT/'status.json');result['current_sram_target']=status['current_sram_target'];result['current_connection_checked_on']=status['current_connection']['checked_on']
    result['tools_sha256']={n:sha(ROOT/n) for n in ('tools/record-d5-correction.py','tools/check-dvp-bitplanes.py','tools/prepare-d5-fixed-candidates.py','tests/test_d5_candidate_guard.py')}
    (lab/'d5-correction.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'mapping_error_confirmed':True,'physical_restoration_passed':result['physical_restoration_passed'],'corrected_builds':len(result['corrected_candidate_builds'])}))
if __name__=='__main__':main()
