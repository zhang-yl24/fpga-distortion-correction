"""Test the second sensor through its separate J2 signals, same I/O bank."""
from pathlib import Path
import json,re
root=Path(__file__).resolve().parents[1];board=root/'board'
pins=json.loads((board/'camera_sync-pins.json').read_text())
mapping={'cam_sda':'V16','cam_scl':'W19','cam_rst_n':'Y20',
    'cam_pclk':'U21','cam_vsync':'V23','cam_href':'W23',
    'cam_data[7]':'T18','cam_data[6]':'T17','cam_data[5]':'AA22','cam_data[4]':'AB25',
    'cam_data[3]':'V19','cam_data[2]':'U25','cam_data[1]':'U26','cam_data[0]':'V21'}
pins.update(mapping)
assert len(pins)==55 and len(set(pins.values()))==55
fdc=(board/'camera_sync.fdc').read_text()
for port,pin in mapping.items():
    pattern=r'(define_attribute \{p:'+re.escape(port)+r'\} \{PAP_IO_LOC\} \{)[^}]+(\})'
    fdc,count=re.subn(pattern,lambda m:m[1]+pin+m[2],fdc)
    assert count==1,(port,count)
(board/'camera2.fdc').write_text(fdc)
(board/'camera2-pins.json').write_text(json.dumps(pins,indent=2)+'\n')
(board/'camera2.v').write_text((board/'camera_sync.v').read_text().replace('module camera_sync(', 'module camera2(').replace("16'h7fd0", "16'h7ff0"))
for prefix in ('build-','program-'):
    (board/f'{prefix}camera2.tcl').write_text((board/f'{prefix}camera_sync.tcl').read_text().replace('camera_sync','camera2'))
for name in ('build-pds.ps1','program-heartbeat.ps1','read-telemetry.ps1'):
    p=root/'tools'/name;t=p.read_text(encoding='utf-8-sig');lines=t.splitlines(keepends=True)
    lines[0]=lines[0].replace("'camera_sync')", "'camera_sync','camera2')");t=''.join(lines)
    for group in ("@('camera_capture','camera_sweep','camera_sync')", "@('camera_init','camera_capture','camera_sweep','camera_sync')", "@('bringup','camera_init','camera_diag','camera_capture','camera_sweep','camera_sync')"):
        t=t.replace(group,group[:-1]+",'camera2')")
    if name=='build-pds.ps1' and "throw 'Camera2 source is newer than bitstream'" not in t:
        t=t.replace("    if($Target -eq 'camera_diag') {",'''    if($Target -eq 'camera2') {
        foreach($src in @('board\\camera2.v','board\\camera2.fdc','board\\build-camera2.tcl')) {
            if((Get-Item (Join-Path $projectRoot $src)).LastWriteTime -gt $bitFile.LastWriteTime){throw 'Camera2 source is newer than bitstream'}
        }
    }
    if($Target -eq 'camera_diag') {''')
    p.write_text(t,encoding='utf-8-sig')
print('Prepared camera2 full 8-bit DVP; all 14 camera signals separately mapped to J2, 55 unique pins.')
