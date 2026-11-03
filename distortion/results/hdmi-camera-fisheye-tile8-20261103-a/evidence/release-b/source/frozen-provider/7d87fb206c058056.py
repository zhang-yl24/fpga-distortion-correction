"""Freeze completed candidate source, warning and parser evidence, CPU only."""
import ast
import hashlib
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

WORK=Path(__file__).resolve().parent
ROOT=WORK.parents[1]
TOOLS=ROOT/'tools'
sys.path.insert(0,str(TOOLS))
import hdmi_camera_fisheye_tile8_audit as audit
import hdmi_camera_fisheye_tile8_protocol as protocol
import hdmi_camera_fisheye_tile8_startup as startup
import hdmi_camera_fisheye_tile8_warnings as warnings

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def ref(p):return {'Path':str(Path(p).resolve()),'SHA256':sha(p)}
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def functions(text):
    return {n.name:ast.dump(n,include_attributes=False) for n in ast.parse(text).body if isinstance(n,ast.FunctionDef)}

output=WORK/'audit-provider-source-manifest-a.json'
assert not output.exists()
old_hashes={'audit':'678b540abb5dce6119b899a4a1fdb579a775d4114856dcba95737d8fef791a0f',
            'protocol':'2a66eccf2c6db9583eef45e00602be29b3ca2310324453e1ae3ede66bc9b046c',
            'startup':'1fb5aa1cb3160f23291fdfe44cad9e93caa02f075c67c56d6dfcecd3f0e6c289',
            'warnings':'e21acf5f39b180653ff045cc643807c840694b8c5ff31026e2bf2d18284130d7'}
changes={'audit':{'atoms'},'protocol':{'source_review'},'startup':set(),
         'warnings':{'source_facts','bind_simulation_receipts','derive'}}
rows=[]
for part,module in [('audit',audit),('protocol',protocol),('startup',startup),('warnings',warnings)]:
    old=TOOLS/('hdmi_camera_fisheye_fill8r3s3_'+part+'.py');new=Path(module.__file__)
    assert sha(old)==old_hashes[part]
    oldtext=old.read_text(encoding='utf-8-sig').replace('fill8r3s3','tile8').replace('FILL8R3S3','TILE8')
    newtext=new.read_text(encoding='utf-8-sig')
    before,after=functions(oldtext),functions(newtext)
    for name,node in before.items():
        if name not in changes[part]:assert after.get(name)==node,(part,name)
    rows.append({'Role':part,'Original':ref(old),'New':ref(new),'Schema':module.SCHEMA,
                 'ChangedOriginalFunctions':sorted(changes[part]),
                 'AllOtherOriginalFunctionASTEqualAfterExactNamespaceMapping':True})
assert warnings.INVENTORY_SHA==sha(warnings.INVENTORY)
proof=read(WORK/'source-warnings-a.json')
assert proof['Passed']is True and proof['SourceDiagnosticReviewPassed']is True
assert proof['Inventory']==ref(warnings.INVENTORY)
assert proof['TimingAccepted']is False and proof['HardwareReleaseAllowed']is False
assert read(WORK/'atoms-cache-equivalence-a.json')['Passed']is True
report=ET.parse(WORK/'audit-provider-final-regression-a.xml').getroot()
suites=report.findall('testsuite') if report.tag!='testsuite' else [report]
assert sum(int(s.attrib['tests'])for s in suites)==145
assert all(int(s.attrib.get(k,0))==0 for s in suites for k in ('failures','errors','skipped'))
inputs={}
for row in rows:
    for group in ('Original','New'):inputs[row[group]['Path']]=row[group]['SHA256']
files=[TOOLS/'hdmi_camera_fisheye_macro_modes.py',WORK/'source-warning-inventory-a.json',WORK/'source-warning-diff-completed-a.json',
       WORK/'source-warnings-a.json',WORK/'atoms-cache-equivalence-a.json',WORK/'audit-provider-final-regression-a.xml',
       WORK/'engine-exact-source-diff-a.json',WORK/'build-protocol-independent-peer-a.json',WORK/'native-semantic-comparison-a.json',
       Path(__file__)]
files += [ROOT/'tests'/('test_hdmi_camera_fisheye_tile8_'+part+'.py') for part in ('audit','protocol','startup','warnings','warning_binding','candidate_contracts')]
for p in files:inputs[str(p.resolve())]=sha(p)
assert all(sha(p)==h for p,h in inputs.items())
value={'Schema':'hdmi-camera-fisheye-tile8-audit-provider-source-freeze-v1','Passed':True,
       'Providers':rows,'InputSHA256':dict(sorted(inputs.items())),
       'Tests':{'Passed':145,'Skipped':0,'Failures':0,'Report':ref(WORK/'audit-provider-final-regression-a.xml')},
       'WarningProof':ref(WORK/'source-warnings-a.json'),'WarningInventory':ref(warnings.INVENTORY),
       'ActualCompletedBuildRequired':True,'WarningsDerivedFromOwnEightLogs':True,
       'OldS3ProvidersUnchanged':True,'PureAtomsSemantics':ref(WORK/'atoms-cache-equivalence-a.json'),
       'HelperMacroModesSharedAndUnchanged':True,'NativeAuditAcceptanceNotInherited':True,
       'EDAExecuted':False,'HardwareAccessed':False,'TimingOrHardwareAcceptanceGranted':False}
with output.open('x',encoding='utf-8',newline='\n')as f:json.dump(value,f,ensure_ascii=False,indent=2);f.write('\n')
print(json.dumps({'Passed':True,'Manifest':ref(output),'Providers':[{k:r[k]for k in ('Role','New','Schema')}for r in rows],
                  'WarningProof':ref(WORK/'source-warnings-a.json')}))
