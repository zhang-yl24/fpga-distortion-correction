"""Independent raster-pixel/CRC oracle for the isolated dual-stripe writer."""
import argparse,hashlib,json,re,sys,time,zlib
from pathlib import Path
import run_hdmi_camera_snapshot_uart_wire_sim as simulator
from simulation_tools import resolve_vivado_bin,prepare_compile_sources,verify_compile_sources
ROOT=Path(__file__).resolve().parents[1]
SELF=Path(__file__).resolve()
RTL='rtl/experimental/ddr_adaptive_result_writer_dualstripe.v'
BENCH='tests/tb_ddr_adaptive_result_writer_dualstripe.sv'
HEADER='rtl/video_crc32.vh'
SCHEMA='ddr-adaptive-result-writer-dualstripe-simulation-v1'
sha=simulator.sha
def pixel(tag,salt):
    r=(tag*17+3+salt*37)%256;g=(tag*7+11+salt*19)%256;b=(tag*29+5+salt*23)%256
    return((r>>3)<<11)|((g>>2)<<5)|(b>>3)
def assess(work,width,height):
    frames={};complete=[];faults=[]
    for line in(work/'writes.txt').read_text().splitlines():
        f=line.split();kind=f[0];case=int(f[1])
        if kind=='BEGIN':frames[case]={'Salt':int(f[2]),'Tiled':bool(int(f[3])),'Data':bytearray(),'Beats':0}
        elif kind=='W':
            salt,index=int(f[2]),int(f[3]);value=int(f[4],16);row=frames[case]
            assert row['Salt']==salt and row['Beats']==index,'independent beat order/identity mismatch'
            data=value.to_bytes(32,'little')
            expected=b''.join(pixel(index*16+n,salt).to_bytes(2,'little')for n in range(16))
            assert data==expected,'independent raster RGB565 oracle mismatch'
            row['Data'].extend(data);row['Beats']+=1
        elif kind=='DONE':
            row=frames[case];data=bytes(row.pop('Data'))
            assert len(data)==width*height*2 and int(f[2],16)==zlib.crc32(data)
            assert row['Beats']==int(f[3])==width*height//16
            complete.append({'Case':case,**row,'RasterPixels':len(data)//2,'CRC32':f[2],
                'IndependentPythonCRC32':f'{zlib.crc32(data):08x}','SameCycleAWFirstW':int(f[4]),
                'OverlapCycles':int(f[5]),'AWStalls':int(f[6]),'WStalls':int(f[7])})
        elif kind=='FAULT':faults.append({'Case':case,'Fault':int(f[2],16),'WrittenBeats':int(f[3])})
        else:raise ValueError('unknown simulation oracle record')
    text=(work/'simulation.log').read_text()
    assert f'PASS dualstripe writer width={width} height={height}'in text and '$finish called'in text
    assert not re.search(r'(?im)^\s*(fatal|error):',text)
    assert len(complete)>=3 and any(r['Tiled']for r in complete)and any(not r['Tiled']for r in complete)
    assert any(r['SameCycleAWFirstW']>0 for r in complete),'same-cycle first W coverage absent across frames'
    return{'CompletedFrames':complete,'FaultScenarios':faults,'IndependentRasterTagPixelCRCOraclePassed':True}
def run(work):
    work=Path(work).resolve();assert work.is_relative_to(ROOT/'work')and not work.exists();work.mkdir(parents=True)
    binary=resolve_vivado_bin(ROOT.parent).resolve()
    inputs={str(ROOT/n):sha(ROOT/n)for n in(RTL,BENCH,HEADER)}
    for p in(SELF,Path(simulator.__file__),ROOT/'tools/simulation_tools.py',Path(sys.executable),
             binary/'xvlog.bat',binary/'xelab.bat',binary/'xsim.bat'):inputs[str(p.resolve())]=sha(p)
    started=time.monotonic();result={'Schema':SCHEMA,'Passed':False,'SourceSHA256':inputs,
        'HardwareAccessed':False,'PDSAccessed':False,'Cases':[]}
    try:
        for width,height,faults in((96,32,1),(1920,24,0),(8,32,0),(16,16,0),(48,16,0)):
            stage=work/f'w{width}-h{height}';stage.mkdir()
            (stage/'dualstripe_writer_config.vh').write_text(f'localparam WIDTH={width},HEIGHT={height},DO_FAULTS={faults};\n')
            compiled,bindings=prepare_compile_sources(ROOT,(RTL,BENCH),(HEADER,),stage)
            for p in compiled:
                if not p.is_relative_to(stage):
                    target=stage/'compiled'/p.relative_to(ROOT);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(p.read_bytes())
            sources=[p if p.is_relative_to(stage)else stage/'compiled'/p.relative_to(ROOT)for p in compiled]
            commands=[('xvlog.bat',['--sv','-i',str(stage),*[str(p)for p in sources]],'compile'),
                ('xelab.bat',['tb_ddr_adaptive_result_writer_dualstripe','-s','dualstripe_writer','--timescale','1ns/1ps'],'elaborate'),
                ('xsim.bat',['dualstripe_writer','-runall','-log','simulation.log'],'simulate')]
            for name,args,label in commands:simulator.tool(binary,name,args,stage,started+300,label)
            verify_compile_sources(ROOT,(RTL,BENCH),(HEADER,),stage,bindings)
            measured=assess(stage,width,height)
            if faults:
                assert len(measured['FaultScenarios'])==9
                assert {r['Fault']for r in measured['FaultScenarios']}=={0x32,2,1,8}
            result['Cases'].append({'Width':width,'Height':height,'FaultCoverageEnabled':bool(faults),**measured})
            print(json.dumps({'Width':width,'Height':height,'Passed':True,'Frames':len(measured['CompletedFrames'])}),flush=True)
        result['Passed']=True
    except BaseException as error:result['Error']=type(error).__name__+': '+str(error)
    result['InputDrift']=[p for p,h in inputs.items()if sha(p)!=h]
    result['Passed']=result['Passed']and not result['InputDrift']
    result['ElapsedSeconds']=round(time.monotonic()-started,3)
    result['Artifacts']={p.relative_to(work).as_posix():sha(p)for p in work.rglob('*')if p.is_file()}
    with(work/'simulation.json').open('x',encoding='utf-8')as out:json.dump(result,out,indent=2);out.write('\n')
    return result
def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--work-dir',type=Path,required=True);args=parser.parse_args()
    result=run(args.work_dir);print(json.dumps({k:result.get(k)for k in('Passed','ElapsedSeconds','InputDrift','Error')}),flush=True)
    return 0 if result['Passed']else 1
if __name__=='__main__':raise SystemExit(main())
