"""Current CE candidate paired RTL, unchanged real FIFO and pixel/CRC oracle."""
from pathlib import Path
import json,re,sys,time,subprocess
B=Path(__file__).resolve().parent;OFF=B.parent
sys.path.insert(0,str(OFF/'night-recovery-edid-20261030-a/wire-progress-a'))
import run_progress as owned
def main():
    work=B/'directed-b';work.mkdir();start=time.monotonic();deadline=start+120
    c=json.loads((B/'candidate/board-source-closure.json').read_text())
    bound=dict(c['SourceSHA256']);bound.update(json.loads((OFF/'penn-pcf-validate-20261029-a/admission.json').read_text())['FrozenInputsSHA256'])
    for p in [Path(__file__),B/'candidate/tb_ce_scan_v2.sv',B/'candidate/board-source-closure.json',B/'reference/ddr_video_output_1080_reference.v',B/'candidate/preparation.json',B/'extra_cases.sv.part']:bound[str(p)]=owned.sha(p)
    assert not owned.stable(bound),'input drift'
    p=owned.power(work);assert p['ACOnline'] and p['BatteryPercent'] is not None and p['BatteryPercent']>35
    conflict=subprocess.run(['powershell.exe','-NoProfile','-Command','Get-Process -Name pds_shell,pds_shell_64,xsim,xelab,xvlog -ErrorAction SilentlyContinue | Select-Object Id,ProcessName | ConvertTo-Json -Compress'],capture_output=True,timeout=15,creationflags=subprocess.CREATE_NO_WINDOW);assert not conflict.stdout.strip()
    r={'Marker':'CFG100-1030-CE-CANDIDATE-ONE','Passed':False,'StartedUtc':owned.stamp(),'MaximumToolSeconds':120,'CleanupSeconds':30,'PowerBefore':p,'InputsSHA256Before':bound,'Commands':[],'HardwareAccessed':False,'GateState':owned.GATES,'ReferenceScope':'old module rename only, test side not production','IndependentOracle':'existing serialCRC/RGB565/realFIFO latency scoreboard unchanged'}
    owned.save(work/'admission.json',r)
    src=[B/'candidate/ddr_video_output_1080_board_ce.v',B/'reference/ddr_video_output_1080_reference.v',Path(c['ModuleNames']['video_async_fifo']),B/'candidate/tb_ce_scan_v2.sv']
    cmds=[('compile',['E:/Vivado/Vivado/2017.4/bin/xvlog.bat','--sv',*[str(q) for q in src]]),('elaborate',['E:/Vivado/Vivado/2017.4/bin/xelab.bat','tb_board1080_scan','-s','ce_scan']),('simulate',['E:/Vivado/Vivado/2017.4/bin/xsim.bat','ce_scan','-runall','-log','simulation.log'])]
    try:
        for name,argv in cmds:
            rec={'Stage':name};r['Commands'].append(rec)
            if owned.stage(argv,work,deadline,name,rec)!=0:raise RuntimeError(name+' native failure')
        log=(work/'simulation.log').read_text(encoding='utf-8',errors='replace')
        assert not re.search(r'(?m)^(Fatal|Error):',log),'RTL assertion failure'
        assert 'CE_EXTENSION_PASS cases=28 extra=19 collisions=5 legal_abort=1' in log
        assert 'PASS board1080 scan: independent RGB565/CRC' in log
        s=json.loads((work/'summary.json').read_text());assert s['passed'] and s['cases']==28 and s['good_frames']==24
        r.update(Passed=True,Summary=s)
    except (Exception,KeyboardInterrupt) as e:r['Error']=type(e).__name__+': '+str(e)
    finally:
        r['InputDrift']=owned.stable(bound);r['Passed']=r['Passed'] and not r['InputDrift'];r['WallSeconds']=time.monotonic()-start;r['EndedUtc']=owned.stamp();r['EvidenceSHA256']={p.name:owned.sha(p) for p in work.iterdir() if p.is_file()};owned.save(work/'result.json',r)
    print(json.dumps({k:r[k] for k in ('Passed','WallSeconds','Summary','Error','InputDrift') if k in r}),flush=True)
    return 0 if r['Passed'] else 1
if __name__=='__main__':raise SystemExit(main())
