"""Prepare an isolated upright sensor candidate; never run EDA or hardware.

The frozen VGA closure is validated intact before replacing exactly its top
and sensor-init source roles. Shared table, production core, pins and DDR are
unchanged. The new candidate inherits no old physical repair or timing pass.
"""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import re

import prepare_camera_vga_output as baseline

PROJECT=Path(__file__).resolve().parents[1]
SELF=Path(__file__).resolve()
TARGET='camera_vga_upright_top'
TOP='board/camera_vga_upright_top.v'
INIT='rtl/experimental/ov5640_cadence_upright_init.v'
OLD_INIT='rtl/experimental/ov5640_cadence_trial_init.v'
MANIFEST='board/camera-vga-upright-sources.json'
WORK=PROJECT/'work/camera-vga-upright'
RUNNER='tools/run_camera_vga_upright_diagnostic.py'
SCHEMA='camera-vga-upright-diagnostic-preparation-v1'
SOURCE_SCHEMA='camera-vga-upright-source-closure-v1'
BASE_MANIFEST_SHA='0411ded7b3d22599137c2b9abeffcafd2a1bb80900bbe10daef95aa8148edb21'
FIXED_HELPERS={'tools/prepare_camera_vga_output.py':'34d5ce67f9fe959f505bdcbfb63726076b0955f23e86e18b8f49a2e7bbfde8f3',
               'tools/run_camera_vga_output_diagnostic.py':'e1937f3d1115873a12e2947c729ede2184dd78b2e744ff2e8b3f9e71e84d1c87',
               'tools/prepare_board1080_timing.py':'53ff6502662f0f100f0cd7169af9fe8744ad8f46f4e681c5da1dacb7cc05bae8'}
REPLACE={baseline.TOP:TOP,OLD_INIT:INIT}
INCLUDES={REPLACE.get(n,n):v for n,v in baseline.INCLUDES.items()}
INCLUDES[INIT]=('board/ov5640_cadence_trial_commands.vh','board/ov5640_cadence_trial_commands.vh')
FLAGS=baseline.FALSE_FLAGS
require,sha=baseline.require,baseline.paths.sha


def utc():return datetime.now(timezone.utc).isoformat()


def normalized(text):
    text=re.sub(r'/\*.*?\*/|//[^\n]*','',text,flags=re.S)
    return ''.join(text.split())


def validate_top(old,new):
    expected=old.replace('module camera_vga_output_top','module '+TARGET).replace('ov5640_cadence_trial_init #','ov5640_cadence_upright_init #')
    require(normalized(new)==normalized(expected),'upright top differs outside module/init names and comments')


def roles():
    require(sha(PROJECT/baseline.MANIFEST)==BASE_MANIFEST_SHA,'frozen VGA manifest changed')
    for name,h in FIXED_HELPERS.items():require(sha(PROJECT/name)==h,'frozen helper changed: '+name)
    old=baseline.validate(PROJECT)
    validate_top((PROJECT/baseline.TOP).read_text(),(PROJECT/TOP).read_text())
    init=(PROJECT/INIT).read_text()
    require(re.findall(r'\bmodule\s+(\w+)',re.sub(r'//[^\n]*','',init))==['ov5640_cadence_upright_init'],
            'one isolated upright init module required')
    names=[REPLACE.get(n,n) for n in old['Sources']]
    require(len(names)==len(set(names)) and set(REPLACE).isdisjoint(names),'upright replacement roles differ')
    for name in names:
        if Path(name).suffix in ('.v','.vh'):
            data=(PROJECT/name).read_bytes();inc=baseline.paths.INCLUDE.findall(data);mapping=INCLUDES.get(name)
            require(len(baseline.paths.INCLUDE_DIRECTIVE.findall(data))==len(inc) and
                    inc==([] if mapping is None else [mapping[0].encode('ascii')]),'upright include role differs: '+name)
    return {**old,'Manifest':MANIFEST,'Sources':names,'SourceSHA256':{n:sha(PROJECT/n) for n in names},
            'ExplicitDesigns':[REPLACE.get(n,n) for n in old['ExplicitDesigns']],
            'DDRBodyComparison':{**old['DDRBodyComparison'],'CandidateTop':TOP,'UprightTopEquivalentExceptNames':True},
            'UnchangedSourceSHA256':{n:h for n,h in old['SourceSHA256'].items() if n not in REPLACE}}


