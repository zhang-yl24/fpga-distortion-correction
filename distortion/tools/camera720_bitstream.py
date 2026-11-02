"""Audit current 720p evidence once, then hash-bind diagnostic bit generation.

The explicit authority SHA is the caller's anchor to the completed CPU audit.
Every later boundary rehashes the full original evidence/tool closure. Fresh
native STA, exact exceptions, ADF identity and bit provenance remain mandatory.
This tool never accesses a board and never claims 720p optical acceptance.
"""
import argparse
import copy
from collections import Counter
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

import camera720_inspect as inspect
import camera720_reset_inspect as final
import audit_camera720_reset_effect as effect
import camera720_cdc_batch as cdc
import audit_camera_vga_physical as timing

prep = inspect.prep
require, sha = prep.require, prep.sha
SELF = Path(__file__).resolve()
PYTHON = prep.PROJECT.parent/'.venv/Scripts/python.exe'
REQUEST_SCHEMA = 'camera720-bitstream-request-v1'
AUTHORITY_SCHEMA = 'camera720-bitstream-authority-v1'
PLAN_SCHEMA = 'camera720-bitstream-plan-v1'
EXEC_SCHEMA = 'camera720-bitstream-execution-v1'
STAGES = ['Report Timing', 'Generate Bitstream']
COMPLETE = 'CAMERA720_BITSTREAM_COMPLETE'
REPORT = 'report_timing/'+prep.TARGET+'.rtr'
EXCEPTIONS = 'report_timing/'+prep.TARGET+'_exception.rtr'
BIT = 'generate_bitstream/'+prep.TARGET+'.sbit'
REQUEST_FIELDS = {'Schema','Target','BuildPlan','CandidateADF','FinalInspectionReceipt','FinalCDCProof',
                  'FinalIOProof','ResetApplicationReceipt','ResetEffectAudit'}
LAUNCH_COVERAGE_SCHEMA = 'camera720-cdc-launch-qualified-coverage-v1'
NATIVE_MANUAL = Path('D:/pango/PDS_2023.2/doc/Pango_Design_Suite_User_Guide.pdf')
NATIVE_MANUAL_SHA = '4b49b329809fa5dd4998213e715c2996c92cba26fbed74a8b9f43cb711943bb1'
CLM_COVERAGE_SCHEMA = 'camera720-physical-clm-through-coverage-v1'
SINGLE_COVERAGE_SCHEMA = 'camera720-single-clm-recovery-coverage-v1'
CLM_DOCUMENTS = {
    Path('D:/pango/PDS_2023.2/doc/Tcl_Command_User_Guide.pdf'):
        '7be74cf2d0fba752cc7016a47b994d9bfb05805f4c7b19fb4d15266033de9ba4',
    Path('D:/pango/PDS_2023.2/doc/Timing_Analyzer_User_Guide.pdf'):
        '9d04d214d74f95348ce292b3c244e6ee880dd7095014209db243f8b8c1b2b420'}
CLM_BASIS = prep.PROJECT/'work/camera720-clm-vendor-sta-basis.json'
CLM_BASIS_SHA = '7507a8262d7fa61ccf2334e05e5d282cc1b005f86f41c607343f8728f193010b'
CLM_BASIS_NOTE = prep.PROJECT/'work/camera720-clm-vendor-sta-acceptance.md'
CLM_BASIS_NOTE_SHA = '53436f1a119b302dd70c7c191f7a1eab2d5f42ac7d9db6e43d28ac5b6478bd58'
CLM_EXTRACT = prep.PROJECT/'work/camera720-clm-timing-manual-evidence.json'
CLM_EXTRACT_SHA = '1d86f0682e8df259efd30000daf3660c7ccc544b382a3cba4e4fb6d4b1096524'


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def add(watched, path, digest=None, pds=None):
    # One explicitly reviewed vendor authority; never permit its directory.
    path = Path(path).absolute()
    if path == NATIVE_MANUAL:
        require(path == path.resolve() and path.is_file() and digest == NATIVE_MANUAL_SHA
                and sha(path) == digest, 'exact native manual path/hash required')
        require(path not in watched or watched[path] == digest, 'conflicting native manual identity')
        watched[path] = digest
        return path
    if path in CLM_DOCUMENTS:
        require(path == path.resolve() and path.is_file() and digest == CLM_DOCUMENTS[path]
                and sha(path) == digest, 'exact physical STA document path/hash required')
        require(path not in watched or watched[path] == digest, 'conflicting physical STA document identity')
        watched[path] = digest
        return path
    return final.add(watched, path, digest, pds)


def ref(value, watched, pds=None):
    return final.physical.binding(value, watched, pds)


def binding(path):
    path = Path(path).absolute()
    return {'Path': str(path), 'SHA256': sha(path)}


def merge(watched, other, pds=None):
    for path, digest in other.items():
        add(watched, path, digest, pds)


def rehash_inputs(value, watched, pds=None):
    require(isinstance(value.get('InputSHA256'), dict) and value['InputSHA256'], 'missing full input closure')
    merge(watched, value['InputSHA256'], pds)


def watch_tools(watched, pds=None):
    # Record already-loaded parser bytes before and after expensive parsing.
    for module in list(sys.modules.values()):
        name = getattr(module, '__file__', None)
        if name:
            path = Path(name).resolve()
            if path.suffix == '.py' and path.is_relative_to(prep.PROJECT/'tools'):
                add(watched, path, pds=pds)
    add(watched, SELF, pds=pds)
    add(watched, PYTHON, pds=pds)


def equal_audit(actual, claimed):
    # A caller can load extra tools; all old bound bytes must remain present.
    # The source/tool closure is separately rehashed, never ignored as evidence.
    omit = {'CreatedUTC', 'InputSHA256'}
    clean = lambda value: json.loads(json.dumps({k:v for k,v in value.items() if k not in omit}))
    require(clean(actual) == clean(claimed), 'recomputed audit differs from saved report')
    require(all(actual['InputSHA256'].get(p) == h for p,h in claimed['InputSHA256'].items()),
            'saved audit inputs absent from recomputation')


def passed_tables(report):
    tables, clocks = timing.summaries(report)
    require(set(tables) == {(c,k) for c in ('slow','fast') for k in ('setup','hold','recovery','removal','mpw')}
            and all(tables.values()) and clocks, 'all ten timing tables and clocks required')
    require(all(row['FailingChecks'] == 0 and row['WorstSlackNS'] >= 0 and row['TotalNegativeSlackNS'] == 0
                for rows in tables.values() for row in rows.values()), 'all ten timing tables must pass')
    return tables, clocks


def false_paths(path):
    with Path(path).open(encoding='gb18030') as stream:
        return timing.native.parse_false_paths(stream)


def reset_flags(value, candidate):
    require(value.get('Schema') == 'camera720-reset-effect-v1' and value.get('Target') == prep.TARGET
            and value.get('CandidateADFSHA256') == candidate,
            'current 720p reset effect identity required')
    for key in ('AuditPassed','ResetEffectVerified','AllInternalChecksMet','FunctionalGraphIdentical',
                'AllFFPlacementsIdentical','ExactResetExceptionUnionVerified','NoDataFalsePaths',
                'ClockDefinitionsAndLoadsUnchanged'):
        require(value.get(key) is True, 'incomplete reset effect: '+key)
    route = value.get('RouteComparison', {})
    require(route.get('RoutingUnchanged') is True and route.get('ChangedNets') == []
            and route.get('NonconstraintSemanticsUnchanged') is True, 'reset application changed routes/semantics')


