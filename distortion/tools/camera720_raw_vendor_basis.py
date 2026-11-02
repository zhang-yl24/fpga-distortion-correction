"""CPU-only vendor operating-contract basis for the exact raw720 route-b reset scope.

This accepts the documented, generated HMIC_S reset architecture as supplied IP.
It does not prove encrypted controller internals, authorize a native action, or
import the vendor's broad asynchronous clock groups into the user's design.
"""
import argparse
import json
from pathlib import Path

import camera720_raw_reset_current as current

prep, require, sha = current.prep, current.require, current.sha
SELF = Path(__file__).resolve()
SCHEMA = 'camera720-current-raw-vendor-reset-basis-v1'
SCOPE = prep.WORK/'reset-current-c/plan.json'
SCOPE_SHA = 'b1924751e8a0a919da33e41b2a4d622fd7d5b101f8c38bb2068374012aac4e9d'
REFERENCE = prep.PROJECT/'results/camera-vga-reset-analysis-20261031-a/vendor-reference.json'
REFERENCE_SHA = 'ff4a7dd5b7fda35b73a80d293fe0ec837ce13c22f00cde7737b66dbb179a8af0'
MANIFEST = prep.PROJECT/'board/raw_camera_capture_cam2_current720-sources.json'
MANIFEST_SHA = '66c333dbb7cf0c40708dc813ee3eeedc8e960c5cbbc0ced11cae79be87040113'
VENDOR = prep.PROJECT.parent/'vendor/reference/ddr/2_9_ddr3_test/2_9_ddr3_test/ddr3_test/ipcore/ddr3_test'
MANUAL = prep.PROJECT.parent/'vendor/board/盘古100Pro+开发板（MES2L676-100HP）配套资料/6_IP_setup_packet/PG2L/DDR3/UG042003_HMIC_S_IP.pdf'
MANUAL_SHA = 'c158c326ccf0146d5f6c1eca1efde61a70669667a7eeae78bce016bfcdaffc02'
COMPILED = prep.WORK/'build-a/compiled/platform/video_base/ipcore/ddr3_test'
FAMILIES = {'entry_rdc':1, 'cpd_reset':1, 'dqs_reset':104, 'iol_reset':14, 'training_reset':7}


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def bind_file(watched, path, digest):
    path = Path(path).resolve()
    require(path.is_relative_to(prep.PROJECT.parent), 'vendor basis input escapes repository')
    require(path.is_file() and sha(path) == digest, 'vendor basis digest differs: '+str(path))
    require(path not in watched or watched[path] == digest, 'conflicting vendor basis digest')
    watched[path] = digest
    return path