def source_manifest():
    r=roles()
    return {'Schema':SOURCE_SCHEMA,'Target':TARGET,'BaseManifest':{'Path':baseline.MANIFEST,'SHA256':BASE_MANIFEST_SHA},
            'SourceReplacements':REPLACE,'source_files':r['Sources'],'SourceSHA256':r['SourceSHA256'],
            'Constraint':r['Constraint'],'RouteConstraint':r['RouteConstraint'],
            'ConstraintSHA256':r['ConstraintSHA256'],'RoleCounts':r['RoleCounts'],'PinAudit':r['PinAudit'],
            'DDRBodyComparison':r['DDRBodyComparison'],'FrozenSharedSourcesUnchanged':True,
            'OrientationIntent':{'Register3820':'0x00','Register3821':'0x06','GlobalTableUnchanged':True,
                                 'RTLReadbackSimulationRequiredSeparately':True},
            'HardwareAccessed':False,'EDAExecuted':False,**{k:False for k in FLAGS}}


def freeze_manifest():
    result=source_manifest()
    with (PROJECT/MANIFEST).open('x',encoding='utf-8',newline='\n') as f:json.dump(result,f,indent=2);f.write('\n')
    return result


def validate_sources():
    actual=json.loads((PROJECT/MANIFEST).read_text(encoding='utf-8-sig'))
    require(actual==source_manifest(),'upright manifest does not match exact derived source closure')
    return roles()


def work_path(value):
    p=Path(value).absolute()
    require(p==p.resolve() and p.parent==WORK and p.parent==p.parent.resolve() and re.fullmatch(r'[A-Za-z0-9_-]+',p.name),
            'only canonical direct upright workspace children are allowed')
    return p


def literal(path):
    p=Path(path).absolute();require(p==p.resolve() and p.is_relative_to(PROJECT),'recipe path escaped upright project')
    return baseline.paths.tcl_path(p.as_posix())


def make_tcl(designs,fdc,rcf,work):
    lines=['# Upright diagnostic only; no old routed repairs, bitstream or hardware.',
           'set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676']
    lines+=['add_design '+literal(p) for p in designs]
    lines+=['add_constraint '+literal(fdc),'compile -top_module '+TARGET,'synthesize -ads -selected_syn_tool_opt 2',
            'dev_map','add_constraint '+literal(rcf),'pnr -optimize_multi_corner_timing -fix_hold_violation',
            'if {[file exists '+literal(work/'place_route'/(TARGET+'_pnr.adf'))+']} {',
            '    file copy '+literal(work/'place_route'/(TARGET+'_pnr.adf'))+' '+literal(work/'pre-sta-final.adf'),
            '}','report_timing -force_to_run -delay_type min_max -max_path 1000 -nworst 4 -report_exception TRUE']
    return '\n'.join(lines)+'\n'


