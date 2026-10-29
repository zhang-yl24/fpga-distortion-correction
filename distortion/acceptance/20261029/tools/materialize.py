"""Prepare a fresh portable offline case. Never launch EDA, RTL, or hardware."""
from pathlib import Path
import argparse,hashlib,json,shutil
P=Path(__file__).resolve().parents[1]
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def checked(path,expected):
    path=Path(path).resolve()
    if not path.is_file() or sha(path)!=expected:raise ValueError('Missing/mismatched external or source input: '+str(path))
    return path
def safe(path):
    s=Path(path).resolve().as_posix()
    if any(x in s for x in '{}\r\n'):raise ValueError('Unsafe Tcl path')
    return s
def main():
    m=json.loads((P/'manifest.json').read_text(encoding='utf-8'))
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--case',required=True,choices=[*m['Cases'],'board'])
    ap.add_argument('--out',type=Path,required=True)
    for flag in ('fixture-dir','vivado-bin','vendor-root','parameter-header','fdc','pds-shell','final-adf'):
        ap.add_argument('--'+flag,type=Path)
    a=ap.parse_args();out=a.out.resolve()
    if out.exists() or out.is_relative_to(P):raise ValueError('Use a fresh output outside the frozen package')
    for name,h in m['PackageFilesSHA256'].items():checked(P/name,h)
    inputs={str(P/n):h for n,h in m['PackageFilesSHA256'].items()}
    copied=[];plan={'Case':a.case,'GateState':m['GateState'],'ToolsExecuted':False,'HardwareAccessed':False,'PortableEntryPreviouslyExecuted':False,'PackageManifestSHA256':sha(P/'manifest.json')}
    pending=[]
    def source(relative):
        p=checked(P/relative,m['Sources'][relative]['DeliveredSHA256']);pending.append((p,p.name));copied.append(p.name);return p.name
    if a.case!='board':
        if not a.vivado_bin:ap.error('--vivado-bin is required for RTL preparation')
        c=m['Cases'][a.case]
        names=[source(n) for n in c['Sources']]
        for n in ('rtl/video_crc32.vh','rtl/gamma_curves.vh'):source(n)
        if c['Fixtures'] and not a.fixture_dir:ap.error('--fixture-dir must supply the exact private fixtures')
        for n,h in c['Fixtures'].items():
            p=checked(a.fixture_dir/n,h);pending.append((p,n));inputs[str(p)]=h
        plan.update(Top=c['Top'],MaximumTotalSeconds=c['MaximumTotalSeconds'],PassMarker=c['PassMarker'])
        plan['Commands']=[{'Stage':stage,'Exe':exe,'Args':args} for stage,exe,args in (
            ('compile','xvlog.bat',['--sv',*names]),
            ('elaborate','xelab.bat',[c['Top'],'-s','acceptance_snapshot']),
            ('simulate','xsim.bat',['acceptance_snapshot','-runall','-log','simulation.log']))]
        plan['VivadoBin']=str(a.vivado_bin.resolve())
    else:
        if not all((a.vendor_root,a.parameter_header,a.fdc,a.pds_shell)):ap.error('board requires --vendor-root,--parameter-header,--fdc,--pds-shell')
        external={}
        for e in m['ExternalDependencies']:
            p=a.vendor_root/e['RelativePath'] if e['Anchor']=='vendor-root' else a.parameter_header if e['Anchor']=='parameter-header' else a.fdc
            p=checked(p,e['SHA256']);external[e['Id']]=p;inputs[str(p)]=e['SHA256']
        names=[]
        for e in m['BoardAddDesign']:
            names.append(safe(out/source(e['PackagePath'])) if 'PackagePath' in e else safe(external[e['ExternalId']]))
        for n in ('rtl/video_crc32.vh','rtl/gamma_curves.vh'):source(n)
        pending.append((a.parameter_header.resolve(),'board1080-penn.vh'))
        fdc=checked(a.fdc,next(e['SHA256'] for e in m['ExternalDependencies'] if e['Anchor']=='fdc'))
        prefix=''.join('add_design {'+n+'}\n' for n in names)
        prefix+='add_constraint {'+safe(fdc)+'}\nset_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676\n'
        freshmap=out/'device_map/board1080_top_map.adf';freshpcf=out/'device_map/board1080_top.pcf'
        pnr=prefix+'add_constraint {'+safe(freshpcf)+'}\npnr -force_to_run -input_db_file {'+safe(freshmap)+'} -gplace_seed 2 -optimize_multi_corner_timing -fix_hold_violation -fix_hold_violation_iterations 50 -fix_hold_violation_threshold 100\n'
        final=a.final_adf.resolve() if a.final_adf else out/'place_route/board1080_top_pnr.adf'
        if a.final_adf:
            expected='6e3a254a5e62dc32811c46e0610209bb98d5ef5d37444722c833793756c45143'
            checked(final,expected);inputs[str(final)]=expected
        plan['PreparedTcl']={'compile-map.tcl':prefix+'compile -top_module board1080_top\nsynthesize -ads -selected_syn_tool_opt 2\ndev_map\n',
            'pnr.tcl':pnr,
            'sta-final.tcl':prefix+'report_timing -force_to_run -input_db_file {'+safe(final)+'} -delay_type min_max -nworst 1 -max_path 20 -report_exception TRUE -report_max_skew\n'}
        plan['Commands']={n:[str(a.pds_shell.resolve()),'-file',str(out/n),'-work_dir',str(out),'-project_name','acceptance_board'] for n in plan['PreparedTcl']}
        plan['Warning']='Preparation only. Source/FDC closure and resource admission precede PNR. Exact saved --final-adf needs STA only, not frontend/PNR. Tools require separate scheduling/budget approval. No bit or hardware commands.'
    assert len({n for _,n in pending})==len(pending),'duplicate flattened source/fixture name'
    out.mkdir(parents=True,exist_ok=False)
    for p,n in pending:shutil.copyfile(p,out/n)
    for n,text in plan.pop('PreparedTcl',{}).items():(out/n).write_text(text,encoding='utf-8')
    plan['InputsSHA256']=inputs;plan['WorkFilesSHA256']={p.name:sha(p) for p in out.iterdir() if p.is_file()}
    (out/'commands.json').write_text(json.dumps(plan,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'PreparedOnly':str(out),'Case':a.case,'NoToolExecuted':True}))
if __name__=='__main__':main()
