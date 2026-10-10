"""Emit only from an up-to-date final routed-DB report; do not reroute."""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
work = root / 'build/corrected_video'
report = work / 'report_timing/corrected_video.rtr'
db = work / 'place_route/corrected_video_pnr.adf'
text = report.read_text()
assert 'Design Summary : All Constraints Met.' in text
assert 'Device       : PG2L100H' in text and 'Package      : FBG676' in text
assert report.stat().st_mtime >= db.stat().st_mtime
prefix = (root / 'board/build-corrected_video.tcl').read_text().split('compile -top_module')[0]
script = prefix + f'gen_bit_stream -force_to_run -input_db_file {{{db.as_posix()}}} -scbv {{High Voltage}} -unused_io_status UNUSED\n'
(root / 'board/finalize-corrected-video.tcl').write_text(script)
print('Final routed DB report passes device, corners and freshness; prepared bitstream generation.')
