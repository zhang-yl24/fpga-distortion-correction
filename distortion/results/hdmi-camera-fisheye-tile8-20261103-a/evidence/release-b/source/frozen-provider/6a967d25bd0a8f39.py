"""Run the candidate's own physical proof after an explicit native handoff.

The handed-off raw receipts are rebound; ordinary core timing must already
pass. Every constraint, query and final report is derived afresh for r2.
This worker does not generate bits or access the board.
"""
from pathlib import Path
import json
import os
import subprocess
import sys

WORK = Path(__file__).resolve().parent
REPO = WORK.parents[2]
sys.path[:0] = [str(REPO / 'distortion/tools'), str(REPO / '.venv/Lib/site-packages')]
import hdmi_camera_fisheye_fill8r3s3_build as build
import hdmi_camera_fisheye_fill8r3s3_native as raw
import hdmi_camera_fisheye_fill8r3s3v2_scoped_native as native
import hdmi_camera_fisheye_fill8r3s3_audit as audit
import hdmi_camera_fisheye_fill8r3s3_warnings as warnings
import hdmi_camera_fisheye_fill8r3s3v2_physical as physical
import hdmi_camera_fisheye_fill8r3s3v2_physical_checks as checks
import hdmi_camera_fisheye_fill8r3s3v2_target_query as target
import hdmi_camera_fisheye_fill8r3s3v2_final as final

_APPROVED_MANIFEST = None


def verify_revision(record=None):
    global _APPROVED_MANIFEST
    if record is not None:
        build.require(_APPROVED_MANIFEST is None, 'revision authority already selected')
        _APPROVED_MANIFEST = dict(record)
    path = WORK / 'provider-revision-v2-source-manifest-a.json'
    build.require(_APPROVED_MANIFEST == native.ref(path), 'approved revision manifest drift')
    manifest = build.read(path)
    build.require(manifest.get('Schema') == 'hdmi-camera-fisheye-fill8r3s3v2-provider-source-manifest-v1'
                  and manifest.get('ProviderRevision') == 's3v2-bounded-b'
                  and isinstance(manifest.get('InputSHA256'), dict) and manifest['InputSHA256'],
                  'exact complete isolated revision input closure required')
    for name, digest in manifest['InputSHA256'].items():
        source = Path(name).absolute()
        build.require(source == source.resolve() and source != path and
                      build.local_io(source).is_file() and build.sha(source) == digest,
                      'approved revision input changed: ' + name)


def note(stage, **values):
    record = {'Stage': stage, **values}
    print(json.dumps(record), flush=True)
    with (WORK / 'physical-progress-v2-a.json').open('w', encoding='utf-8') as stream:
        json.dump(record, stream, indent=2)


def save(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, separators=(',', ':'), allow_nan=False)


def compress_completed(stage):
    """Preserve bytes and receipts while keeping room for fresh native reports."""
    helper = WORK / 'compress_completed_physical_v2_evidence_a.py'
    manifest = build.read(WORK / 'physical-compression-helper-source-manifest-v2.json')
    build.require(build.ref(helper) == manifest['NewHelper'], 'completed-stage compression helper drift')
    subprocess.run([sys.executable, '-B', str(helper), '--stage', Path(stage).name, '--tag', 'a'],
                   check=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))


def run_stage(provider, plan, label):
    verify_revision()
    note(label, Started=True)
    result = provider.execute(plan)
    build.require(result.get('ExecutionPassed') is True, label + ' failed')
    receipt = Path(plan).parent / 'result.json'
    provider.bind_receipt(receipt)
    compress_completed(receipt.parent)
    note(label, Passed=True)
    return receipt