def recipe(work,pds_shell='D:/pango/PDS_2023.2/bin/pds_shell.exe',maximum_seconds=1800):
    work=work_path(work);require(type(maximum_seconds) is int and 60<=maximum_seconds<=1800,'deadline must be60..1800 seconds')
    r=validate_sources();pds=Path(pds_shell).absolute()
    require(pds==pds.resolve() and pds.is_file() and pds.name.lower()=='pds_shell.exe','canonical PDS shell required')
    auxiliary={MANIFEST:sha(PROJECT/MANIFEST),baseline.MANIFEST:BASE_MANIFEST_SHA,
               **FIXED_HELPERS,SELF.relative_to(PROJECT).as_posix():sha(SELF),RUNNER:sha(PROJECT/RUNNER),
               baseline.BASE:baseline.BASE_SHA256,baseline.RAW_FDC:baseline.RAW_FDC_SHA,baseline.RAW_PINS:baseline.RAW_PINS_SHA,
               baseline.TOP:sha(PROJECT/baseline.TOP),OLD_INIT:sha(PROJECT/OLD_INIT)}
    inputs={**r['SourceSHA256'],**r['ConstraintSHA256'],**auxiliary};payloads={};copies=[];rewrites=[];designs=[]
    for name in r['Sources']+[r['RouteConstraint']]:
        data=(PROJECT/name).read_bytes();require(baseline.paths.sha_bytes(data)==inputs[name],'input drift: '+name)
        transformed=data
        if name in INCLUDES:
            old,header=INCLUDES[name];match=list(baseline.paths.INCLUDE.finditer(data))
            require(len(match)==1 and match[0][1]==old.encode(),'source include transform differs')
            replacement=(work/'compiled'/header).as_posix();baseline.paths.tcl_path(replacement)
            transformed=data[:match[0].start(1)]+replacement.encode()+data[match[0].end(1):]
            rewrites.append({'Source':name,'OriginalInclude':old,'CompiledInclude':replacement,'Header':header,'HeaderSHA256':inputs[header]})
        destination=work/'compiled'/name;payloads[destination]=transformed
        copies.append({'Source':name,'OriginalSHA256':inputs[name],'CompiledPath':destination.as_posix(),
                       'CompiledSHA256':baseline.paths.sha_bytes(transformed)})
        if name in r['ExplicitDesigns']:designs.append(destination)
    tcl=make_tcl(designs,work/'compiled'/r['Constraint'],work/'compiled'/r['RouteConstraint'],work).encode('ascii')
    plan={'Schema':SCHEMA,'Target':TARGET,'Scope':'PrepareOnlyNoEDA','ProjectRoot':str(PROJECT),'WorkDirectory':str(work),
          'ScratchRoot':str(WORK),'RepoAlias':'direct','Manifest':MANIFEST,'InputSHA256':inputs,'RoleCounts':r['RoleCounts'],
          'SourceReplacements':REPLACE,'BaselineManifestSHA256':BASE_MANIFEST_SHA,'PinAudit':r['PinAudit'],
          'DDRBodyComparison':r['DDRBodyComparison'],'CompiledInputs':copies,'ExplicitDesigns':[p.as_posix() for p in designs],
          'IDFExpandedSourcesNotAdded':r['IDFExpandedSources'],'IncludeRewrites':rewrites,
          'Constraints':{'FDC':r['Constraint'],'RCF':r['RouteConstraint'],'CopiedIntoFrozenCompiledTree':True},
          'Tcl':{'Path':(work/'timing.tcl').as_posix(),'SHA256':baseline.paths.sha_bytes(tcl)},
          'PDS':{'Executable':str(pds),'ExecutableSHA256':sha(pds),'ExpectedVersion':baseline.paths.PDS_VERSION},
          'CommandToRunSeparately':[str(pds),'-file',(work/'timing.tcl').as_posix(),'-work_dir',work.as_posix(),'-project_name',TARGET],
          'MaximumSecondsForExternalExecutor':maximum_seconds,'ExternalDeadlineRequired':True,
          'PreSTAFinalDatabase':(work/'pre-sta-final.adf').as_posix(),'ExpectedActualStages':['Compile','Synthesize','Device Map','Place','Route','Route Optimize','Report Timing'],
          'HardwareAccessed':False,'EDAExecuted':False,'BitstreamRequested':False,**{k:False for k in FLAGS},
          'Limits':'Independent upright implementation. Old physical net names, repair routes and endpoint exceptions are not imported. New timing/CDC/pin/bit proofs are required separately.'}
    require(all(sha(PROJECT/n)==h for n,h in inputs.items()),'inputs changed while forming recipe')
    return plan,payloads,tcl


def prepare(work,pds_shell='D:/pango/PDS_2023.2/bin/pds_shell.exe',maximum_seconds=1800):
    work=work_path(work);require(not work.exists(),'fresh upright stage required')
    plan,payloads,tcl=recipe(work,pds_shell,maximum_seconds);work.mkdir(parents=True)
    for path,data in payloads.items():path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
    (work/'timing.tcl').write_bytes(tcl);plan['PreparedUTC']=utc()
    with (work/'plan.json').open('x',encoding='utf-8',newline='\n') as f:json.dump(plan,f,indent=2);f.write('\n')
    return plan


def main():
    p=argparse.ArgumentParser(description=__doc__);mode=p.add_mutually_exclusive_group(required=True)
    mode.add_argument('--freeze-manifest',action='store_true');mode.add_argument('--audit-only',action='store_true');mode.add_argument('--work-dir',type=Path)
    p.add_argument('--maximum-seconds',type=int,default=1800);p.add_argument('--pds-shell',default='D:/pango/PDS_2023.2/bin/pds_shell.exe')
    args=p.parse_args()
    if args.freeze_manifest:result=freeze_manifest();summary={'Manifest':MANIFEST,'SHA256':sha(PROJECT/MANIFEST),'Sources':len(result['source_files'])}
    elif args.audit_only:result=validate_sources();summary={'Validated':True,'RoleCounts':result['RoleCounts']}
    else:
        result=prepare(args.work_dir,args.pds_shell,args.maximum_seconds);summary={'PreparedOnly':True,'Plan':str(Path(result['WorkDirectory'])/'plan.json'),'Command':result['CommandToRunSeparately']}
    print(json.dumps({**summary,'EDAExecuted':False,'HardwareAccessed':False}))


if __name__=='__main__':main()