def cdc_flags(value, candidate):
    if value.get('Schema') in (CLM_COVERAGE_SCHEMA,SINGLE_COVERAGE_SCHEMA):
        module = audit_module(value,'cdc')
        physical = module.parent if module.__name__ == 'camera720_cdc_single' else module
        require(physical.__name__ == 'camera720_cdc_clm_native' and value.get('Target') == prep.TARGET
                and value.get('CandidateADF') == candidate and value.get('Policy') == physical.old.policy_reference(),
                'current physical CLM candidate/policy required')
        require(all(value.get(k) is True for k in ('Complete','EnumeratedPathsTimingPassed',
                'PhysicalCoverageComplete','PhysicalBoundaryCoverageComplete','PhysicalBoundaryChecksPassed',
                'AllLogicalRelationshipsStructurallyRepresented'))
                and value.get('MissingCases') == [] and value.get('Violations') == []
                and value.get('OrdinaryMissingCases') == [], 'incomplete actual physical CLM coverage')
        require(type(value.get('ExpectedCases')) is int and value['ExpectedCases'] > 0
                and value.get('CoveredCases') == value['ExpectedCases']
                and type(value.get('LogicalRelationshipsRetained')) is int and value['LogicalRelationshipsRetained'] > 0
                and type(value.get('OrdinaryCoveredCases')) is int and value['OrdinaryCoveredCases'] > 0,
                'physical CLM case/logical counts differ')
        require(all(value.get(k) is False for k in ('IndividualFFArcsEnumerated','PhysicalTimingAggregationProved',
                'LogicalFFTimingAccepted','TimingAccepted','NativeTimingAccepted','HardwareReleaseAllowed',
                'HardwareAccessed','EDAExecuted')), 'physical CLM proof exceeds vendor-model scope')
        require(value.get('NativeSTAContext') == {'Engine':'PDS 2023.2-SP3 build154097',
                'Scope':'Native physical sequential endpoints','ActualTcoRequired':True,
                'CriticalDiagnosticsRejected':True,'IndividualFFArcsEnumerated':False,
                'SharedClockAliasUsedAsCaptureFFProof':False}, 'physical native timing context differs')
        return
    if value.get('Schema') == LAUNCH_COVERAGE_SCHEMA:
        module = audit_module(value,'cdc')
        require(module.__name__ == 'camera720_cdc_native' and value.get('Target') == prep.TARGET
                and value.get('CandidateADF') == candidate and value.get('Policy') == module.policy_reference()
                and module.MANUAL == NATIVE_MANUAL and module.MANUAL_SHA == NATIVE_MANUAL_SHA,
                'current launch-qualified CDC candidate/policy required')
        require(value.get('Complete') is True and value.get('EnumeratedPathsTimingPassed') is True
                and value.get('Violations') == [] and value.get('MissingCases') == []
                and value.get('MissingIdentityCount') == 0 and value.get('InvalidPins') == []
                and value.get('RemainingGroups') == [] and value.get('RemainingBodies') == {},
                'incomplete launch-qualified CDC coverage')
        require(type(value.get('ExpectedCases')) is int and value['ExpectedCases'] > 0
                and value.get('CoveredCases') == value['ExpectedCases'], 'CDC count differs')
        require(value.get('HoldAnalysisSuppressedForDatapathOnly') is True
                and value.get('MinDelayNotAccepted') is True, 'datapath-only native policy differs')
        require(all(value.get(key) is False for key in ('SameBLEInternalTimingAccepted','NativeSiteMappingVerified',
                'NativeElectricalSettingsVerified','AnalogMTBFProven','TimingAccepted','HardwareReleaseAllowed',
                'HardwareAccessed','EDAExecuted')), 'launch-qualified proof exceeds enumerated CPU scope')
        return
    require(value.get('Schema') == 'camera720-cdc-native-coverage-v1' and value.get('Target') == prep.TARGET
            and value.get('CandidateADF') == candidate, 'current 720p CDC candidate required')
    require(value.get('Complete') is True and value.get('EnumeratedPathsTimingPassed') is True
            and value.get('NativeSiteMappingVerified') is True and value.get('EnumeratedPathsAndSitesPassed') is True
            and value.get('Violations') == [] and value.get('MissingCases') == []
            and value.get('MissingPairCount') == 0 and value.get('NativeSiteError') is None,
            'incomplete native CDC/site coverage')
    require(type(value.get('ExpectedCases')) is int and value['ExpectedCases'] > 0
            and value.get('CoveredCases') == value['ExpectedCases'], 'CDC count differs')


def audit_module(value, kind):
    """Explicit producer dispatch; legacy reports never impersonate new tools."""
    require(kind in ('cdc','io'), 'unsupported evidence kind')
    legacy = 'camera720_cdc_batch' if kind == 'cdc' else 'camera720_io_evidence'
    newer = ('camera720_cdc_grouped','camera720_cdc_native','camera720_cdc_clm_native','camera720_cdc_single') if kind == 'cdc' else ('camera720_io_fast',)
    if 'Producer' not in value:
        require(not {'OriginalBatchPlan','InspectionSeed','EndpointInventory','Plan'} & set(value),
                'new evidence requires its explicit producer')
        return importlib.import_module(legacy)
    require(isinstance(value['Producer'],dict) and set(value['Producer']) == {'Path','SHA256'},
            'exact evidence producer binding required')
    for name in newer:
        if value['Producer'].get('Path') == str(prep.PROJECT/'tools'/(name+'.py')):
            module = importlib.import_module(name)
            require(value['Producer'] == binding(module.SELF), 'unexpected current evidence producer')
            require(name != 'camera720_cdc_native' or value.get('Schema') == LAUNCH_COVERAGE_SCHEMA,
                    'launch-qualified producer requires its own coverage schema')
            require(name != 'camera720_cdc_clm_native' or value.get('Schema') == CLM_COVERAGE_SCHEMA,
                    'physical CLM producer requires its own coverage schema')
            require(name != 'camera720_cdc_single' or value.get('Schema') == SINGLE_COVERAGE_SCHEMA,
                    'single-launch producer requires its own coverage schema')
            return module
    raise ValueError('unexpected current evidence producer')


def grouped_context(value, export_path, watched):
    module = audit_module(value,'cdc')
    require(module.__name__ == 'camera720_cdc_grouped', 'grouped CDC producer required')
    local = {}
    plan, initial, seed_context = module.bind_plan(value['BatchPlan']['Path'],value['BatchPlan']['SHA256'],local)
    require(value.get('OriginalBatchPlan') == plan['OriginalBatchPlan']
            and value.get('InspectionSeed') == plan['InspectionSeed']
            and value['Producer'] == plan['Producer'] and plan['ExportReceipt'] == binding(export_path),
            'grouped coverage plan/source/producer chain differs')
    merge(watched,local,Path(read(export_path)['Command'][0]))
    return module,plan,initial,seed_context


def launch_context(value, export_path, watched):
    """Bind a completed launch-qualified audit without re-parsing the graph."""
    module = audit_module(value,'cdc')
    require(module.__name__ == 'camera720_cdc_native', 'launch-qualified CDC producer required')
    pds = Path(read(export_path)['Command'][0]); local = {}
    path = ref(value['Plan'],local,pds); plan = read(path)
    require(plan.get('Schema') == module.SCHEMA and plan.get('Target') == prep.TARGET
            and plan.get('Producer') == value['Producer'] and plan.get('Policy') == module.policy_reference()
            and plan.get('CoverageAssumedFromGrouping') is False
            and all(plan.get(k) is False for k in ('EDAExecuted','HardwareAccessed','TimingAccepted','HardwareReleaseAllowed')),
            'launch-qualified plan producer/policy/scope differs')
    rehash_inputs(plan,local,pds)
    require(value['InputSHA256'].get(str(path)) == value['Plan']['SHA256'],
            'launch-qualified plan missing from full audit closure')
    for key in ('Producer','Policy','EndpointInventory','OriginalBatchPlan','InspectionSeed','CandidateADF',
                'BuildPlanSHA256','SameBLESupplement','SupplementalProducer','SupplementalLogicalRelationshipOffset'):
        require(value.get(key) == plan.get(key), 'launch-qualified plan/report differs: '+key)
    original_inputs = {}
    old = module.grouped.bind_original(plan['OriginalBatchPlan']['Path'],plan['OriginalBatchPlan']['SHA256'],original_inputs)
    merge(local,original_inputs,pds)
    require(old['ExportReceipt'] == binding(export_path) and old['CandidateADF'] == plan['CandidateADF']
            and old['BuildPlanSHA256'] == plan['BuildPlanSHA256'], 'launch-qualified final source differs')
    context = module.grouped.bind_seed(plan['InspectionSeed'],old['CandidateADF'],old['BuildPlanSHA256'],{})
    merge(local,context[2],pds)
    inventory_path = ref(plan['EndpointInventory'],local,pds); inventory = read(inventory_path)
    rehash_inputs(inventory,local,pds)
    require(inventory.get('Schema') == 'camera720-native-endpoints-v1'
            and inventory.get('CandidateADF') == old['CandidateADF']
            and inventory.get('BuildPlanSHA256') == old['BuildPlanSHA256']
            and inventory.get('ExportReceipt') == old['ExportReceipt']
            and inventory['InputSHA256'].get(str(module.mapping_tool.SELF)) == sha(module.mapping_tool.SELF)
            and inventory['InputSHA256'].get(plan['OriginalBatchPlan']['Path']) == plan['OriginalBatchPlan']['SHA256'],
            'launch-qualified endpoint inventory source/producer differs')
    supplement = plan['SameBLESupplement']; offset = plan['SupplementalLogicalRelationshipOffset']
    require(type(offset) is int and offset == len(inventory['LogicalRelationships'])
            and value.get('SameBLEInterstageInventory') == inventory['SameBLEInterstageInventory']
            and supplement.get('Schema') == 'camera720-sameble-supplement-v1'
            and supplement.get('Producer') == plan['SupplementalProducer'] == binding(module.sameble.SELF)
            and supplement.get('Mapper') == binding(module.mapping_tool.SELF)
            and supplement.get('CandidateADF') == old['CandidateADF']
            and supplement.get('BuildPlanSHA256') == old['BuildPlanSHA256']
            and supplement.get('StructuralClassificationPassed') is True
            and supplement.get('NativeTimingAccepted') is False and supplement.get('HardwareReleaseAllowed') is False,
            'launch-qualified same-BLE supplement differs')
    augmented = copy.deepcopy(inventory)
    augmented['LogicalRelationships'].extend(copy.deepcopy(supplement['LogicalRelationships']))
    for original in supplement['Queries']:
        query = copy.deepcopy(original)
        query['LogicalRelationships'] = [i+offset for i in query['LogicalRelationships']]
        augmented['Queries'].append(query)
    require(plan['Queries'] == module.normalize_queries(augmented,old['Constraints']),
            'launch-qualified mapped identities or native policy differ')
    require(plan['InitialEvidence'] and plan['InitialEvidence'][0] == old['ExportReceipt']
            and len({r['Path'] for r in plan['InitialEvidence']}) == len(plan['InitialEvidence']),
            'launch-qualified initial final-export chain differs')
    groups = module.groups_for(plan['Queries'],plan['InitialCoverage']['MissingCases'],plan['MaximumExpectedIdentitiesPerGroup'])
    bodies = module.query_bodies(groups,plan['MaximumTimingCommandsPerBody'])
    require(groups == plan['Groups'] and plan['QueryBodies'] == {n:hashlib.sha256(t.encode('ascii')).hexdigest()
            for n,t in bodies.items()}, 'launch-qualified native query recipe differs')
    for name,digest in plan['QueryBodies'].items():
        add(local,inspect.canonical(path.parent/name,path.parent),digest,pds)
    for item in (plan['OriginalBatchPlan'],plan['EndpointInventory'],plan['InspectionSeed'],old['ExportReceipt'],
                 plan['Producer'],plan['SupplementalProducer'],binding(module.mapping_tool.SELF)):
        bound = ref(item,local,pds)
        require(plan['InputSHA256'].get(str(bound)) == item['SHA256'], 'launch-qualified plan omits source/tool')
    require(plan['InputSHA256'].get(str(NATIVE_MANUAL)) == NATIVE_MANUAL_SHA, 'native policy document absent')
    merge(watched,local,pds)
    commands = [module.timing_command(q['Source'],q['Endpoint']) for q in supplement['Queries']]
    return module,plan,old,context,bodies,commands


