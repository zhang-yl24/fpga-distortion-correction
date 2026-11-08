#!/usr/bin/env python3
"""Read-only late-select source/configuration gate; no EDA, network or hardware."""
from __future__ import annotations
import argparse, csv, hashlib, importlib.util, json, os, re, shutil, subprocess, sys
import xml.etree.ElementTree as ET
from pathlib import Path
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
TOP = 'native/source/build/offline-20261024/cfg100-independent-20261030-a/candidate/board1080_cfg100_top.v'
SYSTEM = 'native/source/build/offline-20261024/bypass-system1080-20261029-a/hdmi1080_video_system_geometry_ab.v'
CACHE = 'native/source/rtl/experimental/d256_runtime_prefetch_cache.sv'
FDC = 'native/source/build/offline-20261024/boardtop-penn-prep-20261029-a/board1080-diagnostic.fdc'
DDR = 'native/source/platform/video_base/ipcore/ddr3_test/ddr3_test.idf'
PLL = [('cfg_pll', 'native/source/platform/video_base/ipcore/cfg_pll/cfg_pll.v'), ('bringup_pll', 'native/source/board/bringup_pll.v')]

def sha(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1024*1024), b''):digest.update(block)
    return digest.hexdigest()

def resolve_pds(pds):
    # Resolve in the caller's cwd exactly once; pass this absolute file onward.
    return Path(shutil.which(str(pds)) or str(pds)).resolve()

def canonical(obj):
    return json.dumps(obj, sort_keys=True, separators=(',', ':')).encode()

def safe_file(root, rel):
    p = Path(rel)
    if p.is_absolute() or '..' in p.parts or not p.parts:
        raise ValueError('Unsafe relative input: ' + rel)
    q = root / p
    if q.is_symlink() or not q.resolve().is_relative_to(root.resolve()):
        raise ValueError('Input escapes isolated root: ' + rel)
    return q

def load_module(path):
    spec = importlib.util.spec_from_file_location('aa_original_verifier', path)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m

def strip(text):
    return re.sub(r'\s+', '', re.sub(r'/\*.*?\*/|//[^\n]*', '', text, flags=re.S))

def read_receipt(path, label, errors):
    if path is None:
        errors.append(label + ' receipt required; no implicit IP/tool acceptance')
        return None
    try:
        value=json.loads(Path(path).read_text())
        if not isinstance(value,dict) or not value:raise ValueError('Receipt must be a nonempty JSON object')
        return value
    except (OSError, ValueError) as exc:
        errors.append(label + ' receipt unreadable: ' + str(exc)); return None

