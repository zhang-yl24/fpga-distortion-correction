"""Attach the J2 DVP receiver and coherent telemetry to the accepted init image."""
from pathlib import Path
import json

board = Path(__file__).resolve().parents[1] / 'board'
top = (board / 'camera_init.v').read_text().replace('module camera_init(', 'module camera_capture(')
top = top.replace('input clk_27m,', 'input clk_27m,cam_pclk,cam_vsync,cam_href,input [7:0] cam_data,')
insert = '''    wire [23:0] dvp_edges;
    wire [31:0] dvp_frames,dvp_pixels,dvp_sum;
    wire [15:0] dvp_lines;
    wire dvp_odd;
    dvp_monitor monitor(.sysclk(clk_27m),.rst_n(rst_n),.pclk(cam_pclk),
        .vsync(cam_vsync),.href(cam_href),.data(cam_data),.edges_per_window(dvp_edges),
        .frames(dvp_frames),.last_pixels(dvp_pixels),.last_checksum(dvp_sum),.last_lines(dvp_lines),.last_odd(dvp_odd));
    reg [23:0] report_edges;
    reg [31:0] report_frames,report_pixels,report_sum;
    reg [15:0] report_lines;
    reg report_odd;
'''
top = top.replace('    function [7:0] hexchar;', insert + '    function [7:0] hexchar;')
cases = []
def text_at(start, s):
    for i, c in enumerate(s, start):
        cases.append(f'{i}:message="{c}";')
def hex_at(start, reg, digits):
    for i in range(digits):
        hi = (digits-i)*4-1
        cases.append(f'{start+i}:message=hexchar({reg}[{hi}:{hi-3}]);')
text_at(60,' C='); hex_at(63,'report_edges',6)
text_at(69,' F='); hex_at(72,'report_frames',8)
text_at(80,' P='); hex_at(83,'report_pixels',8)
text_at(91,' L='); hex_at(94,'report_lines',4)
text_at(98,' O='); cases += ['101:message=report_odd ? "1":"0";']
text_at(102,' S='); hex_at(105,'report_sum',8)
cases += ['113:message=13;114:message=10;']
top = top.replace('60:message=13;61:message=10;', '\n                '.join(cases))
top = top.replace('input [5:0] idx;', 'input [6:0] idx;').replace('reg [5:0] report_index;', 'reg [6:0] report_index;')
top = top.replace('report_index==61', 'report_index==114')
top = top.replace('report_state<=0; report_index<=0;', 'report_sum<=0;report_edges<=0;report_frames<=0;report_pixels<=0;report_lines<=0;report_odd<=0;\n            report_state<=0; report_index<=0;',1)
top = top.replace('report_observed<=camera_observed;', 'report_sum<=dvp_sum;report_edges<=dvp_edges;report_frames<=dvp_frames;report_pixels<=dvp_pixels;report_lines<=dvp_lines;report_odd<=dvp_odd;\n                    report_observed<=camera_observed;')
(board/'camera_capture.v').write_text(top)

pins = json.loads((board/'bringup-pins.json').read_text())
# Module J17 -> FMC J2 -> BASE-V1.4 FPGA balls, from the supplied schematics.
extra = {'cam_pclk':'Y22','cam_vsync':'Y23','cam_href':'W18',
         'cam_data[7]':'V14','cam_data[6]':'V18','cam_data[5]':'Y21',
         'cam_data[4]':'T15','cam_data[3]':'W25','cam_data[2]':'Y26',
         'cam_data[1]':'U20','cam_data[0]':'T14'}
pins.update(extra)
assert len(pins)==55 and len(set(pins.values()))==55, 'Duplicate or missing board pin'
(board/'camera_capture-pins.json').write_text(json.dumps(pins,indent=2)+'\n')
fdc = (board/'camera_init.fdc').read_text()
fdc = fdc.replace('[get_cells -hierarchical {*scl_meta* *sda_meta*}]', '[get_clocks clk_27m]')
fdc = fdc.replace('[get_cells -hierarchical {*pixel_reset_sync*}]', '[get_clocks pixel_clk]')
fdc += '''\n# Initial 48 MHz timing budget (2x configured 24 MHz VGA PCLK), not a frequency change.
# Actual clock activity and PCB data delay still require measurement.
create_clock -name camera_pclk -period 20.833 [get_ports cam_pclk]
set_clock_groups -name camera_async -asynchronous -group [get_clocks camera_pclk] -group [get_clocks {clk_27m pixel_clk}]
set_input_delay -clock camera_pclk -max 5.0 [get_ports {cam_data[*] cam_vsync cam_href}]
set_input_delay -clock camera_pclk -min 0.0 [get_ports {cam_data[*] cam_vsync cam_href}]
'''
for port, pin in extra.items():
    fdc += f'define_attribute {{p:{port}}} {{PAP_IO_LOC}} {{{pin}}}\n'
    fdc += f'define_attribute {{p:{port}}} {{PAP_IO_VCCIO}} {{3.3}}\n'
    fdc += f'define_attribute {{p:{port}}} {{PAP_IO_STANDARD}} {{LVCMOS33}}\n'
(board/'camera_capture.fdc').write_text(fdc)
build = (board/'build-camera_init.tcl').read_text().replace('camera_init','camera_capture')
build = ('add_design {D:/English/FPGA/distortion/rtl/dvp_rgb565_capture.v}\n'
         'add_design {D:/English/FPGA/distortion/rtl/dvp_monitor.v}\n') + build
build = build.replace('report_timing -from [get_clocks pixel_clk] -to [get_ports {r_out[*] g_out[*] b_out[*] de_out hs_out vs_out}] -max_path 2', 'report_timing -max_path 5')
(board/'build-camera_capture.tcl').write_text(build)
(board/'program-camera_capture.tcl').write_text(
    (board/'program-camera_init.tcl').read_text().replace('camera_init','camera_capture'))
print('Prepared 55-pin camera_capture; C=edges/ms (hex), F=frames, P=pixels/frame, L=lines/frame, O=odd byte.')
