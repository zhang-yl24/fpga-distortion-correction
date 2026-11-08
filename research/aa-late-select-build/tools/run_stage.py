#!/usr/bin/env python3
"""Fail-closed identity/lineage adapter around the unchanged public PDS launcher."""
from __future__ import annotations
import argparse, datetime, json, math, os, subprocess, sys
from pathlib import Path
sys.dont_write_bytecode=True
from preflight import ROOT, check, sha, safe_file, resolve_pds
STAGES=['map','place','route','sta','bitgen']
PREVIOUS={'place':'map','route':'place','sta':'route','bitgen':'route'}
SUFFIX={'place':'_map.adf','route':'_plc.adf','sta':'_pnr.adf','bitgen':'_pnr.adf'}

def validate_predecessor(root, stage, checkpoint, review, *, vendor_receipt_sha256=None, tool_receipt_sha256=None):
    if stage=='map':
        if checkpoint or review: raise ValueError('Map cannot consume a checkpoint or predecessor review')
        return None
    if not checkpoint or not review: raise ValueError('Prior stage checkpoint and reviewed receipt are required')
    previous=PREVIOUS[stage]; p=Path(checkpoint).resolve(); stage_dir=root/'build-repro'/previous
    if stage_dir.is_symlink() or not stage_dir.resolve().is_relative_to(root.resolve()):raise ValueError('Predecessor stage directory escapes isolated root or is a symlink')
    out=stage_dir.resolve()
    if not p.is_file() or not p.is_relative_to(out) or not p.name.endswith(SUFFIX[stage]):raise ValueError('Checkpoint must be the newly generated matching predecessor output inside this root')
    record=json.loads(safe_file(root,f'build-repro/{previous}.receipt.json').read_text())
    identity=json.loads((root/'BUILD_IDENTITY.json').read_text())['build_input_identity']
    if record['stage']!=previous or record['build_input_identity']!=identity or record['exit_code']!=0:raise ValueError('Predecessor identity/stage/exit mismatch')
    if vendor_receipt_sha256 is not None and record.get('vendor_receipt_sha256')!=vendor_receipt_sha256:raise ValueError('Vendor receipt/inputs changed since predecessor stage')
    if tool_receipt_sha256 is not None and record.get('tool_receipt_sha256')!=tool_receipt_sha256:raise ValueError('PDS tool receipt changed since predecessor stage')
    recorded={x['path']:x['sha256'] for x in record['output_adfs']}
    if recorded.get(p.relative_to(root).as_posix())!=sha(p):raise ValueError('Predecessor ADF has changed or was not recorded')
    acceptance=json.loads(Path(review).read_text())
    for k,v in {'build_input_identity':identity,'stage':previous,'checkpoint_sha256':sha(p),'accepted_for_next_stage':True,'unresolved_cells_or_blackboxes':False}.items():
        if acceptance.get(k)!=v:raise ValueError('Manual predecessor review missing/mismatching: '+k)
    reports=acceptance.get('reviewed_reports',[])
    generated={x['path']:x['sha256'] for x in record.get('output_files',[])}
    if not reports:raise ValueError('Review must identify actual generated reports and hashes')
    for item in reports:
        rp=safe_file(root,item['path']).resolve()
        if not rp.is_relative_to(out) or not rp.is_file() or sha(rp)!=item.get('sha256'):raise ValueError('Reviewed report missing or hash differs')
        if generated.get(item['path'])!=item.get('sha256'):raise ValueError('Reviewed report was not recorded as a generated predecessor output')
    return p


def validate_sta_review(root, checkpoint, review, identity, vendor_sha, tool_sha):
    if not review:raise ValueError('Bitgen requires an explicit reviewed STA/coverage receipt; exit zero is not signoff')
    out=root/'build-repro/sta'
    if out.is_symlink() or not out.resolve().is_relative_to(root.resolve()):raise ValueError('STA output directory escapes isolated root or is a symlink')
    record=json.loads(safe_file(root,'build-repro/sta.receipt.json').read_text())
    for k,v in {'stage':'sta','exit_code':0,'build_input_identity':identity,'input_adf_sha256':sha(checkpoint),'vendor_receipt_sha256':vendor_sha,'tool_receipt_sha256':tool_sha}.items():
        if record.get(k)!=v:raise ValueError('STA execution identity mismatch: '+k)
    acceptance=json.loads(Path(review).read_text())
    required={'stage':'sta','build_input_identity':identity,'checkpoint_sha256':sha(checkpoint),'vendor_receipt_sha256':vendor_sha,'tool_receipt_sha256':tool_sha,'accepted_for_offline_bitgen':True,'unresolved_cells_or_blackboxes':False,'setup_and_hold_reviewed':True,'unconstrained_and_zero_coverage_reviewed':True,'clock_and_exception_coverage_reviewed':True,'physical_io_and_cdc_limitations_acknowledged':True}
    for k,v in required.items():
        if acceptance.get(k)!=v:raise ValueError('STA report/coverage review mismatch: '+k)
    for key in ('worst_setup_slack_ns','worst_hold_slack_ns'):
        value=acceptance.get(key)
        try:valid=type(value) in (int,float) and math.isfinite(value) and value>=0
        except (OverflowError,TypeError):valid=False
        if not valid:raise ValueError('STA review requires finite nonnegative numeric '+key)
    clocks=acceptance.get('reviewed_clock_count');unconstrained=acceptance.get('unconstrained_path_count')
    if type(clocks) is not int or clocks<=0:raise ValueError('STA review requires positive integer reviewed_clock_count')
    if type(unconstrained) is not int or unconstrained!=0:raise ValueError('STA review requires zero integer unconstrained_path_count')
    reports=acceptance.get('reviewed_reports',[])
    generated={x['path']:x['sha256'] for x in record.get('output_files',[])}
    if not reports:raise ValueError('STA review requires actual generated reports with hashes')
    for item in reports:
        p=safe_file(root,item['path'])
        if not p.resolve().is_relative_to(out.resolve()) or not p.is_file() or sha(p)!=item.get('sha256'):raise ValueError('STA reviewed report missing, outside stage or changed')
        if generated.get(item['path'])!=item.get('sha256'):raise ValueError('STA reviewed report was not recorded as a generated output')