def launch_extra_receipts(value, plan):
    receipts = value.get('NativeReceipts'); initial = plan['InitialEvidence']
    require(isinstance(receipts,list) and receipts and receipts[:len(initial)] == initial
            and len({r['Path'] for r in receipts}) == len(receipts), 'launch-qualified receipt order/identity differs')
    return receipts[len(initial):]


def reuse_launch_cdc(value, export_path, watched, application):
    module,plan,old,context,bodies,commands = launch_context(value,export_path,watched)
    extra = launch_extra_receipts(value,plan); local = {}; pds = Path(read(export_path)['Command'][0])
    reports,initial,issues,omitted = module.bind_reports(plan['InitialEvidence'],old,plan['InspectionSeed'],context,local,
        initial_commands=commands)
    require([binding(p) for p in reports] == plan['InitialReports']
            and omitted == plan['ExcludedInitialReports'], 'launch-qualified initial native reports differ')
    bound = []
    if extra:
        more,bound,pin_issues,excluded = module.bind_reports(extra,old,plan['InspectionSeed'],context,local,
            set(bodies.values()),plan['Groups'])
        reports = sorted(set(reports+more)); issues += pin_issues; omitted += excluded
    require(not issues and initial+bound == value['NativeReceipts'] and omitted == value['ExcludedReports'],
            'launch-qualified receipt/pin evidence differs')
    for item in value['NativeReceipts']:
        path = ref(item,local,pds)
        require(value['InputSHA256'].get(str(path)) == item['SHA256']
                and read(path).get('SourceReceipt') == application, 'launch-qualified receipt source/closure differs')
    expected = module.coverage(plan['Queries'],value['Records'],value['Violations'])
    require(all(value.get(k) == v for k,v in expected.items()), 'reviewed launch-qualified case coverage differs')
    require(value.get('SuppressedCrossingCount') == sum('Clock' not in q for q in plan['Queries']),
            'suppressed crossing count differs')
    native_reports = {str(p) for p in reports}; lookup = {module.identity(q):q for q in plan['Queries']}
    for record in value['Records']:
        require(record.get('Report') in native_reports and record['Report'] in value['InputSHA256']
                and type(record.get('ReportLine')) is int and record['ReportLine'] > 0
                and final.physical.digest(record.get('PathSHA256')) and record['SlackNS'] >= 0,
                'launch-qualified record lacks receipt-bound native origin/slack')
        query = lookup[module.identity(record)]
        require(record.get('Launch',{}).get('LaunchOutput') == record['LaunchOutput'], 'native tco launch identity differs')
        if 'Clock' in query:
            require(record.get('Clock') == query['Clock'] and record.get('HoldAnalysisSuppressed') is False,
                    'ordinary native setup/hold scope differs')
        else:
            require(record.get('Kind') == 'max-delay' and record.get('HoldAnalysisSuppressed') is True
                    and record.get('MinDelayNotAccepted') is True and record.get('BoundNS') == query['MaximumNS']
                    and 0 <= record['ArrivalNS'] < query['SourcePeriodNS'], 'datapath-only native maximum scope differs')
    merge(watched,local,pds)
    return plan


def physical_sta_basis(value, plan, watched, pds):
    """Vendor-model reliance is explicit; individual FF arcs are not invented."""
    add(watched,CLM_BASIS,CLM_BASIS_SHA,pds)
    add(watched,CLM_BASIS_NOTE,CLM_BASIS_NOTE_SHA,pds)
    add(watched,CLM_EXTRACT,CLM_EXTRACT_SHA,pds)
    basis = read(CLM_BASIS); rehash_inputs(basis,watched,pds)
    require(basis.get('Schema') == 'camera720-clm-vendor-sta-basis-v1'
            and basis.get('CandidateADF') == value['CandidateADF']
            and basis.get('BuildPlanSHA256') == value['BuildPlanSHA256']
            and basis.get('PhysicalMapping') == value['PhysicalMapping'] == plan['PhysicalMapping'],
            'vendor physical STA basis candidate/mapping differs')
    require(all(basis.get(k) is True for k in ('AllMergedGroupsHomogeneous','StructuralMappingAuditPassed',
            'VendorPhysicalSequentialTimingModelReliedUpon','CompletePhysicalCaseCoverageRequiredSeparately',
            'FinalCandidateFullSTARequiredSeparately')) and all(basis.get(k) is False for k in (
            'PhysicalTimingAggregationProved','IndependentWorstOverInternalFFFormulaClaimed',
            'NativeTimingAccepted','HardwareReleaseAllowed')), 'vendor physical STA basis scope differs')
    documents = {NATIVE_MANUAL:NATIVE_MANUAL_SHA,**CLM_DOCUMENTS}
    extracts = read(CLM_EXTRACT)
    require(isinstance(extracts,list) and extracts, 'fixed vendor evidence extract required')
    referenced = {}
    for item in extracts:
        path = Path(item['Document'])
        require(path in documents and item.get('SHA256') == documents[path], 'unexpected vendor document reference')
        add(watched,path,item['SHA256'],pds); referenced[path] = item['SHA256']
    require(referenced == documents, 'vendor document closure incomplete')
    mapping_path = ref(value['PhysicalMapping'],watched,pds); mapping = read(mapping_path)
    require(mapping.get('PhysicalBoundaryDerivationPassed') is True
            and mapping.get('CandidateADF') == value['CandidateADF']
            and mapping.get('BuildPlanSHA256') == value['BuildPlanSHA256']
            and mapping.get('Producer') == value['PhysicalMapper'] == plan['PhysicalMapper'],
            'physical mapping producer or candidate differs')
    offset = len(mapping['LogicalRelationships']); supplemental = plan['SameBLESupplement']
    require(offset == basis['BaseLogicalRelationshipCount'] == value['SupplementalLogicalRelationshipOffset']
            == plan['SupplementalLogicalRelationshipOffset'] and len(mapping['Queries']) == basis['BasePhysicalQueryCount']
            and value['LogicalRelationshipsRetained'] == offset+len(supplemental['LogicalRelationships'])
            and value['SameBLESupplement'] == supplemental, 'physical logical relationship inventory differs')
    represented = {i for q in plan['Queries'] for i in q['LogicalRelationships']}
    require(represented == set(range(value['LogicalRelationshipsRetained'])), 'physical queries omit logical relations')
    merged = [q for q in mapping['Queries'] if len(q['LogicalRelationships']) > 1]
    by_key = {(q['Source'],q['LaunchOutput'],q['Endpoint']):q for q in basis['MergedQueries']}
    require(len(by_key) == len(merged) == basis['MergedQueryCount'], 'vendor merged-group inventory differs')
    for query in merged:
        key = query['Source'],query['LaunchOutput'],query['Endpoint']
        require(key in by_key and by_key[key]['LogicalRelationships'] == query['LogicalRelationships'],
                'vendor merged-group logical membership differs')
        rows = [mapping['LogicalRelationships'][i] for i in query['LogicalRelationships']]
        require(by_key[key]['DestinationFFs'] == [r['DestinationFF'] for r in rows]
                and {r['DestinationPlacement']['Site'] for r in rows} == {by_key[key]['PhysicalSite']},
                'vendor merged-group capture identities differ')


