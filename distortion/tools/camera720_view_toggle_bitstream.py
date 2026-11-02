"""Fresh KEY1 candidate authority and bounded STA/gate/bit generation.

Only stable execution mechanics are reused in an isolated namespace. Current
reset, IO/CDC, build diagnostics and three-frame switching evidence must be
recomputed. Frozen baseline authority binds unchanged module simulations only.
"""
import argparse
from collections import Counter
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
import types

import numpy as np
import camera720_view_toggle_build as build
import camera720_view_toggle_final_inspect as final
import camera720_view_toggle_reset_effect as effect
import camera720_view_toggle_cdc_proof as cdc_proof
import camera720_view_toggle_diagnostics as disposition
import camera720_view_toggle_receipts as receipts
import camera720_stats_delay_bitstream as base
import run_camera720_view_toggle_sim as simulation
import audit_camera_vga_physical as timing

SELF = Path(__file__).resolve()
prep = types.SimpleNamespace(TARGET=build.TARGET,PROJECT=build.ROOT,WORK=build.WORK,work_path=build.work_path)
require, sha, read = build.require, build.sha, build.read
PYTHON = prep.PROJECT.parent/'.venv/Scripts/python.exe'
PREFIX = 'camera720-view-toggle'
REQUEST_SCHEMA,AUTHORITY_SCHEMA,PLAN_SCHEMA,EXEC_SCHEMA = (PREFIX+'-'+n+'-v1' for n in
    ('bitstream-request','bitstream-authority','bitstream-plan','bitstream-execution'))
COMPLETE = 'CAMERA720_VIEW_TOGGLE_BITSTREAM_COMPLETE'
GATE = 'CAMERA720_VIEW_TOGGLE_GATE_PASS'
STAGES = ['Report Timing','Generate Bitstream']
REPORT = 'report_timing/'+prep.TARGET+'.rtr'
EXCEPTIONS = 'report_timing/'+prep.TARGET+'_exception.rtr'
BIT = 'generate_bitstream/'+prep.TARGET+'.sbit'
REQUEST_FIELDS = {'Schema','Target','BuildPlan','CandidateADF','FinalInspectionReceipt',
    'ResetApplicationReceipt','ResetEffectAudit','FinalCDCProof','BuildDiagnosticsDisposition',
    'SystemSimulation','BaselineAuthority'}
inspect = types.SimpleNamespace(utc=final.utc, canonical=base.inspect.canonical, drift=receipts.drift,
    scan_diagnostics=final.diagnostics, diagnostic=types.SimpleNamespace(write=build.write,
    stage_events=base.inspect.diagnostic.stage_events,cleanup=build.cleanup))
BASE_AUTHORITY_SHA = '48923490de9592d22638216da3af03efa57b2e576de24f40979894ebe5d45ec2'


def clone_code(code):
    """Retarget exact emitted schema/marker constants; no source/evidence adaptation."""
    def constant(value):
        if isinstance(value,types.CodeType): return clone_code(value)
        if isinstance(value,str):
            return value.replace('camera720-calibrated-stats-delay','camera720-view-toggle').replace(
                'camera720_stats_delay_bitstream.audit_authority','camera720_view_toggle_bitstream.audit_authority').replace(
                'CAMERA720_CALIBRATED_STATS_DELAY','CAMERA720_VIEW_TOGGLE')
        return value
    return code.replace(co_consts=tuple(constant(v) for v in code.co_consts))


# Exact baseline code is hash-bound below. All dependencies resolve in this
# module; old modules/globals are immutable. Native command/deadline/cleanup,
# artifact inventory and before/after SHA checks stay the reviewed mechanics.
for _name in ('sha_bytes','digest','add','merge','binding','ref','module','same_saved','passed_tables',
              'prepare_authority','bind_authority','recipe','prepare','validate','gate','events',
              'bit_header','verify','execute','main','control_delay_flags'):
    _f=getattr(base,_name)
    globals()[_name]=types.FunctionType(clone_code(_f.__code__),globals(),_name,_f.__defaults__,_f.__closure__)


