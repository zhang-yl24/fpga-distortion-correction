"""Exact failed-build diagnostic disposition for controlled current720 raw capture.

The original C:Sdm-3003 receipt is immutable and remains a failed diagnostic
receipt. This separate engineering disposition admits its exact explained
optimization messages for a controlled SRAM raw-image experiment, conditional
on independent current reset, IO, CDC, timing and programming checks.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import re

import camera720_raw_vendor_basis as vendor

current, prep = vendor.current, vendor.prep
inspect, require, sha = current.inspect, current.require, current.sha
SELF = Path(__file__).resolve()
SCHEMA = 'camera720-current-raw-diagnostic-disposition-v1'
REVIEW = prep.PROJECT/'work/camera720-raw-build-a-diagnostics-review.json'
REVIEW_SHA = '67cd970a3537cb1b3b34824e788b55547ea0d3782f119d4fef7a097e9bd5a638'
BUILD = prep.WORK/'build-a'
BUILD_RECEIPT_SHA = 'e29939423d7550e58c87414e3011aabfcd81247fa69450161606c24ce5bb21d6'
BUILD_PLAN_SHA = '71a93883fb84660bb287f10efb70555bee8886c8d2b0239fa283c43d79fcb12b'
ORIGINAL_ADF_SHA = '799296ded7e2fd66969d4cfdf25a9a30e316c2d8ac9c520b659cb83576f8fed7'
VENDOR_LOG = vendor.VENDOR/'pnr/compile/run.log'
VENDOR_LOG_SHA = '8c21ca2889f8357e329e488c844f671efbcba7aa6d43332e9afc4b59c6a3943d'
PUBLIC = [('byte_count',2561,12),('line_count',721,10),('pclk_age',270000,19),
          ('vsync_age',2700000,22),('href_age',2700000,22),('frame_age',2700000,22),
          ('snapshot_age',270000,19),('snapshot_timer',26999,15),('startup_timer',27000000,25),
          ('watchdog',1349999,21),('watchdog',1349999,21),('column',1280,11),('row',720,10)]
PROTECTED = [('cnt',7,6,'ips2l_mcdq_dcp_buf_v1_2.vp',541),
             ('delay_cnt',4,2,'ips2l_ddrphy_data_slice_wrcal_v1_10.vp',614)]


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def parameter_blocks(text):
    blocks, name, values = {}, None, []
    for line in text.splitlines()+['']:
        match = re.fullmatch(r'I: Module instance \{([^}]+)\} parameter value:', line)
        if name is not None and (not line.startswith('    ') or match):
            require(name not in blocks, 'duplicated elaborated parameter block')
            blocks[name] = values
            name, values = None, []
        if match:
            name = match[1]
        elif name is not None:
            values.append(line.strip())
    return blocks


def ddr_parameters(text):
    result = {}
    for name, values in parameter_blocks(text).items():
        marker = '/u_ddr3_test_h'
        if marker in name:
            key = name.split(marker,1)[1]
            require(key not in result, 'ambiguous normalized DDR block')
            result[key] = values
    require(result, 'elaborated DDR parameters missing')
    return result


def validate_events(events, compile_lines, watched):
    require(len(events) == len(PUBLIC)+len(PROTECTED), 'diagnostic event inventory differs')
    rows = []
    for index, (symbol, maximum, bits) in enumerate(PUBLIC):
        event = events[index]
        require((event['Symbol'],event['ReachableMaximum'],event['ReducedBits']) == (symbol,maximum,bits)
                and event['ReachableMinimum'] == 0 and event['RTLBoundProved'] is True
                and event['FunctionalRiskFromThisReductionIdentified'] is False,
                'public counter identity or reviewed bound differs')
        require(maximum.bit_length() == event['RequiredBits'] == bits and
                event['ReducedUnsignedMaximum'] == (1 << bits)-1 and maximum < (1 << bits),
                'public fault or terminal sentinel does not fit reduced counter')
        rows.append({'Symbol':symbol,'ReachableMaximum':maximum,'ReducedBits':bits,
                     'InferredInstancePaths':event['InferredInstancePaths'],
                     'Reason':event['Reason'],'ProofKind':event['ProofKind']})
    for index, spec in enumerate(PROTECTED,len(PUBLIC)):
        event = events[index]
        actual = (event['Symbol'],event['DeclaredBits'],event['ReducedBits'],
                  Path(event['Source']['Path']).name,event['ReportedSourceLine'])
        require(actual == spec and event['RTLBoundProved'] is False
                and event['ReachableMaximum'] is None and event['EncryptedSource'] is True,
                'protected counter identity or claimed proof differs')
    for event in events:
        source = vendor.bind_file(watched,event['Source']['Path'],event['Source']['SHA256'])
        require(compile_lines[event['CompileLogLine']-1] == event['Text'], 'diagnostic is not actual compiler text')
        lines = source.read_text(encoding='utf-8-sig').splitlines()
        for excerpt in event.get('ProofExcerpts',[]):
            require(lines[excerpt['StartLine']-1:excerpt['EndLine']] == excerpt['Text'],
                    'reviewed RTL excerpt no longer matches compiled source')
        for entry in event['RemovedConstantZeroNodes']:
            require(compile_lines[entry['Line']-1] == entry['Text'] and
                    'stuck at constant 0.' in entry['Text'], 'compiler removed-zero evidence differs')
    return rows


def validate_diagnostic_copies(receipt, events):
    expected = Counter(e['Text'] for e in events)
    grouped = {}
    for text in receipt['Diagnostics']:
        require(': C: Sdm-3003:' in text, 'non-reviewed critical/error diagnostic present')
        name, body = text.split(': ',1)
        grouped.setdefault(name,[]).append(body)
    require(set(grouped) == {'compile/run.log','execution-stdout.log','flow.log','run.log'}
            and all(Counter(values) == expected for values in grouped.values()),
            'diagnostic log copies differ from the exact reviewed event multiset')
    require(receipt['ExecutionCompletedWithoutError'] is False and len(receipt['Diagnostics']) == 60,
            'original failed receipt status or diagnostic count differs')
    return {name:len(values) for name,values in sorted(grouped.items())}


def validate_original_vendor_zeros(text):
    """Compare actual primitive compiler high-bit removal, not protected transitions."""
    records = []
    pattern = re.compile(r'Removed register node (\S+) that is stuck at constant 0\.')
    for number,line in enumerate(text.splitlines(),1):
        match = pattern.search(line)
        if match and ('/mcdq_dcp_buf/cnt[' in match[1] or '/ddrphy_data_slice_wrcal/delay_cnt[' in match[1]):
            records.append({'Line':number,'Text':line,'Node':match[1]})
    expected = {'I_ips_ddr_top/u_ips_ddrc_top/mcdq_dcp_top/mcdq_dcp_buf/cnt[6]'}
    expected.update('I_ips_ddr_top/u_ddrphy_top/ddrphy_slice_top/i_dqs_group['+str(group)+
                    '].ddrphy_data_slice/ddrphy_data_slice_wrcal/delay_cnt['+str(bit)+']'
                    for group in range(4) for bit in (2,3))
    require(len(records) == len(expected) and {r['Node'] for r in records} == expected,
            'original supplied vendor compile high-bit elimination differs')
    return records


def audit_value():
    original = BUILD/'place_route'/(prep.TARGET+'_pnr.adf')
    readonly = BUILD/'../build-a-readonly-review.json'
    readonly = readonly.resolve()
    _, watched = inspect.bind(BUILD/'plan.json', original, ORIGINAL_ADF_SHA, readonly,
                             '212058bacba126b21d79f0c63b25f4356c34d554f61d24da8abbaa1674b5ead6')
    vendor.bind_file(watched,BUILD/'plan.json',BUILD_PLAN_SHA)
    vendor.bind_file(watched,BUILD/'execution-result.json',BUILD_RECEIPT_SHA)
    vendor.bind_file(watched,REVIEW,REVIEW_SHA)
    review, receipt = read(REVIEW), read(BUILD/'execution-result.json')
    require(review['Schema'] == 'camera720-raw-build-a-diagnostics-readonly-review-v1'
            and review['Target'] == prep.TARGET and review['OriginalExecutionStatusChanged'] is False,
            'review identity/status differs')
    compile_log = BUILD/'compile/run.log'
    compile_text = compile_log.read_text(encoding='gb18030',errors='replace')
    compile_lines = compile_text.splitlines()
    copies = validate_diagnostic_copies(receipt,review['DiagnosticEvents'])
    public = validate_events(review['DiagnosticEvents'],compile_lines,watched)
    blocks = parameter_blocks(compile_text)
    for name,item in review['ActualElaboratedParameters'].items():
        require(blocks.get(name) == item['Parameters'], 'actual public elaborated parameter block differs')
    for item in review['FrozenSourceBindings']:
        for role in ('Original','Compiled'):
            vendor.bind_file(watched,item[role]['Path'],item[role]['SHA256'])
    vendor_evidence = vendor.vendor_bytes(watched)
    actual_ddr = ddr_parameters(compile_text)
    priors = []
    for prior in review['ProtectedVendorProvenance']:
        vendor.bind_file(watched,prior['CompileLog']['Path'],prior['CompileLog']['SHA256'])
        vendor.bind_file(watched,prior['ExecutionReceipt']['Path'],prior['ExecutionReceipt']['SHA256'])
        text = Path(prior['CompileLog']['Path']).read_text(encoding='gb18030',errors='replace')
        require(ddr_parameters(text) == actual_ddr == prior['NormalizedDDRParameters']
                and len(actual_ddr) == prior['PrintedDDRParameterBlockCount'] == 121,
                'same-configuration actual DDR elaborated parameters differ')
        require(len(prior['DDRFiles']) == 75 and
                {row['RelativePath'] for row in prior['DDRFiles']} ==
                {row['RelativePath'] for row in vendor_evidence['Files']}, 'prior expanded DDR ownership differs')
        for row in prior['DDRFiles']:
            require(row['RawBuild']['SHA256'] == row['PriorBuild']['SHA256'], 'prior DDR source differs')
            for role in ('RawBuild','PriorBuild'):
                vendor.bind_file(watched,row[role]['Path'],row[role]['SHA256'])
        lines = text.splitlines()
        require(len(prior['MatchingVendorDiagnostics']) == 2, 'prior protected diagnostic inventory differs')
        for event,spec in zip(prior['MatchingVendorDiagnostics'],PROTECTED):
            require(lines[event['Line']-1] == event['Text'] and
                    'Reduce accumulator '+spec[0]+' size from '+str(spec[1])+' to '+str(spec[2])+'.' in event['Text'],
                    'same-config protected optimization diagnostic differs')
        priors.append({'Label':prior['Label'],'CompileLog':prior['CompileLog'],
                       'DDRFilesVerified':75,'ElaboratedParameterBlocksVerified':len(actual_ddr),
                       'PriorPhysicalAcceptanceInherited':False})
    vendor.bind_file(watched,VENDOR_LOG,VENDOR_LOG_SHA)
    zeros = validate_original_vendor_zeros(VENDOR_LOG.read_text(encoding='gb18030',errors='replace'))
    # Bind current route-b ancestry; all downstream reset/IO/CDC release gates stay separate.
    export_path = prep.WORK/'physical-export-b/result.json'
    vendor.bind_file(watched,export_path,current.EXPORT_SHA)
    exported, bound = current.derived.bind_receipt(export_path)
    current.merge(watched,bound)
    current.exact_export(exported)
    vendor.bind_file(watched,SELF,sha(SELF))
    vendor.bind_file(watched,Path(vendor.__file__).resolve(),sha(Path(vendor.__file__).resolve()))
    vendor.bind_file(watched,Path(current.__file__).resolve(),sha(Path(current.__file__).resolve()))
    result = {'Schema':SCHEMA,'Target':prep.TARGET,
        'BuildPlan':{'Path':str(BUILD/'plan.json'),'SHA256':BUILD_PLAN_SHA},
        'OriginalExecutionReceipt':{'Path':str(BUILD/'execution-result.json'),'SHA256':BUILD_RECEIPT_SHA},
        'OriginalBuildExecutionCompletedWithoutError':False,'OriginalExecutionStatusChanged':False,
        'BuildDiagnosticsCleared':False, 'RecordedCriticalDiagnostics':60,'EventsPerLog':15,
        'DiagnosticLogCopies':copies,'PublicRTLBoundedEvents':public,
        'ProtectedVendorEvents':[{'Symbol':x[0],'DeclaredBits':x[1],'ReducedBits':x[2],
                                 'SourceFile':x[3],'SourceLine':x[4],'InternalCounterProof':False} for x in PROTECTED],
        'ManualSourceReview':{'Path':str(REVIEW),'SHA256':REVIEW_SHA},
        'VendorSameConfiguration':vendor_evidence,'ActualSameConfigurationComparisons':priors,
        'OriginalVendorCompileEvidence':{'Path':str(VENDOR_LOG),'SHA256':VENDOR_LOG_SHA,
            'HighBitsReportedConstantZero':zeros,'Meaning':'Independent supplied example compiler output corroborates these same removed high bits; not a proof of protected source transitions.'},
        'CurrentSourceADFSHA256':current.SOURCE_SHA,
        'CurrentExportReceipt':{'Path':str(export_path),'SHA256':current.EXPORT_SHA},
        'DiagnosticCaptureDispositionApproved':True,
        'Disposition':'Known explained width-optimization diagnostics admitted only for this unchanged vendor configuration and controlled SRAM native raw-image capture. Public bounds retain fault/terminal sentinels; protected reductions rely on vendor IP/tool behavior corroborated by original supplied and two same-configuration compilations.',
        'AllowedUse':'Controlled SRAM raw-image acquisition for calibration/geometry work after independent reset, IO, CDC, timing, bitstream and program checks; review first captures and initialization/error telemetry.',
        'NotAuthorized':['Production release','A different source/configuration/diagnostic set',
                         'Skipping current physical reset/IO/CDC/timing checks','Hardware programming by this CPU report'],
        'InternalCounterProof':False,'SynthesizedEquivalenceProved':False,'ProductionReleaseApproved':False,
        'TimingAccepted':False,'HardwareReleaseAllowed':False,'HardwareAccessed':False,
        'EDAExecuted':False,'OpticalCorrectionAccepted':False,
        'Producer':{'Path':str(SELF),'SHA256':sha(SELF)}}
    require(not inspect.drift(watched), 'diagnostic disposition input drift')
    result['InputSHA256'] = {str(p):h for p,h in sorted(watched.items(),key=lambda x:str(x[0]))}
    return result, watched


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    a = p.parse_args(); output = a.output.absolute()
    require(output == output.resolve() and output.parent == prep.WORK and output.suffix == '.json'
            and not output.exists(), 'fresh canonical raw work JSON output required')
    value,_ = audit_value()
    with output.open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(value,stream,indent=2,ensure_ascii=False);stream.write('\n')
    require(read(output) == value, 'diagnostic disposition output readback differs')
    print(json.dumps({'Path':str(output),'SHA256':sha(output),'DiagnosticCaptureDispositionApproved':True,
                      'OriginalBuildExecutionCompletedWithoutError':False,'HardwareReleaseAllowed':False}))


if __name__ == '__main__':
    main()
