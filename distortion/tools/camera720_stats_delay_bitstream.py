"""Current720 calibrated statistics development bit generation; never programs hardware.

The first authority audit recomputes reset, CDC/IO and compile disposition.
Later boundaries bind its explicit hash and rehash the complete closure.
"""
import argparse
import hashlib
from collections import Counter
import importlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time

import camera720_stats_delay_inspect as inspect
import audit_camera_vga_physical as timing

prep = inspect.prep
require, sha = inspect.require, inspect.sha
SELF = Path(__file__).resolve()
PYTHON = prep.PROJECT.parent/'.venv/Scripts/python.exe'
REQUEST_SCHEMA = 'camera720-calibrated-stats-delay-bitstream-request-v1'
AUTHORITY_SCHEMA = 'camera720-calibrated-stats-delay-bitstream-authority-v1'
PLAN_SCHEMA = 'camera720-calibrated-stats-delay-bitstream-plan-v1'
EXEC_SCHEMA = 'camera720-calibrated-stats-delay-bitstream-execution-v1'
COMPLETE = 'CAMERA720_CALIBRATED_STATS_DELAY_BITSTREAM_COMPLETE'
STAGES = ['Report Timing', 'Generate Bitstream']
REPORT = 'report_timing/'+prep.TARGET+'.rtr'
EXCEPTIONS = 'report_timing/'+prep.TARGET+'_exception.rtr'
BIT = 'generate_bitstream/'+prep.TARGET+'.sbit'
REQUEST_FIELDS = {'Schema','Target','BuildPlan','CandidateADF','FinalInspectionReceipt',
                  'ResetApplicationReceipt','ResetEffectAudit','FinalCDCProof','BuildDiagnosticsDisposition','SystemSimulation','StatisticsSimulation','ControlDelaySimulation','MonitorSimulation'}



def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


STATS_SIM_SHA = '08e9e271945d2054cf6ec3c10d1342a3a824a85eb160c6b3fcd4fef1ea7e1af5'


def statistics_binding(path, buildpath, watched):
    require(sha(path) == STATS_SIM_SHA, 'exact completed statistics UART wire simulation required')
    value = read(path)
    require(value.get('Schema') == 'camera720-core-stats-digital-simulation-v1'
            and value.get('Passed') is True and value.get('SourceDrift') == []
            and value.get('Summary', {}).get('Passed') is True,
            'statistics simulation incomplete or source changed')
    for name, digest in value['SourceSHA256'].items():
        add(watched, prep.PROJECT/name, digest)
    for name, digest in value['EvidenceSHA256'].items():
        add(watched, path.parent/name, digest)
    for name in (prep.source.STATS, prep.source.UART):
        add(watched, buildpath.parent/'source'/name, value['SourceSHA256'][name])
    frozen = prep.source.verify(Path(read(buildpath)['SourcePreparation']['Path']))
    merge(watched, frozen['InputSHA256'])
    merge(watched, frozen['OutputSHA256'])
    require(frozen['BuildIdentitySHA256'] == read(buildpath)['BuildIdentitySHA256'],
            'statistics source identity differs from build')


CONTROL_DELAY_SIM_SHA = '3e7b1ea7e7b9a01fe4b10b8f6a21eb48ad410510d9486601b88c10bb089475ce'
MONITOR_SIM_SHA = '459222f14e8e42d43959518a9e2575fb571a1ebe125a0b28e206a571dacd3860'


