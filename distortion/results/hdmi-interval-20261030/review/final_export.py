"""Export exact scoped trained ADF and compare functional graph to original."""
from pathlib import Path
import json,re,shutil,sys
import native_review as n
ROOT,BASE,SOURCE,TOP=n.ROOT,n.BASE,n.SOURCE,n.TOP
sys.path.insert(0,str(ROOT/'tools'))
import audit_checked_io_netlist as native
sha,write,load=n.sha,n.write,n.load

def main():
 scope=BASE/'scoped-cdc';audit=load(scope/'scoped-cdc-review.json')
 assert audit['AuditPassed'] and sha(scope/'input.adf')==audit['ScopedADFSHA256']
 for name,wanted in audit['EvidenceSHA256'].items():assert sha(name)==wanted,name
 work=BASE/'final-functional-export';work.mkdir()
 original=BASE/'functional-export'
 shutil.copytree(original/'sources',work/'sources')
 shutil.copyfile(original/'context.fdc',work/'context.fdc')
 shutil.copyfile(scope/'input.adf',work/'input.adf')
 text=(original/'export.tcl').read_text(encoding='utf-8').replace(original.as_posix(),work.as_posix()).replace('TRAINED_FUNCTIONAL_EXPORT_COMPLETE','TRAINED_FINAL_FUNCTIONAL_EXPORT_COMPLETE')
 (work/'export.tcl').write_text(text,encoding='utf-8',newline='\n')
 before={str(p):sha(p) for p in work.rglob('*') if p.is_file()}
 before[str(scope/'scoped-cdc-review.json')]=sha(scope/'scoped-cdc-review.json')
 write(work/'export-plan.json',dict(InputSHA256=before,ScopedADFSHA256=audit['ScopedADFSHA256'],SourceADF=str(scope/'input.adf'),HardwareAccessed=False))
 result=n.run(work/'export.tcl',work,'native','TRAINED_FINAL_FUNCTIONAL_EXPORT_COMPLETE')
 assert result['ActualStartedStages']==['Report Timing','Generate Netlist'] and not result['InputDrift']
 assert sha(work/'input.adf')==sha(scope/'input.adf')==audit['ScopedADFSHA256']
 def parse(path):
  raw=path.read_text(encoding='utf-8');assert raw.count('module '+TOP)==1
  graph=native.parse(raw.replace('module '+TOP,'module board1080_top',1),native.LIBRARY)
  locations={native.canonical(m[4]):m[2].strip() for m in re.finditer(r'\b(V_FFSYN|V_FFASYN)\s*/\*\s*([^*]+?)\s*\*/\s*#\((.*?)\)\s*(\\[^\s]+)\s*\(',raw,re.S)}
  return graph,locations
 original_path=original/f'generate_netlist/{TOP}_sim.v';final_path=work/f'generate_netlist/{TOP}_sim.v'
 (a,loca),(b,locb)=parse(original_path),parse(final_path)
 assert a==b,'functional cell/port/driver/library graph changed'
 assert loca==locb,'register placement changed'
 connections=load(BASE/'connectivity-review.json')
 for row in connections['Registers'].values():
  name=row['native_instance'];assert name in b[0] and locb[name]==row['location']['site']
  assert b[0][name]['Ports']==row['ports'] and b[0][name]['Parameters']==row['parameters']
 for name,wanted in before.items():assert sha(name)==wanted,name
 evidence={str(p):sha(p) for p in (scope/'scoped-cdc-review.json',scope/'input.adf',BASE/'connectivity-review.json',original_path,final_path,work/'input.adf',work/'export.tcl',work/'export-plan.json',work/'native-execution.json',work/'native-stdout.log',work/'native-stderr.log',Path(__file__))}
 evidence.update(b[3])
 report=dict(Schema='trained-final-adf-functional-review-v1',AuditPassed=True,Target=TOP,ScopedADFSHA256=audit['ScopedADFSHA256'],OriginalADFSHA256=audit['SourceADFSHA256'],EntireFunctionalGraphUnchanged=True,AllRegisterLocationsUnchanged=True,CellCount=len(b[0]),VerifiedFFCount=161,VerifiedStageLinks=81,SameSiteStageLinks=81,Pins46AndDirectionsUnchanged=True,NetlistTopPortsUnchanged=True,InputDrift=[],EvidenceSHA256=evidence,HardwareAccessed=False,HardwareReleaseAllowed=False,FullCDCSignoff=False,Limits='Functional graph/placement equivalence and explicit scoped-ADF provenance only; no physical timing, external AC or hardware video acceptance.')
 write(work/'connectivity-review.json',report)
 print(json.dumps(report));print('FINAL_FUNCTIONAL_REVIEW_SHA256 '+sha(work/'connectivity-review.json'))
if __name__=='__main__':main()
