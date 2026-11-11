#!/usr/bin/env python3
"""Offline prepare; explicit run launches only compile+synthesize in a fresh private project.
No installation, map, PNR, STA, bitgen, programming or publication. Python >= 3.10.
"""
import argparse
import hashlib
import types
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import time
import uuid
sys.dont_write_bytecode = True
HERE = Path(__file__).absolute().parent
COMMIT = '22d5b2bc09c0013939de57d47436405a380bb5fd'
PINS = {'prepare_native.py': '10f10a048796004283e7c04b9792eb71eb1bc8b239a6215d6cb5000fe15835f1',
        'PUBLIC_MANIFEST.json': 'be66e9c40406e09742b1b0aeae09e5a33493a4162e144862a8b582c303e2e495'}
TOOL_SHA = '32983ea8e0cf0498481e5ae8ff75fcdd4ee329f2efb83dea9d8eee85583931cc'
ROM_SHA = 'e03f1869bf3247ed5ae84e94fa431885a20cca86b85e6d12d8a38053ecb8c8a7'
TOP = 'board1080_elastic_research_top'
ARCH = 'set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676'
class Refusal(RuntimeError): pass
def need(ok, why):
    if not ok: raise Refusal(why)
def sha(data): return hashlib.sha256(data).hexdigest()
def path(value, exists=True, directory=None):
    p = Path(value)
    need('..' not in p.parts and not any(ord(c) < 32 for c in str(p)), 'unsafe path')
    p = p.absolute()
    for q in [*reversed(p.parents), p]:
        if not os.path.lexists(q): continue
        s = q.lstat()
        need(not stat.S_ISLNK(s.st_mode) and not (getattr(s, 'st_file_attributes', 0) & 1024), 'link/reparse point refused')
        need(not getattr(q, 'is_junction', lambda: False)(), 'junction refused')
        if q != p: need(q.is_dir(), 'non-directory ancestor')
    need(not exists or p.exists(), 'required path missing: ' + str(p))
    if p.exists() and directory is not None: need(p.is_dir() if directory else p.is_file(), 'wrong path type')
    return p
def read(p):
    p=path(p, directory=False)
    need(stat.S_ISREG(p.stat().st_mode), 'nonregular file')
    return p.read_bytes()
def load(p):
    def pairs(items):
        d={}
        for k,v in items:
            need(k not in d, 'duplicate JSON key'); d[k]=v
        return d
    return json.loads(read(p), object_pairs_hook=pairs)
def dump(x): return (json.dumps(x, indent=2, sort_keys=True)+'\n').encode()
def write(root, name, data):
    p=root/name; path(p.parent, directory=True)
    with open(p, 'xb') as f: f.write(data if isinstance(data, bytes) else data.encode())
    if os.name != 'nt': p.chmod(0o600)
def inventory(root):
    root=path(root,directory=True); out={}
    for parent,dirs,files in os.walk(root,followlinks=False):
        for name in dirs+files: path(Path(parent)/name)
        for name in files:
            p=Path(parent)/name; out[p.relative_to(root).as_posix()]=sha(read(p))
    return out
def relative(s):
    need(isinstance(s,str) and s and not any(c in s for c in '\\:\n\r\t'), 'invalid relative path')
    need(not s.startswith('/') and all(c not in ('','.','..') for c in s.split('/')), 'relative path traversal')
    return s
def tcl(s):
    s=str(s).replace('\\','/') if isinstance(s,Path) else str(s)
    return '"'+''.join('\\'+c if c in '\\$[]"' else c for c in s)+'"'