def control_delay_binding(path, buildpath, watched):
    require(sha(path) == CONTROL_DELAY_SIM_SHA, 'exact completed control/data delay simulation required')
    value = read(path)
    require(value.get('Schema') == 'camera720-stats-shared-control-data-delay-simulation-v1'
            and value.get('Target') == prep.TARGET and value.get('SimulationExecuted') is True
            and value.get('Passed') is True and value.get('InputDrift') == []
            and value.get('Lanes') == 10 and value.get('NominalDelayPS') == 1500,
            'control/data delay simulation incomplete or source drift')
    observed = value['Observed']
    require(observed.get('ObservedTuples') == 1024 and observed.get('TupleChecks') == 3072
            and observed.get('SamplingChecks') == 32
            and observed.get('RelativeControlDataDelayUnchangedInModel') is True
            and observed.get('ExtraPixelClockCycleObserved') is False
            and observed.get('MonitorMatchesDelayedCaptureInModel') is True
            and value.get('TopWiring', {}).get('MonitorAfterControlDelay') is True
            and value.get('TopWiring', {}).get('RawMonitorPathPreserved') is False
            and value.get('TopWiring', {}).get('MonitorSamplePhaseShiftPS') == 1500,
            'capture and shared delayed monitor observation incomplete')
    merge(watched, value['InputSHA256'])
    require({'transitions.csv', 'sampling.csv', 'summary.json', 'simulation.log'} <= set(value['EvidenceSHA256']),
            'complete observed delay simulation artifacts required')
    for name, digest in value['EvidenceSHA256'].items():
        add(watched, path.parent/name, digest)
    top = buildpath.parent/'source'/inspect.TOP
    require(value.get('GeneratedTop', {}).get('SHA256') == sha(top),
            'delay simulation top wiring differs from actual build')
    add(watched, top, value['GeneratedTop']['SHA256'])
    for name in ('rtl/experimental/raw_camera_input_delay.v', prep.source.CONTROL_DELAY):
        source = prep.PROJECT/name
        require(value['InputSHA256'].get(str(source)) == sha(source), 'delay source missing from actual simulation')
        add(watched, buildpath.parent/'source'/name, sha(source))


def monitor_binding(path, buildpath, watched):
    require(sha(path) == MONITOR_SIM_SHA, 'exact completed shared monitor simulation required')
    value = read(path)
    require(value.get('Schema') == 'camera720-stats-shared-control-monitor-simulation-v1'
            and value.get('Target') == prep.TARGET and value.get('Passed') is True
            and value.get('SimulationExecuted') is True and value.get('InputDrift') == []
            and value.get('Geometry') == [2560, 720]
            and value.get('PCLKModelHz') == [42000000, 47250000]
            and value.get('MonitorAfterControlDelay') is True
            and value.get('RawMonitorPathPreserved') is False
            and value.get('MonitorSamplePhaseShiftPS') == 1500,
            'full-size shared monitor regression incomplete or wrong configuration')
    merge(watched, value['InputSHA256'])
    for name, digest in value['EvidenceSHA256'].items():
        add(watched, path.parent/name, digest)
    runner = module('run_camera720_stats_shared_monitor_sim')
    require(value['InputSHA256'].get(str(Path(runner.__file__).resolve())) == sha(runner.__file__),
            'monitor observation validator differs from actual simulation')
    require([case['Name'] for case in value['Cases']] == [case[0] for case in runner.CASES],
            'all four distinct monitor scenarios required')
    for observed, (name, half, bad, _) in zip(value['Cases'], runner.CASES):
        require(observed.get('Passed') is True and observed.get('Log') == name+'.log'
                and observed.get('SummaryFile') == name+'-summary.json', 'monitor case artifact identity differs')
        log = path.parent/observed['Log']; summary = path.parent/observed['SummaryFile']
        for artifact in (log, summary):
            require(value['EvidenceSHA256'].get(artifact.name) == sha(artifact), 'monitor case evidence missing')
        require(read(summary) == observed['Summary'], 'monitor case summary differs from actual artifact')
        runner.observations(log.read_text(encoding='utf-8', errors='replace'), read(summary), half, bad)
    top = buildpath.parent/'source'/inspect.TOP
    require(value.get('GeneratedTop', {}).get('SHA256') == sha(top), 'monitor simulation uses another top')
    require(runner.delay.top_wiring(top) == value['TopWiring'], 'actual top/monitor wiring differs')
    add(watched, top, value['GeneratedTop']['SHA256'])
    for name in (*runner.SOURCES[:-1], runner.HEADERS[0]):
        source = prep.PROJECT/name
        require(value['InputSHA256'].get(str(source)) == sha(source), 'monitor RTL missing from actual simulation')
        add(watched, buildpath.parent/'source'/name, sha(source))


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def digest(value):
    return isinstance(value,str) and re.fullmatch('[0-9a-f]{64}',value) is not None