def vendor_bytes(watched):
    """Recompute current source ownership and byte identity; no old acceptance flags."""
    bind_file(watched, REFERENCE, REFERENCE_SHA)
    bind_file(watched, MANIFEST, MANIFEST_SHA)
    manifest, reference = read(MANIFEST), read(REFERENCE)
    require(manifest['Target'] == prep.TARGET, 'vendor manifest target differs')
    prefix = 'platform/video_base/ipcore/ddr3_test/'
    expected = {(prep.PROJECT/p).resolve() for p in manifest['source_files'] if p.startswith(prefix)}
    rows = reference['Files']
    require(len(rows) == len(expected) == 75 and
            {Path(row['CandidatePath']).resolve() for row in rows} == expected,
            'current IDF and expanded vendor file ownership differs')
    verified = []
    for row in rows:
        relative = Path(row['RelativePath'])
        require(not relative.is_absolute() and '..' not in relative.parts, 'vendor relative path escapes')
        candidate = (prep.PROJECT/prefix/relative).resolve()
        vendor = (VENDOR/relative).resolve()
        compiled = (COMPILED/relative).resolve()
        require(Path(row['CandidatePath']).resolve() == candidate and
                Path(row['VendorPath']).resolve() == vendor, 'vendor row path differs')
        for path in (candidate, vendor, compiled):
            bind_file(watched, path, row['SHA256'])
        verified.append({'RelativePath':relative.as_posix(), 'CandidatePath':str(candidate),
                         'VendorPath':str(vendor), 'CompiledPath':str(compiled), 'SHA256':row['SHA256']})
    fdc = reference['VendorFDC']
    require(Path(fdc['Path']).resolve() == (VENDOR/'pnr/ddr_test.fdc').resolve(), 'vendor FDC path differs')
    bind_file(watched, fdc['Path'], fdc['SHA256'])
    lines = Path(fdc['Path']).read_text(encoding='utf-8-sig').splitlines()
    relationships = []
    for clock in ('rst_clk', 'phy_dq_clk_0', 'phy_dq_clk_1'):
        text = 'set_clock_groups -name '+clock+' -asynchronous -group [get_clocks {'+clock+'}]'
        matches = [i+1 for i,line in enumerate(lines) if line.strip() == text]
        require(len(matches) == 1, 'vendor reset clock relationship differs')
        relationships.append({'Line':matches[0], 'Text':text})
    return {'CurrentManifest':{'Path':str(MANIFEST),'SHA256':MANIFEST_SHA},
            'ReferenceInventory':{'Path':str(REFERENCE),'SHA256':REFERENCE_SHA},
            'IDFAndExpandedBodyCount':len(verified), 'Files':verified,
            'VendorFDC':fdc, 'ClockRelationshipLines':relationships,
            'VendorSameConfigurationVerified':True, 'GlobalClockGroupsImported':False}


def validate_scope_contract(value):
    require(value.get('Schema') == current.SCHEMA and value.get('Target') == prep.TARGET and
            value.get('SourceADFSHA256') == current.SOURCE_SHA and value.get('Complete') is True,
            'exact current route-b complete reset scope required')
    queries = value['NativeQueries']
    require(len(queries) == 5 and {q['Family']:len(q['Targets']) for q in queries} == FAMILIES,
            'reset family membership/count differs')
    require(all(len(set(q['Targets'])) == len(q['Targets']) for q in queries) and
            sum(len(q['Targets']) for q in queries) == value['UniqueSourceEndpointPairs'] == 127,
            'duplicate or missing exact reset pairs')
    s = value['StructuralProof']
    require(s['RegisteredStickyPropertyVerified'] is True and s['RawClearFunction'] == '~registered_power_ready'
            and s['ExternalResetPortAssumed'] is False and s['FirstStageFunctionalFanout'] == 1
            and s['InternalFunctionalTargetsVerified'] == 126, 'registered entry/internal reset graph differs')
    first, second = s['Stages']
    require(first['Primitive'] == second['Primitive'] == 'V_FFASYN' and
            first['Ports']['Q'] == second['Ports']['D'] and
            first['Ports']['CK'] == second['Ports']['CK'] and
            first['Ports']['SR'] == second['Ports']['SR'] and
            all(stage['Parameters']['INIT'] == "1'b0" and
                stage['Parameters']['SET_RESET'] == '"RESET"' for stage in (first, second)),
            'two-stage asynchronous-assert synchronous-release entry structure differs')
    require(value['TimingExceptionApproved'] is False and value['ConstraintsApplied'] is False
            and value['HardwareReleaseAllowed'] is False, 'scope already carries authority')
    return queries


