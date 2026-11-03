from pathlib import Path
import re,json,hashlib,sys,shutil
third='--third' in sys.argv
root=Path('D:/fpga-stable/scheduler'); work=root/(sys.argv[sys.argv.index('--run-dir')+1] if '--run-dir' in sys.argv else ('system-three' if third else 'system-small'));work.mkdir(exist_ok=True)
if third:
 for p in (root/'system-small').glob('*.mem'):shutil.copy2(p,work/p.name)
 for name in ('config.vh','timing.vh','fixture-source.json'):shutil.copy2(root/'system-small'/name,work/name)
repo=Path('C:/Users/Lenovo/Documents/Codex/2026-11-02/2026-fpga/work/repo/distortion')
original=repo/'tests/tb_board1080_system.sv'
s=original.read_text()
def replace(a,b):
 global s
 assert a in s,a
 s=s.replace(a,b)
replace('wire source_commit,source_commit_bank,source_release,released_bank,result_publish;','wire source_commit,source_release,result_publish; wire [1:0] source_commit_bank,released_bank;')
replace('wire [1:0] capture_reserved;','wire [2:0] capture_reserved;')
replace('hdmi1080_video_system #','hdmi1080_video_system_geometry_ab #')
replace('.core_clk(core_clk),.pix_in_clk(pix_in_clk),.pix_out_clk(pix_out_clk),.rst_n(rst_n),',
 '.core_clk(core_clk),.pix_in_clk(pix_in_clk),.pix_out_clk(pix_out_clk),.rst_n(rst_n),\n'+
 '.telemetry_clk(core_clk),.telemetry_rx(1\'b1),.telemetry_param_id(32\'h8c73465e),\n'+
 '.gamma_enable(1\'b0),.correction_enable(1\'b1),.cfg_rot_cx(VEC_OUT_CX),.cfg_rot_cy(VEC_OUT_CY),.cfg_rot_cos(32\'sd1073741824),.cfg_rot_sin(32\'sd0),')
replace('memory[0:4*FB-1]','memory[0:5*FB-1]')
replace('source_epoch[0:1]','source_epoch[0:2]')
replace('for(i=0;i<2;i=i+1)begin source_epoch[i]=-1;result_epoch[i]=-1;end','for(i=0;i<3;i=i+1)source_epoch[i]=-1;\n            for(i=0;i<2;i=i+1)result_epoch[i]=-1;')
replace('function automatic integer texture','function automatic integer source_slot(input integer slot); source_slot=slot==4?2:slot; endfunction\n    function automatic integer texture')
replace('araddr>=2*STRIDE','araddr>=2*STRIDE&&araddr<4*STRIDE')
replace('awaddr>=2*STRIDE','awaddr>=2*STRIDE&&awaddr<4*STRIDE')
replace('bank>3','bank>4')
replace('f=source_epoch[bank];','f=source_epoch[source_slot(bank)];')
replace('if(bank>1||f<0||!processing||bank!=dut.bank_core.active_source','if((bank!=0&&bank!=1&&bank!=4)||f<0||!processing||source_slot(bank)!=dut.bank_core.active_source')
replace('if(bank<2||f<0||!display_active','if((bank!=2&&bank!=3)||f<0||!display_active')
replace('rbank<2?0:1','(rbank<2||rbank==4)?0:1')
replace('if(rbank>=2)begin','if(rbank==2||rbank==3)begin')
replace('if(bank<2)begin','if(bank<2||bank==4)begin')
replace('!capture_reserved[bank]||(processing&&dut.bank_core.active_source==bank)','!capture_reserved[source_slot(bank)]||(processing&&dut.bank_core.active_source==source_slot(bank))')
replace('tb<2?0:1','(tb<2||tb==4)?0:1')
replace('if(tb<2)begin','if(tb<2||tb==4)begin')
replace('rbank==released_bank','(rbank<2||rbank==4)&&source_slot(rbank)==released_bank')
replace('scatter_group==31','scatter_group==15')
replace('scatter_cycles[f]!=32*','scatter_cycles[f]!=16*')
replace('scatter4 fill count mismatch','scatter8 fill count mismatch')
replace("source_writable!==2'b11","source_writable!==3'b111")
replace('||source_bank_for[i]!=i%2','||source_bank_for[i]<0||source_bank_for[i]>2')
if third:
 replace('texture=(frame+(phase_id==2 ? 2:0))%3;','texture=phase_id==0?(frame+frame/3)%3:(frame+(phase_id==2?2:0))%3;')
 replace('repeat(12)@(negedge core_clk);capture_admit=1;scan_enable=1;','repeat(12)@(negedge core_clk);capture_admit=1;scan_enable=next_phase==0?0:1;')
 replace('clear_scoreboard();reset_domains(0);send_frames(8);','clear_scoreboard();reset_domains(0);\n        fork\n            send_frames(8);\n            begin wait(tx_frame==2&&input_pixels[2]>0);@(negedge core_clk);scan_enable=1;end\n        join')
 replace('normal_captured=captured_frames;','k=0;for(i=0;i<8;i=i+1)k=k|(1<<source_bank_for[i]);\n        if(k!=7)$fatal(1,"directed full system did not use all three source banks");\n        $display("PASS actual-source-bank-mask=%0d: source slot4 exact data and independent output CRC",k);\n        normal_captured=captured_frames;')
# Keep all assertions and exact independent-pixel/CRC checks. The bank sequence
# changes with availability, so require legal ownership rather than i%2.
(work/'tb_board1080_system.sv').write_text(s)
build=Path('D:/fpga-stable/build/stable-a')
sources=[Path(p) for p in re.findall(r'add_design \{([^}]+)\}',(build/'map.tcl').read_text())]
sources=sources[:22]+[p for p in sources if '/b4/' in p.as_posix()]
files=[{'path':str(p),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for p in sources]
(work/'compile-sources.json').write_text(json.dumps({'scope':'Prepared stable-a integration sources, no engine stub; DDR UI modeled in bench','sources':files,'original_bench':str(original),'original_bench_sha256':hashlib.sha256(original.read_bytes()).hexdigest(),'bench_sha256':hashlib.sha256((work/'tb_board1080_system.sv').read_bytes()).hexdigest()},indent=2))
(work/'compile-paths.txt').write_text('\n'.join(str(p) for p in sources))
print('Prepared',len(sources),'RTL files and actual-system bench')
