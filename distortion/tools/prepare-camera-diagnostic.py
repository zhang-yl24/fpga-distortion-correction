"""Prepare an isolated SCCB write/read comparison on the existing board pins."""
from pathlib import Path

board = Path(__file__).resolve().parents[1] / 'board'
top = (board / 'camera_init.v').read_text().replace(
    'module camera_init(', 'module camera_diag(').replace(
    'ov5640_init camera(', 'ov5640_bus_diagnostic camera(')
(board / 'camera_diag.v').write_text(top)
(board / 'camera_diag.fdc').write_text((board / 'camera_init.fdc').read_text())
build = (board / 'build-camera_init.tcl').read_text().replace(
    '/rtl/ov5640_init.v', '/rtl/ov5640_bus_diagnostic.v').replace(
    'camera_init', 'camera_diag')
(board / 'build-camera_diag.tcl').write_text(build)
(board / 'program-camera_diag.tcl').write_text(
    (board / 'program-camera_init.tcl').read_text().replace('camera_init', 'camera_diag'))
print('camera_diag: W=test index (hex), E[4]=read, E[3:0]=bus error, N=STOP-read mode.')
print('INIT=1 means a result is available, not sensor initialization success.')
