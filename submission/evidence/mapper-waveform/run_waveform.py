"""Generate a real, selectively logged VCD from the published KB4 mapper TB.

Only this fresh work directory is written. Existing RTL, fixtures, and old
simulation artifacts are read-only. No PDS, UART, JTAG, or board access.
"""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import shutil
import subprocess
import sys
import time

WORK = Path(__file__).resolve().parent
ROOT = WORK.parents[2]
PROJECT = ROOT/'distortion'
OLD = PROJECT/'work/hdmi-camera-fisheye-20261103-a/mapper-small-b'
sys.path.insert(0, str(PROJECT/'tools'))
import run_hdmi_camera_fisheye_mapper_sim as simulator
from simulation_tools import prepare_compile_sources, verify_compile_sources


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    report = {'schema': 'report-kb4-mapper-waveform-v1', 'Passed': False,
              'StartedUTC': datetime.now(timezone.utc).isoformat(),
              'PublishedCommit': 'a6558c9', 'HardwareAccessed': False, 'PDSAccessed': False,
              'OriginalRTLModified': False, 'OldSimulationDirectoryModified': False,
              'Scope': '32x16 KB4 coordinate mapper unit regression, not full HDMI latency or board FPS'}
    old = json.loads((OLD/'simulation.json').read_text())
    assert old['Passed'] and old['Mode'] == 'small'
    report['ReferenceSimulation'] = {'path': str(OLD/'simulation.json'), 'sha256': sha(OLD/'simulation.json')}
    report['SourceSHA256'] = {}
    names = simulator.COMPILE
    headers = simulator.HEADERS
    for name in (*names, *headers):
        path = PROJECT/name
        raw = subprocess.check_output(['git', 'show', 'a6558c9:distortion/'+name], cwd=ROOT)
        assert raw == path.read_bytes(), name
        assert old['SourceSHA256'][str(path)] == sha(path), name
        report['SourceSHA256'][name] = sha(path)
    for name in ('corrected.mem', 'identity.mem', 'domain.mem'):
        assert sha(OLD/name) == old['Artifacts'][name]
        assert not (WORK/name).exists()
        shutil.copyfile(OLD/name, WORK/name)
    compiled, bindings = prepare_compile_sources(PROJECT, names, headers, WORK)
    report['IncludeRelocations'] = bindings
    binary = Path(old['VivadoBin'])
    report['VivadoBin'] = str(binary)
    signals = ['clk','rst','cfg_valid','cfg_ready','cfg_corrected','in_valid','in_ready',
               'in_u','in_v','in_tag','out_valid','out_ready','out_x','out_y','out_tag',
               'out_black','phase','sent','received','stall_cycles','hold_checks']
    scope = '/tb_hdmi_camera_fisheye_mapper_small/test_case/'
    tcl = ['open_vcd mapper.vcd']
    tcl += ['log_vcd [get_objects {'+scope+name+'}]' for name in signals]
    tcl += ['run -all', 'close_vcd', 'exit']
    (WORK/'waveform.tcl').write_text('\n'.join(tcl)+'\n', encoding='ascii')
    commands = [('xvlog.bat', ['--sv', *[str(p) for p in compiled]], 'compile'),
                ('xelab.bat', ['tb_hdmi_camera_fisheye_mapper_small', '-s', 'report_mapper',
                               '-debug', 'typical', '--timescale', '1ns/1ps'], 'elaborate'),
                ('xsim.bat', ['report_mapper', '-tclbatch', 'waveform.tcl', '-log', 'simulation.log'], 'simulate')]
    report['Commands'] = [{'tool': str(binary/name), 'argv': args, 'stage': stage} for name,args,stage in commands]
    started = time.monotonic()
    try:
        for name,args,stage in commands:
            simulator.tool(binary,name,args,WORK,started+180,stage)
        verify_compile_sources(PROJECT,names,headers,WORK,bindings)
        report['Summary'] = simulator.validate_log('small',(WORK/'simulation.log').read_text(encoding='utf-8'))
        assert report['Summary'] == old['Summary']
        assert (WORK/'mapper.vcd').stat().st_size > 1000
        report['VCD'] = {'path': 'mapper.vcd', 'bytes': (WORK/'mapper.vcd').stat().st_size,
                         'sha256': sha(WORK/'mapper.vcd'), 'Signals': signals}
        report['InputDrift'] = [name for name,h in report['SourceSHA256'].items() if sha(PROJECT/name)!=h]
        assert not report['InputDrift']
        report['Passed'] = True
    except BaseException as error:
        report['Error'] = repr(error)
    report['ElapsedSeconds'] = time.monotonic()-started
    report['Artifacts'] = {p.relative_to(WORK).as_posix():sha(p) for p in WORK.rglob('*')
                           if p.is_file() and p.name!='waveform-run.json'}
    (WORK/'waveform-run.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({k:report.get(k) for k in ('Passed','Summary','VCD','Error','ElapsedSeconds')},indent=2))
    return 0 if report['Passed'] else 1


if __name__=='__main__':
    raise SystemExit(main())