def authenticate(candidate, native, prepared):
    candidate=path(candidate,directory=True); native=path(native,directory=True); prepared=path(prepared,directory=True)
    for name,h in PINS.items(): need(sha(read(candidate/name))==h, 'published candidate identity drift: '+name)
    # Execute authenticated source bytes only; never consult a possibly stale/malicious .pyc.
    source=read(candidate/'prepare_native.py')
    need(sha(source)==PINS['prepare_native.py'],'preparer changed during load')
    module=types.ModuleType('pinned_native'); module.__file__=str(candidate/'prepare_native.py')
    exec(compile(source,module.__file__,'exec'),module.__dict__)
    info=module.inspect(native) # Read-only: authenticates all 164 originals and derives expected bytes in memory.
    plan=info['recipe']['import_plan']
    need(plan['top_module']==TOP and plan['architecture_observed']==ARCH, 'wrong top/device')
    need(plan['new_import_count']==85 and len({i['path'] for i in plan['imports']})==85, 'wrong imports')
    need(inventory(prepared/'native')=={p:sha(b) for p,b in info['derived'].items()}, 'prepared native drift/missing/extra file')
    need(read(prepared/'inputs/KEY1_ONLY.fdc')==info['records']['inputs/KEY1_ONLY.fdc'], 'KEY1 constraint drift')
    need(load(prepared/'IMPORT_PLAN.json')==plan, 'prepared import plan drift')
    rom=plan['rom']; need(sha(read(prepared/'run'/rom['working_filename']))==rom['sha256'], 'prepared ROM drift')
    saved=load(prepared/'PRIVATE_FILES_SHA256.json')
    need(all(sha(read(prepared/relative(p)))==h for p,h in saved.items()), 'private receipt drift')
    need(set(inventory(prepared))==set(saved)|{'PRIVATE_FILES_SHA256.json','PREPARATION_RESULT.json'}, 'untracked private file')
    return info,plan,{'candidate_commit':COMMIT,'raw_seed_files':164,'derived_native_files':174,'ordered_imports':85,
        'top':TOP,'architecture':ARCH,'private_input_hashes':{p:h for p,h in inventory(prepared).items() if p.startswith(('native/','inputs/','run/')) or p=='IMPORT_PLAN.json'},
        'canonical_manifest_sha256':sha(read(native.parent/'NATIVE_SOURCE_MANIFEST.json'))}
def query_inventory(plan,prepared):
    rows=[]
    for c in plan['constraints']:
        p=prepared/c['path'] if c['origin']=='private_record' else prepared/'native'/c['path']
        for lineno,line in enumerate(read(p).decode().splitlines(),1):
            if line.lstrip().startswith('#'): continue
            start=0
            while True:
                m=re.search(r'\[get_(?:ports|pins|clocks)\b',line[start:])
                if not m: break
                a=start+m.start(); braces=0; depth=1; i=a+1
                while i<len(line):
                    ch=line[i]
                    if ch=='\\': i+=2; continue
                    if ch=='{': braces+=1
                    elif ch=='}': braces-=1
                    elif braces==0 and ch=='[': depth+=1
                    elif braces==0 and ch==']':
                        depth-=1
                        if depth==0: break
                    i+=1
                need(i<len(line) and braces==0,'unsupported multiline/unbalanced constraint query')
                expr=line[a+1:i]
                rows.append({'id':len(rows),'file':c['path'],'line':lineno,'expression':expr,
                             'expected_minimum':1,'count_api':'UNVERIFIED; raw Tcl result is NOT a collection count'})
                start=i+1
    need(rows,'constraint query inventory empty')
    return rows