def recompute_physical_cdc(value, export_path, watched):
    """Always run the pure full collector, even in three-SHA reuse mode."""
    producer = audit_module(value,'cdc'); pds = Path(read(export_path)['Command'][0])
    cdc_flags(value,value['CandidateADF'])
    require(value.get('ExportReceipt') == binding(export_path), 'physical CDC is not from final export')
    plan_path = ref(value['Plan'],watched,pds); plan = read(plan_path)
    single = producer.__name__ == 'camera720_cdc_single'
    schema = producer.PLAN_SCHEMA if single else producer.SCHEMA
    require(plan.get('Schema') == schema and plan.get('Producer') == value['Producer']
            and plan.get('CandidateADF') == value['CandidateADF']
            and plan.get('BuildPlanSHA256') == value['BuildPlanSHA256']
            and plan.get('InspectionSeed') == value['InspectionSeed'], 'physical CDC plan/source differs')
    require(value['InputSHA256'].get(str(plan_path)) == value['Plan']['SHA256'],
            'physical CDC plan absent from complete audit closure')
    basis_plan = plan
    if single:
        require(plan.get('ParentPlan') == value.get('ParentPlan') == producer.parent.fixed(producer.PARENT_PLAN,producer.PARENT_SHA)
                and plan.get('ParentProducer') == value.get('ParentProducer') == binding(producer.parent.SELF)
                and plan.get('PreservedPartialReceipts') == value.get('PreservedPartialReceipts') ==
                    [producer.parent.fixed(producer.PARTIAL,producer.PARTIAL_SHA)], 'single-launch parent/partial chain differs')
        parent_path = ref(value['ParentPlan'],watched,pds); basis_plan = read(parent_path)
        require(basis_plan.get('Schema') == producer.parent.SCHEMA
                and basis_plan.get('Producer') == value['ParentProducer']
                and basis_plan.get('CandidateADF') == value['CandidateADF']
                and basis_plan.get('BuildPlanSHA256') == value['BuildPlanSHA256']
                and basis_plan.get('InspectionSeed') == value['InspectionSeed']
                and basis_plan.get('Queries') == plan.get('Queries')
                and value['InputSHA256'].get(str(parent_path)) == value['ParentPlan']['SHA256'],
                'single-launch parent source/query closure differs')
    require(basis_plan.get('OriginalBatchPlan') == value['OriginalBatchPlan'], 'physical CDC original batch differs')
    rehash_inputs(value,watched,pds)
    computed,local = producer.audit_value(value['Plan']['Path'],value['Plan']['SHA256'],value['NativeReceipts'])
    equal_audit(computed,value); merge(watched,local,pds)
    cdc_flags(computed,value['CandidateADF'])
    physical_sta_basis(value,basis_plan,watched,pds)
    return plan


def recompute_cdc(value, export_path, watched):
    """Recompute the final graph, exact cases and native receipt coverage once."""
    producer = audit_module(value,'cdc')
    if producer.__name__ in ('camera720_cdc_clm_native','camera720_cdc_single'):
        return recompute_physical_cdc(value,export_path,watched)
    if producer.__name__ == 'camera720_cdc_native':
        module,plan,_,_,_,_ = launch_context(value,export_path,watched)
        computed,local,supplements = module.audit_value(value['Plan']['Path'],value['Plan']['SHA256'],
            launch_extra_receipts(value,plan))
        require(not supplements, 'complete launch-qualified CDC proof cannot need supplemental native paths')
        equal_audit(computed,value)
        merge(watched,local,Path(read(export_path)['Command'][0]))
        return plan
    if producer.__name__ == 'camera720_cdc_grouped':
        module,plan,_,_ = grouped_context(value,export_path,watched)
        computed,local,supplements = module.audit(value['BatchPlan']['Path'],value['BatchPlan']['SHA256'],
            [item['Path'] for item in value['NativeReceipts']])
        require(not supplements, 'complete grouped CDC proof cannot need supplemental native paths')
        equal_audit(computed,value)
        merge(watched,local,Path(read(export_path)['Command'][0]))
        return plan
    local = {}
    plan_path = ref(value['BatchPlan'], local)
    plan = read(plan_path)
    require(plan.get('Schema') == cdc.SCHEMA and plan.get('Target') == prep.TARGET, 'wrong CDC batch plan')
    actual = cdc.derive(export_path, local)
    require(plan['ExportReceipt'] == binding(export_path), 'CDC export is not final bit export')
    for key, wanted in actual.items():
        require(plan.get(key) == wanted, 'recomputed CDC structure differs: '+key)
    pds = Path(read(export_path)['Command'][0])
    rehash_inputs(plan, local, pds)
    initial, groups = cdc.bodies(plan['Queries'], plan['IOSites'])
    require(plan['Groups'] == groups and plan['QueryBodies'] == {
        f'query-{i:02}.tcl':hashlib.sha256(text.encode('ascii')).hexdigest() for i,text in enumerate(initial)},
        'CDC query recipe changed')
    for name,digest in plan['QueryBodies'].items():
        add(local, plan_path.parent/name, digest, pds)
    reports, logs, native_receipts = [], [], []
    for item in value['NativeReceipts']:
        path = ref(item, local, pds)
        receipt = cdc.bind_native(path, 'query', local, plan['CandidateADF'], plan['BuildPlanSHA256'])
        require(receipt.get('SourceReceipt') == read(export_path).get('SourceReceipt'),
                'CDC query belongs to another reset application')
        body_path = add(local, receipt['QueryBody'], pds=pds)
        require(receipt['InputSHA256'].get(str(body_path)) == sha(body_path), 'unbound CDC body')
        cdc.approved_body(body_path.read_text(encoding='ascii'), plan, initial)
        for name,digest in receipt['Artifacts'].items():
            if name.endswith('.rtr'):
                reports.append(add(local, path.parent/name, digest, pds))
        logs.append(add(local, path.parent/'stdout.log', receipt['Artifacts']['stdout.log'], pds)
                    .read_text(encoding='gb18030'))
        native_receipts.append(binding(path))
    require(reports, 'no native CDC reports')
    records, violations = cdc.collect(plan['Queries'], sorted(set(reports)))
    computed = cdc.coverage(plan['Queries'], records, violations)
    site_blocks = {}
    for log in logs:
        for block in re.findall(r'(?ms)^Site \S+ \(\d+\) :\r?\n.*?(?=^Site |^Executing :|\Z)', log):
            site = re.match(r'Site (\S+)', block)[1]
            require(site not in site_blocks or site_blocks[site] == block, 'conflicting native site evidence')
            site_blocks[site] = block
    pins = copy.deepcopy(plan['ComponentChecks']['Pins'])
    cdc.structure.io.apply_native_sites(pins, ''.join(site_blocks.values()))
    computed.update(Records=records, Violations=violations, Pins=pins, NativeReceipts=native_receipts,
                    MissingPairCount=len({(p['Source'],p['Endpoint']) for p in computed['MissingCases']}),
                    NativeSiteError=None, NativeSiteMappingVerified=True,
                    EnumeratedPathsAndSitesPassed=computed['EnumeratedPathsTimingPassed'])
    require(all(value.get(k) == v for k,v in computed.items()), 'recomputed CDC coverage differs')
    rehash_inputs(value, local, pds)
    merge(watched, local, pds)
    return plan


def electrical_flags(value, candidate):
    require(value.get('Schema') == 'camera720-io-evidence-v1' and value.get('Target') == prep.TARGET
            and value.get('CandidateADF') == candidate, 'current 720p electrical evidence required')
    for key in ('AuditPassed','PinDeclarationsVerified','NativePadElectricalParametersVerified',
                'NativePinSitesVerified','InputDelayStructureVerified','TXMaximumPathsVerified',
                'DVPReportedBudgetCoverageComplete'):
        require(value.get(key) is True, 'incomplete IO evidence: '+key)


def reviewed_anchors(reviewed, request):
    require(isinstance(reviewed, dict) and set(reviewed) == {'ResetEffectAudit','FinalCDCProof','FinalIOProof'},
            'reuse requires all three explicit completed-audit SHA256 anchors')
    for key, digest in reviewed.items():
        require(final.physical.digest(digest) and digest == request[key]['SHA256'],
                'reviewed audit SHA differs from exact request: '+key)


