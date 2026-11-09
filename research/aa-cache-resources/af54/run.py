"""Portable Icarus runner. Run only inside a materialized workspace."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parent
CACHE = 'source/rtl/experimental/d256_runtime_prefetch_cache.sv'

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode', choices=['units', 'busy', 'full', 'hierarchy', 'proof'])
    p.add_argument('--iverilog', default='iverilog')
    p.add_argument('--vvp', default='vvp')
    p.add_argument('--output', required=True, type=Path, help='Exclusive fresh output directory')
    p.add_argument('--allow-partial-missing-modules', action='store_true',
                   help='Explicit opt-in to Icarus -i parameter binding, never a board build pass')
    a = p.parse_args()
    if not (ROOT/'MATERIALIZED.json').exists():
        p.error('First run materialize.py with an explicitly supplied frozen AA native tree')
    if a.allow_partial_missing_modules and a.mode != 'hierarchy':
        p.error('Partial-module option is only valid for hierarchy mode')
    out = a.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    report = {'mode':a.mode, 'status':'RUNNING', 'cases':[], 'physical_implementation':'NOT_RUN'}
    def invoke(cmd, log, cwd=ROOT, timeout=600):
        result = subprocess.run(cmd,cwd=cwd,text=True,capture_output=True,timeout=timeout)
        text = result.stdout + result.stderr
        text = text.replace(str(out),'<OUTPUT>').replace(str(ROOT),'<WORKSPACE>')
        (out/log).write_text(text)
        return result.returncode,text
    try:
        if a.mode == 'proof':
            import sys
            code, text = invoke([sys.executable,str(ROOT/'check_traversal.py')], 'proof.log')
            if code: raise RuntimeError('Traversal proof failed')
            report['proof'] = json.loads(text)
        else:
            iv = shutil.which(a.iverilog)
            vv = shutil.which(a.vvp)
            if not iv or not vv: raise RuntimeError('Explicit Icarus/vvp executable unavailable')
            invoke([iv,'-V'],'iverilog-version.log')
            invoke([vv,'-V'],'vvp-version.log')
            identities = json.loads((ROOT/'SOURCE_IDENTITY.json').read_text())['Sources']
            for tree,key in [('baseline','AA_SHA256'),('candidate','AF54_SHA256')]:
                for relative, identity in identities.items():
                    if hashlib.sha256((ROOT/tree/'native'/relative).read_bytes()).hexdigest()!=identity[key]:
                        raise RuntimeError('Source identity mismatch: '+tree+'/'+relative)
            src=ROOT/'candidate/native/source/rtl/experimental'
            deps=[str(src/n) for n in ('sync_token_fifo.sv','quad_parity_prefetch_store.sv')]
            for tree,name in [('baseline','cache_baseline'),('candidate','cache_fallback')]:
                text=(ROOT/tree/'native'/CACHE).read_text()
                (out/(name+'.sv')).write_text(text.replace('module d256_runtime_prefetch_cache #(', 'module '+name+' #(',1))
            def test(name,tb,top,params,sources,expected='PASS_',incompatible=False,partial=False):
                exe=out/(name+'.vvp')
                command=[iv,'-g2012','-s',top,'-o',str(exe)]
                if partial:command+=['-i']
                command += [f'-P{top}.{k}={v}' for k,v in params.items()]
                code,text=invoke(command+[str(ROOT/'tests'/tb)]+sources,name+'.compile.log',ROOT/'candidate/native')
                if code:raise RuntimeError(name+' compile failed')
                code,text=invoke([vv,str(exe)],name+'.run.log',ROOT/'candidate/native')
                ok=(code!=0 and 'AF raster-tag packing requires explicit native AA configuration' in text) if incompatible else (code==0 and expected in text)
                report['cases'].append({'case':name,'parameters':params,'pass':ok,'exit':code,'output':text.strip()})
                if not ok:raise RuntimeError(name+' failed')
            if a.mode=='units':
                (out/'cache_AA.sv').write_text((ROOT/'baseline/native'/CACHE).read_text().replace('module d256_runtime_prefetch_cache #(','module cache_AA #(',1))
                cases={'enabled':{},'final24':{'FINAL':1},'default':{'PACK':0},'generic_tag8':{'PACK':0,'TW':8},**{f'bad_bit{b}':{'BAD':b+1} for b in (0,1,2,3,4,5,21,22,23)},**{f'incompatible_{k}':{k:v} for k,v in [('W',2048),('H',1024),('TW',24),('STRIDE',0),('HEAD',1),('COMPACT',0),('IB',6),('PACK',2)]}}
                for name,params in cases.items():
                    test(name,'tb_tagpack.sv','tb_tagpack',params,[str(src/'d256_runtime_prefetch_cache.sv'),str(out/'cache_AA.sv')]+deps,incompatible=name.startswith('incompatible'))
            elif a.mode in ('busy','full'):
                sources=[str(out/'cache_baseline.sv'),str(out/'cache_fallback.sv')]+deps
                if a.mode=='busy':
                    for pressure in range(3):test('pressure'+str(pressure),'tb_busy_reject.sv','tb_full_cache_ab',{'PRESSURE':pressure},sources,'PASS_BUSY_REJECTION')
                else:test('full','tb_actual_head0.sv','tb_full_cache_ab',{},sources,'PASS_FULL_CACHE_AB')
            else:
                sources=sorted(str(f) for f in (ROOT/'candidate/native').rglob('*') if f.suffix in ('.v','.sv'))
                code,text=invoke([iv,'-g2012','-s','tb_hierarchy','-o',str(out/'strict.vvp'),str(ROOT/'tests/tb_hierarchy.sv')]+sources,'strict.compile.log',ROOT/'candidate/native')
                report['strict_compile_exit']=code
                report['note']='Only parameter binding. No full-board functional or implementation validity.'
                if a.allow_partial_missing_modules:
                    for pack in (0,1):test('partial'+str(pack),'tb_hierarchy.sv','tb_hierarchy',{'PACK':pack},sources,'PASS_HIERARCHY',partial=True)
                    report['status']='PARTIAL_PARAMETER_BINDING_ONLY'
                elif code:
                    raise RuntimeError('Strict hierarchy compile failed; inspect log. Partial -i requires explicit opt-in.')
                else:report['status']='STRICT_ELABORATION_ONLY'
        if report['status']=='RUNNING':report['status']='PASS'
    except Exception as e:
        report['status']='FAILED_OR_BLOCKED';report['error']=str(e)
        raise
    finally:
        (out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    print(report['status'])

if __name__=='__main__':
    main()
