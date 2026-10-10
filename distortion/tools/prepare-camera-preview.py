from pathlib import Path
root=Path(__file__).resolve().parents[1];board=root/'board'
t=(board/'camera_capture.v').read_text().replace('module camera_capture(', 'module preview(')
t=t.replace('ov5640_init camera(', "ov5640_init #(.DYNAMIC_PAD_MASK(1)) camera(.trial_pad_mask(16'h7ff0),")
t=t.replace('.vsync(cam_vsync),.href(cam_href)', '.vsync(!cam_vsync),.href(!cam_href)')
t=t.replace('    video_pattern #(.MODE_720P(1)) pattern(.clk(pix_clk),.rst_n(pixel_reset_sync[1]),\n        .hs(hs_out),.vs(vs_out),.de(de_out),.r(r_out),.g(g_out),.b(b_out));', '''    wire preview_ready;
    camera_preview picture(.cam_clk(cam_pclk),.rst_n(rst_n && pll_lock),.cam_ready(camera_ready),
        .vsync(!cam_vsync),.href(!cam_href),.data(cam_data),.pix_clk(pix_clk),
        .hs(hs_out),.vs(vs_out),.de(de_out),.r(r_out),.g(g_out),.b(b_out),.display_valid(preview_ready));''')
assert 'camera_preview picture' in t
t=t.replace("assign led={2'b00,", "assign led={1'b0,preview_ready,")
(board/'preview.v').write_text(t)
for ext in ('.fdc','-pins.json'):
    (board/f'preview{ext}').write_text((board/f'camera2{ext}').read_text())
with (board/'preview.fdc').open('a') as f:
    f.write('''\n# The ONLY SYS->PIX link in this preview is the asynchronous global reset.
# camera_preview uses two-flop reset release in each destination clock domain.
# Ignore asynchronous first-stage recovery; all PIX->PIX setup/hold stays timed.
set_false_path -from [get_clocks clk_27m] -to [get_clocks pixel_clk]
''')
build=(board/'build-camera2.tcl').read_text().replace('camera2','preview')
build='add_design {D:/English/FPGA/distortion/rtl/camera_preview.v}\n'+build
(board/'build-preview.tcl').write_text(build)
(board/'program-preview.tcl').write_text((board/'program-camera2.tcl').read_text().replace('camera2','preview'))
for name in ('build-pds.ps1','program-heartbeat.ps1','read-telemetry.ps1'):
    p=root/'tools'/name;s=p.read_text(encoding='utf-8-sig');lines=s.splitlines(keepends=True)
    lines[0]=lines[0].replace("'camera2')", "'camera2','preview')");s=''.join(lines)
    for group in ("@('camera_capture','camera_sweep','camera_sync','camera2')", "@('camera_init','camera_capture','camera_sweep','camera_sync','camera2')", "@('bringup','camera_init','camera_diag','camera_capture','camera_sweep','camera_sync','camera2')"):
        s=s.replace(group,group[:-1]+",'preview')")
    if name=='build-pds.ps1' and "throw 'Preview source is newer than bitstream'" not in s:
        s=s.replace("    if($Target -eq 'camera_diag') {",'''    if($Target -eq 'preview') {
        foreach($src in @('board\\preview.v','board\\preview.fdc','board\\build-preview.tcl','rtl\\camera_preview.v')) {
            if((Get-Item (Join-Path $projectRoot $src)).LastWriteTime -gt $bitFile.LastWriteTime){throw 'Preview source is newer than bitstream'}
        }
    }
    if($Target -eq 'camera_diag') {''')
    p.write_text(s,encoding='utf-8-sig')
print('Prepared full 640x480 camera2 acquisition + double-buffered 160x120 BRAM preview, centered/scaled 4x in 720p output.')