def completed_audit(value, path, producer, watched, pds):
    """Hash-check the full result of a caller-anchored completed audit."""
    rehash_inputs(value, watched, pds)
    source = prep.PROJECT/'tools'/producer
    require(value['InputSHA256'].get(str(source)) == sha(source), 'completed audit producer missing or changed')
    add(watched, path, pds=pds)
    require(value.get('HardwareAccessed') is False and value.get('EDAExecuted') is False,
            'expected a completed CPU-only audit')


def anchored_native(path, watched, pds, candidate, build_sha, application, mode):
    """Check the exact receipt chain already covered by an anchored full audit."""
    path = add(watched, path, pds=pds)
    value = read(path)
    final.receipt_flags(value)
    require(value.get('Schema') == final.SCHEMA and value.get('Target') == prep.TARGET
            and value.get('Mode') == mode and value.get('SourceADF') == candidate['Path']
            and value.get('SourceADFSHA256') == candidate['SHA256']
            and value.get('BuildPlanSHA256') == build_sha and value.get('SourceReceipt') == application,
            'anchored native candidate/build/application differs')
    require(value.get('EDAExecuted') is True and value.get('ExecutionPassed') is True
            and value.get('ExitCode') == 0 and value.get('InputDrift') == [] and value.get('Diagnostics') == []
            and value.get('TimedOut') is False and value.get('StoppedForUnexpectedStage') is False
            and value.get('InputADFUnchanged') is True and value.get('CompletionMarker') is True
            and value.get('Cleanup',{}).get('Complete') is True and not value.get('Error'),
            'unclean anchored native receipt')
    require(value.get('HardwareAccessed') is False and value.get('HardwareReleaseAllowed') is False,
            'native receipt exceeds diagnostic scope')
    rehash_inputs(value, watched, pds)
    stage_path = add(watched, path.parent/'stage-plan.json', value['StagePlanSHA256'], pds)
    stage = read(stage_path)
    require(all(value.get(k) == v for k,v in stage.items()), 'native receipt differs from frozen stage plan')
    add(watched, path.parent/'input.adf', candidate['SHA256'], pds)
    require(isinstance(value.get('Artifacts'), dict)
            and {'stage.tcl','stdout.log','stderr.log'} <= set(value['Artifacts']), 'missing native artifacts')
    for name, digest in value['Artifacts'].items():
        artifact = inspect.canonical(path.parent/name, path.parent)
        add(watched, artifact, digest, pds)
    require(value['Artifacts']['stage.tcl'] == stage['TclSHA256'], 'native Tcl identity differs')
    if mode == 'export':
        require(value.get('NativeNetlistWithFFloc') is True, 'placed export required')
        add(watched, value['Netlist']['Path'], value['Netlist']['SHA256'], pds)
    return value


def reuse_completed(request, paths, watched, pds, reviewed):
    """Reuse only caller-identified completed full audits; never bare pass flags."""
    reviewed_anchors(reviewed, request)
    effect_value, cdc_value, io_value = (read(paths[key]) for key in ('ResetEffectAudit','FinalCDCProof','FinalIOProof'))
    cdc_module,io_module = audit_module(cdc_value,'cdc'),audit_module(io_value,'io')
    for key, value, producer in (
        ('ResetEffectAudit',effect_value,'audit_camera720_reset_effect.py'),
        ('FinalCDCProof',cdc_value,Path(cdc_module.__file__).name),
        ('FinalIOProof',io_value,Path(io_module.__file__).name)):
        completed_audit(value, paths[key], producer, watched, pds)
    candidate = request['CandidateADF']; build_sha = request['BuildPlan']['SHA256']
    app = request['ResetApplicationReceipt']; export = request['FinalInspectionReceipt']
    reset_flags(effect_value, candidate['SHA256']); cdc_flags(cdc_value, candidate); electrical_flags(io_value, candidate)
    require(effect_value['Application'] == app and effect_value['FinalExport'] == export,
            'reviewed reset effect chain differs')
    application = read(paths['ResetApplicationReceipt'])
    require(application.get('Schema') == final.physical.SCHEMA and application.get('Target') == prep.TARGET
            and application.get('ExecutionPassed') is True and application.get('ResultADFSHA256') == candidate['SHA256']
            and application.get('BuildPlanSHA256') == build_sha and application.get('Mode') == 'save-reset',
            'reviewed reset application chain differs')
    require(effect_value['InputSHA256'].get(str(paths['ResetApplicationReceipt'])) == app['SHA256']
            and effect_value['InputSHA256'].get(str(paths['FinalInspectionReceipt'])) == export['SHA256'],
            'reviewed reset report omits its application/export')
    anchored_native(paths['FinalInspectionReceipt'],watched,pds,candidate,build_sha,app,'export')
    if cdc_module.__name__ in ('camera720_cdc_clm_native','camera720_cdc_single'):
        recompute_physical_cdc(cdc_value,paths['FinalInspectionReceipt'],watched)
    elif cdc_module.__name__ == 'camera720_cdc_native':
        reuse_launch_cdc(cdc_value,paths['FinalInspectionReceipt'],watched,app)
    else:
        plan_path = ref(cdc_value['BatchPlan'], watched, pds)
        grouped = cdc_module.__name__ == 'camera720_cdc_grouped'
        seed_context = None
        if grouped:
            _,plan,initial,seed_context = grouped_context(cdc_value,paths['FinalInspectionReceipt'],watched)
        else:
            plan=read(plan_path)
            initial,groups = cdc.bodies(plan['Queries'],plan['IOSites'])
            require(plan['Groups'] == groups and plan['QueryBodies'] == {
                f'query-{i:02}.tcl':hashlib.sha256(text.encode('ascii')).hexdigest() for i,text in enumerate(initial)},
                'reviewed CDC query recipe differs')
        require(plan.get('Schema') == cdc_module.SCHEMA and plan.get('Target') == prep.TARGET
                and plan.get('CandidateADF') == candidate and plan.get('BuildPlanSHA256') == build_sha
                and plan.get('ExportReceipt') == export and (grouped or plan.get('FinalExportReevaluated') is True),
                'reviewed CDC batch belongs to another final export')
        rehash_inputs(plan, watched, pds)
        require(cdc_value['InputSHA256'].get(str(plan_path)) == cdc_value['BatchPlan']['SHA256'],
                'CDC plan missing from completed audit closure')
        require(plan['ExpectedCases'] == len(plan['Queries'])*4 == cdc_value['ExpectedCases'], 'CDC expected case count differs')
        computed = cdc.coverage(plan['Queries'], cdc_value['Records'], cdc_value['Violations'])
        require(all(cdc_value.get(k) == v for k,v in computed.items()), 'reviewed CDC case coverage differs')
        require(all(r['SlackNS'] >= 0 for r in cdc_value['Records']), 'reviewed CDC has negative slack')
        require(isinstance(cdc_value.get('NativeReceipts'),list) and cdc_value['NativeReceipts'],
                'completed CDC audit has no actual native receipts')
        native_reports = set()
        for item in cdc_value['NativeReceipts']:
            path = ref(item,watched,pds)
            require(cdc_value['InputSHA256'].get(str(path)) == item['SHA256'], 'CDC receipt missing from full audit closure')
            receipt = (cdc_module.bind_native_fast(path,'query',watched,candidate,build_sha,plan['InspectionSeed'],seed_context)
                if grouped else anchored_native(path,watched,pds,candidate,build_sha,app,'query'))
            if grouped:
                require(receipt.get('SourceReceipt') == app, 'grouped query belongs to another reset application')
            body = add(watched,receipt['QueryBody'],pds=pds)
            require(receipt['InputSHA256'].get(str(body)) == sha(body), 'unbound reviewed query body')
            cdc_module.approved_body(body.read_text(encoding='ascii'),plan,initial)
            native_reports.update(str(path.parent/name) for name in receipt['Artifacts'] if name.endswith('.rtr'))
        for record in cdc_value['Records']:
            require(record.get('Report') in native_reports and record['Report'] in cdc_value['InputSHA256']
                    and type(record.get('ReportLine')) is int and record['ReportLine'] > 0
                    and final.physical.digest(record.get('PathSHA256')), 'CDC record lacks receipt-bound native origin')
    require(io_value['ExportReceipt'] == export and io_value['BuildPlanSHA256'] == build_sha,
            'reviewed electrical export/build differs')
    require(io_value['QueryReceipts'], 'electrical query receipts missing')
    io_context = None
    if io_module.__name__ == 'camera720_io_fast':
        require(io_value.get('NativeSourceProofReused') is True and io_value.get('ActualIOChecksRecomputed') is True,
                'fast IO computational scope differs')
        io_context = io_module.fast.bind_seed(io_value['InspectionSeed']['Path'],io_value['InspectionSeed']['SHA256'])
        group = importlib.import_module('camera720_cdc_grouped')
        group.bind_native_fast(paths['FinalInspectionReceipt'],'export',watched,candidate,build_sha,
            io_value['InspectionSeed'],io_context)
    for item in io_value['QueryReceipts']:
        path = ref(item,watched,pds)
        require(io_value['InputSHA256'].get(str(path)) == item['SHA256'], 'IO receipt missing from full audit closure')
        if io_context is None:
            anchored_native(path,watched,pds,candidate,build_sha,app,'query')
        else:
            receipt=group.bind_native_fast(path,'query',watched,candidate,build_sha,io_value['InspectionSeed'],io_context)
            require(receipt['SourceReceipt'] == app, 'fast IO query belongs to another reset application')


