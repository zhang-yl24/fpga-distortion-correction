from pathlib import Path
import hashlib,json,math
R=Path(__file__).resolve().parent
def load(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
p=load(R/'SOURCE_PROVENANCE.json')
for row in p['copied_exact_files']:
 f=(R/row['path']).resolve()
 assert f.is_relative_to(R) and f.stat().st_size==row['bytes'] and sha(f)==row['sha256'],row['path']
for row in p.get('derived_records',[]):
 assert sha(R/row['path'])==row['delivered_sha256']
rx=load(R/'rx/NATIVE_MAP_SUMMARY.json')
assert sha(R/'rx/candidate/telemetry_uart_link.sv')==rx['wrapper_sha256']
assert sha(R/'rx/rtl/measurement_rx_router.sv')==rx['router_sha256']
assert rx['map_root_exit']==0 and not rx['strict_timing_accepted'] and not rx['hardware_release_allowed']
ix=load(R/'index6/INDEX6_ENGINE_SUMMARY.json')
for key,name in [('candidate_engine_sha256','pipeline_gamma_frame_engine_1080_geometry_bypass.v'),('runtime_sha256','d256_runtime_prefetch_cache.sv'),('sampler_sha256','ddr_remap_sample_scatter4.v')]:
 assert sha(R/'index6/source/ce'/name)==ix[key]
assert ix['process']['begin_to_done_edges']==2073957 and ix['process']['observed_misses']==18268
assert ix['process']['model_miss_match']==0 and ix['not_continuous_camera_or_board60']
assert ix['raw_cache_audit']['neighbour_pixels_checked']==8294400
b=load(R/'board/VALIDATED_COUNTER_SUMMARY.json')
assert b['independent_v1_offline_replay_PASS'] and b['external_E2E']=='UNMEASURED'
w=b['core_window'];assert w['delta']['processed_frames']==468
assert math.isclose(w['delta']['processed_frames']/w['seconds_nominal'],23.3613440680714)
assert b['does_not_qualify_RX_or_INDEX6_bit']
print(json.dumps({'exact_authored_files_verified':len(p['copied_exact_files']),'RX_map_not_hardware':True,'INDEX6_one_frame_only':True,'board_nominal_fps':b['rates']['processed_new_correction_fps_nominal'],'external_E2E':'UNMEASURED'}))