def add(watched,path,expected=None):
    path=Path(path).absolute()
    require(path==path.resolve() and path.is_file() and
            (path.is_relative_to(prep.PROJECT.parent) or path in watched), 'unbound external input')
    actual=sha(path)
    require(expected is None or digest(expected) and actual==expected, 'artifact SHA differs: '+str(path))
    require(path not in watched or watched[path]==actual,'conflicting artifact SHA')
    watched[path]=actual
    return path


def merge(watched,other):
    for name,h in other.items():
        p=Path(name).absolute()
        require(p==p.resolve() and p.is_file() and digest(h) and sha(p)==h,'verified closure drift')
        require(p not in watched or watched[p]==h,'conflicting verified input')
        watched[p]=h


def binding(path):
    path=Path(path).absolute()
    return {'Path':str(path),'SHA256':sha(path)}


def ref(value,watched):
    require(isinstance(value,dict) and set(value)=={'Path','SHA256'} and digest(value['SHA256']),
            'exact Path/SHA256 reference required')
    return add(watched,value['Path'],value['SHA256'])


def module(name):
    path=prep.PROJECT/'tools'/(name+'.py')
    require(path.is_file(),'current calibrated verifier unavailable: '+name)
    value=importlib.import_module(name)
    require(Path(value.__file__).resolve()==path.resolve(),'verifier location differs')
    return value


def same_saved(actual,claimed):
    clean=lambda d:json.loads(json.dumps({k:v for k,v in d.items() if k not in ('CreatedUTC','InputSHA256')}))
    require(clean(actual)==clean(claimed),'recomputed evidence differs from saved audit')


def passed_tables(report):
    tables,clocks=timing.summaries(report)
    require(set(tables)=={(c,k) for c in ('slow','fast') for k in ('setup','hold','recovery','removal','mpw')}
            and all(tables.values()) and clocks,'all ten native tables and clocks required')
    require(all(r['FailingChecks']==0 and r['WorstSlackNS']>=0 and r['TotalNegativeSlackNS']==0
                for rows in tables.values() for r in rows.values()),'all ten timing tables must pass')
    return tables,clocks


def false_paths(path):
    with Path(path).open(encoding='gb18030') as stream:
        return timing.native.parse_false_paths(stream)



SIM_SHA = 'e0f38ae39f43a5088896c9cd34dbeaa486c92297835259852abda8885814d76c'
DIAGNOSTICS_SHA = 'c4f96be5747a9bda5948720b0f6f720c6e5432625a4a314e6db5c3a27d5e1406'
HEADER_SHA = '01c797c6f5e327dae6977c8738ea472551f2f715b415784eaa52ffd2019b9e4a'


def simulation_binding(path,buildpath,watched):
    require(sha(path)==SIM_SHA,'exact completed current-lens system simulation required')
    value=read(path)
    require(value['Passed'] is True and value['SimulationExecuted'] is True
            and value['RTLResultUsedForGolden'] is False and value['ActualScanPixelsCompared']==1843200,
            'complete independent two-frame scan comparison required')
    require(value['InputSHA256']==value['InputSHA256After'] and value['FixtureSHA256']==value['FixtureSHA256After'],
            'simulation input/fixture drift')
    merge(watched,value['InputSHA256'])
    for group in ('FixtureSHA256','LogSHA256','ResultSHA256'):
        for name,h in value[group].items():add(watched,path.parent/name,h)
    header=buildpath.parent/'source/board/camera720-current-lens.vh'
    add(watched,header,HEADER_SHA)
    require(value['FixtureSHA256']['config.vh']==sha(header),'simulation used other coefficients')
    require(len(value['Frames'])==len(value['ActualScanChecks'])==2,'exactly two corrected frame records required')
    for frame,scan in zip(value['Frames'],value['ActualScanChecks']):
        require(frame['SourceCRC32']!=frame['CorrectedCRC32'] and scan['ActualScanCRC32']==frame['CorrectedCRC32']
                and scan['Pixels']==921600,'corrected data/scan CRC evidence differs')