def audit_authority(request_path, reviewed=None):
    """Full CPU verification. This is the only producer of an authority seed."""
    watched = {}
    request_path = inspect.canonical(request_path, prep.WORK)
    add(watched, request_path)
    request = read(request_path)
    require(set(request) == REQUEST_FIELDS and request['Schema'] == REQUEST_SCHEMA and request['Target'] == prep.TARGET,
            'exact 720p bit request required')
    build_path = ref(request['BuildPlan'], watched)
    build = read(build_path); pds = Path(build['PDS']['Executable'])
    candidate = ref(request['CandidateADF'], watched, pds)
    export_path = ref(request['FinalInspectionReceipt'], watched, pds)
    application_path = ref(request['ResetApplicationReceipt'], watched, pds)
    effect_path = ref(request['ResetEffectAudit'], watched, pds)
    cdc_path = ref(request['FinalCDCProof'], watched, pds)
    electrical_path = ref(request['FinalIOProof'], watched, pds)
    claimed = read(effect_path)
    reset_flags(claimed, sha(candidate))
    require(claimed['Application'] == binding(application_path) and claimed['FinalExport'] == binding(export_path),
            'reset effect application/export differs')
    electrical = audit_module(read(electrical_path),'io')
    watch_tools(watched, pds)
    if reviewed is None:
        baseline_export = ref(claimed['BaselineExport'], watched, pds)
        actual = effect.run(application_path, baseline_export, export_path)
        equal_audit(actual, claimed)
        rehash_inputs(actual, watched, pds)
        rehash_inputs(claimed, watched, pds)
    else:
        reuse_completed(request, {'ResetEffectAudit':effect_path,'FinalCDCProof':cdc_path,'FinalIOProof':electrical_path,
            'ResetApplicationReceipt':application_path,'FinalInspectionReceipt':export_path}, watched,pds,reviewed)
    export = read(export_path); application = read(application_path)
    require(export['Schema'] == final.SCHEMA and export['SourceADFSHA256'] == sha(candidate)
            and export['SourceADF'] == str(candidate) and export['BuildPlan'] == str(build_path)
            and export['BuildPlanSHA256'] == sha(build_path)
            and application['ResultADFSHA256'] == sha(candidate)
            and application['BuildPlanSHA256'] == sha(build_path), 'bit candidate/build chain differs')
    report = effect.artifact(export_path, export, prep.TARGET+'.rtr', watched)
    exceptions = effect.artifact(export_path, export, prep.TARGET+'_exception.rtr', watched)
    passed_tables(report)
    require(all(not rows for (_,kind),rows in false_paths(exceptions).items() if kind in ('setup','hold')),
            'data false paths cannot authorize a bitstream')
    cdc_proof = read(cdc_path)
    cdc_flags(cdc_proof, request['CandidateADF'])
    if reviewed is None:
        recompute_cdc(cdc_proof, export_path, watched)
    io_proof = read(electrical_path)
    electrical_flags(io_proof, request['CandidateADF'])
    require(io_proof['ExportReceipt'] == binding(export_path) and io_proof['BuildPlanSHA256'] == sha(build_path),
            'electrical proof belongs to another export/build')
    # This API is implemented by the independently developed electrical audit.
    if reviewed is None:
        args=(export_path,[item['Path'] for item in io_proof['QueryReceipts']])
        if electrical.__name__ == 'camera720_io_fast':
            args += (io_proof['InspectionSeed']['Path'],io_proof['InspectionSeed']['SHA256'])
        io_actual = electrical.audit(*args)
        equal_audit(io_actual, io_proof)
        rehash_inputs(io_actual, watched, pds)
        rehash_inputs(io_proof, watched, pds)
    watch_tools(watched, pds)
    require(not inspect.drift(watched), 'authority input/tool drift')
    return {'Request':request, 'RequestPath':request_path, 'Build':build, 'PlanPath':build_path,
            'Candidate':candidate, 'CandidateSHA256':sha(candidate), 'FinalReport':report,
            'FinalExceptions':exceptions, 'Watched':watched, 'ReviewedAuditSHA256':reviewed or {}}


def prepare_authority(request_path, output, reviewed=None):
    output = Path(output).absolute()
    require(output == output.resolve() and output.is_relative_to(prep.WORK)
            and output.parent.is_dir() and not output.exists(), 'fresh authority file under 720 work required')
    context = audit_authority(request_path, reviewed)
    inputs = {str(p):h for p,h in context['Watched'].items()}
    value = {'Schema':AUTHORITY_SCHEMA, 'Target':prep.TARGET, 'CreatedUTC':inspect.utc(),
        'FullVerificationCompleted':True, 'HardwareAccessed':False, 'EDAExecuted':False,
        'PriorFullAuditsReused':reviewed is not None, 'ReviewedAuditSHA256':reviewed or {},
        'ValidationMethod':{'Function':'camera720_bitstream.audit_authority','Path':str(SELF),'SHA256':sha(SELF)},
        'Request':binding(context['RequestPath']), 'BuildPlan':binding(context['PlanPath']),
        'CandidateADF':binding(context['Candidate']), 'FinalReport':binding(context['FinalReport']),
        'FinalExceptions':binding(context['FinalExceptions']), 'InputSHA256':inputs,
        'ToolSHA256':{p:h for p,h in inputs.items() if Path(p).suffix.lower() in ('.py','.exe')},
        'HardwareReleaseAllowed':False, 'ExternalACTimingAccepted':False, 'OpticalCorrectionAccepted':False,
        'DiagnosticOnly':True}
    require(not inspect.drift(context['Watched']), 'authority changed before sealing')
    with output.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, indent=2); stream.write('\n')
    return value


def bind_authority(path, expected_sha):
    """Use only the exact completed CPU audit hash supplied by the caller."""
    watched = {}
    require(final.physical.digest(expected_sha), 'explicit authority SHA256 required')
    inspect.canonical(path, prep.WORK)
    path = ref({'Path':str(Path(path).absolute()),'SHA256':expected_sha}, watched)
    seed = read(path)
    require(seed.get('Schema') == AUTHORITY_SCHEMA and seed.get('Target') == prep.TARGET
            and seed.get('FullVerificationCompleted') is True
            and seed.get('HardwareAccessed') is False and seed.get('EDAExecuted') is False,
            'completed 720p CPU authority required')
    require(seed.get('ValidationMethod') == {'Function':'camera720_bitstream.audit_authority',
            'Path':str(SELF),'SHA256':sha(SELF)}, 'authority validator changed')
    for key in ('HardwareReleaseAllowed','ExternalACTimingAccepted','OpticalCorrectionAccepted'):
        require(seed.get(key) is False, 'authority overclaims diagnostic scope')
    require(seed.get('DiagnosticOnly') is True, 'diagnostic authority required')
    request_path = ref(seed['Request'], watched); request = read(request_path)
    require(set(request) == REQUEST_FIELDS and request.get('Schema') == REQUEST_SCHEMA and request.get('Target') == prep.TARGET,
            'authority request identity differs')
    require(type(seed.get('PriorFullAuditsReused')) is bool, 'authority reuse mode missing')
    if seed['PriorFullAuditsReused']:
        reviewed_anchors(seed['ReviewedAuditSHA256'], request)
    else:
        require(seed.get('ReviewedAuditSHA256') == {}, 'unexpected reviewed audit anchors')
    require(seed['BuildPlan'] == request['BuildPlan'] and seed['CandidateADF'] == request['CandidateADF'],
            'authority context differs from request')
    build_path = ref(seed['BuildPlan'], watched); build = read(build_path); pds = Path(build['PDS']['Executable'])
    rehash_inputs(seed, watched, pds)
    require(seed['ToolSHA256'] == {p:h for p,h in seed['InputSHA256'].items() if Path(p).suffix.lower() in ('.py','.exe')},
            'authority tool closure differs')
    for name in ('BuildPlan','CandidateADF','FinalInspectionReceipt','FinalCDCProof','FinalIOProof',
                 'ResetApplicationReceipt','ResetEffectAudit'):
        evidence = ref(request[name], watched, pds)
        require(seed['InputSHA256'].get(str(evidence)) == sha(evidence), 'authority omits request evidence: '+name)
    candidate = ref(seed['CandidateADF'], watched, pds)
    report = ref(seed['FinalReport'], watched, pds)
    exceptions = ref(seed['FinalExceptions'], watched, pds)
    for item in (request_path, build_path, candidate, report, exceptions, SELF, PYTHON):
        require(seed['InputSHA256'].get(str(item)) == sha(item), 'authority omits required context/tool')
    export_path = Path(request['FinalInspectionReceipt']['Path']); export = read(export_path)
    require(export['SourceADFSHA256'] == sha(candidate) and export['SourceADF'] == str(candidate)
            and export['BuildPlanSHA256'] == sha(build_path), 'authority final export differs')
    require(report == effect.artifact(export_path, export, prep.TARGET+'.rtr', watched)
            and exceptions == effect.artifact(export_path, export, prep.TARGET+'_exception.rtr', watched),
            'authority report is not final receipt artifact')
    require(not inspect.drift(watched), 'sealed authority drift')
    return {'Request':request, 'RequestPath':request_path, 'Build':build, 'PlanPath':build_path,
            'Candidate':candidate, 'CandidateSHA256':sha(candidate), 'FinalReport':report,
            'FinalExceptions':exceptions, 'Watched':watched, 'Authority':binding(path)}


