"""One N=0 elaboration rejection; no DUT simulation or hardware."""
from pathlib import Path
import json,sys,time
B=Path(__file__).resolve().parent
sys.path.insert(0,str(B.parent/'night-recovery-edid-20261030-a/wire-progress-a'))
import run_progress as owned
def main():
    w=B/'invalid-a';w.mkdir();start=time.monotonic();r={'ExpectedRejectionObserved':False,'Commands':[],'HardwareAccessed':False,'GateState':owned.GATES}
    try:
        p=owned.power(w);assert p['ACOnline'] and p['BatteryPercent']>35
        for name,argv in [('compile',['E:/Vivado/Vivado/2017.4/bin/xvlog.bat',str(B/'candidate/cfg100_startup_hold.v'),str(B/'candidate/tb_cfg100_invalid.v')]),('elaborate',['E:/Vivado/Vivado/2017.4/bin/xelab.bat','tb_cfg100_invalid','-s','cfg_invalid'])]:
            rec={'Stage':name};r['Commands'].append(rec);code=owned.stage(argv,w,start+60,name,rec)
            if name=='compile':assert code==0
            else:
                log=(w/'elaborate-stdout.log').read_text(encoding='utf-8',errors='replace')+(w/'elaborate-stderr.log').read_text(encoding='utf-8',errors='replace')
                assert code!=0 and 'CFG_SETTLE_CYCLES_MUST_BE_POSITIVE_AND_BOUNDED' in log
                r['ExpectedRejectionObserved']=True
    except Exception as e:r['Error']=type(e).__name__+': '+str(e)
    finally:
        r['WallSeconds']=time.monotonic()-start;r['HoldSHA256']=owned.sha(B/'candidate/cfg100_startup_hold.v');r['EvidenceSHA256']={p.name:owned.sha(p) for p in w.iterdir() if p.is_file()};owned.save(w/'result.json',r)
    print(json.dumps({k:r[k] for k in ('ExpectedRejectionObserved','WallSeconds','Error') if k in r}),flush=True)
    return 0 if r['ExpectedRejectionObserved'] else 1
if __name__=='__main__':raise SystemExit(main())
