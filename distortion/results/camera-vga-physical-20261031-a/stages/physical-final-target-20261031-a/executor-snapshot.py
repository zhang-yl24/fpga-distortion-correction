"""Read-only query/export of a camera ADF with a completed physical receipt.

Keep original query/export helpers immutable so their existing receipts retain
valid tool hashes. A derived source always remains read-only and is copied.
"""
import argparse
import json
from pathlib import Path

import run_camera_vga_export as export
import run_camera_vga_physical as core
import run_camera_vga_repair as repair


def bind_derived(source, extra=()):
    source = core.canonical_file(source, core.ROOT)
    plan, watched = core.bind_inputs(extra=(Path(__file__).resolve(), Path(export.__file__).resolve(),
                                           Path(repair.__file__).resolve(), *extra))
    if source != core.ORIGINAL:
        core.require(source.name == 'input.adf' and source.parent.parent == core.ROOT,
                     'derived source must be an exact isolated stage input.adf')
        receipt = core.canonical_file(source.parent / 'result.json', core.ROOT)
        watched[receipt] = core.sha(receipt)
        repair.completed_receipt(receipt, core.sha(source), watched)
        watched[source] = core.sha(source)
    core.require(not core.check_inputs(watched), 'derived source proof changed')
    return plan, watched


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--name', required=True)
    parser.add_argument('--mode', choices=('query', 'export'), required=True)
    parser.add_argument('--source-adf', type=Path, required=True)
    parser.add_argument('--body', type=Path)
    parser.add_argument('--maximum-seconds', type=int, default=300)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--validate-only', action='store_true')
    modes.add_argument('--prepare-only', action='store_true')
    args = parser.parse_args(argv)
    work, maximum = core.fresh_work(core.ROOT / args.name), core.deadline(args.maximum_seconds)
    source = core.canonical_file(args.source_adf, core.ROOT)
    extra, body = [], None
    if args.mode == 'query':
        core.require(args.body is not None, 'query body required')
        bodypath = core.canonical_file(args.body, core.ROOT)
        body = bodypath.read_text(encoding='ascii')
        core.validate_query_body(body)
        extra.append(bodypath)
    else:
        core.require(args.body is None, 'functional export does not accept a body')
    plan, watched = bind_derived(source, tuple(extra))
    if args.mode == 'query':
        tcl = core.render_query(body, work)
        marker, schema, stages = core.MARKER, core.SCHEMA, []
    else:
        tcl = export.render_tcl((core.BASE / 'timing.tcl').read_text(encoding='ascii'),
                               plan['AliasWorkDirectory'], work)
        marker, schema, stages = export.MARKER, 'camera-vga-functional-export-v1', export.STAGES
    if args.validate_only:
        print(json.dumps({'Validated': True, 'EDAExecuted': False, 'SourceADF': str(source),
                          'SourceADFSHA256': core.sha(source), 'ExpectedActualStages': stages}))
        return 0
    result = core.run_stage(work=work, source=source, watched=watched, tcl=tcl, maximum=maximum,
        marker=marker, schema=schema, expected_stages=stages, executor=Path(__file__).resolve(),
        dummy=args.mode == 'query', prepare_only=args.prepare_only, require_netlist=args.mode == 'export')
    print(json.dumps({k: result[k] for k in ('Prepared', 'ExecutionPassed', 'ElapsedSeconds', 'ExitCode',
                     'InputDrift', 'Diagnostics', 'ActualStages', 'Netlist', 'WorkDirectory') if k in result}), flush=True)
    return 0 if args.prepare_only or result['ExecutionPassed'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
