"""Archive the accepted1080p direct display without changing release inputs.

Produces portable objects/source snapshots and exact original receipts. SDK
binaries/models and private machine configuration remain external hash records.
No PDS, UART, JTAG, Flash or network access is performed by this archiver.
"""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import shutil


def sha(data):return hashlib.sha256(data).hexdigest()
def read(path):return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def archive(source_root,package):
    source_root=Path(source_root).resolve();package=Path(package).resolve()
    d=source_root/'distortion';work=d/'work/direct-20261102-a'
    request_path=work/'bit-request-a.json';request=read(request_path)
    bitplan=read(work/'bit-a/bitstream-plan.json');programplan=read(work/'program-a/plan.json')
    buildpath=Path(bitplan['BuildPlan']['Path']);buildplan=read(buildpath)
    simpath=Path(request['ControlSimulation']['Path']);sim=read(simpath)
    program=read(work/'program-a/receipt.json');observation=read(work/'user-display-confirmed-a.json')
    assert program['Passed']and program['DoneConfirmed']and not program['FlashWritten']
    assert observation['RealCameraMotionObservedByUser']and observation['StableDisplayConfirmedByUser']
    assert observation['BitstreamSHA256']==program['Bitstream']['SHA256']=='33aca64d692778a9ba316828c32b9b816a0878de701e8e7fd4febcc703335156'
    bindings={}
    def add(path,expected=None):
        path=Path(path).resolve();data=path.read_bytes();actual=sha(data)
        assert expected is None or actual==expected, 'source evidence drift: '+str(path)
        assert str(path)not in bindings or bindings[str(path)]==actual
        bindings[str(path)]=actual
        return path
    for group in (bitplan['InputSHA256'],programplan['BoundInputSHA256'],sim['SourceSHA256']):
        for path,h in group.items():add(path,h)
    roles={
        'BuildPlan':buildpath,'BuildExecution':work/'build-a/execution-result.json',
        'PhysicalProof':Path(request['PhysicalProof']['Path']),
        'BitRequest':request_path,'BitPlan':work/'bit-a/bitstream-plan.json',
        'BitVerification':work/'bit-a/verification.json','BitExecution':work/'bit-a/execution-result.json',
        'PreBitGate':work/'bit-a/pre-bit-audit.json','ProgramPlan':work/'program-a/plan.json',
        'ProgramReceipt':work/'program-a/receipt.json','UserObservation':work/'user-display-confirmed-a.json',
        'ControlSimulation':simpath,'SimulationLog':simpath.parent/'simulation.log',
        'Bitstream':Path(program['Bitstream']['Path']),
        'FinalADF':work/'bit-a/audited-final.adf',
        'FreshSTA':work/'bit-a/report_timing/hdmi_camera_direct_top.rtr',
        'FreshSTAExceptions':work/'bit-a/report_timing/hdmi_camera_direct_top_exception.rtr',
        'NativeBGR':work/'bit-a/generate_bitstream/hdmi_camera_direct_top.bgr',
        'TimingProfile':Path(buildplan['InputTiming']['Profile']['Path']),
        'TimingSession':Path(buildplan['InputTiming']['Source']['Path']),
        'TimingWire':Path(buildplan['InputTiming']['Wire']['Path']),
        'TimingDecoder':d/'tools/hdmi_raw_status.py',
        'OriginalSourceManifest':d/'board/hdmi-camera-direct-build-sources.json',
    }
    for path in roles.values():add(path)
    for path in (work/'program-a').glob('*'):
        if path.is_file():add(path)
    for relative,h in sim['Artifacts'].items():add(simpath.parent/relative,h)
    origins=[];external=[];objects={}
    for name,h in sorted(bindings.items()):
        path=Path(name)
        try:relative=path.relative_to(source_root)
        except ValueError:relative=None
        if relative is None or relative.parts[0]in ('.venv','.git')or relative.name=='team-config.local.json'or path.suffix in ('.db','.exe','.pyd','.dll','.lic'):
            external.append({'OriginalPath':name,'SHA256':h,'Disposition':
                'machine-private configuration not distributed'if relative and relative.name=='team-config.local.json'else
                'generated simulator executable/database not distributed'if relative and relative.parts[0]=='distortion'and path.suffix in ('.exe','.db','.dll')else
                'external licensed SDK or machine Python runtime; not required for portable verification'})
            continue
        assert path.suffix not in ('.db','.exe','.pyd','.dll','.lic'),str(path)
        data=path.read_bytes();assert sha(data)==h
        object_name='objects/'+h+'.gz'
        if h not in objects:
            encoded=gzip.compress(data,compresslevel=9,mtime=0);out=package/object_name
            out.parent.mkdir(parents=True,exist_ok=True);out.write_bytes(encoded)
            objects[h]={'File':object_name,'Encoding':'gzip','Bytes':len(encoded),'SHA256':sha(encoded),
                'DecodedBytes':len(data),'DecodedSHA256':h}
        origins.append({'OriginalPath':name,'RepositoryPath':relative.as_posix(),'SHA256':h,'Object':object_name})
    snapshots=[]
    for row in buildplan['CompiledInputs']:
        name=row['Source'];original=add(d/name,row['OriginalSHA256']);compiled=add(row['CompiledPath'],row['CompiledSHA256'])
        for kind,path,expected in (('source',original,row['OriginalSHA256']),('compiled',compiled,row['CompiledSHA256'])):
            out=package/kind/name;out.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,out)
            assert sha(out.read_bytes())==expected
        snapshots.append({'Source':name,'OriginalFile':'source/'+name,'OriginalSHA256':row['OriginalSHA256'],
            'CompiledFile':'compiled/'+name,'CompiledSHA256':row['CompiledSHA256'],'Changes':row['Changes']})
    # Readable copies of the original bound CPU tools are provenance. Portable
    # verify/reproduce entry points do not import their machine-specific work.
    for row in origins:
        name=row['RepositoryPath']
        if name.startswith('distortion/tools/')and name.endswith('.py'):
            out=package/'source'/name.removeprefix('distortion/');out.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(source_root/name,out)
    target=package/'candidate/hdmi_camera_direct_top.sbit';target.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(roles['Bitstream'],target)
    source_top=(d/'board/hdmi_camera_direct_top.v').read_bytes()
    source_sampler=(d/'rtl/experimental/hdmi_camera_pixel_sampler.v').read_bytes()
    assert sha(source_top)==buildplan['InputSHA256'][str(d/'board/hdmi_camera_direct_top.v')]
    assert sha(source_sampler)==buildplan['InputSHA256'][str(d/'rtl/experimental/hdmi_camera_pixel_sampler.v')]
    files=[]
    for path in sorted(package.rglob('*')):
        if not path.is_file()or path.name=='manifest.json'or '__pycache__'in path.parts:continue
        data=path.read_bytes();files.append({'File':path.relative_to(package).as_posix(),'Bytes':len(data),'SHA256':sha(data)})
    manifest={'Schema':'hdmi-camera1080-direct-display-portable-bundle-v1','Target':'hdmi_camera_direct_top',
        'Resolution':[1920,1080],'SignalFrameRateHz':60,'OutputClockSource':'forwarded input PCLK',
        'UniqueOpticalFPSMeasured':False,'FlashWritten':False,'UserStableMotionDisplayAccepted':True,
        'Objects':list(objects.values()),'OriginIndex':origins,'ExternalInputs':external,
        'Roles':{k:{'OriginalPath':str(v.resolve()),'SHA256':bindings[str(v.resolve())]}for k,v in roles.items()},
        'SourceSnapshots':snapshots,'Files':files,'ExpectedBitstreamBytes':3791112,
        'ExpectedBitstreamSHA256':program['Bitstream']['SHA256'],
        'ExpectedFinalADFSHA256':program['FinalADFSHA256'],
        'VerificationScope':'Portable byte integrity, complete RTL/compiled closure, UART timing replay, '
            'recorded digital/physical assertions, actual bit header/gate/STA summaries, SRAM and user acceptance. '
            'No PDS re-execution, analog AC, bitwise device readback or unique optical FPS claim.'}
    (package/'manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n',encoding='utf-8',newline='\n')
    assert all(sha(Path(p).read_bytes())==h for p,h in bindings.items()),'source changed during archive'
    return {'ArchivedOrigins':len(origins),'ExternalSDKOrRuntimeInputs':len(external),
        'UniqueObjects':len(objects),'Files':len(files),'StoredBytes':sum(f['Bytes']for f in files)}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source-root',type=Path,required=True)
    p.add_argument('--package',type=Path,required=True);args=p.parse_args()
    print(json.dumps(archive(args.source_root,args.package)))