def diagnostics_binding(path,buildpath,watched):
    require(sha(path)==DIAGNOSTICS_SHA,'exact reviewed current-build width diagnostics required')
    value=read(path);merge(watched,value['InputSHA256'])
    require(value['Target']==prep.TARGET and value['BuildPlan']['SHA256']==sha(buildpath)
            and Path(value['BuildPlan']['Path'])==buildpath,'diagnostics refer to another build')
    require(value['PublicCounterBoundsReviewed'] is True and value['VendorSameConfigurationProvenanceReviewed'] is True
            and value['ExactDiagnosticsExplainedForReadOnlyInvestigation'] is True
            and value['OriginalReceiptModified'] is False and value['SynthesisEquivalenceProved'] is False,
            'width diagnostic disposition incomplete')
    # This development-only provider explicitly accepts the reviewed, bounded
    # counter reductions plus same-configuration vendor provenance. It does not
    # modify the failed original receipt or claim vendor equivalence proof.
    require(value['DiagnosticsSummary']['RecordedCount']==52 and value['DiagnosticsSummary']['EventsPerLog']==13,
            'unexpected diagnostics cannot use the bounded development disposition')


def cdc_flags(value,candidate,export_ref):
    require(value.get('Schema')=='camera720-calibrated-stats-delay-cdc-proof-v1' and value.get('Target')==prep.TARGET
            and value.get('CandidateADFSHA256')==candidate and value.get('ExportReceipt')==export_ref,
            'CDC proof belongs to another current calibrated export')
    require(value.get('ScopedDigitalChecksPassed') is True and value.get('Missing')==[]
            and value.get('Violations')==[],'current calibrated CDC evidence incomplete')
    require(type(value.get('ExpectedCases')) is int and value['ExpectedCases']>0
            and value.get('ObservedCases')==value['ExpectedCases'],'CDC complete expected/observed inventory required')
    pins=value.get('Pins',{})
    require(pins.get('TopPortCount')==129 and pins.get('CAM2Pins')==14
            and pins.get('DDRMemoryPins')==71,'exact final current calibrated pin inventory required')
    for key in ('DeclarationAndSourceBuildMappingPassed','FinalFunctionalPortConnectionsPassed',
                'FinalFunctionalPadSiteMappingPassed','FinalNativeSiteMappingPassed',
                'FinalNativeElectricalAttributesVerified'):
        require(pins.get(key) is True,'final IO evidence missing: '+key)
    electrical=value.get('NativeElectricalParameters',{})
    require(electrical.get('Passed') is True and electrical.get('Ports')==129,
            'native final electrical parameter coverage required')
    dvp=value.get('DVP',{})
    require(dvp.get('ReportedBudgetCoverageComplete') is True
            and dvp.get('ExpectedPortCornerKindCases')==40 and dvp.get('CoveredCases')==40
            and dvp.get('MissingCases')==[],'all conditional DVP port/corner/kind cases required')
    tx=value.get('TX',{})
    ports={*(f'{color}_out[{i}]' for color in 'rgb' for i in range(8)),
           'hs_out','vs_out','de_out','pix_clk'}
    expected={(port,corner,'max') for port in ports for corner in ('slow','fast')}
    actual={(row.get('Port'),row.get('Corner'),row.get('DelayType'))
            for row in tx.get('NativeMaximumPaths',[])}
    require(tx.get('Vendor49CommandsIdentical') is True and expected<=actual,
            'final native HDMI output path coverage required')
    domain = value.get('StatisticsDomain', {})
    require(type(domain.get('ActualStatisticsFFs')) is int and domain['ActualStatisticsFFs'] > 0
            and domain.get('Clock') == 'ddrphy_sysclk'
            and domain.get('AllStatisticsSequentialInputsSameCoreDomain') is True
            and domain.get('NoStatisticsFeedbackToVideoRegistersOrOtherPads') is True,
            'actual statistics clock and nonfeedback topology required')
    uart = value.get('UART', {})
    attributes = dict(LOC='C24', VCCIO='3.3', STANDARD='LVCMOS33', DRIVE='4', SLEW='SLOW')
    require(uart.get('Port') == 'uart_txd' and uart.get('Attributes') == attributes
            and uart.get('NativeElectricalParametersVerified') is True
            and uart.get('LaunchCoverageComplete') is True and uart.get('Missing') == []
            and uart.get('ExternalACAccepted') is False
            and uart.get('ReceiverSamplingBudgetSpecified') is False,
            'actual UART pad/electrical evidence required without invented external timing')
    launches = uart.get('ActualNativeLaunches', [])
    require(isinstance(launches, list) and launches and len(set(launches)) == len(launches)
            and all(isinstance(n, str) and n.startswith('core_statistics/') and n.endswith('/CLK') for n in launches),
            'actual statistics UART launch identities required')
    expected_uart = {(n, corner) for n in launches for corner in ('slow', 'fast')}
    rows = uart.get('NativeMaximumPaths', [])
    observed_uart = {(r.get('Source'), r.get('Corner')) for r in rows}
    require(observed_uart == expected_uart and len(rows) == len(expected_uart)
            and type(uart.get('ExpectedMaximumCases')) is int
            and uart['ExpectedMaximumCases'] == uart.get('ObservedMaximumCases') == len(expected_uart),
            'both corners for every UART launch required')


