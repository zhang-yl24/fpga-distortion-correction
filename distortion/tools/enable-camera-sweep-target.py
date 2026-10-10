from pathlib import Path
root=Path(__file__).resolve().parent
for name in ('build-pds.ps1','program-heartbeat.ps1','read-telemetry.ps1'):
    p=root/name
    t=p.read_text(encoding='utf-8-sig')
    t=t.replace("'camera_capture')", "'camera_capture','camera_sweep')")
    t=t.replace("if($Target -eq 'camera_capture')", "if($Target -in @('camera_capture','camera_sweep'))")
    t=t.replace("{'board\\camera_capture-pins.json'}", "{'board\\'+$Target+'-pins.json'}")
    if name=='build-pds.ps1':
        marker="    if($Target -eq 'camera_diag') {"
        addition='''    if($Target -eq 'camera_sweep') {
        foreach($src in @('board\\camera_sweep.v','board\\camera_sweep.fdc','board\\build-camera_sweep.tcl','rtl\\ov5640_pad_sweep.v')) {
            if((Get-Item (Join-Path $projectRoot $src)).LastWriteTime -gt $bitFile.LastWriteTime){throw 'Sweep source is newer than bitstream'}
        }
    }
'''
        if "throw 'Sweep source is newer than bitstream'" not in t:
            t=t.replace(marker,addition+marker)
    t=t.replace("$Target -eq 'camera_capture','camera_sweep'", "$Target -in @('camera_capture','camera_sweep')")
    p.write_text(t,encoding='utf-8-sig')