ROM_TEMPLATE='''# First-party guarded ROM staging. This generated file remains PRIVATE.
set aa_root @ROOT@
set aa_cwd [file normalize [pwd]]
set aa_cmp $aa_cwd
set aa_allowed [file normalize $aa_root]
if {$::tcl_platform(platform) eq "windows"} {
    set aa_cmp [string tolower $aa_cmp]
    set aa_allowed [string tolower $aa_allowed]
}
if {$aa_cmp ne $aa_allowed && [string first "$aa_allowed/" $aa_cmp] != 0} {error "ROM cwd outside fresh project"}
set aa_bytes [binary format H* @HEX@]
set aa_dest [file join $aa_cwd run8_intervals_30bit.mem]
if {[file exists $aa_dest]} {
    if {[file type $aa_dest] ne "file"} {error "ROM destination not regular"}
    set f [open $aa_dest rb]; set previous [read $f]; close $f
    if {$previous ne $aa_bytes} {error "ROM conflict; no overwrite"}
} else {
    set f [open $aa_dest {WRONLY CREAT EXCL}]; fconfigure $f -translation binary
    puts -nonewline $f $aa_bytes; close $f
}
set f [open @TRACE@ a]
puts $f "@PHASE@\\t$aa_cwd\\t$aa_dest"
close $f
puts "AA_ROM_PHASE @PHASE@"
'''
CHECKED='''proc aa_checked {label command} {
    puts "AA_BEGIN $label"; flush stdout
    set rc [catch {uplevel 1 $command} result options]
    puts "AA_RESULT $label RC=$rc"; flush stdout
    if {$rc != 0} {puts stderr $result; exit 1}
    return $result
}
'''
def generate(info,plan,prepared,out,run_id):
    work=out/'work'; scripts={}; rom=info['derived'][plan['rom']['source']]
    for phase in ['bootstrap','compile','synthesize']:
        values={'ROOT':tcl(work),'HEX':tcl(rom.hex()),'TRACE':tcl(out/'ROM_WORKDIRS.tsv'),'PHASE':phase}
        scripts['rom_'+phase+'.tcl']=re.sub(r'@(ROOT|HEX|TRACE|PHASE)@',lambda m:values[m.group(1)],ROM_TEMPLATE)
    rows=query_inventory(plan,prepared)
    queries=['# Read-only probes only. Stage and collection semantics need real PDS verification.','proc aa_probe_queries {} {']
    for row in rows:
        queries+=['    set rc [catch {uplevel #0 '+tcl(row['expression'])+'} value]',
                  '    binary scan $value H* encoded',f'    puts "AA_QUERY\\t{row["id"]}\\t$rc\\t$encoded"']
    queries+=['    flush stdout','}']
    scripts['query_probes.tcl']='\n'.join(queries)+'\n'
    lines=[CHECKED,'puts '+tcl('AA_RUN_ID '+run_id)]
    for i,item in enumerate(plan['imports']): lines += [f'aa_checked IMPORT_{i} [list add_design '+tcl(prepared/'native'/item['path'])+']']
    for i,c in enumerate(plan['constraints']):
        p=prepared/c['path'] if c['origin']=='private_record' else prepared/'native'/c['path']
        cmd='add_constraint -fdc' if c['origin']=='private_record' else 'add_constraint'
        lines += [f'aa_checked CONSTRAINT_{i} [list {cmd} '+tcl(p)+']']
    lines += ['aa_checked ARCH [list '+ARCH+']', 'aa_checked ROM_BOOTSTRAP [list source '+tcl(out/'rom_bootstrap.tcl')+']']
    incs='[list '+' '.join(tcl(prepared/'native'/p) for p in plan['include_paths'])+']'
    lines += ['aa_checked COMPILE [list compile -verilog_standard SystemVerilog -top_module '+TOP+' -include_path '+incs+' -pre_tcl '+tcl(out/'rom_compile.tcl')+']',
              'aa_checked SYNTHESIZE [list synthesize -ads -selected_syn_tool_opt 2 -pre_tcl '+tcl(out/'rom_synthesize.tcl')+']',
              'puts "AA_SYNTHESIS_COMMAND_RETURNED"',
              'source '+tcl(out/'query_probes.tcl'),'aa_probe_queries',
              'puts '+tcl('AA_END '+run_id),'flush stdout']
    scripts['SYNTHESIS.tcl']='\n'.join(lines)+'\n'
    return scripts,rows

def verify_assets(out,cfg,info,plan):
    need(re.fullmatch(r'[0-9a-f]{32}',cfg['run_id']) is not None,'invalid run nonce')
    need(cfg['project_name']=='aa_elastic_'+cfg['run_id'][:12],'wrong project identity')
    scripts,rows=generate(info,plan,path(cfg['prepared']),out,cfg['run_id'])
    expected={name:sha(data.encode()) for name,data in scripts.items()}
    expected['CONSTRAINT_QUERY_INVENTORY.json']=sha(dump(rows))
    need(cfg['asset_hashes']==expected,'prepared assets do not match canonical recipe')
    need(all(sha(read(out/name))==h for name,h in expected.items()),'generated scripts changed')