def control_delay_flags(value):
    delay = value.get('ControlInputDelay', {})
    require(delay.get('Schema') == 'camera720-shared-control-input-delay-v1'
            and delay.get('Passed') is True and delay.get('ExpectedControlSignals') == 2
            and delay.get('NativeDelayCells') == 10 and delay.get('ControlDelayCells') == 2
            and delay.get('DataDelayCells') == 8 and delay.get('NominalDelayPS') == 1500
            and delay.get('MonitorAfterControlDelay') is True
            and delay.get('AllControlConsumersDelayed') is True
            and delay.get('RawMonitorPathPreserved') is False,
            'actual ten-cell data/control delay graph required')


def final_provider(path):
    providers = {
        'camera720-calibrated-stats-delay-final-inspection-v1': 'camera720_stats_delay_final_inspect',
        'camera720-calibrated-stats-delay-repaired-final-inspection-v1': 'camera720_stats_delay_repaired_final_inspect',
    }
    schema = read(path).get('Schema')
    require(schema in providers, 'unsupported final native statistics inspection schema')
    return module(providers[schema])


def effect_provider(path, final_path):
    providers = {
        'camera720-calibrated-stats-delay-final-inspection-v1': (
            'camera720-calibrated-stats-delay-reset-effect-v1', 'camera720_stats_delay_reset_effect'),
        'camera720-calibrated-stats-delay-repaired-final-inspection-v1': (
            'camera720-calibrated-stats-delay-repaired-reset-effect-v1', 'camera720_stats_delay_repaired_reset_effect'),
    }
    schema = read(final_path).get('Schema')
    require(schema in providers and read(path).get('Schema') == providers[schema][0],
            'reset effect and final candidate lineage differ')
    return module(providers[schema][1])


