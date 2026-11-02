"""Portable offline verification using only Python's standard library.

Historical absolute paths are keys in OriginIndex, never files opened here.
No PDS, simulator, local work tree, UART, JTAG or machine configuration is used.
"""
import argparse
import gzip
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import re
import sys

TARGET='hdmi_camera_direct_top'
BIT_SHA='33aca64d692778a9ba316828c32b9b816a0878de701e8e7fd4febcc703335156'
ADF_SHA='2c88e0d98fee65326afbea25ae2282e0a182a7a0becbc5baf434da36dd84287f'


def require(ok,message):
    if not ok:raise ValueError(message)


def sha(data):return hashlib.sha256(data).hexdigest()


def safe(package,name):
    require(isinstance(name,str)and '\\'not in name and not Path(name).is_absolute(),'relative POSIX bundle path required')
    path=(package/name).resolve();require(path.is_relative_to(package)and path.is_file(),'missing/escaping bundle file: '+name)
    return path


class Bundle:
    def __init__(self,package):
        self.package=Path(package).resolve();self.manifest=json.loads((self.package/'manifest.json').read_text(encoding='utf-8'))
        m=self.manifest
        require(m['Schema']=='hdmi-camera1080-direct-display-portable-bundle-v1'and m['Target']==TARGET,'wrong bundle target/schema')
        require(m['Resolution']==[1920,1080]and m['SignalFrameRateHz']==60 and
            m['OutputClockSource']=='forwarded input PCLK'and m['UniqueOpticalFPSMeasured']is False and
            m['FlashWritten']is False and m['UserStableMotionDisplayAccepted']is True,'release scope differs')
        names=set()
        for row in m['Files']:
            require(row['File']not in names,'duplicate package inventory');names.add(row['File'])
            data=safe(self.package,row['File']).read_bytes()
            require(len(data)==row['Bytes']and sha(data)==row['SHA256'],'stored file hash differs: '+row['File'])
        actual={p.relative_to(self.package).as_posix()for p in self.package.rglob('*')if p.is_file()
            and p.name!='manifest.json'and '__pycache__'not in p.parts}
        require(actual==names,'bundle file inventory differs')
        self.objects={}
        for row in m['Objects']:
            require(row['Encoding']=='gzip'and row['DecodedSHA256']not in self.objects,'duplicate/unknown object encoding')
            stored=safe(self.package,row['File']).read_bytes();data=gzip.decompress(stored)
            require(len(stored)==row['Bytes']and sha(stored)==row['SHA256']and
                len(data)==row['DecodedBytes']and sha(data)==row['DecodedSHA256'],'decoded historical evidence differs')
            self.objects[row['DecodedSHA256']]=row
        self.origins={}
        for row in m['OriginIndex']:
            require(row['OriginalPath']not in self.origins and row['SHA256']in self.objects and
                row['Object']==self.objects[row['SHA256']]['File'],'origin evidence is missing or duplicated')
            self.origins[row['OriginalPath']]=row['SHA256']
        self.external={r['OriginalPath']:r['SHA256']for r in m['ExternalInputs']}
        require(not(set(self.external)&set(self.origins)),'ambiguous historical origin')

    def raw(self,reference):
        require(set(reference)=={'OriginalPath','SHA256'}or set(reference)=={'Path','SHA256'},'exact original reference required')
        origin=reference.get('OriginalPath',reference.get('Path'));h=reference['SHA256']
        require(self.origins.get(origin)==h,'reference not archived: '+str(origin))
        return gzip.decompress(safe(self.package,self.objects[h]['File']).read_bytes())

    def role(self,name):return self.raw(self.manifest['Roles'][name])
    def json(self,name):return json.loads(self.role(name).decode('utf-8-sig'))

    def declared_inputs(self,values):
        require(isinstance(values,dict)and values,'missing declared historical input closure')
        for path,h in values.items():
            require(self.origins.get(path,self.external.get(path))==h,'unaccounted historical dependency: '+path)


def timing_tables(data):
    header=re.compile(r'^(Setup|Hold|Recovery|Removal|Minimum Pulse Width) Summary\((Slow|Fast) Corner\):$')
    tables={};current=None
    for raw in io.TextIOWrapper(io.BytesIO(data),encoding='gb18030',errors='strict'):
        line=raw.strip()
        if line.startswith('Startpoint'):break
        match=header.fullmatch(line)
        if match:
            current=match[2].lower()+'/'+match[1].lower().replace(' ','_')
            require(current not in tables,'duplicate STA summary');tables[current]=[];continue
        if current is None:continue
        parts=line.split();expected=5 if current.endswith('minimum_pulse_width')else 6
        if len(parts)!=expected or not all(x.isdigit()for x in parts[-2:]):continue
        try:slack=float(parts[-4]);total_slack=float(parts[-3])
        except ValueError:continue
        fail,total=map(int,parts[-2:]);require(fail==0 and slack>=0 and total_slack>=0,'native STA summary has failing endpoints')
        tables[current].append({'Launch':parts[0],'Capture':parts[0]if expected==5 else parts[1],
            'WorstSlackNS':slack,'FailingEndpoints':fail,'TotalEndpoints':total})
    expected={corner+'/'+kind for corner in ('slow','fast')for kind in ('setup','hold','recovery','removal','minimum_pulse_width')}
    require(set(tables)==expected and all(tables.values()),'all ten populated STA summaries required')
    return tables


