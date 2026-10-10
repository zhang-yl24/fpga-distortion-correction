"""Isolated full-video and board copies, with coherent Gamma telemetry."""
from pathlib import Path
import hashlib,json,re,shutil
root=Path(__file__).resolve().parents[1]
old,new='corrected_host_cadence','corrected_gamma'
assert not (root/'build'/new/(new+'.pds')).exists(),'Preserve active candidate'
def one(s,a,b):assert s.count(a)==1,a;return s.replace(a,b)
v=(root/'rtl/experimental/ddr_adaptive_video.v').read_text()
v=one(v,'module ddr_adaptive_video #(','module ddr_gamma_video #(')
v=one(v,'input cam_clk,core_clk,pix_clk,rst_n,ready,','input cam_clk,core_clk,pix_clk,rst_n,ready,gamma_enable,\n    output [1:0] gamma_mode,output [31:0] gamma_frames,')
v=one(v,'adaptive_tiled_frame_engine #(','adaptive_gamma_frame_engine #(')
v=one(v,'.frame_valid(engine_start),.frame_ready(engine_ready),','.frame_valid(engine_start),.frame_ready(engine_ready),.gamma_enable(gamma_enable),.gamma_mode(gamma_mode),.gamma_frames(gamma_frames),')
(root/'rtl/experimental/ddr_gamma_video.v').write_text(v)
top=(root/'board'/(old+'.v')).read_text().replace('module '+old+'(', 'module '+new+'(')
top=one(top,'reg [175:0] held_host=0,host_status=0,report_host=0;', 'wire [1:0] gamma_mode;wire [31:0] gamma_frames;\n    reg [209:0] held_host=0,host_status=0,report_host=0;')
top=one(top,'ddr_adaptive_video #(','ddr_gamma_video #(')
top=one(top,'.ready(store_arm),.vsync(!cam_vsync)',".ready(store_arm),.gamma_enable(1'b1),.gamma_mode(gamma_mode),.gamma_frames(gamma_frames),.vsync(!cam_vsync)")
top=one(top,'held_host<={host_accepted_sequence,','held_host<={gamma_frames,gamma_mode,host_accepted_sequence,')
messages=[];index=366
for ch in ' GM=':messages.append(f'                {index}:message="{ch}";');index+=1
messages.append(f"                {index}:message=hexchar({{2'b0,report_host[177:176]}});");index+=1
for ch in ' GF=':messages.append(f'                {index}:message="{ch}";');index+=1
for bit in range(209,177,-4):messages.append(f'                {index}:message=hexchar(report_host[{bit}:{bit-3}]);');index+=1
messages.extend([f'                {index}:message=13;',f'                {index+1}:message=10;'])
top=one(top,'                366:message=13;\n                367:message=10;','\n'.join(messages))
top=one(top,'if(report_index==367)',f'if(report_index=={index+1})')
(root/'board'/(new+'.v')).write_text(top)
replacements={'rtl/rotated_remap_core.v':'rtl/experimental/rotated_remap_core_gamma.v','rtl/experimental/adaptive_tiled_frame_engine.v':'rtl/experimental/adaptive_gamma_frame_engine.v','rtl/experimental/ddr_adaptive_video.v':'rtl/experimental/ddr_gamma_video.v'}
tcl=(root/'board'/('build-'+old+'.tcl')).read_text().replace(old,new)
for a,b in replacements.items():tcl=one(tcl,'/'+a+'}','/'+b+'}')
tcl="add_design {D:/English/FPGA/distortion/rtl/experimental/adaptive_gamma_stream.v}\nadd_design {D:/English/FPGA/distortion/rtl/experimental/adaptive_gamma_tagged.v}\n"+tcl
(root/'board'/('build-'+new+'.tcl')).write_text(tcl)
for suffix in ('.fdc','-pins.json'):shutil.copy2(root/'board'/(old+suffix),root/'board'/(new+suffix))
(root/'board'/('program-'+new+'.tcl')).write_text((root/'board'/('program-'+old+'.tcl')).read_text().replace(old,new))
sources=[]
for p in json.loads((root/'board'/(old+'-sources.json')).read_text()):
    p=p.replace(old,new)
    for a,b in replacements.items():p=p.replace(a.replace('/','\\'),b.replace('/','\\'))
    sources.append(p)