def audit_authority(request_path):
    watched={};request_path=add(watched,inspect.canonical(request_path,prep.WORK));request=read(request_path)
    require(set(request)==REQUEST_FIELDS and request['Schema']==REQUEST_SCHEMA and request['Target']==prep.TARGET,
            'exact calibrated development bit request required')
    paths={k:ref(request[k],watched) for k in REQUEST_FIELDS-{'Schema','Target'}}
    build=read(paths['BuildPlan']);candidate=paths['CandidateADF'];candidate_sha=sha(candidate)
    require(build.get('Target')==prep.TARGET and build.get('VideoControlFeedbackAdded') is False and build.get('ExpectedLiteralPinCount') == 129,'current calibrated build required')
    effect=effect_provider(paths['ResetEffectAudit'], paths['FinalInspectionReceipt'])
    final=final_provider(paths['FinalInspectionReceipt'])
    actual,effect_inputs=effect.verify(paths['ResetEffectAudit']);merge(watched,effect_inputs)
    require(actual['ApplicationReceipt']==request['ResetApplicationReceipt']
            and actual['CandidateExportReceipt']==request['FinalInspectionReceipt']
            and actual['CandidateADFSHA256']==candidate_sha,'reset effect belongs to another final candidate')
    for key in ('AuditPassed','FunctionalGraphIdentical','AllFFPlacementsIdentical','RoutingUnchanged',
                'ExactResetExceptionUnionVerified','NoDataFalsePaths','DataTimingChecksPreserved','AllInternalChecksMet'):
        require(actual.get(key) is True,'reset effect incomplete: '+key)
    export,export_inputs=final.bind_receipt(paths['FinalInspectionReceipt']);merge(watched,export_inputs)
    require(export['Mode']=='export' and export['SourceADFSHA256']==candidate_sha and Path(export['SourceADF'])==candidate
            and export['BuildPlanSHA256']==sha(paths['BuildPlan']) and export['SourceReceipt']==request['ResetApplicationReceipt'],
            'final native export identity differs')
    report=paths['FinalInspectionReceipt'].parent/REPORT;exceptions=paths['FinalInspectionReceipt'].parent/EXCEPTIONS
    for p in (report,exceptions):
        require(export['Artifacts'].get(p.relative_to(paths['FinalInspectionReceipt'].parent).as_posix())==sha(p),'unbound final report')
        add(watched,p)
    passed_tables(report)
    require(all(not rows for (_,kind),rows in false_paths(exceptions).items() if kind in ('setup','hold')),'data false paths disallowed')
    cdc=module('camera720_stats_delay_cdc_proof');evidence,inputs=cdc.verify(paths['FinalCDCProof']);merge(watched,inputs)
    require(evidence['CandidateADFSHA256']==candidate_sha and evidence['ExportReceipt']==request['FinalInspectionReceipt']
            and evidence['ScopedDigitalChecksPassed'] is True and evidence['Missing']==[] and evidence['Violations']==[]
            and evidence['ExpectedCases']==evidence['ObservedCases'] and evidence['ExpectedCases']>0,'final CDC/IO evidence incomplete')
    cdc_flags(evidence,candidate_sha,request['FinalInspectionReceipt'])
    control_delay_flags(evidence)
    simulation_binding(paths['SystemSimulation'],paths['BuildPlan'],watched)
    statistics_binding(paths['StatisticsSimulation'],paths['BuildPlan'],watched)
    control_delay_binding(paths['ControlDelaySimulation'],paths['BuildPlan'],watched)
    monitor_binding(paths['MonitorSimulation'],paths['BuildPlan'],watched)
    diagnostics_binding(paths['BuildDiagnosticsDisposition'],paths['BuildPlan'],watched)
    for mod in (effect,final,cdc,timing,timing.native,timing.hold,inspect):add(watched,mod.__file__)
    for p in (SELF,PYTHON):add(watched,p)
    require(not inspect.drift(watched),'calibrated bit authority evidence drift')
    return {'Request':request,'RequestPath':request_path,'Build':build,'PlanPath':paths['BuildPlan'],
            'Candidate':candidate,'CandidateSHA256':candidate_sha,'FinalReport':report,'FinalExceptions':exceptions,'Watched':watched}


def prepare_authority(request_path,output):
    output=Path(output).absolute();require(output.parent==prep.WORK and not output.exists(),'fresh authority in calibrated work root required')
    c=audit_authority(request_path)
    result={'Schema':AUTHORITY_SCHEMA,'Target':prep.TARGET,'CreatedUTC':inspect.utc(),
        'ValidationMethod':{'Function':'camera720_stats_delay_bitstream.audit_authority','Path':str(SELF),'SHA256':sha(SELF)},
        'Request':binding(c['RequestPath']),'BuildPlan':binding(c['PlanPath']),'CandidateADF':binding(c['Candidate']),
        'FinalReport':binding(c['FinalReport']),'FinalExceptions':binding(c['FinalExceptions']),
        'FullVerificationCompleted':True,'EDAExecuted':False,'HardwareAccessed':False,'HardwareReleaseAllowed':False,
        'ExternalACTimingAccepted':False,'OpticalCorrectionAccepted':False,'DiagnosticOnly':True,
        'InputSHA256':{str(p):h for p,h in c['Watched'].items()}}
    result['ToolSHA256']={p:h for p,h in result['InputSHA256'].items() if Path(p).suffix.lower() in ('.py','.exe')}
    inspect.diagnostic.write(output,result);return result


