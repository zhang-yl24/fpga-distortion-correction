"""Single root-owned bounded TX49 test; no expired night deadline/hardware access."""
from pathlib import Path
import csv, importlib.util, json, re, subprocess, sys, time
from datetime import datetime,timezone
B=Path(__file__).resolve().parent
TX=B.parent/'tx49-preamble-20261030-a'
sys.path.insert(0,str(TX))
OLD=B.parent/'night-recovery-edid-20261030-a'
sys.path.insert(0,str(OLD/'wire-progress-a'))
import run_progress as owned
from wire_contract import assess
sha=owned.sha;save=owned.save
def inputs():
    m=json.loads((B/'candidate/wire-source-manifest-v2.json').read_text())
    bound=json.loads((B.parent/'penn-pcf-validate-20261029-a/admission.json').read_text())['FrozenInputsSHA256']
    bound.update({v['path']:v['sha256'] for v in m['sources'].values()})
    for p in [B/'boundary-b/result.json',B/'invalid-a/result.json',Path(__file__),TX/'wire_contract.py',TX/'guard-selfcheck-v2/result.json',TX/'guard-selfcheck/result.json',OLD/'wire-progress-a/run_progress.py',OLD/'wrapper-verify/run_wrapper_sim.py',B/'candidate/wire-source-manifest-v2.json',*sorted((B/'candidate').glob('*'))]:
        if p.is_file():bound[str(p)]=sha(p)
    return m,bound
def commands(bench,top,snapshot):
    m,_=inputs();bin=Path('E:/Vivado/Vivado/2017.4/bin')
    src=[m['sources'][r]['path'] for r in m['compile_roles']]
    return [('compile-verilog',[str(bin/'xvlog.bat'),'--relax',*src]),
            ('compile-bench',[str(bin/'xvlog.bat'),'--sv',str(TX/'candidate/tx49_wire_edge_guard.sv'),str(bench)]),
            ('elaborate',[str(bin/'xelab.bat'),top,'-s',snapshot])]
