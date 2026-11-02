"""Exact current view-switch IO/CDC proof and native query preparation.

Existing pure coverage, protocol and native pad algorithms run in an isolated
candidate namespace. Their frozen modules and old physical evidence are never
changed or used as acceptance of this candidate.
"""
from datetime import datetime, timezone
from pathlib import Path
import argparse
import hashlib
import json
import re
import types

import audit_camera720_view_toggle as physical
import camera720_view_toggle_build as build
import camera720_view_toggle_final_inspect as final
import camera720_view_toggle_receipts as receipts
import camera720_stats_delay_cdc_proof as algorithms

SELF = Path(__file__).resolve()
TARGET, PROJECT, WORK = build.TARGET, build.ROOT, build.WORK
SCHEMA = 'camera720-view-toggle-cdc-proof-v1'
PLAN_SCHEMA = 'camera720-view-toggle-final-query-plan-v1'
require, sha, read = build.require, build.sha, build.read
add, ref, merge = receipts.add, receipts.ref, receipts.merge
cdc = physical.cdc
inspect = types.SimpleNamespace(query_commands=final.native.query_commands, drift=receipts.drift,
    diagnostic=types.SimpleNamespace(write=build.write), utc=lambda:datetime.now(timezone.utc).isoformat())
adapter = types.SimpleNamespace(**{**vars(physical.base), 'TARGET':TARGET,
    'graph':physical.graph, 'collect':physical.collect})


def query_bodies(queries,missing,per_body=80):
    require(type(per_body) is int and 1<=per_body<=80,'one to80 bounded timing commands per context required')
    groups=adapter.grouped.groups(queries,missing)
    bodies={}
    for offset in range(0,len(groups),per_body):
        body='\n'.join(command for group in groups[offset:offset+per_body]
                       for command in (group['PinCommand'],group['Command']))+'\n'
        final.native.query_commands(body)
        bodies[f'query-{offset//per_body:02}.tcl']=body
    return groups,bodies


adapter.cdc_query_bodies=query_bodies


def bind_native(path, modes, watched, candidate=None):
    value, inputs = final.bind_receipt(path)
    merge(watched, inputs)
    require(value.get('Target') == TARGET and value.get('Mode') in modes
            and value.get('ExecutionPassed') is True, 'wrong current candidate receipt mode or target')
    if candidate is not None:
        require(value['SourceADF'] == candidate['Path']
                and value['SourceADFSHA256'] == candidate['SHA256'], 'query uses another candidate ADF')
    return value


def derive(export_path, route_path):
    watched = {}
    export_path, route_path = Path(export_path).resolve(), Path(route_path).resolve()
    export = bind_native(export_path, {'export'}, watched)
    route = bind_native(route_path, {'report','query'}, watched)
    require(all(export[k] == route[k] for k in ('SourceADF','SourceADFSHA256','BuildPlan','BuildPlanSHA256'))
            and export.get('NativeNetlistWithFFloc') is True
            and 'route-dump.txt' in route['Artifacts'], 'export/route lineage or placed netlist differs')
    raw, _, io_body = physical.derive(Path(export['BuildPlan']).parent,export_path.parent,route_path.parent)
    merge(watched, raw['InputSHA256'])
    g = physical.graph(Path(export['Netlist']['Path']).read_text(encoding='utf-8-sig'))
    gray = cdc.endpoints.base.gray_structures(g)+cdc.endpoints.monitor.monitor_gray(g)
    held = cdc.endpoints.monitor.held_snapshot(g)
    held['AllFirstConsumers'] = cdc.endpoints.monitor.held_first_sinks(g, held)
    candidate = {'Path':export['SourceADF'], 'SHA256':export['SourceADFSHA256']}
    value = {**raw['CDC'], 'CandidateADF':candidate, 'CandidateADFSHA256':candidate['SHA256'],
        'ExportReceipt':ref(export_path), 'RouteReceipt':ref(route_path),
        'BuildPlan':ref(export['BuildPlan']), 'Netlist':export['Netlist'],
        'RouteDump':ref(route_path.parent/'route-dump.txt'), 'TimingReport':export['TimingReport'],
        'Pins':raw['Pins'], 'Key':raw['Key'], 'Constraints':raw['Constraints'],
        'NativeInterfaceSourceLocationNormalization':raw['NativeRouteNormalization'],
        'InputDelays':raw['InputDelays']['DataDelayProof'], 'ControlInputDelay':raw['InputDelays'],
        'Structure':{'Gray':gray,'MonitorHeld':held}, 'StatisticsDomain':raw['Telemetry'],
        'InitialRecords':raw['CDCRecords'], 'Violations':raw['CDCViolations'],
        'OtherLaunches':raw['OtherLaunches'], 'InitialCoverage':raw['CDCCoverage'],
        'DVPQuerySources':raw['DVPQuerySources'], 'TimingSummary':raw['TimingSummary'],
        'NativeElectricalParametersVerified':False, 'HardwareReleaseAllowed':False}
    for p in physical.base.structure.local_helpers((physical,algorithms,receipts,final)):
        add(watched,p)
    add(watched,SELF)
    require(not receipts.drift(watched), 'current CDC derivation input drift')
    return value, watched, io_body


# Clone only stable pure algorithms, preserving their code/defaults while
# resolving all target, receipt and structural dependencies in this module.
# No mutable module globals are patched and no native executor is reused here.
for _name in ('query_reports','uart_records','uart_summary','audit_value','verify','prepare','main'):
    _function = getattr(algorithms,_name)
    globals()[_name] = types.FunctionType(_function.__code__,globals(),_name,
                                        _function.__defaults__,_function.__closure__)


if __name__ == '__main__':
    main()