def bind_authority(path,expected_sha):
    require(digest(expected_sha),'explicit completed authority SHA required')
    watched={};path=ref({'Path':str(Path(path).absolute()),'SHA256':expected_sha},watched);seed=read(path)
    require(seed.get('Schema')==AUTHORITY_SCHEMA and seed.get('Target')==prep.TARGET
            and seed.get('FullVerificationCompleted') is True and seed.get('DiagnosticOnly') is True,
            'completed exact calibrated authority required')
    require(seed.get('ValidationMethod')=={'Function':'camera720_stats_delay_bitstream.audit_authority','Path':str(SELF),'SHA256':sha(SELF)},
            'authority validator changed')
    for key in ('EDAExecuted','HardwareAccessed','HardwareReleaseAllowed','ExternalACTimingAccepted','OpticalCorrectionAccepted'):
        require(seed.get(key) is False,'authority overclaims '+key)
    require(isinstance(seed.get('InputSHA256'),dict) and seed['InputSHA256'],'authority closure missing')
    merge(watched,seed['InputSHA256'])
    require(seed.get('ToolSHA256')=={p:h for p,h in seed['InputSHA256'].items() if Path(p).suffix.lower() in ('.py','.exe')},
            'authority tool closure differs')
    request_path=ref(seed['Request'],watched);request=read(request_path)
    require(set(request)==REQUEST_FIELDS and request['Schema']==REQUEST_SCHEMA and request['Target']==prep.TARGET,
            'sealed request differs')
    for k in REQUEST_FIELDS-{'Schema','Target'}:
        p=ref(request[k],watched);require(seed['InputSHA256'].get(str(p))==sha(p),'authority omitted '+k)
    require(seed['BuildPlan']==request['BuildPlan'] and seed['CandidateADF']==request['CandidateADF'],'authority/request identities differ')
    buildpath=ref(seed['BuildPlan'],watched);candidate=ref(seed['CandidateADF'],watched)
    report=ref(seed['FinalReport'],watched);exceptions=ref(seed['FinalExceptions'],watched)
    exportpath=Path(request['FinalInspectionReceipt']['Path']);export=read(exportpath)
    require(export['SourceADFSHA256']==sha(candidate) and export['SourceADF']==str(candidate)
            and export['BuildPlanSHA256']==sha(buildpath) and export['SourceReceipt']==request['ResetApplicationReceipt'],
            'sealed final export identity differs')
    for p,name in ((report,REPORT),(exceptions,EXCEPTIONS)):
        require(p==exportpath.parent/name and export['Artifacts'].get(name)==sha(p),'sealed report is not exact native artifact')
    for p in (request_path,buildpath,candidate,report,exceptions,SELF,PYTHON):
        require(seed['InputSHA256'].get(str(p))==sha(p),'required authority input missing')
    require(not inspect.drift(watched),'sealed authority drift')
    return {'Request':request,'RequestPath':request_path,'Build':read(buildpath),'PlanPath':buildpath,
            'Candidate':candidate,'CandidateSHA256':sha(candidate),'FinalReport':report,
            'FinalExceptions':exceptions,'Watched':watched,'Authority':binding(path)}


def render(context,work):
    base=context['PlanPath'].parent
    rendered=inspect.render('export',(base/'timing.tcl').read_text(encoding='ascii'),base,work)
    boundary='report_timing -force_to_run -input_db_file '
    require(rendered.count(boundary)==1,'one fresh native report context required')
    prefix=rendered[:rendered.index(boundary)];w=work.as_posix();marker='CAMERA720_CALIBRATED_STATS_DELAY_GATE_PASS '+context['CandidateSHA256']
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
        'TclSHA256':sha_bytes(tcl.encode('ascii')),
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
    require(inspect.scan_diagnostics(work)==[], 'critical/error diagnostics before bit generation')
    before={n:sha(work/n) for n in ('bitstream-plan.json','audited-final.adf','bitstream.tcl',REPORT,EXCEPTIONS)}
    checks=compare_native(c,work/REPORT,work/EXCEPTIONS);validate(work)
    require(before=={n:sha(work/n) for n in before},'fresh STA artifacts changed during gate')
    require(inspect.scan_diagnostics(work)==[], 'critical/error diagnostics appeared during gate')
    result={'Schema':'camera720-calibrated-stats-delay-pre-bit-gate-v1','GatePassed':True,'Target':prep.TARGET,
        'CandidateADFSHA256':c['CandidateSHA256'],'CheckedUTC':inspect.utc(),**checks,
        'EvidenceSHA256':before}
    inspect.diagnostic.write(work/'pre-bit-audit.json',result);return result


