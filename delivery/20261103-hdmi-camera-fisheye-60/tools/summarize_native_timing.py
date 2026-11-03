"""Read completed native PDS XML reports and emit a compact, reproducible audit.

All slow/fast setup, hold, recovery, removal, pulse-width and skew summaries
are retained. Each clock pair retains its worst 12 reported paths for every
check; only the first setup path per pair carries the detailed arrival chain.
The original .rtr is never opened. This tool does not alter any constraint.
"""
from pathlib import Path
import argparse,hashlib,json,xml.etree.ElementTree as ET
CHECKS=('setup','hold','recovery','removal','mpw','skew')

def sha(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()

def rows(path):
 t=ET.parse(path).getroot().find('table');heads=[e.text or '' for e in t.find('column_headers').findall('data')]
 return [dict(zip(heads,[e.text or '' for e in r.findall('data')])) for r in t.findall('row')]

def classify(row,relations):
 a=row.get('Launch Clock',row.get('Clock',''));b=row.get('Capture Clock',a)
 if a==b and a:return 'same_clock'
 if not a or not b:return 'external_or_unclocked_requires_review'
 relation=relations.get((a,b),{})
 if 'Asynchronous' in relation.get('Inter-Clock Constrains',''):return 'explicit_asynchronous_group'
 if relation.get('Common Primary Clock')=='NO':return 'independent_clock_domains_cdc_review_required'
 if {a,b}&{'ddrphy_sysclk'} and {a,b}&{'phy_dq_sysclk_0','phy_dq_sysclk_1'}:return 'core_to_divided_phy_timed'
 return 'related_clock_domains_timed'

def paths(path,check,relations,limit):
 stack=[];heads=[];groups={};counts={};total=0
 for event,e in ET.iterparse(path,events=('start','end')):
  if event=='start':stack.append(e);continue
  if len(stack)==3 and e.tag=='column_headers':heads=[x.text or '' for x in e.findall('data')]
  if len(stack)==3 and e.tag=='row':
   row=dict(zip(heads,[x.text or '' for x in e.findall('data')]))
   launch=row.get('Launch Clock',row.get('Clock',''));capture=row.get('Capture Clock',launch);key=launch+' -> '+capture
   counts[key]=counts.get(key,0)+1;group=groups.setdefault(key,[])
   if len(group)<limit:
    row['domain_status']=classify(row,relations)
    if check=='setup' and not group:
     detail=e.find('./general_container/table_container/table[@id="arrival"]')
     if detail is not None:
      h=[x.text or '' for x in detail.find('column_headers').findall('data')]
      row['arrival']=[dict(zip(h,[x.text or '' for x in r.findall('data')])) for r in detail.findall('row')]
    group.append(row)
   total+=1;e.clear()
  stack.pop()
 return dict(total_reported_paths=total,reported_per_clock_pair=counts,worst_per_clock_pair=groups)

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--project',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--paths-per-domain',type=int,default=12);a=p.parse_args()
 if not 1<=a.paths_per_domain<=12:p.error('--paths-per-domain must be 1..12')
 project=a.project.resolve();db=project/'prj_tasks/pnr_1/report_timing/report_db';plan_path=project/'candidate-plan.json';plan=json.loads(plan_path.read_text())
 interactions=rows(db/'report_clock_interaction.db');relations={(r['Launch Clock'],r['Capture Clock']):r for r in interactions};hashes={}
 def record(path):hashes[str(path.relative_to(project))]=dict(bytes=path.stat().st_size,sha256=sha(path))
 record(plan_path)
 result=dict(schema='fisheye60-native-timing-summary-v1',project=str(project),source_identity=plan['source_identity'],build_id=plan['build_id'],scope='Diagnostic evidence; physical signoff is incomplete',hardware_accessed=False,summaries={},paths={},clock_interaction=interactions,source_reports=hashes)
 for corner in ['slow','fast']:
  for check in CHECKS:
   name=corner+'_'+check;summary_path=db/f'report_timing_{name}.db';record(summary_path);summary=rows(summary_path)
   for row in summary:row['domain_status']=classify(row,relations)
   result['summaries'][name]=summary
   path=db/f'report_timing_{corner}_path_{check}.db';record(path);result['paths'][name]=paths(path,check,relations,a.paths_per_domain)
  print(corner+' reports parsed',flush=True)
 for name in ['check_timing_summary.db','report_clock_interaction.db','report_timing_clock_summary.db','report_timing_settings.db','report_timing_messages.db']:
  record(db/name)
 result['check_timing']=rows(db/'check_timing_summary.db');issues={r['Check']:r['Number of Issues'] for r in result['check_timing']}
 result['external_io_status']=dict(status='PENDING_EXTERNAL_IO_ACCEPTANCE',no_input_delay=issues.get('no_input_delay'),no_output_delay=issues.get('no_output_delay'),explanation='Internal clock checks do not prove board-level HDMI AC or DDR physical margins; absent IO delays remain reported.')
 result['cdc_status']=dict(status='PENDING_PHYSICAL_CDC_AND_RESET_ACCEPTANCE',independent_pairs=[r for r in interactions if r['Launch Clock']!=r['Capture Clock'] and r['Common Primary Clock']=='NO'],explanation='Independent user clock domains remain timed in these reports. Their setup/hold/recovery/removal figures require CDC/reset interpretation; no exception is added by this summarizer.')
 result['limits']=['Worst paths are sampled from the native reported path list, not all possible paths.','Timing exceptions and vendor IP clock ownership require audit_ddr_constraints.py.','Local CA replication equivalence requires audit_ddr_ca_fanout.py.']
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
 lines=[f'# Native timing: {project.name}',f'\nBuildID `{plan["build_id"]}`, source `{plan["source_identity"]}`. Diagnostic scope; external IO, CDC and reset acceptance remain pending.','\n| Corner/check | Launch | Capture | Worst slack (ns) | Failing endpoints | Domain status |','| --- | --- | --- | ---: | ---: | --- |']
 for check,items in result['summaries'].items():
  for r in items:
   slack=next((r[k] for k in ['WNS(ns)','WHS(ns)','WPWS','WSS'] if k in r),'');fails=next((r[k] for k in ['Failing Endpoints','Failing End Point'] if k in r),'');launch=r.get('Launch Clock',r.get('Clock',''));capture=r.get('Capture Clock',launch)
   lines.append(f'| {check} | {launch} | {capture} | {slack} | {fails} | {r["domain_status"]} |')
 a.output.with_suffix('.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
 print(json.dumps({'output':str(a.output),'bytes':a.output.stat().st_size,'source_identity':plan['source_identity']},indent=2))
if __name__=='__main__':main()