def simulation_binding(path, buildpath, watched):
    value=read(path)
    require(value.get('Schema')=='camera720-view-toggle-simulation-v1'
            and value.get('Passed') is True and value.get('SimulationExecuted') is True
            and value.get('RTLResultUsedForGolden') is False and not value.get('Error')
            and value.get('ModeSequence')==['corrected','raw','corrected']
            and value.get('SourceGeometry')==[1280,720], 'complete fresh view-switch simulation required')
    require(value['InputSHA256']==value['InputSHA256After']
            and value['FixtureSHA256']==value['FixtureSHA256After'], 'view-switch simulation drift')
    merge(watched,value['InputSHA256'])
    for group in ('FixtureSHA256','LogSHA256','ResultSHA256'):
        for name,h in value[group].items():add(watched,path.parent/name,h)
    require(value['InputSHA256'].get(str(Path(simulation.__file__).resolve()))==sha(simulation.__file__),
            'view-switch simulation validator differs')
    simulation.validate_summary(value['Summary'])
    require(value['ActualScanPixelsCompared']==value['Summary']['scanned_pixels']
            and value['ActualScanPixelsCompared']>=3*simulation.PIXELS, 'complete scan pixel coverage required')
    simulation.verify_compile_sources(simulation.ROOT,simulation.COMPILE,simulation.HEADERS,path.parent,value['CompileBindings'])
    for item in value['CompileBindings'].values():
        add(watched,item['CompiledPath'],item['CompiledSHA256'])
        for header in item['IncludePathReplacements']:
            add(watched,header['CompiledHeaderPath'],header['HeaderSHA256'])
    with tempfile.TemporaryDirectory(prefix='view-authority-oracle-') as temporary:
        oracle=Path(temporary)
        expected,records,model=simulation.fixtures(oracle,(path.parent/'config.vh').read_text(encoding='ascii'))
        require(records==value['Frames'] and model==value['Model'], 'independent view geometry/frame reference differs')
        require({p.name:sha(p) for p in oracle.iterdir() if p.is_file()}==value['FixtureSHA256'],
                'current independent fixture regeneration differs from simulation')
    require(simulation.validate_outputs(path.parent,expected,value['Frames'],value['Summary'])==value['ActualScanChecks'],
            'actual per-pixel scans differ from completed simulation receipt')
    compiled=Path(buildpath).parent/'compiled'
    for path_text,h in value['InputSHA256'].items():
        source=Path(path_text)
        if not source.is_relative_to(prep.PROJECT):continue
        relative=source.relative_to(prep.PROJECT)
        target=compiled/relative
        if target.is_file():
            # PDS preparation rewrites only include location literals.
            if relative.suffix=='.v':
                normalize=lambda data:re.sub(rb'(`include\s+")[^"\r\n]*?([^/\\"\r\n]+)(")',rb'\1\2\3',data)
                require(normalize(source.read_bytes())==normalize(target.read_bytes()), 'simulation/compiled RTL differs: '+str(relative))
            else:require(sha(target)==h, 'simulation/compiled header differs: '+str(relative))
            add(watched,target)
    require((compiled/'board/camera720-current-lens.vh').read_bytes()==(path.parent/'config.vh').read_bytes(),
            'view-switch simulation used another current-lens profile')


def baseline_binding(path, buildpath, watched):
    require(sha(path)==BASE_AUTHORITY_SHA, 'exact completed unchanged-module authority required')
    context=base.bind_authority(path,BASE_AUTHORITY_SHA)
    merge(watched,context['Watched'])
    old=Path(context['PlanPath']).parent/'compiled'
    new=Path(buildpath).parent/'compiled'
    excluded={'board/'+build.OLD+'.v','board/camera720-calibrated-stats-delay.fdc'}
    for source in old.rglob('*'):
        if not source.is_file():continue
        relative=source.relative_to(old).as_posix()
        if relative in excluded:continue
        target=new/relative
        require(target.is_file(), 'unchanged-module source missing: '+relative)
        normalize=lambda data,prefix:data.replace(prefix.as_posix().encode(),b'@COMPILED@')
        require(normalize(source.read_bytes(),old)==normalize(target.read_bytes(),new),
                'baseline simulation reuse source changed: '+relative)
        add(watched,target)
    for p in (Path(base.__file__),Path(simulation.__file__),Path(cdc_proof.__file__),
              Path(final.__file__),Path(receipts.__file__),Path(effect.__file__),Path(disposition.__file__)):
        add(watched,p)


