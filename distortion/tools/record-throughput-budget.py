"""Measured VGA cycle cost and explicit prerequisites for higher resolution."""
from pathlib import Path
import hashlib
import json

root=Path(__file__).resolve().parents[1]
lab=root/'results/lab-20261007'
proof_path=lab/('pipeline-hit-native-check.json' if (lab/'pipeline-hit-native-check.json').exists() else 'paired-cache-native-check.json')
proof=json.loads(proof_path.read_text());assert proof['passed']
clock=125000000
rows=[]
for width,height,fps in ((640,480,30),(1280,720,30),(1920,1080,30),(1920,1080,60)):
    pixels=width*height
    pixel_rate=pixels*fps
    byte_rate=pixel_rate*2
    stride=((pixels*2+1048575)//1048576)*1048576
    rows.append({'width':width,'height':height,'target_new_frames_per_second':fps,
        'output_pixels_per_second':pixel_rate,
        'required_average_core_cycles_per_pixel_at_125mhz':clock/pixel_rate,
        'minimum_8bit_dvp_rgb565_byte_clock_hz_excluding_blanking':byte_rate,
        'source_frame_rgb565_bytes':pixels*2,
        'suggested_power_of_two_bank_stride_bytes':stride,
        'four_bank_storage_bytes':stride*4,
        'current_1MiB_bank_stride_fits_frame':pixels*2<=1048576,
        'current_48MHz_camera_input_constraint_covers_minimum_byte_clock':byte_rate<=48000000})
measured=[{'angle_deg':f['angle_deg'],'simulated_cycles_per_pixel':f.get('pipeline_cycles',f.get('paired_cycles'))/f['pixels'],
           'vga_simulated_frame_ms_at_125mhz':f['process_ms_at_125mhz']} for f in proof['frames']]
result={'hardware_accessed':False,'core_clock_hz':clock,'current_input':[640,480],
    'current_8bit_rgb565_bytes_per_pixel':2,'current_bank_stride_bytes':1048576,
    'latest_isolated_native_simulation':measured,'target_budgets':rows,
    'native_proof_sha256':hashlib.sha256(proof_path.read_bytes()).hexdigest(),
    'latest_native_proof_file':str(proof_path.relative_to(root)),
    'next_architecture_need':'Coordinate math already accepts a ray each enabled cycle. The isolated replicated hit pipeline now supports one resident query per cycle, while misses and image order still determine whole-frame cost. Higher resolution needs controller/bandwidth and physical timing/resource validation, more cache locality, new camera mode and bank geometry. More camera fps alone does not establish the target.',
    'limits':'Budgets are arithmetic requirements, not achieved hardware performance or sensor maximum ratings. DVP byte-clock minima exclude blanking; actual camera mode, clock electrical limits and FPGA timing must be verified. VGA cycles must not be extrapolated into a claimed higher-resolution fps. 1080p requires new bank geometry, camera mode/intrinsics, HDMI timing and complete timing/optical checks.'}
(lab/'throughput-budget.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'camera_1080p30_rgb565_min_byte_clock_hz':1920*1080*30*2,
    'core_1080p30_cycles_per_pixel_budget':clock/(1920*1080*30),
    'scope':'Requirements only; no higher-resolution hardware claim.'}))