def disjoint(out,protected):
    for p in protected:
        p=path(p,directory=True)
        need(not out.is_relative_to(p) and not p.is_relative_to(out),'output overlaps protected input/package')

def validate_config_paths(out,cfg):
    need(out==path(cfg['out']),'prepared directory moved; regenerate for target computer')
    disjoint(out,[cfg['candidate'],path(cfg['native']).parent,cfg['prepared'],HERE])
    need(sha(read(__file__))==cfg['helper_sha256'],'helper changed after preparation')

def fresh_output(value,protected):
    out=path(value,exists=False); need(not os.path.lexists(out),'output exists; choose a fresh directory')
    path(out.parent,directory=True)
    disjoint(out,protected)
    return out

def prepare(a):
    candidate=path(a.candidate,directory=True); native=path(a.native,directory=True); prepared=path(a.prepared,directory=True)
    info,plan,identity=authenticate(candidate,native,prepared)
    if a.dry_run:
        return {**{k:v for k,v in identity.items() if k!='private_input_hashes'},'status':'OFFLINE_INPUTS_VERIFIED_PDS_NOT_RUN','PDS_executed':False,'build_ready':False}
    out=fresh_output(a.out,[candidate,native.parent,prepared,HERE]); out.mkdir(mode=0o700)
    run_id=uuid.uuid4().hex
    scripts,rows=generate(info,plan,prepared,out,run_id)
    for name,data in scripts.items(): write(out,name,data)
    write(out,'CONSTRAINT_QUERY_INVENTORY.json',dump(rows))
    config={'candidate':str(candidate),'native':str(native),'prepared':str(prepared),'out':str(out),'run_id':run_id,
      'identity':identity,'helper_sha256':sha(read(__file__)),'asset_hashes':inventory(out),'status':'PREPARED_NOT_RUN',
      'pds_version_required':'2025.2 build 211867','pds_executable_sha256':TOOL_SHA,
      'project_name':'aa_elastic_'+run_id[:12], 'query_occurrences':len(rows)}
    write(out,'PREPARED.json',dump(config))
    write(out,'PRIVATE_DO_NOT_PUBLISH.txt','Private PDS work area. Do not upload logs, source, ROM or generated vendor artifacts.\n')
    return {'status':'PREPARED_NOT_RUN','PDS_executed':False,'build_ready':False,'private_out':str(out),'query_occurrences':len(rows)}

def run(a):
    out=path(a.run,directory=True); cfg=load(out/'PREPARED.json')
    validate_config_paths(out,cfg)
    need(inventory(out)=={**cfg['asset_hashes'],'PREPARED.json':sha(read(out/'PREPARED.json')),
        'PRIVATE_DO_NOT_PUBLISH.txt':sha(read(out/'PRIVATE_DO_NOT_PUBLISH.txt'))},'run already started or untracked/stale output')
    info,plan,identity=authenticate(cfg['candidate'],cfg['native'],cfg['prepared'])
    need(identity==cfg['identity'],'input identity drift after preparation')
    verify_assets(out,cfg,info,plan)
    tool=path(a.pds,directory=False)
    need(sha(read(tool))==TOOL_SHA, 'tool differs from recorded PDS executable; do not substitute or bypass pin')
    work=out/'work'; need(not os.path.lexists(work),'stale project refused'); work.mkdir(mode=0o700)
    command=[str(tool),'-file',str(out/'SYNTHESIS.tcl'),'-work_dir',str(work),'-project_name',cfg['project_name']]
    start=time.time_ns()
    write(out,'EXECUTION_STARTED.json',dump({'run_id':cfg['run_id'],'start_ns':start,'command':command,'tool_sha256':TOOL_SHA,
         'status':'RUNNING_OR_UNKNOWN_UNTIL_FINISHED','prepared_sha256':sha(read(out/'PREPARED.json'))}))
    with open(out/'pds_stdout.log','xb') as f:
        result=subprocess.run(command,cwd=work,stdout=f,stderr=subprocess.STDOUT,check=False)
    need(sha(read(tool))==TOOL_SHA,'tool changed during execution')
    _,_,after=authenticate(cfg['candidate'],cfg['native'],cfg['prepared'])
    need(after==identity,'inputs changed during PDS run')
    need(all(sha(read(out/n))==h for n,h in cfg['asset_hashes'].items()),'run assets changed')
    write(out,'EXECUTION_FINISHED.json',dump({'run_id':cfg['run_id'],'returncode':result.returncode,
        'end_ns':time.time_ns(),'input_identity_unchanged':True,'outputs':inventory(work),
        'stdout_sha256':sha(read(out/'pds_stdout.log')),'rom_trace_sha256':sha(read(out/'ROM_WORKDIRS.tsv')) if (out/'ROM_WORKDIRS.tsv').is_file() else None,
        'status':'EXECUTED_UNREVIEWED_NOT_BUILD_ACCEPTED'}))
    return collect(out)