def diagnostics_binding(path, buildpath, watched):
    saved=read(path)
    require(saved.get('Schema')==disposition.SCHEMA and saved.get('Target')==prep.TARGET
            and saved.get('BuildPlan')==binding(buildpath), 'diagnostic review uses another build')
    actual=disposition.inspect(buildpath)
    same_saved(actual,saved)
    merge(watched,actual['InputSHA256'])
    require(actual['ExactDiagnosticsEqualAfterBuildPathNormalization'] is True
            and actual['DiagnosticsSummary']['RecordedCount']==52
            and actual['PublicCounterBoundsReviewed'] is True
            and actual['VendorSameConfigurationProvenanceReviewed'] is True
            and actual['OriginalReceiptModified'] is False, 'exact current width disposition required')


def cdc_flags(value,candidate,export_ref):
    require(value.get('Schema')==cdc_proof.SCHEMA and value.get('Target')==prep.TARGET
            and value.get('CandidateADFSHA256')==candidate and value.get('ExportReceipt')==export_ref
            and value.get('ScopedDigitalChecksPassed') is True and value.get('Missing')==[]
            and value.get('Violations')==[] and type(value.get('ExpectedCases')) is int
            and value['ExpectedCases']>0 and value.get('ObservedCases')==value['ExpectedCases'],
            'complete final candidate CDC cases required')
    pins=value.get('Pins',{})
    require(pins.get('TopPortCount')==130 and pins.get('CAM2Pins')==14 and pins.get('DDRMemoryPins')==71,
            'all130 current candidate pins required')
    for key in ('DeclarationAndSourceBuildMappingPassed','FinalFunctionalPortConnectionsPassed',
                'FinalFunctionalPadSiteMappingPassed','FinalNativeSiteMappingPassed','FinalNativeElectricalAttributesVerified'):
        require(pins.get(key) is True,'final pin evidence incomplete: '+key)
    require(value['NativeElectricalParameters']['Passed'] is True
            and value['NativeElectricalParameters']['Ports']==130, 'full actual electrical coverage required')
    key=value['Key']
    require(key['Passed'] is True and key['RawPadOnlyFeedsFirstD'] is True
            and key['FirstOnlyFeedsSecondD'] is True, 'actual KEY1 synchronizer/fanout proof required')
    if key['Chain']['SameBLE']:
        direct=[row for row in value['SameBLESupplement']['DirectInternalRows']
                if (row['SourceFF'],row['DestinationFF'])==(key['First'],key['Second'])]
        require(len(direct)==1 and direct[0]['DirectQToD'] is True
                and direct[0]['SourceOnlyFeedsSecondStage'] is True
                and value['PhysicalSTABasis']['VendorPhysicalSequentialTimingModelReliedUpon'] is True
                and value['TimingSummary']['AllSummaryChecksPassed'] is True,
                'packed KEY1 interstage requires current native classification and full STA')
    require(value['DVP']['ReportedBudgetCoverageComplete'] is True and value['DVP']['CoveredCases']==40
            and value['DVP']['MissingCases']==[], 'all40 conditional DVP cases required')
    tx={(r['Port'],r['Corner'],r['DelayType']) for r in value['TX']['NativeMaximumPaths']}
    expected={(p,c,'max') for p in cdc_proof.adapter.native_io.tx.PORTS for c in ('slow','fast')}
    require(expected<=tx and value['TX']['Vendor49CommandsIdentical'] is True, 'all HDMI path maxima required')
    require(value['UART']['LaunchCoverageComplete'] is True and value['UART']['Missing']==[]
            and value['UART']['NativeElectricalParametersVerified'] is True, 'all current UART launches required')
    require(value['StatisticsDomain']['AllStatisticsSequentialInputsSameCoreDomain'] is True
            and value['StatisticsDomain']['NoStatisticsFeedbackToVideoRegistersOrOtherPads'] is True,
            'current statistics domain/nonfeedback proof required')


