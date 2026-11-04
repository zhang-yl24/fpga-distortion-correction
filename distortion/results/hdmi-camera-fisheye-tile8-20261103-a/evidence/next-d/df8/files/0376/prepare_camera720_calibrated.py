"""Prepare isolated measured-candidate720 correction sources; no EDA/hardware.

The fixed transport source tree remains untouched. A real paired-transfer and
target-pose validation are mandatory; first-fit previews cannot authorize this
diagnostic build. Optical acceptance and new routed signoff remain separate.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import sys

import prepare_camera720_output as transport

PROJECT = transport.PROJECT
baseline = transport.baseline
sys.path.insert(0, str(PROJECT))
from tools import camera720_target_validation as target
from tools import wideangle_mapping_audit as numerical

SELF = Path(__file__).resolve()
WORK = PROJECT/'work/camera720-calibrated'
TARGET = 'camera720_calibrated_top'
TOP = 'board/camera720_calibrated_top.v'
HEADER = 'board/camera720-current-lens.vh'
SCHEMA = 'camera720-calibrated-diagnostic-preparation-v1'
REQUEST_SCHEMA = 'camera720-calibrated-diagnostic-request-v1'
SOURCE_SCHEMA = 'camera720-calibrated-source-closure-v1'
RUNNER = PROJECT/'tools/run_camera720_calibrated_diagnostic.py'
NAMES = 'OUT_CX OUT_CY SRC_CX SRC_CY SRC_FX SRC_FY INV_FX INV_FY K1 K2 K3 P1 P2'.split()
BITS = [24]*6+[32]*7
ANCHORS = {
    'tools/prepare_camera720_output.py': 'dda5db3443830e1da06952e5f8c3c747b12730c7798f8ab1b43df7217a161376',
    'board/camera720-output-sources.json': 'a4f6257c8614b43ebe8d09beef764a8d0f06c31d2d474755b8e5865a55009be5',
    'board/camera720_transport_top.v': 'b71329fe4621f6a820fbc2b4e2513e51bfc06bed4bf87dd4adea42f78d8c0629',
    'board/camera720-identity.vh': '84a8cfc58afc17bed4ee7eae7dcdb90cbe2a7c3edd6d900b52a5b8553435e4a8',
}
require, sha = transport.require, transport.sha


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def ref(path):
    return {'Path': str(Path(path).resolve()), 'SHA256': sha(path)}


def bind(watched, item):
    require(isinstance(item, dict) and set(item) == {'Path', 'SHA256'}
            and re.fullmatch('[0-9a-f]{64}', item['SHA256']) is not None, 'explicit file path and SHA256 required')
    path = Path(item['Path']).resolve()
    require(path.is_relative_to(PROJECT) and path.is_file() and sha(path) == item['SHA256'], 'bound evidence missing or changed')
    require(str(path) not in watched or watched[str(path)] == item['SHA256'], 'conflicting file binding')
    watched[str(path)] = item['SHA256']
    return path


def validate_config(config, guard):
    require(isinstance(config, list) and len(config) == 13 and
            all(type(v) is int and -(1 << (b-1)) <= v < (1 << (b-1)) for v,b in zip(config,BITS)),
            '13 correctly sized signed coefficients required')
    require(all(config[i] > 0 for i in (4,5,6,7)) and config[11:] == [0,0], 'positive focal lengths and radial-only mapping required')
    require(type(guard) is int and 0 < guard < (1 << 31), 'positive signed32 radius required')


def validate_profile(profile, validation):
    require(validation.get('schema') == target.REPORT_SCHEMA
            and validation.get('native_physical_observed_views_passed') is True
            and validation.get('coverage_passed') is not False
            and validation.get('intrinsics_refitted') is False, 'passing measured target poses required')
    parameters = validation['candidate_parameters']
    require(profile.get('model') == 'fisheye' and profile.get('image_size') == [1280,720]
            and profile.get('K') == parameters['K'] and profile.get('D') == parameters['D']
            and all(profile.get(k) == v for k,v in validation['target_identity'].items()),
            'numerical profile differs from measured fixed target parameters')
    require(profile.get('model_scope') == {k:parameters[k] for k in
            ('projection','maximum_ray_angle_deg','inverse_method')}, 'target model scope differs')
    require(profile.get('development_only') is True and profile.get('passed') is False
            and profile.get('candidate_ready_for_profile_review') is False
            and profile.get('independent_spatial_coverage_passed') is False,
            'retain diagnostic-only profile flags; no inherited optical acceptance')


def mapping_parameters(mapping):
    require(mapping.get('passed') is True and mapping.get('sample_stride') == 1
            and mapping.get('full_requested_frames_checked') is True
            and mapping.get('source_image_size') == mapping.get('output_size') == [1280,720]
            and mapping.get('coordinates_checked') == mapping.get('requested_full_frame_coordinates') == 921600,
            'full921600 native720 numerical mapping required')
    require(mapping.get('output_K') == [[480.0,0.0,639.5],[0.0,480.0,359.5],[0.0,0.0,1.0]],
            'this diagnostic uses the explicitly selected centered f480 output view')
    require(mapping.get('criteria') == {'maximum_coordinate_error_px': .25, 'minimum_in_bounds_fraction': .99,
            'arithmetic_invalid_max': 0, 'folded_samples_max': 0, 'requires_stride_one': True},
            'predeclared numerical budgets differ')
    rows = mapping.get('frames', [])
    require(len(rows) == 1 and rows[0].get('angle_deg') == 0 and rows[0].get('coordinates_checked') == 921600,
            'one complete zero-degree frame required')
    row = rows[0]
    require(row.get('numerical_gates_passed') is True and row.get('finite_opencv_reference') is True
            and all(row.get(k) == 0 for k in ('fixed_point_invalid_coordinates','reference_folded_samples','fixed_point_folded_samples'))
            and row.get('maximum_coordinate_error_px') is not None and 0 <= row['maximum_coordinate_error_px'] <= .25,
            'mapping overflow/fold/error gate failed')
    require(row.get('bilinear_all_neighbours_in_bounds_fraction') == 1.0
            and row.get('opencv_all_neighbours_in_bounds_fraction') == 1.0,
            'selected f480 candidate must actually retain all bilinear neighbours; not a new optical coverage claim')
    guard = mapping['required_radius_guard_q22_for_checked_rays']
    require(guard == row['maximum_normalized_radius_squared_q22']+2, 'radius must come from the actual mapping')
    config = mapping['integer_config']; validate_config(config, guard)
    return config, guard


def calibration(request_path):
    watched = {};request_path = bind(watched, ref(request_path));request = read(request_path)
    require(set(request) == {'Schema','TargetValidation','Profile','MappingAudit'}
            and request['Schema'] == REQUEST_SCHEMA, 'exact diagnostic calibration request required')
    report_path = bind(watched, request['TargetValidation'])
    validation, closure = target.verify(report_path)
    for p,h in closure.items():
        require(str(Path(p).resolve()) not in watched or watched[str(Path(p).resolve())] == h, 'target closure conflict')
        watched[str(Path(p).resolve())] = h
    profile_path = bind(watched, request['Profile']); profile = read(profile_path)
    validate_profile(profile, validation)
    mapping_path = bind(watched, request['MappingAudit']);mapping = read(mapping_path)
    config, guard = mapping_parameters(mapping)
    actual = numerical.audit_profile(profile, output_size=(1280,720), output_k=mapping['output_K'],
        angles=(0,), stride=1, maximum_error_px=.25, minimum_in_bounds_fraction=.99,
        maximum_points_per_frame=mapping['maximum_points_per_frame'])
    actual['source_profile_file_sha256'] = sha(profile_path)
    require(actual == mapping, 'mapping differs from complete numerical recomputation')
    for p,h in mapping['source_sha256'].items():bind(watched, {'Path':str(PROJECT/p),'SHA256':h})
    for module in (target, numerical):watched[str(Path(module.__file__).resolve())] = sha(module.__file__)
    evidence = {'Request':ref(request_path), **{k:request[k] for k in ('TargetValidation','Profile','MappingAudit')},
                'TargetViewsChecked':validation['observed_view_count'],
                'TargetCoveragePolicy':validation['coverage_policy'],
                'TargetCoveragePassed':validation['coverage_passed'],
                'TargetObservedPosesPassed':True, 'IntegerConfig':config, 'RadiusQ22':guard,
                'OpticalCorrectionAccepted':False, 'FPGAImplementationAccepted':False}
    return evidence, watched


def render_header(config, guard, evidence):
    validate_config(config, guard)
    lines = ['// Measured-transfer720 diagnostic candidate; optical/board acceptance remains separate.',
             '// Profile SHA256 '+evidence['Profile']['SHA256'],
             '// Full mapping SHA256 '+evidence['MappingAudit']['SHA256']]
    for n,v,b in zip(NAMES,config,BITS):
        lines.append(f"localparam signed [{b-1}:0] C720_{n}={'-' if v < 0 else ''}{b}'sd{abs(v)};")
    return ('\n'.join(lines+[f'localparam C720_RADIUS_Q22={guard};'])+'\n').encode('ascii')


def render_top(original):
    old_module = 'module '+transport.TARGET
    old_include = '`include "'+transport.HEADER+'"'
    require(original.count(old_module) == original.count(old_include) == 1, 'exact transport module/include anchors required')
    return original.replace(old_module,'module '+TARGET,1).replace(old_include,'`include "'+HEADER+'"',1)


def work_path(value):
    p = Path(value).absolute()
    require(p == p.resolve() and p.parent == WORK.resolve() and re.fullmatch('[A-Za-z0-9_-]+',p.name),
            'fresh canonical direct calibrated720 stage required')
    return p


def recipe(request_path, work, pds_shell='D:/pango/PDS_2023.2/bin/pds_shell.exe', maximum_seconds=1800):
    work = work_path(work)
    for name,h in ANCHORS.items():require(sha(PROJECT/name) == h, 'frozen transport changed: '+name)
    # Reuse the baseline CPU source/include/IDF validation and full watched closure.
    base_plan,_,_ = transport.recipe(transport.WORK/'_calibrated_source_template',pds_shell,maximum_seconds)
    roles = transport.validate_sources(); evidence,watched = calibration(request_path)
    watched.update({str((PROJECT/n).resolve()):h for n,h in base_plan['InputSHA256'].items()})
    for path in (SELF,RUNNER,Path(sys.executable),PROJECT/'tools/run_camera_vga_output_diagnostic.py'):
        require(path.is_file(), 'missing preparer/executor dependency');watched[str(path.resolve())] = sha(path)
    top_bytes = render_top((PROJECT/transport.TOP).read_text(encoding='utf-8')).encode('utf-8')
    header_bytes = render_header(evidence['IntegerConfig'],evidence['RadiusQ22'],evidence)
    generated = {TOP:top_bytes,HEADER:header_bytes}
    replacements = {transport.TOP:TOP,transport.HEADER:HEADER}
    names = [replacements.get(n,n) for n in roles['Sources']]
    explicit = [replacements.get(n,n) for n in roles['ExplicitDesigns']]
    includes = {replacements.get(n,n):v for n,v in transport.INCLUDES.items()};includes[TOP] = (HEADER,HEADER)
    hashes = {replacements.get(n,n):hashlib.sha256(generated[replacements[n]]).hexdigest() if n in replacements else sha(PROJECT/n)
              for n in roles['Sources']}
    manifest = {'Schema':SOURCE_SCHEMA,'Target':TARGET,'BaseManifest':ref(PROJECT/transport.MANIFEST),
                'SourceReplacements':replacements,'source_files':names,'SourceSHA256':hashes,
                'RoleCounts':roles['RoleCounts'],'Constraint':roles['Constraint'],'RouteConstraint':roles['RouteConstraint'],
                'Calibration':evidence,'Geometry':[1280,720],'OutputActiveArea':[1920,1080],
                'FPSParametersChanged':False,'UnchangedExceptTopNameIncludeAndHeader':True,
                'InheritedRoutedTiming':False,'HardwareReleaseAllowed':False,'OpticalCorrectionAccepted':False}
    source_payloads = {work/'source'/n:b for n,b in generated.items()}
    source_payloads[work/'source/manifest.json'] = (json.dumps(manifest,indent=2,allow_nan=False)+'\n').encode('utf-8')
    payloads = dict(source_payloads);copies=[];rewrites=[];designs=[]
    for name in names+[roles['RouteConstraint']]:
        data = generated[name] if name in generated else (PROJECT/name).read_bytes()
        transformed = data
        if name in includes:
            old,header = includes[name];matches = list(transport.baseline.paths.INCLUDE.finditer(data))
            require(len(matches) == 1 and matches[0][1] == old.encode('ascii'), 'include transformation differs')
            replacement = (work/'compiled'/header).as_posix();transport.baseline.paths.tcl_path(replacement)
            transformed = data[:matches[0].start(1)]+replacement.encode('ascii')+data[matches[0].end(1):]
            rewrites.append({'Source':name,'OriginalInclude':old,'CompiledInclude':replacement,'Header':header})
        destination = work/'compiled'/name;payloads[destination] = transformed
        copies.append({'Source':name,'OriginalSHA256':hashlib.sha256(data).hexdigest(),
                       'CompiledPath':str(destination),'CompiledSHA256':hashlib.sha256(transformed).hexdigest()})
        if name in explicit:designs.append(destination)
    # Only exact top token and final ADF filename change in the existing native recipe.
    tcl = transport.make_tcl(designs,work/'compiled'/roles['Constraint'],work/'compiled'/roles['RouteConstraint'],work)
    tcl = tcl.replace('compile -top_module '+transport.TARGET,'compile -top_module '+TARGET)
    tcl = tcl.replace(transport.TARGET+'_pnr.adf',TARGET+'_pnr.adf').encode('ascii')
    pds = base_plan['PDS'];watched[pds['Executable']] = pds['ExecutableSHA256']
    plan = {'Schema':SCHEMA,'Target':TARGET,'Request':ref(request_path),'ProjectRoot':str(PROJECT),
            'WorkDirectory':str(work),'ScratchRoot':str(WORK),'Scope':'PrepareOnlyNoEDA',
            'CalibrationEvidence':evidence,'InputSHA256':watched,'SourceManifest':str(work/'source/manifest.json'),
            'GeneratedSourceSHA256':{str(p):hashlib.sha256(b).hexdigest() for p,b in source_payloads.items()},
            'CompiledInputs':copies,'ExplicitDesigns':[str(p) for p in designs],'IncludeRewrites':rewrites,
            'IDFExpandedSourcesNotAdded':roles['IDFExpandedSources'],'RoleCounts':roles['RoleCounts'],
            'Tcl':{'Path':str(work/'timing.tcl'),'SHA256':hashlib.sha256(tcl).hexdigest()},'PDS':pds,
            'CommandToRunSeparately':[pds['Executable'],'-file',(work/'timing.tcl').as_posix(),
                                     '-work_dir',work.as_posix(),'-project_name',TARGET],
            'MaximumSecondsForExternalExecutor':maximum_seconds,'ExpectedActualStages':base_plan['ExpectedActualStages'],
            'ExternalDeadlineRequired':True,'HardwareAccessed':False,'EDAExecuted':False,'BitstreamRequested':False,
            'TimingAccepted':False,'HardwareReleaseAllowed':False,'OpticalCorrectionAccepted':False,
            'FPSParametersChanged':False,'Limits':'Measured-parameter diagnostic candidate only. Fresh implementation timing/CDC/IO, RTL regression and board optical checks remain required; no transport routed repair or release inherited.'}
    require(all(sha(p) == h for p,h in watched.items()), 'inputs drifted during preparation')
    return plan,payloads,tcl


def prepare(request_path, work, pds_shell='D:/pango/PDS_2023.2/bin/pds_shell.exe', maximum_seconds=1800):
    work = work_path(work);require(not work.exists(), 'fresh calibrated stage required')
    plan,payloads,tcl = recipe(request_path,work,pds_shell,maximum_seconds)
    for path,data in payloads.items():
        path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('xb') as stream:stream.write(data)
    (work/'timing.tcl').write_bytes(tcl)
    plan['PreparedUTC'] = datetime.now(timezone.utc).isoformat()
    with (work/'plan.json').open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(plan,stream,indent=2,allow_nan=False);stream.write('\n')
    return plan


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--request',type=Path,required=True);p.add_argument('--work-dir',type=Path,required=True)
    p.add_argument('--pds-shell',default='D:/pango/PDS_2023.2/bin/pds_shell.exe')
    p.add_argument('--maximum-seconds',type=int,default=1800);p.add_argument('--audit-only',action='store_true')
    args = p.parse_args()
    value = recipe(args.request,args.work_dir,args.pds_shell,args.maximum_seconds)[0] if args.audit_only else prepare(args.request,args.work_dir,args.pds_shell,args.maximum_seconds)
    print(json.dumps({'PreparedOnly':not args.audit_only,'Plan':str(Path(value['WorkDirectory'])/'plan.json'),
                      'Target':TARGET,'EDAExecuted':False,'HardwareAccessed':False}))


if __name__ == '__main__':main()