def check(root=ROOT, *, require_eda=False, pds=None, vendor_receipt=None, tool_receipt=None):
    root = Path(root).resolve(); errors = []; gates = []
    identity = json.loads((root / 'BUILD_IDENTITY.json').read_text())
    payload = identity['payload']
    if hashlib.sha256(canonical(payload)).hexdigest() != identity['build_input_identity']:
        errors.append('BUILD_IDENTITY payload digest mismatch')
    for item in payload['files']:
        p = safe_file(root, item['path'])
        if not p.is_file() or sha(p) != item['sha256']:
            errors.append('First-party input identity mismatch: ' + item['path'])
    if errors:
        return {'status':'STOP','errors':errors,'eda_launched':False,'build_input_identity':identity['build_input_identity']}
    # All published native files and every recipe input are exact-hash locked.
    for item in payload['files']:
        if item['path'].startswith('native/') and item['path'] not in (TOP, SYSTEM):
            if item.get('upstream_sha256') != item['sha256']:
                errors.append('Unapproved upstream native delta: ' + item['path'])
    if sha(root / SYSTEM) != '44fa12a52082ca9e2319e7c1ad7ed1e6603efc99c4687a39353a5e8d7895c918':
        errors.append('Frozen late wrapper changed')
    if sha(root / CACHE) != 'ff5e551c13083cecf9325b6acef0a00b58f7f1776cd7f5dbec341e52f2082088':
        errors.append('Frozen AA cache changed')
    top = strip((root / TOP).read_text()); system = strip((root / SYSTEM).read_text())
    for token in ['parameterDISPLAY_SELECT_GRACE_CYCLES=8192,', '.DISPLAY_SELECT_GRACE_CYCLES(DISPLAY_SELECT_GRACE_CYCLES)', '.DEBOUNCE_CYCLES(2500000)', '.CACHE_HEAD_PREDECODE(RATIONAL_BROWN_PROFILE?0:1)', '.RESULT_BANKS(2)', '.STATS_ENABLE(1)', '.STATS_CORE_HZ(125000000)', '.ENABLE_RUNTIME_ROTATION(!RATIONAL_BROWN_PROFILE&&CAMERA_RUNTIME_GAMMA)', ".cfg_rot_cos(RATIONAL_BROWN_PROFILE?32'sd1073741824:B1080_ROT_COS)", ".cfg_rot_sin(RATIONAL_BROWN_PROFILE?32'sd0:B1080_ROT_SIN)", '.HT(2200)', '.VT(1125)']:
        if top.count(token) != 1: errors.append('Late TOP configuration mismatch: ' + token)
    if 'parameterintegerDISPLAY_SELECT_GRACE_CYCLES=0' not in system:
        errors.append('System compatibility default must remain zero')
    expected = (root / 'rebuild/expected_source_files.txt').read_text().splitlines()
    imports = (root / 'rebuild/design_imports.txt').read_text().splitlines()
    for rel in expected + imports: safe_file(root, rel)
    if (root / 'rebuild/source-list.txt').read_bytes() != (root / 'rebuild/expected_source_files.txt').read_bytes():
        errors.append('Tcl and Python closure manifests differ')
    for recipe in ('map.tcl', 'physical.tcl'):
        text = (root / 'rebuild' / recipe).read_text()
        actual = re.findall(r'add_design \[repo \{([^}]+)\}\]', text)
        if actual != imports: errors.append(recipe + ' ordered imports mismatch')
    missing, original_errors = load_module(root / 'rebuild/verify_sources.py').check(root, root / 'rebuild')
    declared = {x['path'] for x in json.loads((root / 'EXTERNAL_INPUTS.json').read_text())['required']}
    if len(declared) != 77 or len(expected) != 155 or len(imports) != 68:
        errors.append('Closure cardinality mismatch')
    errors.extend(original_errors)
    # Keep every referenced synthesis input inside the same recorded 155-file
    # closure. New generator dependencies need a separately reviewed contract.
    expected_set=set(expected)
    for rel in expected:
        p=root/rel
        if not p.is_file(): continue
        text=p.read_text(encoding='utf-8',errors='replace')
        references=[]
        if p.suffix.lower() in ('.v','.sv','.vh','.svh','.vp'):
            # Encrypted .vp payload is opaque; plaintext header dependencies
            # still matter. Never silently ignore a macro/nonliteral include.
            uncommented=re.sub(r'"(?:\\.|[^"\\])*"|/\*.*?\*/|//[^\r\n]*',lambda m:m[0] if m[0].startswith('"') else ' ',text,flags=re.S)
            tokens=re.finditer(r'"(?:\\.|[^"\\])*"|`include\b([^\r\n]*)',uncommented)
            for token in tokens:
                if token.group(1) is None:continue
                literal=re.fullmatch(r'\s*"([^"\r\n]+)"\s*',token.group(1))
                if not literal:
                    errors.append('Unsupported nonliteral include requires reviewed dependency contract: '+rel)
                    continue
                name=literal.group(1)
                candidates=[p.parent/name,root/'native'/name,root/'native/b4/rtl'/name]
                q=next((q for q in candidates if q.is_file()),candidates[0])
                references.append(q)
        if p.suffix.lower()=='.idf':
            try:
                references.extend(p.parent/e.attrib['pathname'] for e in ET.fromstring(text).findall('./file_list/source/file'))
            except (ET.ParseError,KeyError): pass # Original verifier records this error.
        for q in references:
            resolved=q.resolve()
            if not resolved.is_relative_to(root) or resolved.relative_to(root).as_posix() not in expected_set:
                errors.append('Synthesis dependency outside recorded closure: '+rel)
    unexpected_missing = sorted(set(missing) - declared)
    errors.extend('Missing non-vendor input: ' + p for p in unexpected_missing)
    gates.append({'name':'public_source_identity_and_config','pass':not errors})
    eda_errors = []
    if require_eda:
        eda_errors.extend('Missing vendor/IP input: ' + p for p in missing if p in declared)
        vr = read_receipt(vendor_receipt, 'External input', eda_errors)
        tr = read_receipt(tool_receipt, 'PDS tool', eda_errors)
        if vr:
            required = {'schema':1, 'authorized_use':True, 'placeholder_or_blackbox_inputs':False, 'ddr_generator':'2022.2-SP6.4 build146967', 'ddr_model':'HMIC_S1.10', 'device':'Logos2 PG2L100H -6 FBG676'}
            for k, v in required.items():
                if vr.get(k) != v: eda_errors.append('External receipt mismatch: ' + k)
            if not isinstance(vr.get('provenance'), str) or not vr['provenance'].strip(): eda_errors.append('External receipt needs actual authorized acquisition/generation provenance')
            entries = vr.get('files', [])
            if len(entries) != 77 or {e.get('path') for e in entries} != declared: eda_errors.append('External receipt must bind exactly 77 required files')
            for ent in entries:
                rel = ent.get('path', ''); p = safe_file(root, rel)
                if not p.is_file() or not re.fullmatch(r'[0-9a-f]{64}', ent.get('sha256', '')) or sha(p) != ent['sha256']:
                    eda_errors.append('External input SHA mismatch/missing: ' + rel)
                elif p.stat().st_size < 64:
                    eda_errors.append('Empty/trivial vendor input rejected: ' + rel)
        tool = None
        if pds:
            tool = resolve_pds(pds)
        if tool is None or not tool.is_file() or not os.access(tool, os.X_OK):
            eda_errors.append('Installed executable pds_shell is missing or not executable')
        if tr:
            for k,v in {'schema':1,'product':'PDS','version':'2025.2','fabric_compiler_build':'211867','normal_authorized_license_setup':True}.items():
                if tr.get(k) != v: eda_errors.append('Tool receipt mismatch: ' + k)
            if tool and tool.is_file() and tr.get('executable_sha256') != sha(tool): eda_errors.append('Tool executable SHA mismatch')
            # Do not invent a vendor --version flag. Operator records official banner/help evidence.
            if not isinstance(tr.get('version_evidence'),str) or not tr['version_evidence'].strip(): eda_errors.append('Tool receipt needs actual official version/banner evidence')
        if not missing:
            commands = [[sys.executable, str(root/'ip_setup/configure_ddr_idf.py'), str(root/DDR), '--check']]
            commands += [[sys.executable, str(root/'ip_setup/check_pll_parameters.py'), name, str(root/rel)] for name, rel in PLL]
            for cmd in commands:
                p = subprocess.run(cmd, capture_output=True, text=True, env={**os.environ, 'PYTHONDONTWRITEBYTECODE':'1'})
                gates.append({'name':'vendor_parameter_check','command':[Path(x).name if Path(x).is_absolute() else x for x in cmd], 'exit_code':p.returncode,'output':(p.stdout+p.stderr).strip()})
                if p.returncode: eda_errors.append('Vendor parameter checker rejected input: ' + Path(cmd[1]).name)
        errors.extend(eda_errors)
    return {'schema':1,'build_input_identity':identity['build_input_identity'], 'status':'STOP' if errors else ('EDA_INPUTS_READY_NOT_SIGNOFF' if require_eda else 'PUBLIC_KIT_STATIC_PASS_EXTERNAL_INPUTS_STILL_REQUIRED'), 'errors':errors, 'public_native_present':len(expected)-sum(p in expected for p in missing),'required_native_total':155,'direct_imports':68,'missing_external_inputs':[p for p in missing if p in declared], 'gates':gates, 'eda_inputs_checked':require_eda,'eda_launched':False,'pds_stage_status':{s:'NOT_RUN' for s in ['map','place','route','sta','bitgen']},'physical_timing_proven':False,'board_test':'NOT_RUN','verification_limit':'File/configuration/declared provenance checks do not establish license entitlement, primitive connectivity, encrypted RTL equivalence, report coverage, timing or hardware behavior.'}

def main():
    ap=argparse.ArgumentParser(description=__doc__); ap.add_argument('--root',type=Path,default=ROOT);ap.add_argument('--require-eda',action='store_true');ap.add_argument('--pds');ap.add_argument('--vendor-receipt',type=Path);ap.add_argument('--tool-receipt',type=Path);ap.add_argument('--report',type=Path)
    a=ap.parse_args()
    try:r=check(a.root,require_eda=a.require_eda,pds=a.pds,vendor_receipt=a.vendor_receipt,tool_receipt=a.tool_receipt)
    except (OSError,ValueError,KeyError,TypeError) as e:r={'status':'STOP','errors':[str(e)],'eda_launched':False}
    output=json.dumps(r,indent=2)+'\n'
    if a.report:
        with a.report.open('x') as f:f.write(output)
    print(output,end='');return 2 if r['errors'] else 0
if __name__=='__main__':sys.exit(main())
