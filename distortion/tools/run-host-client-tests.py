"""Record guarded host-client tests using mocked UART/idle calls exclusively."""
from pathlib import Path
import hashlib,json,subprocess,sys
root=Path(__file__).resolve().parents[1];work=root/'build/host_control_sim'
files=['model/host_protocol.py','tools/host-angle.py','tests/test_host_protocol.py','tests/test_host_cli.py']
hashes={p:hashlib.sha256((root/p).read_bytes()).hexdigest() for p in files}
run=subprocess.run([sys.executable,'-m','unittest','tests.test_host_protocol','tests.test_host_cli','-v'],cwd=root,capture_output=True,text=True)
log=run.stdout+run.stderr;(work/'client-tests.log').write_text(log,encoding='utf-8')
assert run.returncode==0 and 'Ran 12 tests' in log and '\nOK\n' in log,log
assert all(hashlib.sha256((root/p).read_bytes()).hexdigest()==v for p,v in hashes.items())
result={'passed':True,'tests_passed':12,'hardware_accessed':False,'source_sha256':hashes,
    'test_log_sha256':hashlib.sha256((work/'client-tests.log').read_bytes()).hexdigest(),
    'limits':'UART and heartbeat subprocesses are mocked. Confirms packet compatibility, readiness guard, one-write/no-retry behavior, fresh completed-frame acknowledgement and finally-idle invocation; actual CP2102 writes and heartbeat recovery still require hardware.'}
(root/'results/lab-20261007/host-client-check.json').write_text(json.dumps(result,indent=2)+'\n')
print('PASS 12 host protocol/client tests; no UART or real subprocess idle accessed.')
