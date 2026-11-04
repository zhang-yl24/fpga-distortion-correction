"""Single bounded TX49 board frontend compile; no synthesis/PNR/hardware."""
from pathlib import Path
from datetime import datetime,timezone
import ctypes,hashlib,json,os,re,subprocess,time
from ctypes import wintypes
ROOT=Path(__file__).resolve().parent;B=ROOT/'compile-a';OFF=ROOT.parent
TX=OFF/'tx49-preamble-20261030-a';N=OFF/'night-recovery-edid-20261030-a'
SHELL=Path('E:/Pango/PDS_2022.2-SP6.4/bin/pds_shell.exe')
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
load=lambda p:json.loads(Path(p).read_text(encoding='utf-8-sig'))
stamp=lambda:datetime.now(timezone.utc).isoformat()
def save(p,d):
    with Path(p).open('x',encoding='utf-8') as f:json.dump(d,f,indent=2);f.write('\n')
class Power(ctypes.Structure):
    _fields_=[('AC',wintypes.BYTE),('Flags',wintypes.BYTE),('Percent',wintypes.BYTE),('Reserved',wintypes.BYTE),('Life',wintypes.DWORD),('FullLife',wintypes.DWORD)]
def power():
    p=Power()
    if not ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(p)):raise ctypes.WinError()
    d={'Utc':stamp(),'ACOnline':p.AC==1,'ACCode':p.AC,'BatteryPercent':None if p.Percent==255 else int(p.Percent)}
    with (B/'power.jsonl').open('a',encoding='utf-8') as f:f.write(json.dumps(d)+'\n');f.flush()
    return d