def audit_authority(request_path):
    watched={};request_path=add(watched,inspect.canonical(request_path,prep.WORK));request=read(request_path)
    require(set(request)==REQUEST_FIELDS and request['Schema']==REQUEST_SCHEMA and request['Target']==prep.TARGET,
            'exact current view-switch bit request required')
    paths={k:ref(request[k],watched) for k in REQUEST_FIELDS-{'Schema','Target'}}
    plan=build.validate(paths['BuildPlan']);candidate=paths['CandidateADF'];candidate_sha=sha(candidate)
    require(plan['ExpectedPins']==130 and plan['SensorOrClockChanged'] is False, 'current130-pin build required')
    actual,inputs=effect.verify(paths['ResetEffectAudit']);merge(watched,inputs)
    require(actual['ApplicationReceipt']==request['ResetApplicationReceipt']
            and actual['CandidateExportReceipt']==request['FinalInspectionReceipt']
            and actual['CandidateADFSHA256']==candidate_sha, 'reset effect candidate lineage differs')
    for flag in ('AuditPassed','FunctionalGraphIdentical','AllFFPlacementsIdentical','RoutingUnchanged',
        'ExactResetExceptionUnionVerified','NoNewDataFalsePaths','ExistingKEY1PadExceptionPreserved',
        'DataTimingChecksPreserved','AllInternalChecksMet'):
        require(actual.get(flag) is True,'final reset effect missing: '+flag)
    export,inputs=final.bind_receipt(paths['FinalInspectionReceipt']);merge(watched,inputs)
    require(export['Mode']=='export' and export['SourceADF']==str(candidate)
            and export['SourceADFSHA256']==candidate_sha and export['BuildPlanSHA256']==sha(paths['BuildPlan'])
            and export['SourceReceipt']==request['ResetApplicationReceipt'], 'final native export lineage differs')
    report=paths['FinalInspectionReceipt'].parent/REPORT;exceptions=paths['FinalInspectionReceipt'].parent/EXCEPTIONS
    for p in (report,exceptions):
        require(export['Artifacts'].get(p.relative_to(paths['FinalInspectionReceipt'].parent).as_posix())==sha(p),
                'final timing artifact not bound');add(watched,p)
    passed_tables(report)
    evidence,inputs=cdc_proof.verify(paths['FinalCDCProof']);merge(watched,inputs)
    cdc_flags(evidence,candidate_sha,request['FinalInspectionReceipt']);control_delay_flags(evidence)
    simulation_binding(paths['SystemSimulation'],paths['BuildPlan'],watched)
    baseline_binding(paths['BaselineAuthority'],paths['BuildPlan'],watched)
    diagnostics_binding(paths['BuildDiagnosticsDisposition'],paths['BuildPlan'],watched)
    for p in (SELF,PYTHON,Path(timing.__file__),Path(base.__file__)):add(watched,p)
    require(not inspect.drift(watched),'view-switch bit authority input drift')
    return {'Request':request,'RequestPath':request_path,'Build':plan,'PlanPath':paths['BuildPlan'],
        'Candidate':candidate,'CandidateSHA256':candidate_sha,'FinalReport':report,'FinalExceptions':exceptions,'Watched':watched}


def render(context,work):
    prefix=final.export_prefix(context['PlanPath']);w=work.as_posix()
    return (prefix+'report_timing -force_to_run -input_db_file {'+w+'/audited-final.adf} -delay_type min_max -max_path 1000 -nworst 4 -report_exception TRUE\n'
        'if {[info script] ne {}} {\n    set checked [exec {'+PYTHON.as_posix()+'} -B {'+SELF.as_posix()+'} --gate {'+w+'}]\n'
        '    puts $checked\n    if {[string first {'+GATE+' '+context['CandidateSHA256']+'} $checked] < 0} {error {Missing current pre-bit gate}}\n'
        '    gen_bit_stream -force_to_run -input_db_file {'+w+'/audited-final.adf} -scbv {High Voltage} -unused_io_status UNUSED\n'
        '    puts {'+COMPLETE+'}\n    flush stdout\n}\n')


def compare_native(context,report,exceptions):
    require(passed_tables(report)==passed_tables(context['FinalReport']), 'fresh timing summaries/clocks differ')
    normalize=lambda rows:{k:{g:Counter(json.dumps(r,sort_keys=True) for r in v) for g,v in groups.items()}
                           for k,groups in rows.items()}
    require(normalize(effect.false_paths(exceptions))==normalize(effect.false_paths(context['FinalExceptions'])),
            'fresh KEY1/reset exception paths differ')
    effect.semantics.nonfalse_equal(effect.semantics.exception_syntax.read_exceptions(exceptions),
                                   effect.semantics.exception_syntax.read_exceptions(context['FinalExceptions']))
    return {'AllTenTimingTablesPassed':True,'ClockAndSummaryIdentityPreserved':True,'AllExceptionPathsPreserved':True}


if __name__ == '__main__':
    main()
