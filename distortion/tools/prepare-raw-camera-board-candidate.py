"""Stage a full-board raw capture candidate using the OLD verified CAM2 port.

This never identifies the newly arrived module, starts PDS, or downloads a bitstream.
The copied constraints describe the previous board/cable mapping only.
"""
from pathlib import Path
import hashlib
import json
from pds_source_manifest import expand_sources

ROOT = Path(__file__).resolve().parents[1]
TARGET = 'raw_camera_capture_cam2_ref'
REFERENCE = 'gamma_capture_settled_d5'


def expected_files():
    text = (ROOT / f'board/{REFERENCE}.v').read_text(encoding='utf-8')
    text = text.replace('module ' + REFERENCE + '(', 'module ' + TARGET + '(')
    start = text.index('    `include "D:/English/FPGA/distortion/board/calibration-trial.vh"')
    end = text.index('    uart_tx #', start)
    text = text[:start] + '''    // Single raw source bank. The request ID increments only on admission.
    wire raw_failed,raw_done,raw_ready,raw_locked;wire [7:0] raw_fault;
    wire [3:0] raw_state;wire [31:0] raw_crc,raw_written,raw_held_id,raw_camera_id;
    wire [1:0] raw_eye;reg [31:0] raw_sequence=0;
    wire serial_valid,serial_ready,serial_done,serial_busy;wire [7:0] serial_data;
    always @(posedge core_clk) begin
        if(!ddr_reset_sync[1]) raw_sequence<=0;
        else if(store_arm && raw_ready) raw_sequence<=raw_sequence+1'b1;
    end
    raw_camera_capture pipeline(.core_clk(core_clk),.cam_clk(cam_pclk),.rst_n(ddr_reset_sync[1]),
        .request_valid(store_arm),.request_ready(raw_ready),.request_base_address(28'b0),
        .request_frame_id(raw_sequence+1'b1),.request_camera_id(32'h43414d32),.request_eye(2'b10),
        .vsync(!cam_vsync),.href(!cam_href),.data(cam_data),
        .awaddr(axi_awaddr),.awlen(axi_awlen),.awvalid(axi_awvalid),.awready(axi_awready),
        .wdata(axi_wdata),.wstrb(axi_wstrb),.wready(axi_wready),.wlast(axi_wusero_last),
        .araddr(axi_araddr),.arlen(axi_arlen),.arvalid(axi_arvalid),.arready(axi_arready),
        .rdata(axi_rdata),.rvalid(axi_rvalid),.rlast(axi_rlast),.rid(axi_rid),
        .byte_valid(serial_valid),.byte_ready(serial_ready),.byte_done(serial_done),.byte_data(serial_data),
        .bank_locked(raw_locked),.capture_active(),.done(raw_done),.failed(raw_failed),.fault(raw_fault),
        .state(raw_state),.held_frame_id(raw_held_id),.held_camera_id(raw_camera_id),.held_eye(raw_eye),
        .source_crc(raw_crc),.written_beats(raw_written),.frame_width(),.frame_height());
''' + text[end:]
    text = text.replace('assign led={verify_failed,', 'assign led={raw_failed,')
    text = ('// OLD verified CAM2 board-port reference candidate; NEW MODULE PINOUT/ELECTRICAL UNKNOWN.\n'
            '// Native raw PGFRAME1 only. No lens calibration, Brown, rotation or Gamma datapath.\n'
            '// Slot tag encoding: 00=unassigned, 01=CAM1, 10=CAM2, 11=reserved.\n'
            '// CAM2 denotes connector slot; physical left/right and synchronization are unverified.\n' + text)
    for forbidden in ('calibration-trial', 'rotation-domain', 'gamma_frozen_capture', 'CAL_'):
        if forbidden in text:
            raise ValueError('old optical dependency leaked into raw top: ' + forbidden)
    fdc = '# OLD CAM2 reference constraints only; new module compatibility is NOT verified.\n' + (
        ROOT / f'board/{REFERENCE}.fdc').read_text(encoding='utf-8')
    pins = json.loads((ROOT / f'board/{REFERENCE}-pins.json').read_text(encoding='utf-8'))
    if pins['cam_data[5]'] != 'AA23':
        raise ValueError('reference must carry the corrected old CAM2 D5 mapping')
    design = ['rtl/raw_camera_capture.v', 'rtl/experimental/capture_warmup.v', 'rtl/camera_preview.v',
              'rtl/ddr_uart_frame.v', 'rtl/rgb565_burst_pack.v', 'rtl/video_async_fifo.v',
              'rtl/camera_live_bridge.v', 'rtl/ddr_video_writer.v', 'rtl/dvp_rgb565_capture.v',
              'rtl/reg16_i2c.v', 'rtl/uart_tx.v', 'rtl/video_pattern.v',
              'rtl/experimental/ov5640_cadence_trial_init.v',
              'platform/video_base/ipcore/ddr3_test/ddr3_test.idf',
              'board/hdmi_tx_init.v', f'board/{TARGET}.v', 'board/bringup_pll.v']
    tcl = ''.join('add_design {' + str(ROOT / name).replace('\\', '/') + '}\n' for name in design)
    old_tcl = (ROOT / f'board/build-{REFERENCE}.tcl').read_text(encoding='utf-8')
    tcl += old_tcl[old_tcl.index('add_constraint '):].replace(REFERENCE, TARGET)
    extra = [f'board/{TARGET}.fdc', f'board/{TARGET}-pins.json', f'board/build-{TARGET}.tcl',
             'rtl/video_crc32.vh', 'board/ov5640_cadence_trial_commands.vh', 'board/ms7210_commands.vh']
    return {
        f'board/{TARGET}.v': text,
        f'board/{TARGET}.fdc': fdc,
        f'board/{TARGET}-pins.json': json.dumps(pins, indent=2) + '\n',
        f'board/build-{TARGET}.tcl': tcl,
    }, design + extra