def ensure_fresh(root,stage):
    parent=root/'build-repro'
    if parent.is_symlink() or not parent.resolve().is_relative_to(root.resolve()):raise ValueError('Build output parent escapes isolated root')
    for p in [root/'build-repro'/stage,root/'build-repro'/f'{stage}.receipt.json',root/'build-repro'/f'{stage}.lock']:
        if p.exists():raise ValueError('Refusing existing stage output/receipt/lock: '+str(p))

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('stage',choices=STAGES);ap.add_argument('--root',type=Path,default=ROOT);ap.add_argument('--pds',required=True);ap.add_argument('--vendor-receipt',type=Path,required=True);ap.add_argument('--tool-receipt',type=Path,required=True);ap.add_argument('--input-adf',type=Path);ap.add_argument('--predecessor-review',type=Path);ap.add_argument('--sta-review',type=Path)
    a=ap.parse_args();root=a.root.resolve()
    try:
        ensure_fresh(root,a.stage)
        pds_executable=resolve_pds(a.pds)
        gate=check(root,require_eda=True,pds=pds_executable,vendor_receipt=a.vendor_receipt,tool_receipt=a.tool_receipt)
        if gate['errors']:
            print(json.dumps(gate,indent=2));return 2
        checkpoint=validate_predecessor(root,a.stage,a.input_adf,a.predecessor_review,vendor_receipt_sha256=sha(a.vendor_receipt),tool_receipt_sha256=sha(a.tool_receipt))
        if a.stage=='bitgen':
            validate_sta_review(root,checkpoint,a.sta_review,gate['build_input_identity'],sha(a.vendor_receipt),sha(a.tool_receipt))
        elif a.sta_review:raise ValueError('--sta-review is valid only for bitgen')
        parent=root/'build-repro';parent.mkdir(exist_ok=True)
        lock=parent/f'{a.stage}.lock'
        with lock.open('x') as f:f.write('Stage launch attempted; retain this lock even after interruption. Never overwrite or resume.\n')
        command=[sys.executable,str(root/'rebuild/run_build.py'),a.stage,'--root',str(root),'--pds',str(pds_executable)]
        if checkpoint:command+=['--input-adf',str(checkpoint)]
        record={'schema':1,'stage':a.stage,'build_input_identity':gate['build_input_identity'],'started_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'input_adf_sha256':sha(checkpoint) if checkpoint else None,'vendor_receipt_sha256':sha(a.vendor_receipt),'tool_receipt_sha256':sha(a.tool_receipt),'status':'STARTED_NOT_SIGNOFF','sta_review_sha256':sha(a.sta_review) if a.sta_review else None,'predecessor_review_sha256':sha(a.predecessor_review) if a.predecessor_review else None,'command':command}
        receipt=parent/f'{a.stage}.receipt.json'
        with receipt.open('x') as f:json.dump(record,f,indent=2)
        result=subprocess.run(command,cwd=root,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
        outputs=[]
        for p in sorted((parent/a.stage).rglob('*')):
            if p.is_symlink():raise ValueError('Generated output symlink cannot be admitted: '+str(p.relative_to(root)))
            if p.is_file():
                rel=p.relative_to(root).as_posix();safe_file(root,rel)
                outputs.append({'path':rel,'sha256':sha(p),'bytes':p.stat().st_size})
        record.update(exit_code=result.returncode,finished_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),status='GENERATED_UNREVIEWED' if result.returncode==0 else 'FAILED',output_files=outputs,output_adfs=[e for e in outputs if e['path'].endswith('.adf')],output_sbits=[e for e in outputs if e['path'].endswith('.sbit')])
        receipt.write_text(json.dumps(record,indent=2)+'\n')
        print('Stage receipt:',receipt);print('No timing, CDC, I/O or board signoff is inferred. Review real reports and reject all unresolved cells/blackboxes.')
        return result.returncode
    except (OSError,ValueError,KeyError,TypeError) as e:print('STOP:',e,file=sys.stderr);return 2
if __name__=='__main__':sys.exit(main())
