"""Stage camera ISP read-only telemetry with existing live BRAM preview."""
from pathlib import Path
import json,re,shutil
ROOT=Path(__file__).resolve().parents[1];target='camera_isp_probe'

def main():
    if (ROOT/'build'/target/(target+'.pds')).exists():raise ValueError('Probe already built')
    original=(ROOT/'board/preview.v').read_text()
    text=original[:original.index('    wire [23:0] dvp_edges;')]
    text=text.replace('module preview(','module camera_isp_probe(').replace('ov5640_init #','ov5640_cadence_trial_init #')
    text=text.replace("assign led={1'b0,preview_ready",'assign led={probe_failed,preview_ready')
    text+='''    wire byte_valid,byte_ready,serial_busy,serial_done,probe_failed;
    wire [7:0] byte_data;wire [3:0] probe_fault;
    ov5640_state_scan scan(.clk(clk_27m),.rst_n(rst_n),.enabled(camera_ready && !camera_failed),
        .scl(cam_scl),.sda(cam_sda),.byte_valid(byte_valid),.byte_data(byte_data),
        .byte_ready(byte_ready),.failed(probe_failed),.fault(probe_fault));
    uart_tx #(.CLOCK_HZ(27000000),.BAUD(921600)) serial(.clk(clk_27m),.rst_n(rst_n),
        .start(byte_valid && byte_ready),.data(byte_data),.tx(uart_txd),.busy(serial_busy),.done(serial_done));
    assign byte_ready=!serial_busy;
endmodule
'''
    (ROOT/'board'/f'{target}.v').write_text(text)
    for suffix in ('.fdc','-pins.json'):
        shutil.copy2(ROOT/'board'/f'preview{suffix}',ROOT/'board'/f'{target}{suffix}')
    fdc=ROOT/'board'/f'{target}.fdc';constraints=fdc.read_text()
    clock=re.search(r'(?m)^create_clock[^\n]*cam_pclk[^\n]*',(ROOT/'board/gamma_capture.fdc').read_text())
    prior=re.search(r'(?m)^create_clock[^\n]*cam_pclk[^\n]*',constraints)
    assert clock and prior
    fdc.write_text(constraints[:prior.start()]+clock[0]+constraints[prior.end():])
    design=['rtl/camera_preview.v','rtl/dvp_rgb565_capture.v','rtl/reg16_i2c.v','rtl/uart_tx.v',
        'rtl/experimental/ov5640_cadence_trial_init.v','rtl/experimental/ov5640_state_scan.v',
        'board/hdmi_tx_init.v','rtl/video_pattern.v',f'board/{target}.v','board/bringup_pll.v']
    tcl=''.join('add_design {D:/English/FPGA/distortion/'+n+'}\n' for n in design)
    tail=(ROOT/'board/build-gamma_capture.tcl').read_text()
    tail=tail[tail.index('add_constraint '):].replace('gamma_capture',target)
    (ROOT/'board'/f'build-{target}.tcl').write_text(tcl+tail)
    (ROOT/'board'/f'program-{target}.tcl').write_text((ROOT/'board/program-preview.tcl').read_text().replace('preview',target))
    sources=design+[f'board/{target}.fdc',f'board/{target}-pins.json',f'board/build-{target}.tcl',
        'board/ov5640_cadence_trial_commands.vh','board/ms7210_commands.vh',f'board/{target}-sources.json']
    (ROOT/'board'/f'{target}-sources.json').write_text(json.dumps(sources,indent=2)+'\n')
    for name in ('build-pds.ps1','program-heartbeat.ps1'):
        path=ROOT/'tools'/name;script=path.read_text(encoding='utf-8-sig')
        if "'camera_isp_probe'" in script:continue
        script=script.replace("'gamma_capture_colorbars'","'gamma_capture_colorbars','camera_isp_probe'")
        if name=='program-heartbeat.ps1':
            # Diagnostic camera captures share the native pixel gate; the probe
            # instead requires its own read-only wrapper simulation.
            script=script.replace("if($Target -in @('gamma_capture','gamma_capture_settled','gamma_capture_colorbars','camera_isp_probe'))",
                "if($Target -in @('gamma_capture','gamma_capture_settled','gamma_capture_colorbars'))",1)
            script=script.replace("if($Target -in @('gamma_capture_settled','gamma_capture_colorbars','camera_isp_probe'))",
                "if($Target -in @('gamma_capture_settled','gamma_capture_colorbars'))",1)
            position=script.index("if($Target -in @('corrected_video'")
            script=script[:position]+'''if($Target -eq 'camera_isp_probe') {
    & 'C:\\Users\\22955\\AppData\\Local\\Programs\\Python\\Python313\\python.exe' (Join-Path $PSScriptRoot 'validate-camera-state-probe.py')
    if($LASTEXITCODE -ne 0){throw 'Camera ISP read-only simulation gate failed'}
}
'''+script[position:]
        path.write_text(script,encoding='utf-8-sig')
    print('Prepared isolated read-only camera ISP probe; no hardware access.')

if __name__=='__main__':main()
