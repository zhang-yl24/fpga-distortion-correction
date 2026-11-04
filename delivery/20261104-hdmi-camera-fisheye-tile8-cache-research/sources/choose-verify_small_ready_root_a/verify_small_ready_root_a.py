"""Read actual CHOOSE small results and recheck the single-variable control."""
import hashlib
import json
from pathlib import Path
from datetime import datetime, timezone

HERE=Path(__file__).resolve().parent
CONTROL=HERE.parent/'assoc2way256-fifo-a'
CACHE='compiled-sources/rtl/experimental/ddr_neighbour_cache_scatter16_rowpipe_directfill.v'
PINS={'normal':'ea29220793b84dc7c1893a99b764f0a9ae8b9ffaa33a5742bed28fbd22a6815b',
      'sustained':'2fd17b33668a58341d775f3a1fa0b4ac68004b90b4c11424ba73fcb11abcd1b7'}

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def main():
    inputs={}
    def watch(path,pin=None):
        path=Path(path).resolve()
        value=sha(path)
        assert pin is None or pin==value,str(path)
        assert str(path) not in inputs or inputs[str(path)]==value
        inputs[str(path)]=value
    watch(__file__)
    rows=[]
    for kind,pin in PINS.items():
        work=HERE/('system-'+kind+'-small-a')
        control=CONTROL/('system-'+kind+'-small-a')
        path=work/'simulation.json'
        watch(path,pin)
        value=json.loads(path.read_text())
        assert value['Passed'] is True and value['InputDrift']==[]
        assert value['Commands']==[{'Stage':stage,'ReturnCode':0} for stage in ('compile','elaborate','simulate')]
        for name,digest in value['InputSHA256'].items():watch(name,digest)
        for name,digest in value['OutputSHA256'].items():watch(work/name,digest)
        assert len(value['OutputSHA256'])==12
        prepared=[p.relative_to(work).as_posix() for p in (work/'compiled-sources').rglob('*') if p.is_file()]
        headers=[p.relative_to(work).as_posix() for p in (work/'relocated-headers').rglob('*.vh')]
        fixture=['config.vh','timing.vh']+[stem+str(i)+'.mem' for stem in ('source','expected','masks','crc','sourcecrc') for i in range(3)]
        assert len(prepared)==22 and len(headers)==3 and len(fixture)==17
        differences=[]
        for name in prepared+headers+fixture:
            watch(work/name)
            watch(control/name)
            if (work/name).read_bytes()!=(control/name).read_bytes():differences.append(name)
        assert differences==[CACHE]
        assert sha(work/CACHE)=='ea561f9e487e1f03141f13139a8f7ccbb338c2b8e256a4ca81ed73298e6e69d1'
        assert sha(control/CACHE)=='745f4f2cbc26f733d991eca2998484542a131c47f2d747504194f8ecaca95f0b'
        rows.append({'Kind':kind,'Receipt':{'Path':str(path),'SHA256':pin},
            'ActualMonitorSessionID':83503 if kind=='normal' else 55807,
            'ActualMonitorExitCode':0,'ComparedPreparedSources':22,
            'ComparedHeaders':3,'ComparedFixtures':17,'OnlyByteDifference':differences})
    for name,pin in inputs.items():assert sha(name)==pin,name
    result={'Schema':'tile8-choose-small-source-ready-root-v1','Passed':True,
        'ObservedUTC':datetime.now(timezone.utc).isoformat(),'ResearchOnly':True,
        'ActualTwoSmallSystems':rows,'InputSHA256':inputs,'InputDrift':[],
        'NativeSystemPassed':False,'TimingPassed':False,'EDAExecutedByReview':False,
        'HardwareAccessed':False,'ReleaseAllowed':False,
        'Scope':'Both actual small systems and exact same-FIFO input A/B; no native, STA or board acceptance.'}
    with (HERE/'source-ready-root-a.json').open('x',encoding='utf-8') as stream:
        json.dump(result,stream,indent=2)
        stream.write('\n')
    print(json.dumps({'Passed':True,'Files':len(inputs),'SmallSystems':2,'OnlyDifference':CACHE}))

if __name__=='__main__':main()
