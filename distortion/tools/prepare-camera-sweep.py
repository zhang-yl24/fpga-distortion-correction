"""Create a separate 55-pin diagnostic; keep normal camera_capture unchanged."""
from pathlib import Path
board = Path(__file__).resolve().parents[1] / 'board'
top = (board/'camera_capture.v').read_text().replace('module camera_capture(', 'module camera_sweep(')
top = top.replace('    ov5640_init camera(', '''    wire [3:0] camera_trial;
    wire [15:0] camera_pad_mask;
    reg [3:0] report_trial;
    reg [15:0] report_pad_mask;
    ov5640_pad_sweep camera(''')
top = top.replace('.expected_value(camera_expected));', '.expected_value(camera_expected),.trial(camera_trial),.pad_mask(camera_pad_mask));')
top = top.replace('report_index==114','report_index==126')
top = top.replace('report_sum<=0;', 'report_trial<=0;report_pad_mask<=0;report_sum<=0;', 1)
top = top.replace('report_sum<=dvp_sum;', 'report_trial<=camera_trial;report_pad_mask<=camera_pad_mask;report_sum<=dvp_sum;')
top = top.replace('113:message=13;114:message=10;', '''113:message=" ";114:message="Q";115:message="=";
                116:message="0";117:message=hexchar(report_trial);
                118:message=" ";119:message="M";120:message="=";
                121:message=hexchar(report_pad_mask[15:12]);122:message=hexchar(report_pad_mask[11:8]);
                123:message=hexchar(report_pad_mask[7:4]);124:message=hexchar(report_pad_mask[3:0]);
                125:message=13;126:message=10;''')
(board/'camera_sweep.v').write_text(top)
for ext in ('fdc','-pins.json'):
    (board/f'camera_sweep{ext if ext.startswith("-") else "."+ext}').write_text(
        (board/f'camera_capture{ext if ext.startswith("-") else "."+ext}').read_text())
tcl=(board/'build-camera_capture.tcl').read_text().replace('camera_capture','camera_sweep')
tcl='add_design {D:/English/FPGA/distortion/rtl/ov5640_pad_sweep.v}\n'+tcl
(board/'build-camera_sweep.tcl').write_text(tcl)
(board/'program-camera_sweep.tcl').write_text((board/'program-camera_capture.tcl').read_text().replace('camera_capture','camera_sweep'))
print('Prepared camera_sweep: Q=trial 00..0D, M=3017:3018 pad mask; each result held 5s.')
