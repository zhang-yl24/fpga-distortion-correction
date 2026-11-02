"""Freeze the current-lens calibrated VGA candidate, without EDA or hardware."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import prepare_camera_vga_upright as upright

baseline = upright.baseline
PROJECT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()
TARGET = 'camera_vga_calibrated_top'
TOP = 'board/camera_vga_calibrated_top.v'
HEADER = 'board/camera-vga-current-lens.vh'
DELAY = 'rtl/experimental/raw_camera_input_delay.v'
MANIFEST = 'board/camera-vga-calibrated-sources.json'
WORK = PROJECT/'work/calibrated-camera-vga'
RUNNER = 'tools/run_camera_vga_calibrated_diagnostic.py'
SCHEMA = 'camera-vga-calibrated-diagnostic-preparation-v1'
SOURCE_SCHEMA = 'camera-vga-calibrated-source-closure-v1'
UPRIGHT_MANIFEST_SHA = '4a040c09863e5775ca9ac8c1027dfd402b65188e984117cba68f1c5331049c02'
PROFILE = 'results/camera-vga-calibration-20261101-a/profiles/fisheye-profile-a.json'
PROFILE_SHA = '94181c07a4456f511853f51022eba1b55965b115e1569f3fcbad460a2d92999e'
MAPPING = 'results/camera-vga-calibration-20261101-a/reports/brown-mapping-f240-a.json'
MAPPING_SHA = '38c0301fb8e1096dd49523555443a1b591ec0a62eb3c238be35f0a544c4a912e'
DELAY_SHA = '29fe84d4e77daa7ad7d0c6623bfe3650f6dc3d8144ba6bfd4b74931a97d4fb26'
FIXED_HELPERS = {**upright.FIXED_HELPERS,
    upright.MANIFEST: UPRIGHT_MANIFEST_SHA, baseline.MANIFEST: upright.BASE_MANIFEST_SHA,
    'tools/prepare_camera_vga_upright.py': 'c62ea304cdabcf7d066472a7d3c57cfe0937c91bf101c80b9d5e37aaedb78c78',
    'tools/run_camera_vga_upright_diagnostic.py': 'bf8b4ae2a3e1699bbe17811976b1bd405d7f0b39e00814aad65643d4329dcb39'}
REPLACE = {upright.TOP: TOP, 'board/board1080-synthetic.vh': HEADER}
INCLUDES = {REPLACE.get(n, n): v for n, v in upright.INCLUDES.items()}
INCLUDES[TOP] = (HEADER, HEADER)
FLAGS = baseline.FALSE_FLAGS
require, sha = baseline.require, baseline.paths.sha


def utc(): return datetime.now(timezone.utc).isoformat()


def calibration():
    require(sha(PROJECT/PROFILE) == PROFILE_SHA and sha(PROJECT/MAPPING) == MAPPING_SHA, 'frozen calibration evidence changed')
    profile = json.loads((PROJECT/PROFILE).read_text(encoding='utf-8'))
    mapping = json.loads((PROJECT/MAPPING).read_text(encoding='utf-8'))
    require(profile['candidate_ready_for_profile_review'] and mapping['passed'], 'calibration/mapping gate failed')
    require(mapping['source_profile_file_sha256'] == PROFILE_SHA and mapping['output_size'] == [640, 480], 'mapping/profile dimensions differ')
    require(mapping['source_model_scope'] == profile['model_scope'], 'physical visibility scope not propagated')
    require(len(mapping['frames']) == 1 and mapping['frames'][0]['angle_deg'] == 0 and mapping['sample_stride'] == 1, 'only zero-degree full-frame mapping accepted')
    require(mapping['integer_config'] == [81792,61312,82234,64062,40848,40921,4473924,4473924,-674237,121875,-11577,0,0], 'current fixed configuration differs')
    require(mapping['required_radius_guard_q22_for_checked_rays'] == 11610104, 'current guard differs')
    return profile, mapping


def expected_header(mapping):
    names = ['OUT_CX','OUT_CY','SRC_CX','SRC_CY','SRC_FX','SRC_FY','INV_FX','INV_FY','K1','K2','K3','P1','P2']
    lines = ['// Current640x480 CAM2 lens; output f240, angle0 only. Not hardware acceptance.',
             '// Profile SHA256 '+PROFILE_SHA, '// Mapping SHA256 '+MAPPING_SHA]
    for i, (name, value) in enumerate(zip(names, mapping['integer_config'])):
        width = 24 if i < 6 else 32
        literal = ('-' if value < 0 else '')+str(width)+"'sd"+str(abs(value))
        lines.append(f'localparam signed [{width-1}:0] CAL_{name}={literal};')
    lines.append('localparam CAL_RADIUS_Q22=11610104;')
    return '\n'.join(lines)+'\n'


def expected_top(old):
    text = old.replace('module camera_vga_upright_top', 'module '+TARGET)
    begin = text.index('    parameter WIDTH=640'); end = text.index(')(\n', begin)
    text = text[:begin]+'    parameter CAMERA_WARMUP_MS=8000\n'+text[end:]
    end = text.index('    (* async_reg=')
    text = text[:end]+'    localparam WIDTH=640,HEIGHT=480,HT=2200,VT=1125,HS=44,VS=5,X0=192,Y0=41,\n        OUTPUT_WIDTH=1920,OUTPUT_HEIGHT=1080;\n'+text[end:]
    begin = text.index('    `include "board/board1080-synthetic.vh"'); end = text.index('    wire [23:0] pixel_rgb;', begin)
    text = text[:begin]+f'    `include "{HEADER}"\n    wire [7:0] delayed_cam_data;\n    raw_camera_input_delay camera_data_delay(.pad_data(cam_data),.capture_data(delayed_cam_data));\n'+text[end:]
    text = text.replace('.MAX_RADIUS_Q22(B1080_RADIUS_Q22)', '.MAX_RADIUS_Q22(CAL_RADIUS_Q22)')
    text = text.replace('.cam_data(cam_data),', '.cam_data(delayed_cam_data),')
    begin = text.index('        .cfg_out_cx(MODEL_CX)'); end = text.index('        .awaddr(awaddr)', begin)
    text = text[:begin]+'''        .cfg_out_cx(CAL_OUT_CX),.cfg_out_cy(CAL_OUT_CY),.cfg_src_cx(CAL_SRC_CX),.cfg_src_cy(CAL_SRC_CY),
        .cfg_src_fx(CAL_SRC_FX),.cfg_src_fy(CAL_SRC_FY),.cfg_inv_fx(CAL_INV_FX),.cfg_inv_fy(CAL_INV_FY),
        .cfg_k1(CAL_K1),.cfg_k2(CAL_K2),.cfg_k3(CAL_K3),.cfg_p1(CAL_P1),.cfg_p2(CAL_P2),
'''+text[end:]
    text = text.replace('// Upright sensor candidate. FPGA geometry, clocks and frame dimensions remain unchanged.',
                        '// Isolated current-lens calibrated VGA candidate. Separate routed and hardware verification required.')
    text = text.replace('// Default geometry is zero-distortion transport validation, not lens calibration.',
                        '// Fixed current-lens mapping: f240 output, no rotation, gamma bypass.')
    return text


def roles():
    for name, h in FIXED_HELPERS.items(): require(sha(PROJECT/name) == h, 'frozen baseline/helper changed: '+name)
    old = upright.validate_sources(); profile, mapping = calibration()
    require(sha(PROJECT/DELAY) == DELAY_SHA, 'reviewed input-delay primitive source changed')
    require((PROJECT/HEADER).read_text() == expected_header(mapping), 'calibration header differs from audited integers')
    require(upright.normalized((PROJECT/TOP).read_text()) == upright.normalized(expected_top((PROJECT/upright.TOP).read_text())),
            'calibrated top changed outside declared fixed dimensions/config/data delay')
    names = [REPLACE.get(n, n) for n in old['Sources']]+[DELAY]
    designs = [REPLACE.get(n, n) for n in old['ExplicitDesigns']]+[DELAY]
    require(len(names) == len(set(names)) and set(REPLACE).isdisjoint(names), 'calibrated closure replacement differs')
    for name in names:
        if Path(name).suffix in ('.v', '.vh'):
            data = (PROJECT/name).read_bytes(); inc = baseline.paths.INCLUDE.findall(data); role = INCLUDES.get(name)
            require(len(baseline.paths.INCLUDE_DIRECTIVE.findall(data)) == len(inc) and inc == ([] if role is None else [role[0].encode('ascii')]), 'include role differs: '+name)
    counts = {**old['RoleCounts'], 'ManifestSources': len(names), 'ExplicitVerilog': old['RoleCounts']['ExplicitVerilog']+1}
    return {**old, 'Manifest': MANIFEST, 'Sources': names, 'SourceSHA256': {n: sha(PROJECT/n) for n in names},
            'ExplicitDesigns': designs, 'RoleCounts': counts,
            'DDRBodyComparison': {**old['DDRBodyComparison'], 'CandidateTop': TOP,
                'UprightTopEquivalentExceptNames': False, 'CalibratedTopDDRBodyUnchanged': True},
            'UnchangedSourceSHA256': {n: h for n, h in old['SourceSHA256'].items() if n not in REPLACE}}


def source_manifest():
    r = roles(); profile, mapping = calibration()
    return {'Schema': SOURCE_SCHEMA, 'Target': TARGET, 'BaseManifest': {'Path': upright.MANIFEST, 'SHA256': UPRIGHT_MANIFEST_SHA},
            'SourceReplacements': REPLACE, 'AddedSource': DELAY, 'source_files': r['Sources'], 'SourceSHA256': r['SourceSHA256'],
            'Constraint': r['Constraint'], 'RouteConstraint': r['RouteConstraint'], 'ConstraintSHA256': r['ConstraintSHA256'],
            'RoleCounts': r['RoleCounts'], 'PinAudit': r['PinAudit'], 'DDRBodyComparison': r['DDRBodyComparison'],
            'Profile': {'Path': PROFILE, 'SHA256': PROFILE_SHA}, 'Mapping': {'Path': MAPPING, 'SHA256': MAPPING_SHA},
            'PhysicalVisibility': profile['model_scope']['physical_visibility'], 'FrozenSharedSourcesUnchanged': True,
            'HardwareAccessed': False, 'EDAExecuted': False, **{k: False for k in FLAGS}}


def freeze_manifest():
    result = source_manifest()
    with (PROJECT/MANIFEST).open('x', encoding='utf-8', newline='\n') as f: json.dump(result, f, indent=2); f.write('\n')
    return result


def validate_sources():
    actual = json.loads((PROJECT/MANIFEST).read_text(encoding='utf-8-sig'))
    require(actual == source_manifest(), 'calibrated manifest differs from exact current derived closure')
    return roles()


def work_path(value):
    p=Path(value).absolute()
    require(p==p.resolve() and p.parent==WORK and p.parent==p.parent.resolve() and re.fullmatch(r'[A-Za-z0-9_-]+',p.name),
            'only canonical direct calibrated workspace children are allowed')
    return p


def literal(path):
    p=Path(path).absolute();require(p==p.resolve() and p.is_relative_to(PROJECT),'recipe path escaped calibrated project')
    return baseline.paths.tcl_path(p.as_posix())


def make_tcl(designs,fdc,rcf,work):
    lines=['# Calibrated diagnostic only; no old routed repairs, bitstream or hardware.',
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
    auxiliary={MANIFEST:sha(PROJECT/MANIFEST),upright.MANIFEST:UPRIGHT_MANIFEST_SHA,
               **FIXED_HELPERS,SELF.relative_to(PROJECT).as_posix():sha(SELF),RUNNER:sha(PROJECT/RUNNER),
               baseline.BASE:baseline.BASE_SHA256,baseline.RAW_FDC:baseline.RAW_FDC_SHA,baseline.RAW_PINS:baseline.RAW_PINS_SHA,
               upright.TOP:sha(PROJECT/upright.TOP),PROFILE:PROFILE_SHA,MAPPING:MAPPING_SHA}
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
          'SourceReplacements':REPLACE,'BaselineManifestSHA256':UPRIGHT_MANIFEST_SHA,'PinAudit':r['PinAudit'],
          'DDRBodyComparison':r['DDRBodyComparison'],'CompiledInputs':copies,'ExplicitDesigns':[p.as_posix() for p in designs],
          'IDFExpandedSourcesNotAdded':r['IDFExpandedSources'],'IncludeRewrites':rewrites,
          'Constraints':{'FDC':r['Constraint'],'RCF':r['RouteConstraint'],'CopiedIntoFrozenCompiledTree':True},
          'Tcl':{'Path':(work/'timing.tcl').as_posix(),'SHA256':baseline.paths.sha_bytes(tcl)},
          'PDS':{'Executable':str(pds),'ExecutableSHA256':sha(pds),'ExpectedVersion':baseline.paths.PDS_VERSION},
          'CommandToRunSeparately':[str(pds),'-file',(work/'timing.tcl').as_posix(),'-work_dir',work.as_posix(),'-project_name',TARGET],
          'MaximumSecondsForExternalExecutor':maximum_seconds,'ExternalDeadlineRequired':True,
          'PreSTAFinalDatabase':(work/'pre-sta-final.adf').as_posix(),'ExpectedActualStages':['Compile','Synthesize','Device Map','Place','Route','Route Optimize','Report Timing'],
          'HardwareAccessed':False,'EDAExecuted':False,'BitstreamRequested':False,**{k:False for k in FLAGS},
          'Limits':'Independent calibrated implementation. Old physical net names, repair routes and endpoint exceptions are not imported. New timing/CDC/pin/bit proofs are required separately.'}
    require(all(sha(PROJECT/n)==h for n,h in inputs.items()),'inputs changed while forming recipe')
    return plan,payloads,tcl


def prepare(work,pds_shell='D:/pango/PDS_2023.2/bin/pds_shell.exe',maximum_seconds=1800):
    work=work_path(work);require(not work.exists(),'fresh calibrated stage required')
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
