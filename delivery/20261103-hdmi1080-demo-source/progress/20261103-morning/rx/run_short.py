"""Official installed XSim functional test only; use approved sandbox-external entrance."""
from pathlib import Path
import hashlib,json,os,subprocess,sys,time
sys.dont_write_bytecode=True
ROOT=Path(__file__).resolve().parent
BIN=Path(os.environ['FPGA_VIVADO_BIN']).resolve(strict=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def verify():
    rows=json.loads((ROOT/'MANIFEST.json').read_text())['files']
    for row in rows:
        p=ROOT/row['path'];assert p.stat().st_size==row['bytes'] and sha(p)==row['sha256'],row['path']
    return len(rows)
def stage(work,name,exe,args):
    quote=lambda x:"'"+str(x).replace("'","''")+"'"
    script=work/(name+'.ps1');script.write_text('& '+quote(BIN/exe)+' '+' '.join(map(quote,args))+'\nexit $LASTEXITCODE\n',encoding='utf-8')
    t=time.monotonic()
    with (work/(name+'.log')).open('wb') as log:
        p=subprocess.Popen(['powershell.exe','-NoProfile','-NonInteractive','-File',str(script)],cwd=work,
             stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,
             creationflags=subprocess.CREATE_NEW_PROCESS_GROUP|subprocess.CREATE_NO_WINDOW)
        try:code=p.wait(timeout=(180 if name=='simulate' else 30))
        except BaseException:
            try:subprocess.run(['taskkill','/PID',str(p.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=5,creationflags=subprocess.CREATE_NO_WINDOW)
            finally:
                if p.poll() is None:p.kill()
                p.wait(timeout=3)
            raise
    row={'stage':name,'exit':code,'seconds':round(time.monotonic()-t,3),'timeout_seconds':180 if name=='simulate' else 30}
    print(json.dumps(row),flush=True)
    assert code==0,(name,(work/(name+'.log')).read_text(errors='replace')[-5000:])
    return row
def main():
    checked=verify();work=ROOT/'results'/('xsim_'+time.strftime('%Y%m%d_%H%M%S',time.gmtime()))
    work.mkdir(parents=True,exist_ok=False)
    result={'status':'RUNNING','tool_bin':str(BIN),'verified_files':checked,'stages':[],
       'synthesis_map_pnr_sta_hardware_upload':False,'source_manifest_sha256':sha(ROOT/'MANIFEST.json')}
    rc=0
    try:
        assert os.name=='nt' and all((BIN/n).is_file() for n in ['xvlog.bat','xelab.bat','xsim.bat'])
        sources=[ROOT/'rtl/measurement_rx_router.sv',*sorted((ROOT/'deps').rglob('*.v')),*sorted((ROOT/'deps').rglob('*.sv')),
                 ROOT/'candidate/telemetry_uart_link.sv',ROOT/'tests/telemetry_uart_link_before.sv',ROOT/'tests/tb_measurement_rx.sv']
        include=[ROOT/'tests',ROOT/'deps/b4/rtl',ROOT/'deps/b4/rtl/reuse']
        args=['--sv']
        for path in include:args+=['-i',str(path)]
        result['stages'].append(stage(work,'compile','xvlog.bat',args+list(map(str,sources))))
        result['stages'].append(stage(work,'elaborate','xelab.bat',['tb_measurement_rx','-s','measurement_rx','-mt','off']))
        result['stages'].append(stage(work,'simulate','xsim.bat',['measurement_rx','-runall','-log','simulation.log']))
        log=(work/'simulate.log').read_text(errors='replace')
        assert log.count('MEASUREMENT_RX_ROUTING_PASS')==1 and 'Fatal:' not in log and 'FATAL' not in log
        markers=['PASS_CONTIGUOUS_UART_EMBEDDED_MAGIC_BOTH_DIRECTIONS','PASS_ORIGINAL_PARSER_CRC_AND_SCHEMA_REJECTION',
                 'PASS_TRUNCATED_PARTIAL_MAGIC_TIMEOUT_AND_COMMON_RESET','PASS_PHYSICAL_RX_ERROR_RECOVERY_AND_DISABLED_RAW_ALIAS',
                 'PASS_ONE_BYTE_PER_CLOCK_NO_REPLAY_GAP']
        assert all(log.count(x)==1 for x in markers)
        result.update(status='PASS',markers=markers,simulation_log_sha256=sha(work/'simulation.log'),commands_sha256=sha(work/'commands.csv'))
    except BaseException as error:
        rc=1;result.update(status='FAIL_OR_INCOMPLETE',error=repr(error));print(repr(error),flush=True)
    finally:
        try:result['postcheck_verified_files']=verify()
        except BaseException as error:rc=1;result.update(status='FAIL_OR_INCOMPLETE',postcheck_error=repr(error))
        (work/'RESULT.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'status':result['status'],'result':str(work/'RESULT.json')}),flush=True)
    return rc
if __name__=='__main__':raise SystemExit(main())