sources+=['rtl\\experimental\\adaptive_gamma_stream.v','rtl\\experimental\\adaptive_gamma_tagged.v','rtl\\experimental\\gamma_curves.vh']
(root/'board'/(new+'-sources.json')).write_text(json.dumps(sources,indent=2)+'\n')
for name in ('build-pds.ps1','program-heartbeat.ps1','read-telemetry.ps1'):
    p=root/'tools'/name;s=p.read_text(encoding='utf-8-sig')
    s=re.sub(r"(?:@|ValidateSet)\(([^)\n]*'corrected_adaptive_seed2'[^)\n]*)\)",lambda m:m[0] if "'"+new+"'" in m[0] else m[0][:-1]+",'"+new+"')",s)
    p.write_text(s,encoding='utf-8-sig')
work=root/'build/gamma_video_sim';work.mkdir(exist_ok=True)
for p in (root/'build/adaptive_video_sim').iterdir():
    if p.suffix in ('.mem','.json'):shutil.copy2(p,work/p.name)
tb=(root/'tests/tb_ddr_adaptive_video.sv').read_text().replace('tb_ddr_adaptive_video','tb_ddr_gamma_video').replace('tb_ddr_adaptive_serial','tb_ddr_gamma_serial').replace('ddr_adaptive_video #','ddr_gamma_video #')
tb=tb.replace('.ready(ready),',".ready(ready),.gamma_enable(1'b0),")
tb=tb.replace('PASS adaptive DDR video:','PASS Gamma bypass DDR video:')
(root/'tests/tb_ddr_gamma_video.sv').write_text(tb)
runner=(root/'tools/run-adaptive-video-sim.ps1').read_text().replace('adaptive_video_sim','gamma_video_sim').replace('tb_ddr_adaptive_video','tb_ddr_gamma_video').replace('PASS adaptive DDR video:','PASS Gamma bypass DDR video:')
runner=runner.replace("'rotated_remap_core',",'').replace("'adaptive_tiled_frame_engine',",'').replace("'ddr_adaptive_video'","'ddr_gamma_video','rotated_remap_core_gamma','adaptive_gamma_frame_engine','adaptive_gamma_stream','adaptive_gamma_tagged'")
# Hash inputs before xsim, retain tested snapshot, and verify on completion.
insert="""    $deps=$files+@((Join-Path $root 'rtl\\video_crc32.vh'),(Join-Path $root 'rtl\\experimental\\gamma_curves.vh'))+(Get-ChildItem -LiteralPath $work -Filter '*.mem' | ForEach-Object {$_.FullName})
    $hashes=@{}
    foreach($f in $deps){
        $rel=$f.Substring($root.Length+1);$hashes[$rel]=(Get-FileHash -LiteralPath $f).Hash
        $dest=Join-Path $work ('source-snapshot\\'+$rel)
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $dest) | Out-Null
        Copy-Item -LiteralPath $f -Destination $dest
    }
    @{started_at=(Get-Date).ToString('o');source_sha256=$hashes} | ConvertTo-Json -Depth 5 | Set-Content -Encoding utf8 start-proof.json
"""
runner=one(runner,"    & (Join-Path $bin 'xvlog.bat')",insert+"    & (Join-Path $bin 'xvlog.bat')")
runner=one(runner,'    ($log -split',"    foreach($f in $deps){if((Get-FileHash -LiteralPath $f).Hash -ne $hashes[$f.Substring($root.Length+1)]){throw 'Gamma video source changed'}}\n    ($log -split")
(root/'tools/run-gamma-video-sim.ps1').write_text(runner)
(root/'results/lab-20261007/gamma-board-candidate.json').write_text(json.dumps({'target':new,'hardware_accessed':False,'gamma_auto_enable':True,'gamma_telemetry':'GM mode, GF complete tone frames via existing coherent snapshot','source_sha256':{p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in sources},'limits':'Unbuilt candidate; Gamma geometric statistics/DDR integration simulation required, native regression and final routed 125MHz timing/source/pin checks before hardware. No adaptive light-quality claim.'},indent=2)+'\n')
print('Prepared isolated corrected_gamma candidate, coherent GM/GF telemetry and bypass three-clock video regression.')
