from pathlib import Path
import json,hashlib,math
R=Path(__file__).resolve().parent
read=lambda n:json.loads((R/n).read_text(encoding='utf-8'))
d=read('DISPLAY_SUMMARY.json');b=read('BUILD_SUMMARY.json')
assert hashlib.sha256((R/'analyze_scan.py').read_bytes()).hexdigest()==d['analyzer_sha256']=='18c7e38fd4190a53c17ae193098abf14cd815f74854f7820d4d13a03dc07a6d4'
assert d['our_rebuilt_bit_sha256']==b['our_rebuilt_bit_sha256']=='53f37b7e995541be65c4c29a5c8eeba2d5a59cfb5002ebd54f7fb2ea24fa0bdd'
assert d['complete_digital_scan_records']==1798 and d['distinct_displayed_FrameIDs']==1797 and d['repeat_scan_records']==1
assert math.isclose(d['new_displayed_IDs_per_host_second'],1797/d['host_capture_seconds'],rel_tol=1e-12)
assert d['processing_fps'] is None and d['processing_cycles'] is None and d['input_SOF_or_DMA_loss'] is None and d['external_E2E'] is None
assert b['internal12_native_checks_all_zero'] and b['vendor_clock_groups_actually_applied'] and not b['global_physical_timing_signoff']
assert d['profile']['rotation_degrees']==0 and not d['profile']['gamma_enabled']
print(json.dumps({'stable30_bounded_display_observation':True,'display_new_ID_rate_host_hz':d['new_displayed_IDs_per_host_second'],'processing_FPS_or_input_loss_or_E2E_claimed':False,'internal12_model_checks_zero_not_global_signoff':True}))
