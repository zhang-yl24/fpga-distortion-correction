"""Verify exact reset effects on the already hold-repaired 720p candidate.

All routes, functional cells and placements must remain unchanged. This is
an internal timing/exception audit, not external AC, CDC or board acceptance.
"""
import argparse
import json
from pathlib import Path
import sys

import camera720_reset_inspect as final
import camera720_derived_inspect as baseline
import audit_camera720_reset as reset
import audit_camera720_io_cdc as graph
import audit_camera_vga_calibrated_reset_effect as semantics
import audit_camera_vga_routes as routes
import audit_camera_vga_route_reset_scope as route_scope

prep, require, sha = final.prep, final.require, final.sha


def watch(watched, path, expected=None):
    path = Path(path)
    require(path == path.resolve() and path.is_file(), 'noncanonical effect input')
    actual = sha(path)
    require(expected is None or actual == expected, 'effect input identity differs')
    require(path not in watched or watched[path] == actual, 'effect input changed during verification')
    watched[path] = actual
    return path


def watch_tools(watched):
    # Snapshot before parsing as well as after it: a final-only hash would
    # attest current bytes rather than the parser bytes used by this audit.
    for module in list(sys.modules.values()):
        name = getattr(module, '__file__', None)
        if name:
            path = Path(name).resolve()
            if path.suffix == '.py' and path.is_relative_to(prep.PROJECT/'tools'):
                watch(watched, path)
    watch(watched, Path(__file__).resolve())


def artifact(receipt_path, receipt, name, watched):
    paths = [Path(receipt_path).parent/n for n in receipt['Artifacts']
             if Path(n).name == name and 'report_path_timing' not in Path(n).parts]
    require(len(paths) == 1, 'one exact receipt-bound artifact required: '+name)
    path = paths[0]
    return watch(watched, path, receipt['Artifacts'][path.relative_to(Path(receipt_path).parent).as_posix()])


def run(application_path, baseline_export_path, candidate_export_path):
    paths = [Path(p).absolute() for p in (application_path, baseline_export_path, candidate_export_path)]
    application_path, baseline_export_path, candidate_export_path = paths
    watched = {}
    watch_tools(watched)
    application = final.bind_source_receipt(application_path, watched)
    before, old_watched = baseline.bind_receipt(baseline_export_path)
    for path, expected in old_watched.items():
        watch(watched, path, expected)
    after = final.bind_receipt(candidate_export_path, watched)
    require(before['Mode'] == after['Mode'] == 'export', 'two complete placed exports required')
    require(before['BuildPlanSHA256'] == after['BuildPlanSHA256'] == application['BuildPlanSHA256'], 'different source builds')
    require(before['SourceADFSHA256'] == application['SourceADFSHA256'] and
            after['SourceADFSHA256'] == application['ResultADFSHA256'] and
            after['SourceReceipt'] == {'Path': str(application_path), 'SHA256': sha(application_path)}, 'different mutation chain')
    proof_path = Path(application['ResetProof']['Path'])
    require(sha(proof_path) == application['ResetProof']['SHA256'], 'reset proof changed')
    proof = json.loads(proof_path.read_text())
    inventory, _ = reset.inventory(proof['CurrentReport']['Path'])
    br = artifact(baseline_export_path, before, prep.TARGET+'.rtr', watched)
    cr = artifact(candidate_export_path, after, prep.TARGET+'.rtr', watched)
    be = artifact(baseline_export_path, before, prep.TARGET+'_exception.rtr', watched)
    ce = artifact(candidate_export_path, after, prep.TARGET+'_exception.rtr', watched)
    old_net = Path(before['Netlist']['Path'])
    new_net = Path(after['Netlist']['Path'])
    old_graph = graph.functional(old_net.read_text(encoding='utf-8-sig'))
    new_graph = graph.functional(new_net.read_text(encoding='utf-8-sig'))
    require(old_graph == new_graph, 'functional graph or FF placements changed')
    bt, bc = semantics.pure_physical.summaries(br)
    ct, cc = semantics.pure_physical.summaries(cr)
    require(bc == cc, 'clock definitions/loads changed')
    summaries, changes = semantics.compare_timing(bt, ct, inventory)
    with be.open(encoding='gb18030') as f:
        old_false = semantics.native.parse_false_paths(f)
    with ce.open(encoding='gb18030') as f:
        new_false = semantics.native.parse_false_paths(f)
    false_counts = semantics.compare_false_paths(old_false, new_false, inventory)
    other = semantics.nonfalse_equal(semantics.exception_syntax.read_exceptions(be), semantics.exception_syntax.read_exceptions(ce))
    old_dump = Path(application['SourceADF']).parent/'route-dump.txt'
    new_dump = application_path.parent/'route-dump.txt'
    a, b = routes.inspect(old_dump, {}), routes.inspect(new_dump, {})
    sa, sb = route_scope.constraint_separated(old_dump), route_scope.constraint_separated(new_dump)
    comparison = semantics.compare_routes(a, b, sa, sb)
    for path in (proof_path, old_net, new_net, old_dump, new_dump, Path(__file__).resolve()):
        watch(watched, path)
    # Bind the complete actually loaded local parser closure. Only generic
    # compare routines are reused; historical targets/expected counts are not.
    watch_tools(watched)
    require(not baseline.drift(watched), 'effect evidence/tool changed during verification')
    return {'Schema': 'camera720-reset-effect-v1', 'Target': prep.TARGET,
            'CreatedUTC': baseline.utc(), 'AuditPassed': True, 'ResetEffectVerified': True,
            'BaselineExport': {'Path': str(baseline_export_path), 'SHA256': sha(baseline_export_path)},
            'FinalExport': {'Path': str(candidate_export_path), 'SHA256': sha(candidate_export_path)},
            'Application': {'Path': str(application_path), 'SHA256': sha(application_path)},
            'CandidateADFSHA256': after['SourceADFSHA256'], 'ResetProof': application['ResetProof'],
            'AllInternalChecksMet': True, 'FunctionalGraphIdentical': True, 'AllFFPlacementsIdentical': True,
            'CornerSummaries': summaries, 'TimingSummaryChanges': changes, 'RouteComparison': comparison,
            'ExactResetExceptionUnionVerified': True, 'NoDataFalsePaths': True,
            'ClockDefinitionsAndLoadsUnchanged': True, 'FalsePathCounts': false_counts,
            'NonFalseExceptionComparison': other, 'InputSHA256': {str(p): h for p, h in watched.items()},
            'HardwareAccessed': False, 'EDAExecuted': False, 'TimingAccepted': False,
            'HardwareReleaseAllowed': False, 'CDCPhysicalAccepted': False, 'ExternalACAccepted': False,
            'Limits': 'Current internal native STA and exact reset effects only; CDC, input electrical/AC, bitstream and board acceptance remain separate.'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--application', type=Path, required=True)
    p.add_argument('--baseline-export', type=Path, required=True)
    p.add_argument('--candidate-export', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    output = args.output.absolute()
    require(output == output.resolve() and output.is_relative_to(prep.WORK) and
            output.parent.is_dir() and not output.exists(), 'fresh output in 720 work required')
    result = run(args.application, args.baseline_export, args.candidate_export)
    with output.open('x', encoding='utf-8', newline='\n') as f:
        json.dump(result, f, indent=2)
        f.write('\n')
    print(json.dumps({k: result[k] for k in ('AuditPassed', 'AllInternalChecksMet', 'ExactResetExceptionUnionVerified', 'NoDataFalsePaths')}))


if __name__ == '__main__':
    main()
