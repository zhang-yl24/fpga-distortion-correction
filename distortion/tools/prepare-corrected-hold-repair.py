"""Rehydrate PDS device/source context before reusing a placed design DB."""
from pathlib import Path
import shutil

root = Path(__file__).resolve().parents[1]
work = root / 'build/corrected_video'
archive = work / 'failed-second-route'
archive.mkdir(exist_ok=True)
for name in ('hold-repair.log', 'corrected_video.pds', 'place_route/corrected_video_timing_summary_after_hold_fix.txt'):
    src = work / name
    dest = archive / Path(name).name
    if src.exists() and not dest.exists():
        shutil.copyfile(src, dest)
prefix = (root / 'board/build-corrected_video.tcl').read_text().split('compile -top_module')[0]
assert 'set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676' in prefix
assert 'add_constraint' in prefix
db = (work / 'device_map/corrected_video_map.adf').as_posix()
plc = (work / 'place_route/corrected_video_plc.adf').as_posix()
summary = (work / 'report_timing/corrected_video.rtr').as_posix()
tail = f'''# DB reuse requires explicit project setup; pds_shell otherwise starts with PGL12G.
pnr -force_to_run -input_db_file {{{db}}} -input_place_db_file {{{plc}}} -optimize_multi_corner_timing -fix_hold_violation -fix_hold_violation_iterations 50 -fix_hold_violation_threshold 100 -fix_hold_violation_in_route TRUE
report_timing -max_path 5
set timing_file [open {{{summary}}} r]
set timing_summary [read $timing_file]
close $timing_file
if {{[string first {{All Constraints Met}} $timing_summary] < 0}} {{error {{Timing failed; refusing bitstream generation}}}}
gen_bit_stream -force_to_run -scbv {{High Voltage}} -unused_io_status UNUSED
'''
(root / 'board/repair-corrected-video-hold.tcl').write_text(prefix + tail)
print('Prepared explicit Logos2/PG2L100H/FBG676 context, unchanged source constraints, 100ps hold optimization margin and timing gate.')
