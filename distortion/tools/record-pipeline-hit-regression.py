"""Bind completed isolated hit-pipeline runs to the actual unchanged sources."""
from pathlib import Path
import csv
import hashlib
import json
import re
import shutil

root=Path(__file__).resolve().parents[1]
lab=root/'results/lab-20261007'
checks={'native':'PASS pipeline hit native regression: 1843200',
        'query':'PASS pipeline hit composed rotation',
        'video':'PASS pipeline hit DDR video:', 'stream':'PASS pipeline hit stream:'}
common=['bilinear_rgb','ddr_remap_sample','mul32_pipe','pixel_inverse_rotation',
        'bounded_brown_inverse_mapper','rotated_remap_core']
source_hashes={}
log_hashes={}
for kind,marker in checks.items():
    folder=root/f'build/pipeline_hit_{kind}_sim'
    log=folder/'simulation.log'
    text=log.read_text();assert marker in text and not re.search(r'(?im)fatal:|error:',text),kind
    experimental=['ddr_pipeline_hit_cache','ddr_pipeline_serial_cache']
    ordinary=[] if kind=='stream' else common.copy()
    if kind in ('native','video'):experimental+=['pipeline_hit_frame_engine','ddr_adaptive_result_writer']
    if kind=='video':
        ordinary+=['dvp_rgb565_capture','video_async_fifo','ddr_video_writer','ddr_video_reader',
                   'ddr_video_output','ddr_read_arbiter','ddr_write_arbiter']
        experimental+=['rgb565_burst_pack_early','camera_live_bridge_early','ddr_pipeline_hit_video']
    tb={'native':'tb_pipeline_hit_native_regression.sv','query':'tb_pipeline_hit_query.sv',
        'video':'tb_ddr_pipeline_hit_video.sv','stream':'tb_pipeline_hit_stream.sv'}[kind]
    paths=[root/'rtl'/f'{n}.v' for n in ordinary]+[root/'rtl/experimental'/f'{n}.v' for n in experimental]+[root/'tests'/tb]
    if kind=='query':paths+=[folder/'counts.vh']
    if kind in ('native','video'):paths+=[root/'board/calibration-trial.vh',root/'board/rotation-domain.vh']
    if kind in ('native','video'):paths+=[root/'rtl/video_crc32.vh']
    paths+=list(folder.glob('*.mem'))
    snapshot=folder/'source-snapshot';hashes={}
    for p in paths:
        assert p.stat().st_mtime<=log.stat().st_birthtime,('Source modified after simulation began',str(p))
        relative=str(p.relative_to(root));digest=hashlib.sha256(p.read_bytes()).hexdigest()
        target=snapshot/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,target)
        assert hashlib.sha256(target.read_bytes()).hexdigest()==digest
        hashes[relative]=digest;source_hashes[relative]=digest
    (snapshot/'files-sha256.json').write_text(json.dumps(hashes,indent=2)+'\n')
    log_hashes[kind]=hashlib.sha256(log.read_bytes()).hexdigest()
rows=list(csv.DictReader((root/'build/pipeline_hit_native_sim/cycles.csv').open()))
baseline=json.loads((lab/'paired-cache-native-check.json').read_text())['frames']
assert len(rows)==len(baseline)==6
frames=[]
for row,old in zip(rows,baseline):
    assert int(row['pixels'])==307200 and row['crc32'].upper()==old['crc32'].upper()
    assert int(row['read_bursts'])==old['read_bursts'],'Unexpected change in DDR fill count'
    cycles=int(row['cycles'])
    frames.append({'angle_deg':old['angle_deg'],'pixels':307200,'crc32':row['crc32'],
        'pipeline_cycles':cycles,'previous_paired_cycles':old['paired_cycles'],
        'read_bursts':int(row['read_bursts']),'process_ms_at_125mhz':cycles/125000,
        'cycle_reduction_from_paired_percent':(1-cycles/old['paired_cycles'])*100})
result={'passed':True,'hardware_accessed':False,'pixels_checked':1843200,'frames':frames,
    'source_sha256':source_hashes,'simulation_log_sha256':log_hashes,
    'hot_hit_initiation_interval_cycles_verified':1,'hot_hit_consecutive_accepts_verified':64,
    'query_fault_regression_passed':True,'mixed_burst_camera_hdmi_simulation_passed':True,
    'logical_replica_data_capacity_bytes_at_32_lines':32768,
    'logical_fallback_data_capacity_bytes_at_32_lines':8192,
    'strategy':'Four synchronous read replicas, two-stage elastic hit pipeline. A miss drains prior hits before the unchanged serial 8-beat fallback; frame handshake invalidates both caches. Raster near 0/180, tiles otherwise.',
    'limits':'Synthetic DDR and six real-source golden frames; not an achieved physical FPS. The 1-cycle interval applies only to resident hits with ready output. Misses and image order still limit throughput. Logical RAM capacity is calculated, not mapped resources. Four-way address/tag logic and RAM replicas need board mapping, routed timing, controller compatibility and temperature checks. No active board target was changed.'}
(lab/'pipeline-hit-native-check.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'passed':True,'frames':frames},indent=2))
