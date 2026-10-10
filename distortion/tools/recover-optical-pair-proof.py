"""Recover complete saved pixels after an explicitly recorded idle-tool error."""
from pathlib import Path
import argparse,hashlib,json,zlib
from datetime import datetime
root=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser();parser.add_argument('directory',type=Path);args=parser.parse_args()
folder=args.directory.resolve();read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
pairs=[]
for path in sorted(folder.glob('pair*/comparison.json')):
    p=read(path);directory=path.parent
    raw=(directory/'raw-source.rgb565').read_bytes();fpga=(directory/'fpga-corrected.rgb565').read_bytes();golden=(directory/'software-reference.rgb565').read_bytes()
    assert len(raw)==len(fpga)==len(golden)==614400 and fpga==golden
    assert f'{zlib.crc32(raw):08X}'==p['raw_crc32'] and f'{zlib.crc32(fpga):08X}'==p['fpga_crc32']==p['software_crc32']
    assert p['mismatched_pixels']==0;pairs.append(p)
assert pairs
status=read(root/'status.json');assert status['current_sram_target']=='heartbeat'
idle_paths=sorted((root/'build/heartbeat').glob('program-evidence-*/transfer.json'),key=lambda p:p.stat().st_mtime)
idle=read(idle_paths[-1]);assert idle['Done'] and idle['SHA256']==status['current_connection']['last_programmed_sha256']
assert 0<=(datetime.fromisoformat(status['current_connection']['checked_on'])-datetime.fromisoformat(idle['CheckedOn'])).total_seconds()<1
capture_paths=sorted((root/'build/corrected_capture').glob('program-evidence-*/transfer.json'),key=lambda p:p.stat().st_mtime)
transfer=read(capture_paths[-1]);assert transfer['Done'] and transfer['CheckedOn'].startswith('2026-10-07')
result={'passed':True,'hardware_accessed_by_recovery':False,'target':'corrected_capture','bitstream_sha256':transfer['SHA256'],
        'pairs':pairs,'coordinates_sha256':hashlib.sha256((root/'results/calibration-fpga-candidate-20261006/coordinates-q8.bin').read_bytes()).hexdigest(),
        'capture_tool_finished_cleanly':False,'automatic_idle_attempt_passed':False,'packet_parser_final_state_available':False,
        'idle_recovery_verified':True,'idle_recovery_transfer':idle,
        'recovery_reason':'Complete saved raw/FPGA/golden pixels survived the idle-helper failure. SHA/length/CRC and byte equality rechecked. Windows PowerShell child lacked built-in Get-FileHash because it inherited PowerShell 7 module paths. A separate actual heartbeat recovery completed. Do not claim a clean original capture exit or a known packet rejection count.',
        'limits':'One fresh same-frame zero-rotation pixel comparison from the existing corrected_capture binary. New overlap/adaptive video binaries and final optical accuracy are not covered.'}
dest=root/'results/lab-20261007/optical-pair-check.json';dest.write_text(json.dumps(result,indent=2)+'\n')
(folder/'recovered-summary.json').write_text(json.dumps(result,indent=2)+'\n')
print(f'PASS saved pixel recovery: {len(pairs)*307200} pixels, exact FPGA/golden bytes and CRC; original idle failure remains recorded.')
