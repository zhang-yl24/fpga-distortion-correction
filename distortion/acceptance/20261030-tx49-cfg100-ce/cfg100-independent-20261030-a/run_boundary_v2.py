"""Bounded new reset boundary test, actual default counter and real old IIC."""
from pathlib import Path
import json,re,sys,time
B=Path(__file__).resolve().parent;OFF=B.parent
sys.path.insert(0,str(OFF/'night-recovery-edid-20261030-a/wire-progress-a'))
import run_progress as owned
def main():
    work=B/'boundary-b';work.mkdir();start=time.monotonic();deadline=start+120
    m=json.loads((B/'candidate/wire-source-manifest-v2.json').read_text())
    bound={v['path']:v['sha256'] for v in m['sources'].values()}
    bound.update(json.loads((OFF/'penn-pcf-validate-20261029-a/admission.json').read_text())['FrozenInputsSHA256'])
    for p in [Path(__file__),B/'candidate/tb_cfg100_boundary_v2.sv',B/'candidate/wire-source-manifest-v2.json']:bound[str(p)]=owned.sha(p)
    assert not owned.stable(bound)
    power=owned.power(work);assert power['ACOnline'] and power['BatteryPercent'] is not None and power['BatteryPercent']>35
    r={'Passed':False,'StartedUtc':owned.stamp(),'ToolSeconds':120,'CleanupSeconds':30,'PowerBefore':power,'InputsSHA256':bound,'Commands':[],'HardwareAccessed':False,'GateState':owned.GATES}
    owned.save(work/'admission.json',r)
    src=[m['sources'][k]['path'] for k in m['compile_roles']]
    cmds=[('compile',['E:/Vivado/Vivado/2017.4/bin/xvlog.bat','--relax',*src]),('bench',['E:/Vivado/Vivado/2017.4/bin/xvlog.bat','--sv',str(B/'candidate/tb_cfg100_boundary_v2.sv')]),('elaborate',['E:/Vivado/Vivado/2017.4/bin/xelab.bat','tb_cfg100_boundary','-s','cfg_boundary']),('simulate',['E:/Vivado/Vivado/2017.4/bin/xsim.bat','cfg_boundary','-runall','-log','simulation.log'])]
    try:
        for stage,argv in cmds:
            rec={'Stage':stage};r['Commands'].append(rec)
            if owned.stage(argv,work,deadline,stage,rec)!=0:raise RuntimeError(stage+' native failure')
        log=(work/'simulation.log').read_text(encoding='utf-8',errors='replace')
        assert 'CFG_BOUNDARY_PASS' in log and 'CFG_DEFAULT_MEASURED periods=1000000 period_ns=100 elapsed_ns=100000000' in log,'boundary coverage missing'
        assert not re.search(r'(?m)^(Fatal|Error):',log),'RTL assertion failure'
        r['Passed']=True
    except (Exception,KeyboardInterrupt) as e:r['Error']=type(e).__name__+': '+str(e)
    finally:
        r['InputDrift']=owned.stable(bound);r['Passed']=r['Passed'] and not r['InputDrift'];r['WallSeconds']=time.monotonic()-start
        r['EvidenceSHA256']={p.name:owned.sha(p) for p in work.iterdir() if p.is_file()};owned.save(work/'result.json',r)
    print(json.dumps({k:r[k] for k in ('Passed','WallSeconds','Error','InputDrift') if k in r}),flush=True)
    return 0 if r['Passed'] else 1
if __name__=='__main__':raise SystemExit(main())
