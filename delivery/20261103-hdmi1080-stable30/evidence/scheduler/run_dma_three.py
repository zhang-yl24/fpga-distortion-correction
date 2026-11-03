from pathlib import Path
import subprocess,json
r=Path('D:/fpga-stable/scheduler');work=r/'dma-three';work.mkdir(exist_ok=True);v=Path('D:/Vicado/Vivado/2017.4/bin');o=r/'overlay/source/rtl/experimental';native=Path('D:/fpga-build/both-final/native')
cmds=[[v/'xvlog.bat','--sv',native/'source/rtl/video_async_fifo.v',o/'hdmi1080_capture_cdc.v',o/'hdmi1080_input_dma.v',r/'tb_dma_three.sv'],[v/'xelab.bat','tb_hdmi1080_input_dma','--snapshot','dma3'],[v/'xsim.bat','dma3','-runall']]
for i,cmd in enumerate(cmds):
 p=subprocess.run([str(x) for x in cmd],cwd=work,capture_output=True,text=True);(work/f'{i}.log').write_text(p.stdout+p.stderr);print(p.stdout[-3000:],p.stderr[-1000:]);assert p.returncode==0 and "Fatal:" not in p.stdout and "ERROR:" not in p.stdout
 if i==2:assert "PASS invalid fourth logical source bank rejected" in p.stdout and "PASS hdmi1080_input_dma directed" in p.stdout