def collect(out):
    out=path(out,directory=True); cfg=load(out/'PREPARED.json')
    validate_config_paths(out,cfg)
    start=load(out/'EXECUTION_STARTED.json'); end=load(out/'EXECUTION_FINISHED.json')
    need(start['run_id']==end['run_id']==cfg['run_id'],'run identity mismatch')
    need(start['prepared_sha256']==sha(read(out/'PREPARED.json')),'prepared receipt changed')
    need(start['tool_sha256']==TOOL_SHA,'wrong tool receipt')
    need(end['end_ns']>=start['start_ns'],'invalid run interval')
    need(end['input_identity_unchanged'] is True,'input identity not verified')
    need(all(sha(read(out/n))==h for n,h in cfg['asset_hashes'].items()),'generated Tcl/query assets drifted')
    info,plan,identity=authenticate(cfg['candidate'],cfg['native'],cfg['prepared'])
    need(identity==cfg['identity'],'input drift since execution')
    verify_assets(out,cfg,info,plan)
    need(inventory(out/'work')==end['outputs'],'output artifact drift')
    stdout=read(out/'pds_stdout.log'); need(sha(stdout)==end['stdout_sha256'],'log drift')
    log=stdout.decode(errors='replace'); findings=[]
    if end['returncode']!=0: findings.append('PDS returned nonzero')
    for marker in ['AA_RUN_ID '+cfg['run_id'],'AA_SYNTHESIS_COMMAND_RETURNED','AA_END '+cfg['run_id']]:
        if log.count(marker)!=1: findings.append('missing/duplicate stage marker: '+marker.split()[0])
    for stage in ['ARCH','COMPILE','SYNTHESIZE']+[f'IMPORT_{i}' for i in range(85)]+[f'CONSTRAINT_{i}' for i in range(4)]:
        if log.count('AA_RESULT '+stage+' RC=0')!=1: findings.append('stage not verified: '+stage)
    trace=out/'ROM_WORKDIRS.tsv'; phases=[]
    if not trace.is_file(): findings.append('ROM trace missing')
    else:
        need(sha(read(trace))==end['rom_trace_sha256'],'ROM trace changed')
        for line in read(trace).decode().splitlines():
            fields=line.split('\t'); need(len(fields)==3,'invalid ROM trace')
            phase,cwd,dest=fields; cwd=path(cwd,directory=True); dest=path(dest,directory=False)
            need(cwd.is_relative_to(out/'work') and dest==cwd/'run8_intervals_30bit.mem','ROM outside run')
            need(sha(read(dest))==ROM_SHA,'ROM content differs')
            phases.append(phase)
        for phase in ['bootstrap','compile','synthesize']:
            if phase not in phases: findings.append('ROM phase not observed: '+phase)
    reports=[]; diagnostic_hits=[]
    for name in end['outputs']:
        p=out/'work'/relative(name)
        if p.suffix.lower() in {'.log','.rpt','.srr','.rtr'}:
            if p.stat().st_mtime_ns < start['start_ns']-2_000_000_000: findings.append('stale report timestamp: '+name)
            reports.append({'path':name,'sha256':sha(read(p))})
            # Triage only: positive matches demand review; no matches never prove no blackboxes.
            for i,line in enumerate(read(p).decode(errors='replace').splitlines(),1):
                if re.search(r'black\s*box|blackbox|unresolved|undefined|no (?:object|pin|port|clock).*match|license.*(?:fail|error)|fatal',line,re.I):
                    diagnostic_hits.append({'file':name,'line':i,'text':line[:500]})
    for i,line in enumerate(log.splitlines(),1):
        if re.search(r'black\s*box|blackbox|unresolved|undefined|no (?:object|pin|port|clock).*match|license.*(?:fail|error)|fatal',line,re.I):
            diagnostic_hits.append({'file':'pds_stdout.log','line':i,'text':line[:500]})
    query_lines=[x for x in log.splitlines() if x.startswith('AA_QUERY\t')]
    expected_rows=load(out/'CONSTRAINT_QUERY_INVENTORY.json'); seen=[]; query_errors=[]
    for line in query_lines:
        fields=line.split('\t'); need(len(fields)==4,'malformed query probe')
        _,qid,rc,raw=fields; qid=int(qid); value=bytes.fromhex(raw).decode(errors='replace'); seen.append(qid)
        if rc!='0' or not value: query_errors.append({'id':qid,'return_code':rc,'raw_empty':not value})
    if sorted(seen)!=list(range(len(expected_rows))): findings.append('query probe coverage missing/duplicate')
    if query_errors: findings.append('query errors/empty raw results; stage API or objects unresolved')
    if not reports: findings.append('no fresh tool reports found')
    if diagnostic_hits: findings.append('blackbox/unresolved/license/constraint diagnostics require review')
    return {'status':'BLOCKED_EVIDENCE_OR_DIAGNOSTICS' if findings else 'SYNTHESIS_EXECUTED_REVIEW_REQUIRED',
        'PDS_executed':True,'candidate_commit':COMMIT,'run_id':cfg['run_id'],'findings':findings,
        'fresh_report_inventory':reports,'diagnostic_hits':diagnostic_hits,'rom_phases':phases,
        'query_occurrences_observed':len(query_lines),'query_errors':query_errors,
        'constraint_object_counts_verified':False,'no_blackboxes_verified':False,'CDC_verified':False,'STA_verified':False,
        'build_accepted':False,'remaining_review':['PDS version/banner and device/top in actual tool reports',
          'All imports and protected DDR/PLL cells elaborated; explicit unresolved/blackbox count = 0',
          'Documented get_* collection-size API and correct netlist stage; every query has expected nonzero cardinality',
          'All FDC pin definitions/RCF route targets resolved; not only explicit get_* expressions',
          '125 MHz core/DDR UI and 148.5 MHz pixel generated-clock propagation; input constraint 150.2 MHz is not overclocking',
          'ROM initialized contents and inferred memory, resources, held-bundle/FIFO/2-bit-slot CDC',
          'Separate new map/PNR/STA and physical DDR/camera/KEY1 validation before acceptance']}

def main():
    p=argparse.ArgumentParser(description=__doc__); sub=p.add_subparsers(dest='action',required=True)
    q=sub.add_parser('prepare')
    for key in ['candidate','native','prepared']: q.add_argument('--'+key,required=True)
    g=q.add_mutually_exclusive_group(required=True); g.add_argument('--dry-run',action='store_true');g.add_argument('--out')
    q=sub.add_parser('run');q.add_argument('--run',required=True);q.add_argument('--pds',required=True)
    q=sub.add_parser('collect');q.add_argument('--run',required=True)
    a=p.parse_args()
    try:
        answer=prepare(a) if a.action=='prepare' else run(a) if a.action=='run' else collect(a.run)
        print(json.dumps(answer,indent=2,sort_keys=True))
        return 0 if a.action=='prepare' else 3 # Explicitly NEVER signal build acceptance from synthesis/triage.
    except (Refusal,OSError,ValueError,KeyError,TypeError) as e:
        print('REFUSED: '+str(e),file=sys.stderr);return 2
if __name__=='__main__': sys.exit(main())