def audit_value(scope_plan=SCOPE):
    path = Path(scope_plan).resolve()
    require(path == SCOPE.resolve(), 'only the independently derived current scope is reviewed')
    scope, _, watched = current.bind_scope(path, SCOPE_SHA)
    queries = validate_scope_contract(scope)
    vendor = vendor_bytes(watched)
    bind_file(watched, MANUAL, MANUAL_SHA)
    bind_file(watched, SELF, sha(SELF))
    result = {'Schema':SCHEMA, 'Target':prep.TARGET,
        'SourceScopePlan':{'Path':str(path),'SHA256':SCOPE_SHA},
        'SourceADFSHA256':current.SOURCE_SHA, 'ExportReceipt':scope['ExportReceipt'],
        'ExactNativeQueries':queries, 'SupportedFamilies':FAMILIES,
        'UniqueSourceEndpointPairs':127, 'InternalResetPairs':126, 'RegisteredEntryPairs':1,
        'VendorSameConfigurationVerified':True, 'RegisteredEntryContractVerified':True,
        'InternalResetContractVerified':True,
        'ContractMeaning':'Engineering acceptance of the vendor-generated HMIC_S reset and training architecture under its documented IP clock/reset usage and the exact current placed reset graph; not an independent proof of encrypted state machines.',
        'VendorEvidence':vendor,
        'Manual':{'Path':str(MANUAL),'SHA256':MANUAL_SHA,'Pages':[32,47,66,69],
          'Support':['Power/reset starts IP initialization; traffic becomes valid after init_done.',
                     'PHY exposes external reset, reset GPLL lock and PHY system clock.',
                     'rst_clk drives GPLL dynamic phase and the reset sequence; use generated IP/pnr FDC constraints.',
                     'init_done indicates PHY training completed and normal state.']},
        'ReadableWrapperEvidence':[
          {'Path':str(VENDOR/'ddr3_test_ddrphy_top.v'),'Lines':[475,483],'Meaning':'entry synchronizer samples reset GPLL lock on rst_clk with ddr_rstn asynchronous reset'},
          {'Path':str(VENDOR/'ddr3_test_ddrphy_top.v'),'Lines':[528,568],'Meaning':'CPD controller reset output drives GTP_CLKPD.RST and local reset synchronizer'},
          {'Path':str(VENDOR/'ddr3_test_ddrphy_top.v'),'Lines':[576,608],'Meaning':'vendor reset controller owns DQS and IOL reset outputs'},
          {'Path':str(VENDOR/'ddr3_test_ddrphy_top.v'),'Lines':[753,760],'Meaning':'vendor training request/ack controller owns DQS training reset'},
          {'Path':str(VENDOR/'rtl/ddrphy/ddr3_test_slice_top_v1_10.v'),'Lines':[821,822,860,902,947],'Meaning':'DQS/IOL/training nets connect to original DDR I/O primitive reset pins'}],
        'RequiredFollowingChecks':['Exact current native pin query must match all 127 pairs.',
          'Apply only current ExactResetCommands to an isolated copy; never import broad vendor clock groups.',
          'Fresh full STA and exception-effect audit must show exactly the intended reset checks removed while setup/hold/removal/MPW and all other paths remain accepted.',
          'Current IO and CDC evidence and separate bitstream/program approval remain required.'],
        'VendorEncryptedResetInternalsProved':False, 'AnalogMTBFProven':False,
        'PriorPhysicalAcceptanceInherited':False, 'GlobalClockGroupsImported':False,
        'NativeQueriesVerified':False, 'ConstraintsApplied':False, 'TimingExceptionApproved':False,
        'TimingAccepted':False, 'HardwareReleaseAllowed':False, 'HardwareAccessed':False,
        'EDAExecuted':False, 'OpticalCorrectionAccepted':False,
        'Producer':{'Path':str(SELF),'SHA256':sha(SELF)}}
    require(not current.inspect.drift(watched), 'vendor basis input drift')
    result['InputSHA256'] = {str(p):h for p,h in sorted(watched.items(),key=lambda x:str(x[0]))}
    return result, watched


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--scope-plan',type=Path,default=SCOPE)
    p.add_argument('--output',type=Path,required=True)
    a = p.parse_args()
    output = a.output.absolute()
    require(output == output.resolve() and output.parent == prep.WORK and output.suffix == '.json'
            and not output.exists(), 'fresh canonical raw work JSON output required')
    result, _ = audit_value(a.scope_plan)
    with output.open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(result,stream,indent=2,ensure_ascii=False);stream.write('\n')
    require(read(output) == result, 'vendor basis output readback differs')
    print(json.dumps({'Path':str(output),'SHA256':sha(output),'ExactResetPairs':127,
                      'VendorOperatingContractAccepted':True,'TimingAccepted':False,'HardwareReleaseAllowed':False}))


if __name__ == '__main__':
    main()