def verify(package):
    b=Bundle(package);m=b.manifest
    require(m['ExpectedBitstreamSHA256']==BIT_SHA and m['ExpectedFinalADFSHA256']==ADF_SHA,'accepted bit/ADF identity differs')
    bit=b.role('Bitstream');require(len(bit)==3791112 and sha(bit)==BIT_SHA,'accepted programming bytes differ')
    require((b.package/'candidate/hdmi_camera_direct_top.sbit').read_bytes()==bit,'download candidate differs from archived bit')
    require(sha(b.role('FinalADF'))==ADF_SHA,'accepted final ADF differs')
    prefix=bytes.fromhex('00090ff00ff00ff00ff000')+b'PANGO MICROSYSTEMS, INC.\0\1'
    require(bit.startswith(prefix),'native programming header prefix differs');offset=len(prefix);fields={}
    for tag,name in zip(b'abcdef',('Design','Device','Date','Time','Generator','Version')):
        require(bit[offset]==tag,'programming header tag differs');length=int.from_bytes(bit[offset+1:offset+3],'big')
        value=bit[offset+3:offset+3+length];require(value[-1:]==b'\0'and b'\0'not in value[:-1],'invalid header string')
        fields[name]=value[:-1].decode('ascii');offset+=3+length
    require(fields['Design']==TARGET and fields['Device']=='Logos2-PG2L100H--6-FBG676'and bit[offset:offset+3]==b'ghi','wrong programming target')
    program=b.json('ProgramReceipt');observation=b.json('UserObservation');verification=b.json('BitVerification')
    require(program['Target']==TARGET and program['Passed']is True and program['DoneConfirmed']is True and
        program['ExpectedDeviceAndIDConfirmed']is True and program['FlashWritten']is False and
        program['CleanupErrors']==[]and program['Bitstream']['SHA256']==BIT_SHA and
        program['FinalADFSHA256']==ADF_SHA,'SRAM download did not complete cleanly')
    require(observation['RealCameraMotionObservedByUser']is True and observation['StableDisplayConfirmedByUser']is True and
        observation['BitstreamSHA256']==BIT_SHA and observation['ProgramReceipt']['SHA256']==sha(b.role('ProgramReceipt'))and
        observation['UniqueOpticalFPSMeasured']is False,'user display confirmation or scope differs')
    require(verification['Verified']is True and verification['Target']==TARGET and
        verification['Bitstream']['SHA256']==BIT_SHA and verification['FinalADFSHA256']==ADF_SHA,'bit verification differs')
    bp=b.json('BitPlan');pp=b.json('ProgramPlan');sim=b.json('ControlSimulation');build=b.json('BuildPlan')
    for inputs in (bp['InputSHA256'],pp['BoundInputSHA256'],sim['SourceSHA256']):b.declared_inputs(inputs)
    proof=b.json('PhysicalProof')
    for flag in ('Passed','STAAllTenPassed','NetlistEquivalent','AllFFPlacementsEquivalent','RoutesUnchanged',
        'ResetAccepted','SourceSamplingIsolatedVerified','NativeWarningsReviewed'):
        require(proof.get(flag)is True,'recorded physical assertion absent: '+flag)
    require(proof['FinalADF']['SHA256']==ADF_SHA and proof['Pins']['DeclaredTopPorts']==69 and
        proof['Pins']['NativeActivePorts']==69 and proof['Pins']['UnusedPads']==[]and
        proof['Pins']['NativeElectricalParametersVerified']is True and proof['CDC']['InterstageTimingAccepted']is True and
        proof['CDC']['Missing']==proof['CDC']['Violations']==[]and proof['SourceSampling']['ActualSamplerCount']==27,
        'recorded pin/sampling/CDC coverage differs')
    require(proof['ExternalACAccepted']is False,'external AC scope was changed')
    require(sim['Passed']is True and sim['SourceDrift']==[]and sim['ActualTopRTLExecuted']is True and
        sim['ActualSamplerRTLExecuted']is True and sim['Full27BitDigitalBundleVerified']is True and
        sim['HardwareAccessed']is False,'actual direct sampler/control simulation required')
    log=b.role('SimulationLog').decode('utf-8')
    require(not re.search(r'(?im)^\s*(?:fatal|error):',log),'simulation assertion failed')
    counters=re.findall(r'^HDMI_DIRECT_PASS bundle_checks=(\d+) phase_changes=(\d+) ready_checks=(\d+) '
        r'clock_edges=(\d+) resets=(\d+) cold_cycles=(\d+) warm_shortcuts=(\d+)$',log,re.M)
    require(len(counters)==1,'one complete simulator marker required');counts=list(map(int,counters[0]))
    require(counts[0]>=4006 and counts[1]>=576 and counts[2]>=4006 and counts[4]==6 and counts[5]>=1000000,
        'sampler/control coverage differs')
    snapshots=m['SourceSnapshots'];require(len(snapshots)==8 and len(build['SourceRoles']['ExplicitDesigns'])==7,'seven RTL plus FDC required')
    source_manifest=b.json('OriginalSourceManifest')
    built={r['Source']:r for r in build['CompiledInputs']}
    require(len(built)==8 and {r['Source']for r in snapshots}==set(built)==set(source_manifest['source_files']),
        'published source inventory differs from actual build')
    for row in snapshots:
        actual=built[row['Source']]
        require(row['OriginalSHA256']==actual['OriginalSHA256']==source_manifest['SourceSHA256'][row['Source']]and
            row['CompiledSHA256']==actual['CompiledSHA256']and row['Changes']==actual['Changes'],
            'published source hashes/transformations differ from actual build')
        require(sha(b.raw({'Path':actual['CompiledPath'],'SHA256':actual['CompiledSHA256']}))==row['CompiledSHA256'],
            'published compiled source differs from original archived evidence')
        if row['Source']in ('board/hdmi_camera_direct_top.v','rtl/experimental/hdmi_camera_pixel_sampler.v'):
            origins=[p for p in build['InputSHA256']if p.replace('\\','/').endswith('/'+row['Source'])]
            require(len(origins)==1 and build['InputSHA256'][origins[0]]==sim['SourceSHA256'][origins[0]]==row['OriginalSHA256'],
                'top/sampler simulator and implementation source differ')
        original=safe(b.package,row['OriginalFile']).read_bytes();compiled=safe(b.package,row['CompiledFile']).read_bytes()
        require(sha(original)==row['OriginalSHA256']and sha(compiled)==row['CompiledSHA256'],'source/compiled snapshot drift')
        require(build['Manifest']['SHA256']==sha(b.role('OriginalSourceManifest')),'original source manifest differs')
        if row['Source']=='board/hdmi_camera_direct_top.v':
            changed,n=re.subn(rb'(parameter[ \t]+integer[ \t]+INPUT_TIMING_CONFIGURED[ \t]*=[ \t]*)0(?=[ \t]*[,\r\n])',rb'\g<1>1',original)
            require(n==1 and changed==compiled and len(row['Changes'])==1,'frozen timing selection is not the sole top change')
        else:require(original==compiled and row['Changes']==[],'retained source was changed')
    profile=b.json('TimingProfile');session=b.json('TimingSession')
    require(profile['Source']['SHA256']==sha(b.role('TimingSession'))and session['wire_sha256']==sha(b.role('TimingWire')),
        'observed timing profile is not bound to original UART wire')
    decoder=safe(b.package,'source/tools/hdmi_raw_status.py')
    require(sha(decoder.read_bytes())==sha(b.role('TimingDecoder')),'portable decoder differs')
    spec=importlib.util.spec_from_file_location('published_direct_timing_decoder',decoder)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    parser=module.FrameParser();frames=parser.feed(b.role('TimingWire'));summary=module.summarize(frames)
    require(frames==session['frames']and summary==session['summary']and len(frames)==20 and parser.rejected==0 and
        summary['valid_counter_windows']==19 and summary['edge_conservation_failure_windows']==0,
        'raw v2 timing replay or edge conservation failed')
    require(profile['VSPeriodPCLK']==[2475000]and profile['HSPeriodPCLK']==[2200]and profile['DEHighWidthPCLK']==[1920]and
        profile['ActiveLinesPerVS']==[1080]and abs(profile['EstimatedVSRisingHz']-60)<0.001,'1080p60 digital geometry differs')
    tables=timing_tables(b.role('FreshSTA'));gate=b.json('PreBitGate')
    require(gate['GatePassed']is True and gate['FinalADFSHA256']==ADF_SHA and
        gate['Checks']['STAAllTenPassed']and gate['Checks']['ClockAndSummaryIdentityPreserved']and
        gate['Checks']['AllExceptionPathsPreserved'],'fresh pre-bit gate incomplete')
    require(gate['EvidenceSHA256']['report_timing/'+TARGET+'.rtr']==sha(b.role('FreshSTA'))and
        gate['EvidenceSHA256']['report_timing/'+TARGET+'_exception.rtr']==sha(b.role('FreshSTAExceptions')),
        'gate timing/exception artifacts differ')
    return {'Passed':True,'Target':TARGET,'Resolution':[1920,1080],'SignalFrameRateHz':60,
        'MeasuredPCLKHzEstimate':profile['EstimatedPCLKHz'],'OutputClockSource':'forwarded input PCLK',
        'UniqueOpticalFPSMeasured':False,'FlashWritten':False,'UserStableDisplayConfirmed':True,
        'RTLFiles':7,'SourceAndCompiledSnapshots':len(snapshots),'ArchivedOrigins':len(b.origins),
        'VerifiedObjects':len(b.objects),'RecordedSTAAllTenPassed':len(tables)==10,
        'NativePhysicalProofReexecuted':False,'HardwareAccessed':False}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--package',type=Path,default=Path(__file__).resolve().parent)
    args=parser.parse_args();print(json.dumps(verify(args.package),ensure_ascii=False))
