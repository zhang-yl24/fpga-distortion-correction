"""Compare four sampled VSYNC/HREF polarities; keep suspect D1 disabled."""
from pathlib import Path
root=Path(__file__).resolve().parents[1]
board=root/'board'
t=(board/'camera_capture.v').read_text().replace('module camera_capture(', 'module camera_sync(')
t=t.replace('ov5640_init camera(', "ov5640_init #(.DYNAMIC_PAD_MASK(1)) camera(.trial_pad_mask(16'h7fd0),")
declarations=[];cases=[];capture=[];reset=[]
idx=113
for n,(v,h) in enumerate(((1,0),(0,1),(0,0))):
    declarations.append(f'''    wire [31:0] alt_f{n},alt_p{n};wire [15:0] alt_l{n};
    reg [31:0] report_alt_f{n},report_alt_p{n};reg [15:0] report_alt_l{n};
    dvp_monitor alt{n}(.sysclk(clk_27m),.rst_n(rst_n),.pclk(cam_pclk),
        .vsync({'cam_vsync' if v else '!cam_vsync'}),.href({'cam_href' if h else '!cam_href'}),
        .data(cam_data),.frames(alt_f{n}),.last_pixels(alt_p{n}),.last_lines(alt_l{n}));
''')
    capture.append(f'report_alt_f{n}<=alt_f{n};report_alt_p{n}<=alt_p{n};report_alt_l{n}<=alt_l{n};')
    reset.append(f'report_alt_f{n}<=0;report_alt_p{n}<=0;report_alt_l{n}<=0;')
    for char in f' V{v}H{h}=':
        cases.append(f'{idx}:message="{char}";');idx+=1
    for var,digits in ((f'report_alt_f{n}',8),(f'report_alt_p{n}',8),(f'report_alt_l{n}',4)):
        for digit in range(digits):
            hi=(digits-digit)*4-1
            cases.append(f'{idx}:message=hexchar({var}[{hi}:{hi-3}]);');idx+=1
        if digits==8:
            cases.append(f'{idx}:message="/";');idx+=1
cases.append(f'{idx}:message=13;{idx+1}:message=10;')
t=t.replace('    function [7:0] hexchar;', ''.join(declarations)+'    function [7:0] hexchar;')
t=t.replace('input [6:0] idx;', 'input [7:0] idx;').replace('reg [6:0] report_index;', 'reg [7:0] report_index;')
t=t.replace('report_index==114', f'report_index=={idx+1}')
t=t.replace('113:message=13;114:message=10;', '\n                '.join(cases))
t=t.replace('report_sum<=0;', ''.join(reset)+'report_sum<=0;',1)
t=t.replace('report_sum<=dvp_sum;', ''.join(capture)+'report_sum<=dvp_sum;')
(board/'camera_sync.v').write_text(t)
for ext in ('.fdc','-pins.json'):
    (board/f'camera_sync{ext}').write_text((board/f'camera_capture{ext}').read_text())
for prefix in ('build-','program-'):
    (board/f'{prefix}camera_sync.tcl').write_text((board/f'{prefix}camera_capture.tcl').read_text().replace('camera_capture','camera_sync'))
for name in ('build-pds.ps1','program-heartbeat.ps1','read-telemetry.ps1'):
    path=root/'tools'/name
    text=path.read_text(encoding='utf-8-sig');lines=text.splitlines(keepends=True)
    lines[0]=lines[0].replace("'camera_sweep')", "'camera_sweep','camera_sync')")
    text=''.join(lines)
    for group in ("@('camera_capture','camera_sweep')", "@('camera_init','camera_capture','camera_sweep')", "@('bringup','camera_init','camera_diag','camera_capture','camera_sweep')"):
        text=text.replace(group,group[:-1]+",'camera_sync')")
    if name=='build-pds.ps1' and "throw 'Sync source is newer than bitstream'" not in text:
        text=text.replace("    if($Target -eq 'camera_diag') {",'''    if($Target -eq 'camera_sync') {
        foreach($src in @('board\\camera_sync.v','board\\camera_sync.fdc','board\\build-camera_sync.tcl')) {
            if((Get-Item (Join-Path $projectRoot $src)).LastWriteTime -gt $bitFile.LastWriteTime){throw 'Sync source is newer than bitstream'}
        }
    }
    if($Target -eq 'camera_diag') {''')
    path.write_text(text,encoding='utf-8-sig')
print(f'Prepared camera_sync, 7FD0 (D1 disabled), four polarity monitors; last UART index {idx+1}.')