def main():
    handoff = build.read(WORK / 'native-to-physical-v2-go-a.json')
    build.require(handoff.get('PriorWorkerEnded') is True and handoff.get('PDriveReleased') is True,
                  'explicit completed native worker handoff required')
    build.require(handoff.get('ProviderRevision') == 's3v2-bounded-b' and
                  handoff.get('ProviderSourceManifest') == native.ref(WORK / 'provider-revision-v2-source-manifest-a.json'),
                  'root handoff must bind the exact isolated provider revision')
    verify_revision(handoff['ProviderSourceManifest'])
    refs = {}
    for key in ('BuildPlan', 'ExportReceipt', 'RouteReceipt', 'SourceWarningReview'):
        record = handoff[key]
        path = Path(record['Path']).resolve()
        build.require(path.is_relative_to(WORK) and build.sha(path) == record['SHA256'],
                      'handoff artifact changed: ' + key)
        refs[key] = path
    build_plan = refs['BuildPlan']
    exported, _ = raw.bind_receipt(refs['ExportReceipt'])
    raw.bind_receipt(refs['RouteReceipt'])
    report = raw.artifact(refs['ExportReceipt'], exported, build.TARGET + '.rtr')
    tables, _ = physical.summaries(report)
    core_checks = set()
    for key, rows in tables.items():
        for pair, row in rows.items():
            if pair == ('ddrphy_sysclk', 'ddrphy_sysclk'):
                core_checks.add(key)
                build.require(row['FailingChecks'] == 0 and row['WorstSlackNS'] >= 0
                              and row['TotalNegativeSlackNS'] == 0,
                              'ordinary core timing must pass before physical application: ' + str(key))
    build.require({(corner, kind) for corner in ('slow', 'fast') for kind in ('setup', 'hold')}
                  <= core_checks, 'complete core setup/hold summaries required')
    warnings.verify(refs['SourceWarningReview'])
    note('audit-source-load', Started=True)
    scope_path = WORK / 'audit-a/scope.json'
    scope = build.read(scope_path)
    build.require(scope['Schema'] == physical.AUDIT_SCHEMA and scope['Target'] == build.TARGET and
                  scope['ProposalReady'] is True and scope['Blockers'] == [] and
                  scope['BuildPlan'] == native.ref(build_plan) and
                  scope['ExportReceipt'] == native.ref(refs['ExportReceipt']) and
                  scope['RouteReceipt'] == native.ref(refs['RouteReceipt']),
                  'exact completed original S3 audit facts required')
    # application_recipe.bind_audit performs one fresh full original audit derive;
    # later calls reuse only its existing full-hash authority cache.
    proposal = physical.scope_plan(scope)
    note('audit', Passed=True, DataScopes=len(scope['DataScopes']),
         PreflightBodies=len(proposal['PreflightQueryBodies']))
    owned_alias = False
    try:
        build.require(not Path('P:/').exists(), 'native handoff must leave P: free')
        done = subprocess.run(['subst.exe', 'P:', str(REPO)], capture_output=True,
                              creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        build.require(done.returncode == 0 and os.path.samefile('P:/', REPO), 'owned P: alias failed')
        owned_alias = True
        body_dir = WORK / 'physical-bodies-v2-a'
        body_dir.mkdir(exist_ok=False)
        preflights = []
        for index, body in enumerate(proposal['PreflightQueryBodies']):
            body_path = body_dir / f'preflight-{index:02}.tcl'
            body_path.write_text(body, encoding='ascii', newline='\n')
            prior = WORK / f'preflight-a-{index:02}/result.json'
            reuse = False
            if prior.is_file():
                value, _ = raw.bind_receipt(prior)
                reuse = (value['Mode'] == 'query' and value['SourceProof'] is None and
                         value['BuildPlanSHA256'] == build.sha(build_plan) and
                         value['SourceADF'] == scope['SourceADF']['Path'] and
                         value['SourceADFSHA256'] == scope['SourceADF']['SHA256'] and
                         Path(value['QueryBody']).read_text(encoding='ascii') == body)
            if reuse:
                preflights.append(prior)
                note('preflight-reused-exact', Index=index, Receipt=native.ref(prior),
                     ExactBodyAndSourceBinding=True)
            else:
                plan = raw.prepare(build_plan, WORK / f'preflight-v2-a-{index:02}', 'query',
                                   body=body_path, maximum=600)
                preflights.append(run_stage(raw, plan, f'preflight-v2-{index:02}'))
        app_plan = physical.prepare_application(scope_path, refs['SourceWarningReview'],
                                                 preflights, WORK / 'physical-v2-a', maximum=600)
        note('physical-v2-application', Started=True)
        verify_revision()
        applied = physical.execute_application(app_plan)
        build.require(applied.get('ExecutionPassed') is True, 'r2 exact physical application failed')
        app_path = WORK / 'physical-v2-a/result.json'
        physical.bind_application(app_path)
        compress_completed(app_path.parent)
        note('physical-v2-application', Passed=True)
        export_plan = native.prepare(build_plan, WORK / 'export-scoped-v2-a', 'export',
                                     maximum=600, source_proof=app_path)
        scoped_export = run_stage(native, export_plan, 'fresh-scoped-export')
        exp, _ = native.bind_receipt(scoped_export)
        fresh_report = native.artifact(scoped_export, exp, build.TARGET + '.rtr')
        tables, _ = physical.summaries(fresh_report)
        physical.all_ten_pass(tables)
        note('fresh-ten-tables', Passed=True)
        route_plan = native.prepare(build_plan, WORK / 'route-scoped-v2-a', 'report',
                                    maximum=600, source_proof=app_path)
        scoped_route = run_stage(native, route_plan, 'fresh-scoped-route')
        inventory, _ = checks.inventory(scope)
        bodies = checks.query_bodies(inventory)
        receipts = []
        for index, body in enumerate(bodies):
            body_path = body_dir / f'checks-{index:02}.tcl'
            body_path.write_text(body, encoding='ascii', newline='\n')
            plan = target.prepare(build_plan, WORK / f'checks-scoped-v2-a-{index:02}', 'query',
                                  body=body_path, maximum=1200, source_proof=app_path)
            receipts.append(run_stage(target, plan, f'checks-{index:02}'))
        note('final-proof', Started=True)
        proof, _ = final.final_facts(app_path, scoped_export, scoped_route, receipts)
        build.require(proof.get('Passed') is True and proof.get('STAAllTenPassed') is True,
                      'r2 full final proof failed')
        proof_path = WORK / 'final-proof-v2-a.json'
        save(proof_path, proof)
        final.verify(proof_path)
        note('final-proof', Passed=True, Proof=native.ref(proof_path), HardwareAccessed=False,
             BitstreamGenerated=False)
    finally:
        if owned_alias:
            build.require(os.path.samefile('P:/', REPO), 'owned P: alias changed before cleanup')
            subprocess.run(['subst.exe', 'P:', '/D'], check=True, capture_output=True,
                           creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))


if __name__ == '__main__':
    main()