def render(context,work):
    base=context['PlanPath'].parent
    rendered=inspect.render('export',(base/'timing.tcl').read_text(encoding='ascii'),base,work)
    boundary='report_timing -force_to_run -input_db_file '
    require(rendered.count(boundary)==1,'one fresh native report context required')
    prefix=rendered[:rendered.index(boundary)];w=work.as_posix();marker='CAMERA720_GATE_PASS '+context['CandidateSHA256']
    return (prefix+boundary+'{'+w+'/audited-final.adf} -delay_type min_max -max_path 1000 -nworst 4 -report_exception TRUE\n'
        'if {[info script] ne {}} {\n    set checked [exec {'+PYTHON.as_posix()+'} -B {'+SELF.as_posix()+'} --gate {'+w+'}]\n'
        '    puts $checked\n    if {[string first {'+marker+'} $checked] < 0} {error {Missing 720p pre-bit gate}}\n'
        '    gen_bit_stream -force_to_run -input_db_file {'+w+'/audited-final.adf} -scbv {High Voltage} -unused_io_status UNUSED\n'
        '    puts {'+COMPLETE+'}\n    flush stdout\n}\n')


def recipe(authority_path,authority_sha,work,maximum=900):
    work=prep.work_path(work);require(work.name.startswith('bit-'),'720p bit-* stage required')
    require(type(maximum) is int and 60<=maximum<=900,'bit deadline must be60..900 seconds')
    c=bind_authority(authority_path,authority_sha);tcl=render(c,work)
    plan={'Schema':PLAN_SCHEMA,'Target':prep.TARGET,'Request':{'Path':str(c['RequestPath']),'SHA256':sha(c['RequestPath'])},
        'Authority':c['Authority'],
        'WorkDirectory':str(work),'CandidateADFSHA256':c['CandidateSHA256'],'MaximumSeconds':maximum,
        'InputSHA256':{str(p):h for p,h in c['Watched'].items()},'ExpectedActualStages':STAGES,
        'TclSHA256':prep.baseline.paths.sha_bytes(tcl.encode('ascii')),
        'Command':[c['Build']['PDS']['Executable'],'-file',(work/'bitstream.tcl').as_posix(),'-work_dir',work.as_posix(),'-project_name',prep.TARGET],
        'HardwareAccessed':False,'HardwareReleaseAllowed':False,'ExternalACTimingAccepted':False,'DiagnosticOnly':True,
        'BitstreamRequested':True,'EDAExecutedByPreparer':False}
    return plan,tcl,c


def prepare(authority_path,authority_sha,work,maximum=900):
    plan,tcl,c=recipe(authority_path,authority_sha,work,maximum);work=Path(plan['WorkDirectory'])
    require(not work.exists(),'fresh bit stage required');work.mkdir()
    shutil.copyfile(c['Candidate'],work/'audited-final.adf');shutil.copyfile(SELF,work/'tool-snapshot.py')
    (work/'bitstream.tcl').write_text(tcl,encoding='ascii',newline='\n')
    plan['PreparedUTC']=inspect.utc();inspect.diagnostic.write(work/'bitstream-plan.json',plan)
    return plan


def validate(work):
    work=prep.work_path(work);plan=read(work/'bitstream-plan.json')
    require(plan.get('Schema')==PLAN_SCHEMA and plan.get('Target')==prep.TARGET,'720p bit plan identity differs')
    expected,tcl,c=recipe(plan['Authority']['Path'],plan['Authority']['SHA256'],work,plan['MaximumSeconds'])
    require(set(plan)==set(expected)|{'PreparedUTC'} and {k:v for k,v in plan.items() if k!='PreparedUTC'}==expected,'720p bit plan recipe drift')
    require((work/'bitstream.tcl').read_bytes()==tcl.encode('ascii') and sha(work/'audited-final.adf')==c['CandidateSHA256']
            and sha(work/'tool-snapshot.py')==sha(SELF),'720p bit prepared artifact drift')
    return plan,c


def compare_native(c,report,exceptions):
    require(passed_tables(report)==passed_tables(c['FinalReport']),'fresh timing summary/clock identities differ')
    normalize=lambda d:{k:Counter(json.dumps(r,sort_keys=True) for r in v) for k,v in d.items()}
    require(normalize(false_paths(exceptions))==normalize(false_paths(c['FinalExceptions'])),'fresh false-path identities differ')
    require(timing.exceptions(exceptions,set())==timing.exceptions(c['FinalExceptions'],set()),'fresh non-false exception paths differ')
    return {'AllTenTimingTablesPassed':True,'ClockAndSummaryIdentityPreserved':True,'AllExceptionPathsPreserved':True}


def gate(work):
    plan,c=validate(work);work=Path(work)
    before={n:sha(work/n) for n in ('bitstream-plan.json','audited-final.adf','bitstream.tcl',REPORT,EXCEPTIONS)}
    checks=compare_native(c,work/REPORT,work/EXCEPTIONS);validate(work)
    require(before=={n:sha(work/n) for n in before},'fresh STA artifacts changed during gate')
    result={'Schema':'camera720-pre-bit-gate-v1','GatePassed':True,'Target':prep.TARGET,
        'CandidateADFSHA256':c['CandidateSHA256'],'CheckedUTC':inspect.utc(),**checks,
        'EvidenceSHA256':before}
    inspect.diagnostic.write(work/'pre-bit-audit.json',result);return result


def events(text,digest):
    result=[];marker='CAMERA720_GATE_PASS '+digest
    for line in text.splitlines():
        line=line.strip();m=re.fullmatch(r'Process "([^"]+)" (started|done)\.',line)
        if m:result.append(m.groups())
        elif line.startswith('CAMERA720_GATE_PASS'):
            require(line==marker,'wrong 720p gate marker');result.append(('Runtime gate','passed'))
        elif line==COMPLETE:result.append(('Bitstream','complete'))
    expected=[('Report Timing','started'),('Report Timing','done'),('Runtime gate','passed'),
              ('Generate Bitstream','started'),('Generate Bitstream','done'),('Bitstream','complete')]
    require(result==expected,'fresh STA, CPU gate, bit generation order differs');return result


def bit_header(data):
    prefix=bytes.fromhex('00090ff00ff00ff00ff000')+b'PANGO MICROSYSTEMS, INC.\0\1'
    require(data.startswith(prefix),'invalid native bit prefix');offset=len(prefix);values={}
    for tag,name in zip(b'abcdef',('Design','Device','Date','Time','Generator','Version')):
        require(offset+3<=len(data) and data[offset]==tag,'missing bit header field')
        size=int.from_bytes(data[offset+1:offset+3],'big');raw=data[offset+3:offset+3+size]
        require(size>0 and len(raw)==size and raw[-1:]==b'\0' and b'\0' not in raw[:-1],'invalid bit header text')
        values[name]=raw[:-1].decode('ascii');offset+=3+size
    require(data[offset:offset+3]==b'ghi' and len(data)>1000000,'truncated native programming payload')
    for k,v in {'Design':prep.TARGET,'Device':'Logos2-PG2L100H--6-FBG676','Generator':'Fabric Compiler','Version':'2023.2-SP3<154097>'}.items():
        require(values[k]==v,'720p bit identity differs: '+k)
    return values


