"""Prepare bound local compile copies. This script never starts PDS or hardware.

Manufacturer-generated dependencies stay in ignored _build, supplied explicitly
from a legally obtained native closure. Exact hashes are required; no download.
"""
from pathlib import Path
import argparse
import json
import re
from verify_package import ROOT, sha, safe_relative, verify

INCLUDE = re.compile(rb'`include\s+"([^"\r\n]+)"')

def prepare(dependency_native, run_name):
    result = verify()
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,50}', run_name):
        raise ValueError('Run name must be a short simple identifier')
    work = ROOT / '_build' / run_name
    if work.exists():
        raise FileExistsError('Use a new run name; previous prepared outputs are preserved')
    manifest = json.loads((ROOT / 'manifests/source-manifest.json').read_text(encoding='utf-8'))
    rows = manifest['files']
    deps = Path(dependency_native).resolve()
    sources = {}
    # Validate every input before writing anything.
    for r in rows:
        base = ROOT / 'native' if r['disposition']=='included_source' else deps
        p = safe_relative(base, r['path'])
        if not p.is_file() or p.stat().st_size!=r['bytes'] or sha(p)!=r['sha256']:
            raise ValueError('Exact dependency/source mismatch: ' + r['path'])
        sources[r['path']] = p
    compile_root = work / 'native'
    include_changes = []
    compile_records = []
    # Only recognized absolute include prefixes are rewritten. All other text
    # and non-HDL dependency bytes remain unchanged in the derived copies.
    for r in rows:
        src = sources[r['path']]
        original = src.read_bytes()
        blob = original
        if src.suffix.lower() in ('.v','.sv','.vh','.vp'):
            def replace(m):
                original_include = m.group(1).decode('ascii')
                inc = original_include.replace('\\','/')
                if not re.match(r'^[A-Za-z]:/',inc) and not inc.startswith('/'):
                    target = (Path(r['path']).parent / inc).as_posix()
                    if target not in sources and ('b4/rtl/' + inc) not in sources:
                        raise ValueError('Unbound relative include: ' + inc)
                    return m.group(0)
                marker = '/native/'
                if marker not in inc:
                    raise ValueError('Unrecognized absolute include: ' + inc)
                rel = inc.split(marker,1)[1]
                if rel not in sources:
                    raise ValueError('Include outside exact source closure: ' + rel)
                new = safe_relative(compile_root, rel).as_posix()
                if any(c in new for c in '{}\n\r"'):
                    raise ValueError('Unsupported compile path characters')
                include_changes.append({'file':r['path'],'original':original_include,'compiled':new})
                return ('`include "' + new + '"').encode('utf-8')
            blob = INCLUDE.sub(replace, original)
        dest = safe_relative(compile_root, r['path'])
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(blob)
        compile_records.append({'path':r['path'],'original_sha256':r['sha256'],
                                'compile_sha256':sha(dest),'relocated':blob!=original})
    recipe = json.loads((ROOT / 'manifests/build-recipe.json').read_text(encoding='utf-8'))
    def tclpath(p):
        p = p.resolve().as_posix()
        if any(c in p for c in '{}\n\r'):
            raise ValueError('Unsupported Tcl path characters')
        return '{' + p + '}'
    lines = ['# Prepared only; reproduces declaration/compile/synthesis/map intent.',
             '# New PNR, pin overlay, both-corner STA and external IO/CDC are required.',
             'proc checked {command} {',
             '  set rc [catch {uplevel 1 $command} result]',
             '  if {$rc != 0} { puts stderr $result; exit 1 }',
             '  puts $result', '}',
             'cd ' + tclpath(work)]
    for rel in recipe['designs']:
        lines.append('checked [list add_design '+ tclpath(compile_root / rel) + ']')
    for rel in recipe['constraints']:
        lines.append('checked [list add_constraint ' + tclpath(compile_root / rel) + ']')
    lines += ['checked [list set_arch -family Logos2 -device PG2L100H -speedgrade -6 -package FBG676]',
              'checked [list compile -top_module board1080_top -include_path ' + tclpath(compile_root / 'b4/rtl') + ']',
              'checked [list synthesize -ads -selected_syn_tool_opt 2]',
              'checked [list dev_map]',
              'puts {SOURCE_DELIVERY_MAP_COMPLETE_NOT_TIMING_SIGNOFF}']
    (work / 'map.tcl').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    for rel,p in sources.items():
        expected = next(r['sha256'] for r in rows if r['path']==rel)
        if sha(p)!=expected:
            raise ValueError('Input changed while preparing: ' + rel)
    result.update({'schema':'hdmi1080-derived-compile-v1','source_count':len(rows),
                   'work_directory':str(work),'include_changes':include_changes,
                   'compile_files':compile_records,'map_script_sha256':sha(work/'map.tcl'),
                   'full_pnr_recipe_included':False,
                   'note':'No PDS, PNR, STA, bit generation, hardware operation, or Git mutation performed.'})
    (work/'preparation.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    return result

if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dependency-native',type=Path,required=True)
    p.add_argument('--run-name',required=True)
    args=p.parse_args()
    result=prepare(args.dependency_native,args.run_name)
    print(json.dumps({k:result[k] for k in ['source_count','work_directory','eda_executed','hardware_accessed']},indent=2))
