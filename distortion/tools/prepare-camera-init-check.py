"""Extend the accepted board image with verified sensor register setup.

Retains the same physical pins and HDMI pattern; does not claim pixel capture.
"""
from pathlib import Path

root = Path(__file__).resolve().parents[1]
board = root / 'board'
top = (board / 'bringup.v').read_text()
top = top.replace('module bringup(', 'module camera_init(')
start = top.index('    camera_id_probe camera(')
end = top.index('    assign rstn_out', start)
top = top[:start] + '''    wire camera_ready,camera_failed;
    wire [15:0] camera_failed_address;
    wire [8:0] camera_writes;
    wire [8:0] camera_noacks;
    wire [7:0] camera_observed,camera_expected;
    ov5640_init camera(.clk(clk_27m),.rst_n(rst_n),.cam_rst_n(cam_rst_n),
        .cam_scl(cam_scl),.cam_sda(cam_sda),.sensor_id(sensor_id),
        .ready(camera_ready),.failed(camera_failed),.error_code(cam_errors),
        .failed_address(camera_failed_address),.commands_written(camera_writes),.verified_write_noacks(camera_noacks),
        .observed_value(camera_observed),.expected_value(camera_expected));
    assign cam_complete=camera_ready || camera_failed;
    assign cam_match=camera_ready;
''' + top[end:]
top = top.replace('reg report_hd_ready;', '''reg report_hd_ready;
    reg report_camera_ready;
    reg [8:0] report_writes;
    reg [8:0] report_noacks;
    reg [7:0] report_observed,report_expected;
    reg [15:0] report_failed_address;''')
top = top.replace('24:message=13; 25:message=10;', '''24:message=" ";25:message="I";26:message="N";27:message="I";28:message="T";
                29:message="=";30:message=report_camera_ready ? "1":"0";
                31:message=" ";32:message="W";33:message="=";
                34:message=hexchar({3'b0,report_writes[8]});
                35:message=hexchar(report_writes[7:4]);36:message=hexchar(report_writes[3:0]);
                37:message=" ";38:message="A";39:message="=";
                40:message=hexchar(report_failed_address[15:12]);41:message=hexchar(report_failed_address[11:8]);
                42:message=hexchar(report_failed_address[7:4]);43:message=hexchar(report_failed_address[3:0]);
                44:message=" ";45:message="N";46:message="=";
                47:message=hexchar({3'b0,report_noacks[8]});48:message=hexchar(report_noacks[7:4]);49:message=hexchar(report_noacks[3:0]);
                50:message=" ";51:message="R";52:message="=";53:message=hexchar(report_observed[7:4]);54:message=hexchar(report_observed[3:0]);
                55:message=" ";56:message="T";57:message="=";58:message=hexchar(report_expected[7:4]);59:message=hexchar(report_expected[3:0]);
                60:message=13;61:message=10;''')
top = top.replace('report_id<=0; report_errors<=0;', 'report_observed<=0;report_expected<=0;report_noacks<=0;report_camera_ready<=0;report_writes<=0;report_failed_address<=0;\n            report_id<=0; report_errors<=0;')
top = top.replace('report_id<=sensor_id; report_errors<=cam_errors;', 'report_observed<=camera_observed;report_expected<=camera_expected;report_noacks<=camera_noacks;report_camera_ready<=camera_ready;report_writes<=camera_writes;report_failed_address<=camera_failed_address;\n                    report_id<=sensor_id; report_errors<=cam_errors;')
top = top.replace('report_index==25', 'report_index==61')
top = top.replace('// Short hardware acceptance image: HDMI pattern + camera ID + UART telemetry.', '// OV5640 DVP/VGA/RGB565 setup + critical register readback + HDMI pattern.')
(board / 'camera_init.v').write_text(top)
(board / 'camera_init.fdc').write_text((board / 'bringup.fdc').read_text())
tcl = (board / 'build-bringup.tcl').read_text()
tcl = tcl.replace('/rtl/camera_id_probe.v', '/rtl/ov5640_init.v')
tcl = tcl.replace('/board/bringup.v', '/board/camera_init.v').replace('/board/bringup.fdc', '/board/camera_init.fdc')
tcl = tcl.replace('compile -top_module bringup', 'compile -top_module camera_init')
(board / 'build-camera_init.tcl').write_text(tcl)
program = (board / 'program-bringup.tcl').read_text().replace('/build/bringup/generate_bitstream/bringup.sbit', '/build/camera_init/generate_bitstream/camera_init.sbit')
(board / 'program-camera_init.tcl').write_text(program)
print('Prepared camera_init: same 44 physical ports, 264 writes + 7 critical reads; pixels not connected yet.')