def main():
    files, names = expected_files()
    for name, value in files.items():
        path = ROOT / name
        if path.exists():
            if path.read_text(encoding='utf-8') != value:
                raise ValueError('refusing to overwrite differing candidate: ' + name)
        else:
            path.write_text(value, encoding='utf-8')
    expanded = expand_sources(ROOT, names)
    manifest = {
        'target': TARGET, 'hardware_accessed': False, 'new_module_compatibility_verified': False,
        'reference_board_port': 'previous CAM2 connector mapping, D5=AA23',
        'physical_eye': None, 'sensor_identity_readback': None, 'new_module_voltage_pinout': None,
        'connector_slot_tag': 2,
        'connector_slot_encoding': {'0': 'unassigned', '1': 'CAM1', '2': 'CAM2', '3': 'reserved'},
        'RawCaptureContract': {'protocol': 'PGFRAME1', 'payload_role': 'native_raw',
                               'geometry_applied': False, 'image_size': [640, 480]},
        'source_files': expanded,
        'SourceSHA256': {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest().upper()
                         for name in expanded},
        'limits': 'Prepared source/old-board reference constraints only. No PDS result, timing pass, board download, new-module pinout verification, physical eye assignment or optical acceptance is implied.',
    }
    path = ROOT / f'board/{TARGET}-sources.json'
    # The source manifest is reproducible from immutable candidate inputs; do
    # not silently rewrite a different prior candidate record.
    value = json.dumps(manifest, indent=2) + '\n'
    if path.exists() and path.read_text(encoding='utf-8') != value:
        raise ValueError('source manifest differs; use a separately named candidate')
    if not path.exists():
        path.write_text(value, encoding='utf-8')
    print(json.dumps({'target': TARGET, 'source_files': len(expanded), 'hardware_accessed': False,
                      'new_module_compatibility_verified': False}))


if __name__ == '__main__':
    main()
