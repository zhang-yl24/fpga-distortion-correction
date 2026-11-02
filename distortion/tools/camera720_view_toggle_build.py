"""Prepare/build the KEY1 raw/corrected candidate; never program hardware.

The complete frozen C source closure is copied into a fresh directory. Existing
physical acceptance is not inherited. Native execution is bounded and hidden.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time

import run_camera_vga_output_diagnostic as cleanup

ROOT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()
WORK = ROOT / 'work/camera720-view-toggle'
BASE = ROOT / 'work/camera720-stats-delay/build-c'
BASE_SHA = '2a263c20d7c3b5ebc0c2796bcac8bf2a3bf8380793283f0dcd1c8d2c0d405d08'
OLD = 'camera720_calibrated_stats_delay_top'
TARGET = 'camera720_view_toggle_top'
TOP = 'board/' + TARGET + '.v'
FDC = 'board/camera720-view-toggle.fdc'
CONTROL = 'rtl/experimental/camera720_view_control.v'
SELECT = 'board/camera720-view-select.vh'
STAGES = ['Compile', 'Synthesize', 'Device Map', 'Place', 'Route', 'Route Optimize', 'Report Timing']


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write(path, value):
    with Path(path).open('x', encoding='utf-8', newline='\n') as f:
        json.dump(value, f, indent=2)
        f.write('\n')


def replace_once(text, old, new):
    require(text.count(old) == 1, 'source anchor differs: ' + old)
    return text.replace(old, new, 1)


def render_top(text, build_id):
    require(re.fullmatch('[0-9a-f]{16}', build_id), '64-bit build label required')
    text = replace_once(text, 'module '+OLD+' #(', 'module '+TARGET+' #(')
    text = replace_once(text, 'input clk_27m,clk_p,clk_n,reset_n,',
                        'input clk_27m,clk_p,clk_n,reset_n,key1_n,')
    text = replace_once(text, '// Exact identity mapping, no rotation, gamma bypass. Not lens correction.',
                        '// KEY1 selects current-lens correction or exact raw identity; gamma bypass.')
    text = replace_once(text, '// Independent 720p transport candidate. New physical and board verification required.',
                        '// Independent 720p view-switch candidate. Requires its own physical verification.')
    anchors = re.findall(r'    `include "[^"\r\n]*board/camera720-current-lens\.vh"', text)
    require(len(anchors)==1, 'exact current lens include required')
    anchor = anchors[0]
    text = replace_once(text, anchor, '''    wire corrected_requested;
    camera720_view_control view_control(
        .clk(core_clk),.rst_n(core_reset[1]),.key1_n(key1_n),
        .corrected_requested(corrected_requested),.toggle_pulse());
'''+anchor+'\n    `include "board/camera720-view-select.vh"')
    names = ('out_cx','out_cy','src_cx','src_cy','src_fx','src_fy',
             'inv_fx','inv_fy','k1','k2','k3','p1','p2')
    for name in names:
        text = replace_once(text, '.cfg_'+name+'(C720_'+name.upper()+')',
                            '.cfg_'+name+'(view_'+name+')')
    text = replace_once(text, 'ddr_ready_ref[1],heartbeat};',
                        'ddr_ready_ref[1],corrected_requested};')
    text = replace_once(text, '    assign led={',
                        '    // LED0 reports the REQUEST; the picture follows at a complete-frame boundary.\n    assign led={')
    text = replace_once(text, ".BUILD_ID(64'he396af749d6e350d)", ".BUILD_ID(64'h"+build_id+")")
    return text


def render_fdc(text):
    require('key1_n' not in text and not re.search(r'\{PAP_IO_LOC\}\s*\{C23\}', text),
            'KEY1 pin already occupied')
    return text+'''\n# KEY1: hardware guide, user button 1, active low. KEY0/C22 remains reset.
define_attribute {p:key1_n} {PAP_IO_DIRECTION} {INPUT}
define_attribute {p:key1_n} {PAP_IO_LOC} {C23}
define_attribute {p:key1_n} {PAP_IO_VCCIO} {3.3}
define_attribute {p:key1_n} {PAP_IO_STANDARD} {LVCMOS33}
define_attribute {p:key1_n} {PAP_IO_PULLUP} {TRUE}
# Asynchronous mechanical input. Structural audit must show its only endpoint
# is key_sync[0]; the key_sync[0] -> key_sync[1] core-clock path remains timed.
set_false_path -from [get_ports {key1_n}]
'''


def work_path(path):
    p = Path(path).absolute()
    require(p == p.resolve() and p.parent == WORK.resolve()
            and re.fullmatch('[A-Za-z0-9_-]+', p.name), 'canonical direct candidate work directory required')
    return p


def prepare(work):
    work = work_path(work)
    require(not work.exists(), 'fresh candidate build directory required')
    require(sha(BASE/'plan.json') == BASE_SHA, 'frozen source baseline plan differs')
    base = read(BASE/'plan.json')
    bindings = {str(BASE/'plan.json'): BASE_SHA}
    for name, digest in base['PreparedSHA256'].items():
        require(sha(name) == digest, 'frozen source closure changed: '+name)
        bindings[name] = digest
    for p in (SELF, Path(cleanup.__file__).resolve(), ROOT/CONTROL, ROOT/SELECT,
              ROOT.parent/'hardware_check/hardware-guide.txt', Path(base['PDS']['Executable'])):
        bindings[str(p)] = sha(p)
    identity = hashlib.sha256(json.dumps(bindings, sort_keys=True).encode()).hexdigest()
    original = BASE/'compiled'
    payloads = {}
    for name, digest in base['PreparedSHA256'].items():
        p = Path(name)
        if p.is_relative_to(original):
            rel = p.relative_to(original).as_posix()
            data = p.read_bytes()
            if rel == 'board/'+OLD+'.v':
                rel = TOP
                data = render_top(data.decode('utf-8'), identity[:16]).encode('utf-8')
            elif rel == 'board/camera720-calibrated-stats-delay.fdc':
                rel, data = FDC, render_fdc(data.decode('utf-8')).encode('utf-8')
            # Only declared include locations are rewritten; IP and all other
            # payload bytes remain the frozen C source.
            if rel.endswith('.v'):
                data = re.sub(rb'(`include\s+")([^"\r\n]+)(")',
                    lambda m: m[1]+m[2].replace(original.as_posix().encode(),
                        (work/'compiled').as_posix().encode())+m[3], data)
            payloads[rel] = data
    require(TOP in payloads and FDC in payloads and len(payloads)>100,
            'incomplete baseline compiled closure')
    payloads[CONTROL] = (ROOT/CONTROL).read_bytes()
    payloads[SELECT] = (ROOT/SELECT).read_bytes()
    # New include was added as a source-relative header above.
    payloads[TOP] = replace_once(payloads[TOP].decode(), '"board/camera720-view-select.vh"',
        '"'+(work/'compiled'/SELECT).as_posix()+'"').encode()
    tcl = (BASE/'timing.tcl').read_text(encoding='ascii').replace(BASE.as_posix(), work.as_posix())
    tcl = tcl.replace(OLD, TARGET).replace('camera720-calibrated-stats-delay.fdc', 'camera720-view-toggle.fdc')
    marker = 'add_constraint {'+(work/'compiled'/FDC).as_posix()+'}'
    tcl = replace_once(tcl, marker, 'add_design {'+(work/'compiled'/CONTROL).as_posix()+'}\n'+marker)
    require(BASE.as_posix() not in tcl and OLD not in tcl, 'old candidate command path retained')
    require('gen_bitstream' not in tcl.lower() and 'download' not in tcl.lower(), 'build cannot program')
    work.mkdir(parents=True)
    for name, data in payloads.items():
        p = work/'compiled'/name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
    (work/'timing.tcl').write_text(tcl, encoding='ascii', newline='\n')
    outputs = {str(work/'compiled'/name): sha(work/'compiled'/name) for name in payloads}
    outputs[str(work/'timing.tcl')] = sha(work/'timing.tcl')
    plan = {'Schema':'camera720-view-toggle-build-v1', 'Target':TARGET,
        'CreatedUTC':datetime.now(timezone.utc).isoformat(), 'WorkDirectory':str(work),
        'BaselinePlan':str(BASE/'plan.json'), 'BaselinePlanSHA256':BASE_SHA,
        'InputSHA256':bindings, 'PreparedSHA256':outputs, 'BuildID':identity[:16],
        'ProfileID':'f79c44d9bdeb5b11', 'PDS':base['PDS'],
        'Command':[base['PDS']['Executable'],'-file',(work/'timing.tcl').as_posix(),
                   '-work_dir',work.as_posix(),'-project_name',TARGET],
        'ExpectedStages':STAGES, 'MaximumSeconds':1800, 'ExpectedPins':130,
        'DefaultView':'corrected', 'Button':'KEY1/C23 active low',
        'ModeLED':'LED0=requested correction; picture changes at complete-frame boundary',
        'SensorOrClockChanged':False,'InheritedPhysicalAcceptance':False,
        'EDAExecuted':False,'HardwareAccessed':False,'BitstreamRequested':False}
    write(work/'plan.json', plan)
    return plan


def validate(path):
    path = Path(path).resolve()
    p = read(path)
    work = work_path(path.parent)
    require(path.name=='plan.json' and p['Schema']=='camera720-view-toggle-build-v1'
            and p['Target']==TARGET and p['WorkDirectory']==str(work), 'wrong candidate plan')
    for name, digest in {**p['InputSHA256'], **p['PreparedSHA256']}.items():
        require(sha(name)==digest, 'candidate input drift: '+name)
    expected = [p['PDS']['Executable'],'-file',(work/'timing.tcl').as_posix(),
                '-work_dir',work.as_posix(),'-project_name',TARGET]
    require(p['Command']==expected and p['ExpectedStages']==STAGES and p['MaximumSeconds']==1800,
            'candidate execution scope changed')
    return p


def execute(path):
    p = validate(path)
    work = Path(p['WorkDirectory'])
    require(os.name=='nt' and not (work/'execution-start.json').exists(), 'fresh native Windows build required')
    watched = {**p['InputSHA256'], **p['PreparedSHA256'], str(Path(path).resolve()):sha(path)}
    result = {'Schema':'camera720-view-toggle-build-execution-v1','PlanSHA256':sha(path),
              'StartedUTC':datetime.now(timezone.utc).isoformat(), 'HardwareAccessed':False,
              'BitstreamRequested':False,'TimingAccepted':False,'TimedOut':False}
    write(work/'execution-start.json', result)
    process = None
    started = time.monotonic()
    try:
        with (work/'stdout.log').open('xb') as out, (work/'stderr.log').open('xb') as err:
            process = subprocess.Popen(p['Command'], cwd=work, stdout=out, stderr=err,
                shell=False, creationflags=subprocess.CREATE_NO_WINDOW)
            result['OwnedPID'] = process.pid
            try:
                result['ExitCode'] = process.wait(timeout=p['MaximumSeconds'])
            except subprocess.TimeoutExpired:
                result['TimedOut'] = True
    except BaseException as exc:
        result['Error'] = type(exc).__name__+': '+str(exc)
    finally:
        if process is not None and process.poll() is None:
            result['Cleanup'] = cleanup.stop_owned_tree(process, work, 'timeout/interrupted')
        text = (work/'stdout.log').read_text(encoding='gb18030', errors='replace')
        result['Stages'] = re.findall(r'^Process "([^"]+)" (started|done)\.', text, re.M)
        result['Diagnostics'] = [f'{f.relative_to(work)}: {line.strip()}'
            for f in work.rglob('*.log') for line in f.read_text(encoding='gb18030',errors='replace').splitlines()
            if re.match(r'\s*(C:|E:|F:|ERROR:|FATAL:)', line)]
        result['InputDrift'] = [n for n,h in watched.items() if not Path(n).is_file() or sha(n)!=h]
        adf = work/'place_route'/(TARGET+'_pnr.adf')
        snapshot = work/'pre-sta-final.adf'
        result['ADF'] = str(adf)
        result['ADFSHA256'] = sha(adf) if adf.is_file() else None
        result['UnchangedAcrossSTA'] = adf.is_file() and snapshot.is_file() and sha(adf)==sha(snapshot)
        result['StagesCompleted'] = result['Stages']==[(s,e) for s in STAGES for e in ('started','done')]
        result['BuildCompleted'] = result.get('ExitCode')==0 and result['StagesCompleted'] and not result['InputDrift'] and result['UnchangedAcrossSTA'] and not result.get('Error') and not result['TimedOut']
        result['ElapsedSeconds'] = round(time.monotonic()-started,3)
        result['LogSHA256'] = {f.relative_to(work).as_posix():sha(f) for f in work.rglob('*.log')}
        result['Limits'] = 'Build completion alone does not accept native diagnostics, IO, timing, CDC or authorize a bitstream.'
        write(work/'execution-result.json', result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-dir', type=Path)
    parser.add_argument('--plan', type=Path)
    parser.add_argument('--execute', action='store_true')
    a = parser.parse_args()
    if a.execute:
        require(a.plan is not None and a.work_dir is None, '--execute requires only --plan')
        result = execute(a.plan)
        print(json.dumps({k:result.get(k) for k in ('BuildCompleted','ElapsedSeconds','ExitCode','TimedOut','InputDrift')}))
        return 0 if result['BuildCompleted'] else 1
    require(a.work_dir is not None and a.plan is None, 'preparation requires --work-dir')
    result = prepare(a.work_dir)
    print(json.dumps({'Prepared':True,'BuildID':result['BuildID'],'WorkDirectory':result['WorkDirectory']}))
    return 0


if __name__=='__main__':
    raise SystemExit(main())