def run():
    work=B/'wire-a';work.mkdir()
    begin=time.monotonic();deadline=begin+300
    m,bound=inputs();assert not owned.stable(bound),'input drift before run'
    first=owned.power(work);assert first['BatteryPercent'] is not None and first['BatteryPercent']>35,'power rejected'
    assert first['ACOnline'],'fresh AC admission rejected'
    conflict=subprocess.run(['powershell.exe','-NoProfile','-Command','Get-Process -Name pds_shell,pds_shell_64,xsim,xelab,xvlog,vsim,vvp,iverilog -ErrorAction SilentlyContinue | Select-Object Id,ProcessName | ConvertTo-Json -Compress'],capture_output=True,timeout=15,creationflags=subprocess.CREATE_NO_WINDOW)
    assert not conflict.stdout.strip(),'visible EDA conflict'
    r={'Marker':'CFG100-1030-INDEPENDENT-ONE','StartedUtc':owned.stamp(),'Passed':False,'ObservationComplete':False,'MaximumToolSeconds':300,'CleanupReserveSeconds':30,'MaximumWholeSeconds':330,'ToolDeadlineUtc':datetime.fromtimestamp(time.time()+300,timezone.utc).isoformat(),'BudgetReason':'parent strict2epoch68.169s for7.132M cycles; new2M startup periods estimate87..120s; budget300tool+30cleanup, real10MHz/TX WAIT3199897 unchanged','PowerBefore':first,'Commands':[],'HardwareAccessed':False,'PDSAccessed':False,'SyntheticSlaveStimulus':True,'GateState':owned.GATES}
    save(work/'admission.json',{**r,'InputsSHA256Before':bound,'ActualVerilogRoles':m['compile_roles'],'ActualSVSources':[str(TX/'candidate/tx49_wire_edge_guard.sv'),str(B/'candidate/tb_ms72xx_cfg100_wire_v2.sv')],'VisibleEDAConflicts':[],'QueueCompleteState':'UNKNOWN'})
    print(json.dumps({'StartedUtc':r['StartedUtc'],'Work':str(work),'ToolBudgetSeconds':300,'WholeBudgetSeconds':330,'Power':first}),flush=True)
    try:
        boundary=json.loads((B/'boundary-b/result.json').read_text())
        assert boundary['Passed'] and not boundary['InputDrift']
        invalid=json.loads((B/'invalid-a/result.json').read_text())
        assert invalid['ExpectedRejectionObserved']
        guard_check=json.loads((TX/'guard-selfcheck-v2/result.json').read_text())
        assert guard_check['Passed'] and guard_check['GuardSHA256']==sha(TX/'candidate/tx49_wire_edge_guard.sv'),'guard rejection admission'
        assert guard_check['BenchSHA256']==sha(TX/'candidate/tb_edge_guard_negative.sv')
        for name,h in m['goldens'].items():
            p=OLD/'wrapper-verify'/name;assert sha(p)==h
            with (work/name).open('xb') as f:f.write(p.read_bytes())
        cmds=commands(B/'candidate/tb_ms72xx_cfg100_wire_v2.sv','tb_ms72xx_legacy_wire','cfg100_wire')
        cmds.append(('simulate',['E:/Vivado/Vivado/2017.4/bin/xsim.bat','cfg100_wire','-runall','-log','simulation.log']))
        for name,argv in cmds:
            rec={'Stage':name};r['Commands'].append(rec)
            if owned.stage(argv,work,deadline,name,rec)!=0:raise RuntimeError(name+' native failure')
        log=(work/'simulation.log').read_text(encoding='utf-8',errors='replace')
        assert 'MS72XX_CFG100_WIRE_OBSERVATIONS_COMPLETE overall_pass=1' in log
        assert not re.search(r'(?im)^\s*(fatal|error):',log),'RTL failure'
        read=lambda n:list(csv.DictReader((work/n).open(newline='')))
        rows=read('wire-transactions.csv');epochs=read('epoch-summary.csv');events=read('wire-events.csv')
        g25={int(e):int(t) for e,t in re.findall(r'CFG100_G25_RELEASE epoch=(\d+) time_ns=(\d+)',log)}
        arms={int(e):int(t) for e,t in re.findall(r'CFG100_ARM epoch=(\d+) time_ns=(\d+)',log)}
        releases={int(e):int(t) for e,t in re.findall(r'CFG100_CONFIG_RELEASE epoch=(\d+) time_ns=(\d+)',log)}
        assert set(g25)==set(arms)==set(releases)=={1,2}
        timing=[]
        for e in (1,2):
            first=min(int(x['time_ns']) for x in events if int(x['epoch'])==e and x['event']=='START')
            assert releases[e]-arms[e]==100000000 and releases[e]-g25[e]>=100000000 and first>releases[e]
            timing.append({'Epoch':e,'G25ReleaseNs':g25[e],'ArmedNs':arms[e],'ConfigReleaseNs':releases[e],'FirstActualIICStartNs':first,'FullPeriods':1000000,'ArmedToReleaseNs':releases[e]-arms[e],'RawReleaseToFirstStartNs':first-g25[e]})
        r.update(IndependentContract=assess(rows,epochs,events),Epochs=epochs,TransactionCount=len(rows),RawEventCount=len(events),CFGTiming=timing,ObservationComplete=True,Passed=True)
    except (Exception,KeyboardInterrupt) as e:r['Error']=type(e).__name__+': '+str(e)
    finally:
        r['InputDrift']=owned.stable(bound);r['VectorDrift']=[n for n,h in m['goldens'].items() if not(work/n).is_file() or sha(work/n)!=h]
        r['Passed']=r['Passed'] and not r['InputDrift'] and not r['VectorDrift']
        r['EndedUtc']=owned.stamp();r['ElapsedSeconds']=time.monotonic()-begin;r['PowerAfter']=owned.power(work)
        r['EvidenceSHA256']={p.name:sha(p) for p in work.iterdir() if p.is_file()}
        save(work/'result.json',r)
    print(json.dumps({k:r[k] for k in ('Passed','ObservationComplete','TransactionCount','ElapsedSeconds','Error') if k in r}),flush=True)
    return 0 if r['Passed'] else 1
if __name__=='__main__':raise SystemExit(run())
