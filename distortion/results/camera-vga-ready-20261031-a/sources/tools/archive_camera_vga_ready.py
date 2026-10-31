"""Archive explicit camera-ready diagnostic evidence, with decoded readback.

Only named stages/files and immutable document snapshots are selected. ADF,
bitstream, generated/vendor HDL and full route dumps remain local hash-bound
references. Failed stages retain their receipts. No EDA or hardware is run.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re

import archive_camera_vga_physical as physical
import camera_vga_bitstream as bit
import execute_camera_vga_program as program

PROJECT,WORK=physical.PROJECT,physical.WORK
SELF=Path(__file__).resolve()
SCHEMA='camera-vga-ready-archive-config-v1'
ARCHIVE_SCHEMA='camera-vga-ready-evidence-archive-v1'
require,sha,canonical,load=physical.require,physical.sha,physical.canonical,physical.load
TEXT=physical.TEXT_SUFFIXES|{'.py','.bgr','.pds'}


def stage(path):
    work=canonical(path,WORK,directory=True)
    require(work.parent==WORK,'explicit direct camera stage required')
    receipts=[p for p in (work/'result.json',work/'execution-result.json') if p.is_file()]
    require(len(receipts)==1,'exactly one completed native receipt required')
    receipt=load(receipts[0])
    if receipt.get('Schema') in physical.STAGE_SCHEMAS:return physical.completed_stage(work)
    require(receipt.get('Schema')=='camera-vga-bitstream-execution-v1','unsupported camera-ready stage schema')
    require(receipt.get('FinishedUTC') and type(receipt.get('ExitCode')) is int and receipt.get('HardwareAccessed') is False,
            'native bit stage incomplete or hardware boundary differs')
    require(isinstance(receipt.get('Artifacts'),dict) and receipt['Artifacts'],'bit stage lacks artifact binding')
    for name,h in receipt['Artifacts'].items():
        require(not Path(name).is_absolute(),'absolute native artifact path')
        require(sha(canonical(work/name,work))==h,'native bit artifact drift')
    passed=(receipt['ExitCode']==0 and not receipt.get('TimedOut') and not receipt.get('StoppedForUnexpectedStage') and
            not receipt.get('InputDrift') and not receipt.get('Diagnostics') and not receipt.get('Error'))
    return work,{**{k:receipt.get(k) for k in ('Schema','StartedUTC','FinishedUTC','ExitCode','TimedOut','InputDrift',
                                            'Diagnostics','FinalADFSHA256','HardwareAccessed')},
                 'ExecutionPassed':passed,'FailedTrialPreserved':not passed,'OriginalDirectory':str(work),
                 'ReceiptSHA256':sha(receipts[0]),'HistoricalInputHashesPreservedVerbatim':True}


def snapshot(path):
    path=canonical(path,WORK)
    relative=path.relative_to(WORK)
    require(len(relative.parts)>=2 and 'snapshot' in relative.parts[0].lower() and path.suffix.lower() in ('.md','.txt','.json'),
            'documents must come from an explicit camera snapshot directory')
    return path


def source(path):
    path=canonical(path)
    require(path.parent in (PROJECT/'tools',PROJECT/'tests') and path.suffix.lower() in physical.SOURCE_SUFFIXES,
            'source snapshot must be an explicit tool/test file')
    return path


def reason(path,relative=None):
    if path.suffix.lower() in ('.sbit','.bit','.bin'):return 'Programming payload is retained locally; only its exact hash is archived.'
    if path.suffix.lower() in TEXT and not path.name.lower().startswith('route-dump'):return None
    return physical.local_only_reason(path,relative)


def bit_dependencies(bit_work):
    plan=bit.load(bit_work/'bitstream-plan.json');watched={}
    require(isinstance(plan.get('ProjectInputSHA256'),dict) and plan['ProjectInputSHA256'],
            'verified bit has no project input closure')
    for name,h in plan['ProjectInputSHA256'].items():
        path=Path(name).absolute()
        require(path==path.resolve() and path.is_file() and
                (path.is_relative_to(PROJECT.parent) or path.is_relative_to(bit.PDS.parent.parent)),
                'bit dependency escaped allowed roots')
        require(sha(path)==h,'verified bit dependency drift');watched[path]=h
    return watched


def prepare(config_path):
    config_path=canonical(config_path);config=load(config_path)
    fields={'Schema','Destination','BitWork','PreparedProgram','Stages','SourceFiles','ExtraFiles','DocumentSnapshots'}
    require(set(config)==fields and config.get('Schema')==SCHEMA,'ready archive config fields/schema differ')
    dest=Path(config['Destination']);dest=(dest if dest.is_absolute() else PROJECT/dest).absolute()
    require(dest==dest.resolve() and dest.parent==PROJECT/'results' and re.fullmatch(r'camera-vga-ready-[A-Za-z0-9_-]+',dest.name)
            and not dest.exists(),'fresh direct camera-vga-ready results directory required')
    for key in ('Stages','SourceFiles','ExtraFiles','DocumentSnapshots'):
        require(isinstance(config[key],list) and all(isinstance(v,str) for v in config[key]),key+' must be an explicit path list')
    bit_work=bit.work_path(config['BitWork']);verified=bit.verify(bit_work)
    paths=[canonical(p,WORK,directory=True) for p in config['Stages']]
    require(len(paths)==len(set(paths)),'duplicate selected stage')
    if bit_work not in paths:paths.append(bit_work)
    stages=[stage(p) for p in paths]
    audit_path,audit_summary,watched=physical.final_audit(bit.AUDIT)
    watched.update(bit_dependencies(bit_work))
    selected={};references={};directories={}
    def add(path,name,local=None):
        path=canonical(path)
        require(not Path(name).is_absolute() and '..' not in Path(name).parts,'unsafe archive member')
        h=sha(path);require(path not in watched or watched[path]==h,'archive input hash conflict/drift');watched[path]=h
        if local:
            references[path]={**physical.binding(path),'Copied':False,'Reason':local};return
        if path in selected.values():return
        require(name not in selected,'archive member collision');selected[name]=path
    add(config_path,'configuration.json');add(SELF,'sources/tools/'+SELF.name)
    add(Path(physical.__file__).resolve(),'sources/tools/'+Path(physical.__file__).name)
    for work,_ in stages:
        directories[work]=physical.file_set(work)
        for path in sorted(directories[work]):
            rel=path.relative_to(work)
            require(not any(part in ('compiled','sources','xsim.dir') for part in rel.parts),'selected stage unexpectedly contains compiled/source tree')
            add(path,'stages/'+work.name+'/'+rel.as_posix(),reason(path,rel))
    program_path=None;program_summary=None
    if config['PreparedProgram'] is not None:
        program_path=canonical(config['PreparedProgram'],WORK,directory=True)
        require(program_path.parent==WORK,'prepared program must be direct camera work child')
        plan=program.validate(program_path/'plan.json')
        require(plan['Bitstream']==verified['Bitstream'] and plan.get('PreparedOnly') is True and plan.get('Executed') is False,
                'prepared program differs from verified diagnostic bit')
        expected={program_path/n for n in ('plan.json','scan.tcl','program.tcl')}
        require(physical.file_set(program_path)==expected,'program directory contains execution/unexpected files')
        directories[program_path]=expected
        for path in sorted(expected):add(path,'prepared-program/'+path.name)
        program_summary={k:plan[k] for k in ('Schema','Target','Bitstream','DiagnosticOnly','HardwareAccessed','Executed',
                                            'ExternalIOAccepted','CDCPhysicalAccepted','HardwareReleaseAllowed','CDCEvidence','PinEvidence')}
        for name,h in plan['BoundInputSHA256'].items():
            p=Path(name).resolve();require(sha(p)==h,'prepared program input drift');watched[p]=h
    for value in config['SourceFiles']:
        path=source(value);add(path,'sources/'+path.relative_to(PROJECT).as_posix())
    for n,value in enumerate(config['ExtraFiles']):
        path=canonical(value)
        require(path.suffix.lower() not in ('.md',),'live markdown must be supplied through DocumentSnapshots')
        add(path,f'extra/{n:03d}-'+path.name,reason(path))
    for n,value in enumerate(config['DocumentSnapshots']):
        path=snapshot(value);add(path,f'documents/{n:03d}-'+path.name)
    add(audit_path,'audit/'+audit_path.name)
    for path in watched.copy():
        if path not in selected.values():references[path]={**physical.binding(path),'Copied':False,'Reason':'Bound dependency; retain exact local hash.'}
    for path in selected.values():references.pop(path,None)
    require(all(sha(p)==h for p,h in watched.items()),'input drift during archive preflight')
    return {'Config':config_path,'Destination':dest,'BitVerification':verified,'Stages':[v for _,v in stages],
            'Audit':audit_summary,'ProgramDirectory':str(program_path) if program_path else None,'Program':program_summary,
            'Selected':selected,'References':references,'Watched':watched,'DirectoryInventories':directories}


def verify_archive(destination):
    dest=canonical(destination,PROJECT/'results',directory=True);manifest=load(dest/'manifest.json')
    require(manifest.get('Schema')==ARCHIVE_SCHEMA,'ready archive schema differs')
    physical.verify_payloads(dest,manifest['Files'])
    actual={p.relative_to(dest).as_posix() for p in physical.file_set(dest)}
    require(actual==set(manifest['Files'])|{'manifest.json'},'missing or unexpected ready archive member')
    for item in manifest['LocalReferencesOnly']:
        p=Path(item['LocalPath']).absolute()
        require(p==p.resolve() and p.is_file() and
                (p.is_relative_to(PROJECT.parent) or p.is_relative_to(bit.PDS.parent.parent)), 'local reference escaped allowed roots')
        require(sha(p)==item['SHA256'] and p.stat().st_size==item['Bytes'],'local ready reference drift')
    return {'ReadbackVerified':True,'Files':len(manifest['Files']),'LocalReferences':len(manifest['LocalReferencesOnly']),
            'ManifestSHA256':sha(dest/'manifest.json'),'HardwareReleaseAllowed':False}


def archive(config_path):
    plan=prepare(config_path);dest=plan['Destination'];dest.mkdir();files={}
    for name,path in sorted(plan['Selected'].items()):
        compress=path.suffix.lower() in ('.rtr','.rtx','.log') or path.stat().st_size>=131072
        target=name+('.gz' if compress else '')
        if len(str(dest/target))>235:
            target='long-paths/'+hashlib.sha256(name.encode()).hexdigest()[:24]+path.suffix+('.gz' if compress else '')
        require(target not in files,'compressed archive member collision')
        files[target]=physical.copy_bound(path,dest/target,compress);files[target]['OriginalArchiveMember']=name
    physical.verify_payloads(dest,files)
    require(all(sha(p)==h for p,h in plan['Watched'].items()),'input drift before archive freeze')
    for directory,expected in plan['DirectoryInventories'].items():
        require(physical.file_set(directory)==expected,'explicit stage/program directory changed during archive')
    manifest={'Schema':ARCHIVE_SCHEMA,'ArchivedUTC':datetime.now(timezone.utc).isoformat(),'Destination':str(dest),
              'Files':files,'LocalReferencesOnly':[v for _,v in sorted(plan['References'].items())],
              'Stages':plan['Stages'],'FailedTrialCount':sum(v['FailedTrialPreserved'] for v in plan['Stages']),
              'VerifiedBitstream':plan['BitVerification']['Bitstream'],'FinalADFSHA256':bit.ADF_SHA,
              'FinalAudit':plan['Audit'],'PreparedProgramDirectory':plan['ProgramDirectory'],'PreparedProgram':plan['Program'],
              'ExplicitStageListOnly':True,'DocumentsFromExplicitSnapshotsOnly':True,'PerFileDecodedReadbackVerifiedBeforeManifest':True,
              'InputsUnchangedAtFreeze':True,'ManifestSelfHashExcluded':True,'DiagnosticOnly':True,
              'EDAExecutedByArchiver':False,'HardwareAccessedByArchiver':False,'ExternalTimingAccepted':False,
              'AllCDCUniversallyProven':False,'HardwareValidated':False,'HardwareReleaseAllowed':False,
              'Limits':['Offline diagnostic evidence archive; no hardware or external AC acceptance.',
                        'Failed native attempts retain original receipts and outcomes.',
                        'ADF, bitstreams, full routes and vendor/generated HDL remain local hash references.',
                        'Documents are snapshots and do not depend on later live handoff pointer updates.']}
    with (dest/'manifest.json').open('x',encoding='utf-8',newline='\n') as stream:json.dump(manifest,stream,indent=2);stream.write('\n')
    return {'Archived':True,'Manifest':str(dest/'manifest.json'),**verify_archive(dest)}


def main():
    p=argparse.ArgumentParser(description=__doc__);m=p.add_mutually_exclusive_group(required=True)
    m.add_argument('--config',type=Path);m.add_argument('--verify-only',type=Path);p.add_argument('--validate-only',action='store_true')
    args=p.parse_args();require(not args.validate_only or args.config is not None,'--validate-only requires config')
    if args.verify_only:result=verify_archive(args.verify_only)
    elif args.validate_only:
        plan=prepare(args.config);result={'Validated':True,'FilesWouldCopy':len(plan['Selected']),'LocalReferences':len(plan['References']),
                                        'Stages':len(plan['Stages']),'Destination':str(plan['Destination']),'FilesWritten':False,'EDAExecuted':False}
    else:result=archive(args.config)
    print(json.dumps(result))


if __name__=='__main__':main()
