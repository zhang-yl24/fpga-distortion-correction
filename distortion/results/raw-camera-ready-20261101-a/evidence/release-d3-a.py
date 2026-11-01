"""One offline release batch; never execute the prepared programming plan."""
from pathlib import Path
import json
import sys

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[1]
sys.path.insert(0, str(PROJECT / 'tools'))
import raw_camera_delay_bitstream as bit
import raw_camera_delay_program as program
import raw_camera_delay_capture_binding as capture


def announce(phase, **fields):
    print(json.dumps({'Phase':phase, **fields}), flush=True)


announce('Rechecking release evidence')
bitwork = HERE / 'bit-d3-a'
prepared = bit.prepare(HERE / 'bit-d3-a-request.json', bitwork, maximum=900)
announce('Bit preparation passed', Command=prepared['Command'])
verified = bit.execute(bitwork)
announce('Bit verified', Verified=verified['Verified'], Bitstream=verified['Bitstream'])
plan = program.prepare(bitwork, HERE / 'program-d3-a')
announce('SRAM plan prepared only', Plan=str(Path(plan['WorkDirectory']) / 'plan.json'), HardwareAccessed=False)
pending = capture.prepare(bitwork, PROJECT / 'work/camera-vga-calibration-20261031/binding.template.json',
                          HERE / 'binding-d3-a')
announce('Capture binding prepared only', **pending)
announce('Offline batch complete', HardwareAccessed=False, BoardPowerStillRequired=True)