def drift(inputs):return [p for p,h in inputs.items() if not Path(p).is_file() or sha(p)!=h]
def main():
    assert not B.exists(),'consumed run cannot be reused'
    B.mkdir();start=time.monotonic();deadline=start+900;epoch=time.time()
    c=load(ROOT/'candidate/board-source-closure-v2.json');receipt=load(TX/'delivery-receipt.json');r=load(TX/'run-b/result.json')
    assert receipt['Passed'] and r['Passed'] and r['ObservationComplete'] and r['TransactionCount']==744
    assert not r['InputDrift'] and not r['VectorDrift'] and all(x['NativeExitCode']==0 and x['OwnedProcessExited'] for x in r['Commands'])
    assert c['RoleCount']==111 and c['AddDesignCount']==33 and len(c['Roles'])==111 and len(c['AddDesign'])==33
    tx=str(TX/'candidate/ms7210_ctl.v');rx=str(N/'edid/ms7200_1080p30_ctl.v')
    assert c['ModuleNames']['ms7210_ctl']==tx and c['ModuleNames']['ms7200_ctl']==rx
    assert sha(tx)=='04a91cb0713a0ab49f56ec9f3b06b4a858e60c0c1d87111151f630ab7ec419c2'
    assert sha(rx)=='e5055d02e8f7af1c4c3efc151f0a71f2ed50216e55c6f95e3ac4c3f74368b21e'
    assert all(v is False for v in c['GateState'].values())
    current_wire=load(ROOT/'wire-a/result.json')
    assert current_wire['Passed'] and current_wire['ObservationComplete'] and current_wire['TransactionCount']==744
    assert not current_wire['InputDrift'] and not current_wire['VectorDrift']
    assert len(current_wire['CFGTiming'])==2 and all(e['ArmedToReleaseNs']==100000000 for e in current_wire['CFGTiming'])
    assert load(ROOT/'boundary-b/result.json')['Passed'] and load(ROOT/'invalid-a/result.json')['ExpectedRejectionObserved']
    tcl=ROOT/'candidate/compile-cfg100-v2.tcl';text=tcl.read_text()
    design=re.findall(r'^add_design \{([^}]+)\}$',text,re.M)
    assert [str(Path(p)) for p in design]==c['AddDesign']
    assert len(set(design))==33 and tx.replace('\\','/') in design
    assert not any(p.endswith('/source/hdmi/ms7210_ctl.v') for p in design)
    for k in ('cfg100_startup_hold','ms72xx_cfg100_ctl','iic_dri_cfg100_reset'):
        assert c['ModuleNames'][k].replace('\\','/') in design
    assert not any(p.endswith('/source/hdmi/ms72xx_ctl.v') or p.endswith('/source/hdmi/iic_dri.v') for p in design)
    assert len(re.findall(r'^compile -top_module board1080_top$',text,re.M))==1
    active=[s.strip() for s in text.splitlines() if s.strip() and not s.lstrip().startswith('#')]
    assert all(s.startswith(('add_design {','add_constraint {','set_arch -family Logos2 ','compile -top_module board1080_top')) for s in active)
    fdc=re.findall(r'^add_constraint \{([^}]+)\}$',text,re.M);assert len(fdc)==1 and sha(fdc[0])==c['UnchangedFDCSHA256']
    assert 'PG2L100H -speedgrade -6 -package FBG676' in text
    protected=load(OFF/'penn-pcf-validate-20261029-a/admission.json')['FrozenInputsSHA256']
    assert len(protected)==421
    bound=dict(protected);bound.update(c['SourceSHA256']);bound.update(receipt['FilesSHA256']);bound.update(load(TX/'run-b/admission.json')['InputsSHA256Before'])
    bound.update(load(ROOT/'wire-a/admission.json')['InputsSHA256Before'])
    for p in (ROOT/'wire-a/result.json',ROOT/'boundary-b/result.json',ROOT/'invalid-a/result.json',ROOT/'candidate/board-source-closure-v2.json',ROOT/'b-closure-review/repair-closure-review.json',ROOT/'a-contract-review/repair-review.json',Path(__file__),SHELL,tcl,TX/'delivery-receipt.json',TX/'final-readback.json',TX/'a-wire-review/actual-run-review.json',TX/'board-source-closure.json',N/'compile-budget-a/run_compile.py',N/'compile-budget-a/run-a/result.json'):
        bound[str(p)]=sha(p)
    assert not drift(bound),'bound source/closure/result drift'
    p=power();assert p['ACOnline'] and p['BatteryPercent'] is not None and p['BatteryPercent']>=35,'fresh AC/power admission rejected'
    ps=subprocess.run(['powershell.exe','-NoProfile','-Command','Get-Process -Name pds_shell,pds_shell_64,xsim,xelab,xvlog,vsim,vvp,iverilog -ErrorAction SilentlyContinue | Select-Object Id,ProcessName | ConvertTo-Json -Compress'],capture_output=True,timeout=15,creationflags=subprocess.CREATE_NO_WINDOW)
    assert not ps.stdout.strip(),'visible EDA conflict'
    work=B/'compile-work';work.mkdir()
    argv=[str(SHELL),'-file',str(tcl),'-work_dir',str(work),'-project_name','cfg100_penn_board']
    rec={'Marker':'CFG100-1030-INDEPENDENT-ONE','Stage':'compile-only','Argv':argv,'Cwd':str(work),'StartedUtc':stamp(),'NativeExitCode':None,'MaximumToolSeconds':900,'CleanupReserveSeconds':30,'MaximumWholeSeconds':930,'ToolDeadlineUtc':datetime.fromtimestamp(epoch+900,timezone.utc).isoformat(),'HardCleanupBoundaryUtc':datetime.fromtimestamp(epoch+930,timezone.utc).isoformat(),'PowerBefore':p,'GateState':c['GateState'],'HardwareAccessed':False,'SynthesisOrPNRExecuted':False,'QueueCompleteState':'UNKNOWN','BudgetBasis':'parent TX49 frontend68.916s; new hold20bit counter plus reset-only wrapper/driver;900s tool plus30s cleanup. Current CFG100 boundary and744-wire PASS required.'}
    save(B/'admission.json',{**rec,'InputsSHA256Before':bound,'ProtectedInputCount':421,'SourceRoles':c['Roles'],'AddDesign':c['AddDesign'],'VisibleEDASnapshot':ps.stdout.decode(errors='replace'),'ExactTXSHA256':sha(tx),'ExactRXSHA256':sha(rx),'FDCSHA256':sha(fdc[0]),'TclSHA256':sha(tcl)})
    child=None;last=0
    try:
        with (B/'stdout.log').open('xb') as out,(B/'stderr.log').open('xb') as err:
            child=subprocess.Popen(argv,cwd=work,stdin=subprocess.DEVNULL,stdout=out,stderr=err,creationflags=subprocess.CREATE_NO_WINDOW)
            rec['OwnedPID']=child.pid;save(B/'launch.json',rec)
            print(json.dumps({'StartedUtc':stamp(),'OwnedPID':child.pid,'Argv':argv,'ToolSeconds':900,'WholeSeconds':930,'Power':p}),flush=True)
            while child.poll() is None:
                if time.monotonic()>=deadline:raise TimeoutError('900s compile-only tool deadline')
                if time.monotonic()-last>=5:
                    p=power();last=time.monotonic()
                    if p['BatteryPercent'] is None or p['BatteryPercent']<=30:raise RuntimeError('low/unknown power: save and stop own tree')
                    tail=(B/'stdout.log').read_text(encoding='utf-8',errors='replace').splitlines()[-8:]
                    native=work/'compile/run.log'
                    (B/'progress.json').write_text(json.dumps({'Utc':stamp(),'ElapsedSeconds':time.monotonic()-start,'Power':p,'LogTail':tail,'NativeCompileTail':native.read_text(encoding='utf-8',errors='replace').splitlines()[-12:] if native.is_file() else []},indent=2)+'\n',encoding='utf-8')
                time.sleep(1)
            rec['NativeExitCode']=child.returncode
    except BaseException as e:rec['Error']=type(e).__name__+': '+str(e)
    finally:
        if child is not None and child.poll() is None:
            try:
                k=subprocess.run([str(Path(os.environ.get('SystemRoot','C:/Windows'))/'System32/taskkill.exe'),'/PID',str(child.pid),'/T','/F'],capture_output=True,timeout=15,creationflags=subprocess.CREATE_NO_WINDOW)
                rec['OwnedCleanup']={'ExitCode':k.returncode,'Stdout':k.stdout.decode(errors='replace'),'Stderr':k.stderr.decode(errors='replace')};child.wait(timeout=10)
            except BaseException as e:rec['CleanupError']=type(e).__name__+': '+str(e)
            rec['NativeExitCode']=child.poll()
        rec['EndedUtc']=stamp();rec['WallSeconds']=time.monotonic()-start;rec['PowerAfter']=power()
        stdout=(B/'stdout.log').read_text(encoding='utf-8',errors='replace') if (B/'stdout.log').exists() else ''
        rec['ErrorLines']=[l for l in stdout.splitlines() if re.match(r'^\s*(E:|F:|ERROR|FATAL)',l)]
        rec['UnexpectedStages']=re.findall(r'(?m)^Executing : (synthesize|dev_map|pnr|gen_bit_stream|report_timing)\b',stdout)
        rec['InputsDriftAfter']=drift(bound);rec['ProtectedInputsUnchanged']=not rec['InputsDriftAfter'];rec['OwnedProcessExited']=child is None or child.poll() is not None
        rec['CompileLogExists']=(work/'compile/run.log').is_file();rec['CompileCommandObserved']=bool(re.search(r'Executing\s*:\s*compile\b',stdout))
        rec['CompileSuccessMarker']='Executing : compile -top_module board1080_top successfully.' in stdout
        rec['CompileOnlyPassed']=rec['CompileSuccessMarker'] and rec['NativeExitCode']==0 and 'Error' not in rec and 'CleanupError' not in rec and not rec['ErrorLines'] and not rec['UnexpectedStages'] and rec['CompileLogExists'] and rec['CompileCommandObserved'] and rec['ProtectedInputsUnchanged'] and rec['OwnedProcessExited']
        db=work/'compile/board1080_top_comp.adf'
        rec['CompiledDB']={'Path':str(db),'Exists':db.is_file(),'SHA256':sha(db) if db.is_file() else None,'Bytes':db.stat().st_size if db.is_file() else None,'RoutedFinalSTA':False}
        rec['EvidenceSHA256']={str(q.relative_to(B)):sha(q) for q in B.rglob('*') if q.is_file() and q.suffix.lower() in ('.log','.tcl','.jsonl')}
        save(B/'result.json',rec)
        print(json.dumps({k:rec[k] for k in ('CompileOnlyPassed','NativeExitCode','WallSeconds','CompiledDB','ErrorLines','Error') if k in rec}),flush=True)
    return 0 if rec['CompileOnlyPassed'] else 1
if __name__=='__main__':raise SystemExit(main())