def verify(work):
    plan,c=validate(work);work=Path(work);receipt=read(work/'execution-result.json')
    require(receipt.get('Schema')==EXEC_SCHEMA and receipt.get('Target')==prep.TARGET
            and receipt.get('PlanSHA256')==sha(work/'bitstream-plan.json') and receipt.get('ExecutorSHA256')==sha(SELF)
            and receipt.get('Authority')==plan['Authority'] and receipt.get('EDAExecuted') is True
            and receipt.get('HardwareAccessed') is False and receipt.get('ExitCode')==0 and receipt.get('InputDrift')==[]
            and receipt.get('Diagnostics')==[] and not receipt.get('Error') and receipt.get('TimedOut') is False
            and receipt.get('StoppedForUnexpectedStage') is False and receipt.get('Command')==plan['Command']
            and receipt.get('CandidateADFSHA256')==c['CandidateSHA256'] and receipt.get('Cleanup',{}).get('Complete') is True,'unclean 720p bit execution')
    needed={'stdout.log','stderr.log',REPORT,EXCEPTIONS,BIT,'bitstream.tcl','generate_bitstream/'+prep.TARGET+'.bgr'}
    require(isinstance(receipt.get('Artifacts'),dict) and needed<=set(receipt['Artifacts']),'complete bit artifact inventory required')
    receipt_sha=sha(work/'execution-result.json')
    for n,h in receipt['Artifacts'].items():require(sha(inspect.canonical(work/n,work))==h,'native bit artifact drift')
    text=(work/'stdout.log').read_text(encoding='gb18030');actual=events(text,c['CandidateSHA256'])
    proof_sha=sha(work/'pre-bit-audit.json')
    checks=compare_native(c,work/REPORT,work/EXCEPTIONS);proof=read(work/'pre-bit-audit.json')
    require(proof.get('Schema')=='camera720-pre-bit-gate-v1' and proof.get('Target')==prep.TARGET
            and proof.get('GatePassed') is True and proof.get('CandidateADFSHA256')==c['CandidateSHA256']
            and all(proof.get(k)==v for k,v in checks.items()),'pre-bit runtime gate differs')
    require(proof['EvidenceSHA256']=={n:sha(work/n) for n in ('bitstream-plan.json','audited-final.adf','bitstream.tcl',REPORT,EXCEPTIONS)},'pre-bit evidence drift')
    commands=[s for s in re.findall(r'(?m)^Executing : (gen_bit_stream .+)$',text) if not s.endswith(' successfully.')]
    require(len(commands)==1 and '-input_db_file '+(work/'audited-final.adf').as_posix() in commands[0],'bit generation input differs')
    bgr=work/'generate_bitstream'/(prep.TARGET+'.bgr')
    require('Generating Programming File done.' in bgr.read_text(encoding='gb18030'),'programming report not complete')
    data=(work/BIT).read_bytes();header=bit_header(data);validate(work)
    require(sha(work/'execution-result.json')==receipt_sha and sha(work/'pre-bit-audit.json')==proof_sha,
            'execution receipt/runtime gate drift during verification')
    for n,h in receipt['Artifacts'].items():require(sha(inspect.canonical(work/n,work))==h,'native bit artifact drift during verification')
    return {'Schema':'camera720-bitstream-verification-v1','Verified':True,'Target':prep.TARGET,'CheckedUTC':inspect.utc(),
        'CandidateADFSHA256':c['CandidateSHA256'],'NativeTiming':checks,'ActualEvents':actual,
        'Bitstream':{'Path':str(work/BIT),'SHA256':sha(work/BIT),'Bytes':len(data),'Header':header},
        'EvidenceSHA256':{n:sha(work/n) for n in ('bitstream-plan.json','pre-bit-audit.json','execution-result.json','stdout.log','stderr.log',REPORT,EXCEPTIONS,BIT)},
        'VerifierSHA256':sha(SELF),'HardwareAccessed':False,'HardwareReleaseAllowed':False,'ExternalACTimingAccepted':False,'DiagnosticOnly':True}


def execute(work):
    plan,c=validate(work);work=Path(work);require(os.name=='nt','native 720p bit execution requires Windows')
    require({p.name for p in work.iterdir()}=={'audited-final.adf','tool-snapshot.py','bitstream.tcl','bitstream-plan.json'},'fresh prepared bit directory required')
    watched=c['Watched'];watched.update({p:sha(p) for p in work.iterdir()})
    result={'Schema':EXEC_SCHEMA,'StartedUTC':inspect.utc(),'Target':prep.TARGET,'Command':plan['Command'],
        'PlanSHA256':sha(work/'bitstream-plan.json'),'ExecutorSHA256':sha(SELF),'Authority':plan['Authority'],
        'CandidateADFSHA256':c['CandidateSHA256'],'MaximumSeconds':plan['MaximumSeconds'],'HardwareAccessed':False,
        'TimedOut':False,'StoppedForUnexpectedStage':False,'ExitCode':None,'EDAExecuted':False}
    inspect.diagnostic.write(work/'execution-start.json',result);process=None;started=time.monotonic()
    expected=[(s,e) for s in STAGES for e in ('started','done')]
    try:
        with (work/'stdout.log').open('xb') as out,(work/'stderr.log').open('xb') as err:
            process=subprocess.Popen(plan['Command'],cwd=work,stdout=out,stderr=err,shell=False,
                                     creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            result.update(EDAExecuted=True,OwnedPID=process.pid)
            while process.poll() is None:
                remaining=plan['MaximumSeconds']-(time.monotonic()-started)
                if remaining<=0:result['TimedOut']=True;break
                try:process.wait(timeout=min(3,remaining))
                except subprocess.TimeoutExpired:pass
                current=inspect.diagnostic.stage_events((work/'stdout.log').read_text(encoding='gb18030',errors='replace'))
                if current!=expected[:len(current)]:result['StoppedForUnexpectedStage']=True;break
    except BaseException as error:result['Error']=type(error).__name__+': '+str(error)
    finally:
        if process is not None:
            if process.poll() is None:result['Cleanup']=inspect.diagnostic.cleanup.stop_owned_tree(process,work,'bounded 720p bit')
            else:result['Cleanup']={'Complete':True,'OwnedPID':process.pid,'ParentExited':True,'DescendantLivenessIndependentlyVerified':False}
            result['ExitCode']=process.poll()
        else:result['Cleanup']={'Complete':True,'Required':False}
    diagnostics=[]
    for p in work.rglob('*.log'):
        diagnostics += [p.relative_to(work).as_posix()+': '+line.strip() for line in re.findall(
            r'(?m)^\s*(?:E:|F:|ERROR:|FATAL:|Traceback).*$',p.read_text(encoding='gb18030',errors='replace'))]
    result.update(FinishedUTC=inspect.utc(),ElapsedSeconds=round(time.monotonic()-started,3),InputDrift=inspect.drift(watched),
        Diagnostics=diagnostics,Artifacts={p.relative_to(work).as_posix():sha(p) for p in work.rglob('*') if p.is_file()
        and p.suffix in ('.log','.rtr','.sbit','.bgr','.tcl')})
    inspect.diagnostic.write(work/'execution-result.json',result)
    verification=verify(work);inspect.diagnostic.write(work/'verification.json',verification);return verification


def main():
    p=argparse.ArgumentParser(description=__doc__);m=p.add_mutually_exclusive_group(required=True)
    for name in ('prepare','validate','execute','gate','verify'):m.add_argument('--'+name,type=Path)
    m.add_argument('--audit-request',type=Path)
    p.add_argument('--authority-output',type=Path);p.add_argument('--authority',type=Path);p.add_argument('--authority-sha256')
    p.add_argument('--reviewed-effect-sha256');p.add_argument('--reviewed-cdc-sha256');p.add_argument('--reviewed-io-sha256')
    p.add_argument('--maximum-seconds',type=int,default=900);a=p.parse_args()
    if a.audit_request:
        require(a.authority_output is not None,'fresh authority output required')
        reviewed={name:value for name,value in (('ResetEffectAudit',a.reviewed_effect_sha256),
            ('FinalCDCProof',a.reviewed_cdc_sha256),('FinalIOProof',a.reviewed_io_sha256)) if value is not None}
        r=prepare_authority(a.audit_request,a.authority_output,reviewed or None)
        print(json.dumps({'FullVerificationCompleted':True,'PriorFullAuditsReused':r['PriorFullAuditsReused'],
            'Authority':binding(a.authority_output),'BoundInputs':len(r['InputSHA256']),'EDAExecuted':False}))
    elif a.prepare:
        require(a.authority is not None and a.authority_sha256 is not None,'explicit completed authority and SHA required')
        r=prepare(a.authority,a.authority_sha256,a.prepare,a.maximum_seconds)
        print(json.dumps({'Prepared':True,'Command':r['Command'],'EDAExecuted':False}))
    elif a.gate:
        r=gate(a.gate);print('CAMERA720_GATE_PASS '+r['CandidateADFSHA256'])
    elif a.validate:
        r,_=validate(a.validate);print(json.dumps({'Validated':True,'Target':prep.TARGET,'EDAExecuted':False}))
    else:
        r=execute(a.execute) if a.execute else verify(a.verify)
        print(json.dumps({'Verified':r['Verified'],'Bitstream':r['Bitstream']}))


if __name__=='__main__':main()