def events(text,digest):
    result=[];marker='CAMERA720_CALIBRATED_STATS_DELAY_GATE_PASS '+digest
    for line in text.splitlines():
        line=line.strip();m=re.fullmatch(r'Process "([^"]+)" (started|done)\.',line)
        if m:result.append(m.groups())
        elif line.startswith('CAMERA720_CALIBRATED_STATS_DELAY_GATE_PASS'):
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
    actual_artifacts={p.relative_to(work).as_posix() for p in work.rglob('*') if p.is_file()
                      and p.suffix in ('.log','.rtr','.sbit','.bgr','.tcl')}
    require(set(receipt['Artifacts'])==actual_artifacts,'native bit artifact inventory differs')
    require(inspect.scan_diagnostics(work)==[], 'actual bit logs contain critical/error diagnostics')
    receipt_sha=sha(work/'execution-result.json')
    for n,h in receipt['Artifacts'].items():require(sha(inspect.canonical(work/n,work))==h,'native bit artifact drift')
    text=(work/'stdout.log').read_text(encoding='gb18030');actual=events(text,c['CandidateSHA256'])
    proof_sha=sha(work/'pre-bit-audit.json')
    checks=compare_native(c,work/REPORT,work/EXCEPTIONS);proof=read(work/'pre-bit-audit.json')
    require(proof.get('Schema')=='camera720-calibrated-stats-delay-pre-bit-gate-v1' and proof.get('Target')==prep.TARGET
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
    require(inspect.scan_diagnostics(work)==[], 'critical/error diagnostic appeared during verification')
    return {'Schema':'camera720-calibrated-stats-delay-bitstream-verification-v1','Verified':True,'Target':prep.TARGET,'CheckedUTC':inspect.utc(),
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
            r'(?m)^\s*(?:C:|E:|F:|CRITICAL:|ERROR:|FATAL:|Traceback).*$',p.read_text(encoding='gb18030',errors='replace'))]
    result.update(FinishedUTC=inspect.utc(),ElapsedSeconds=round(time.monotonic()-started,3),InputDrift=inspect.drift(watched),
        Diagnostics=diagnostics,Artifacts={p.relative_to(work).as_posix():sha(p) for p in work.rglob('*') if p.is_file()
        and p.suffix in ('.log','.rtr','.sbit','.bgr','.tcl')})
    inspect.diagnostic.write(work/'execution-result.json',result)
    verification=verify(work);inspect.diagnostic.write(work/'verification.json',verification);return verification


def main():
    parser=argparse.ArgumentParser(description=__doc__);mode=parser.add_mutually_exclusive_group(required=True)
    for name in ('prepare','validate','execute','gate','verify','audit-request'):mode.add_argument('--'+name,type=Path)
    parser.add_argument('--authority-output',type=Path);parser.add_argument('--authority',type=Path)
    parser.add_argument('--authority-sha256');parser.add_argument('--maximum-seconds',type=int,default=900)
    a=parser.parse_args()
    if a.audit_request:
        require(a.authority_output is not None,'fresh authority output required')
        result=prepare_authority(a.audit_request,a.authority_output)
        print(json.dumps({'FullVerificationCompleted':True,'Authority':binding(a.authority_output),
                          'BoundInputs':len(result['InputSHA256']),'EDAExecuted':False}))
    elif a.prepare:
        require(a.authority and a.authority_sha256,'explicit completed authority SHA required')
        result=prepare(a.authority,a.authority_sha256,a.prepare,a.maximum_seconds)
        print(json.dumps({'Prepared':True,'Command':result['Command'],'EDAExecuted':False}))
    elif a.gate:
        result=gate(a.gate);print('CAMERA720_CALIBRATED_STATS_DELAY_GATE_PASS '+result['CandidateADFSHA256'])
    elif a.validate:
        validate(a.validate);print(json.dumps({'Validated':True,'Target':prep.TARGET,'EDAExecuted':False}))
    else:
        result=execute(a.execute) if a.execute else verify(a.verify)
        print(json.dumps({'Verified':result['Verified'],'Bitstream':result['Bitstream']}))


if __name__=='__main__':main()


