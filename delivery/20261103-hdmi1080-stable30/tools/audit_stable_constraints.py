"""Independent audit of stable30 constraints and emitted PDS evidence.

This script reads the prepared build and writes one JSON report. It neither
edits the project nor runs PDS. Missing later stages remain explicitly pending.
Use --require-final after the final routed STA exists.
"""
from pathlib import Path
import argparse,hashlib,itertools,json,re,xml.etree.ElementTree as ET

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def commands(path):
    return [line.strip() for line in path.read_text(encoding='utf-8-sig').splitlines()
            if line.strip() and not line.lstrip().startswith('#')]
def rows(path):
    table=ET.parse(path).getroot().find('table')
    headers=[x.text or '' for x in table.find('column_headers').findall('data')]
    return [dict(zip(headers,[d.text or '' for d in r.findall('data')])) for r in table.findall('row')]
def clock_audit(path):
    table=ET.parse(path).getroot().find('table')
    isclock=lambda row: bool(re.match(r'^\S+ \([\d.]+MHZ\) \(drive',row.findtext('data','')))
    def leaves(row):
        children=row.findall('row')
        if not children: yield row.findtext('data','').rsplit(' (',1)[0]
        for child in children:
            if not isclock(child): yield from leaves(child)
    result=[]
    for row in table.iter('row'):
        if not isclock(row): continue
        label=row.findtext('data');name=label.split()[0];pins=list(leaves(row))
        expected=int(re.search(r'\(drive (\d+) loads\)',label).group(1))
        outside=[p for p in pins if not p.startswith('u_ddr3_test_h/')]
        item={'clock':name,'tool_load_count':expected,'parsed_load_count':len(pins),'count_matches':expected==len(pins),'outside_ip_count':len(outside)}
        if name in IP_DOMAINS: item['all_endpoint_pins']=pins;item['unexpected_user_pins']=outside
        result.append(item)
    return result

USER=['board27','cfg_clk','input_pixel','pixel_clk','ddrphy_sysclk']
GROUPS=['rst_clk','phy_dq_clk_0','phy_dq_clk_1']
IP_DOMAINS=set(GROUPS+['phy_dq_sysclk_0','phy_dq_sysclk_1'])
p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
p.add_argument('--require-final',action='store_true');p.add_argument('--diagnostic-report-db',type=Path)
a=p.parse_args();b=a.build.resolve();errors=[];pending=[];checks=[]
def check(name,ok,detail=None):
    checks.append({'name':name,'pass':bool(ok),'detail':detail})
    if not ok: errors.append(name)
diag=b/'native/source/build/offline-20261024/boardtop-penn-prep-20261029-a/board1080-diagnostic.fdc'
ipfdc=b/'native/stable-constraints/ddr-ip-clock-relations.fdc'
rcf=b/'native/stable-constraints/vendor-ddr.rcf';uart=b/'uart-pins.fdc'
files=[diag,ipfdc,rcf,uart]
for f in files: check('file_exists:'+f.name,f.is_file())
if errors: a.output.write_text(json.dumps({'status':'FAIL','errors':errors},indent=2),encoding='utf8');raise SystemExit(1)
fdcs=[diag,ipfdc,uart];allcmd=[line for f in fdcs for line in commands(f)]
groups=[s for s in allcmd if s.startswith('set_clock_groups')]
expected=[f'set_clock_groups -name {g} -asynchronous -group [get_clocks {{{g}}}]' for g in GROUPS]
check('exactly_three_vendor_clock_groups',sorted(groups)==sorted(expected),groups)
check('no_new_false_path',not any(s.startswith('set_false_path') for s in allcmd))
pairs=[]
for src,dst in itertools.permutations(USER,2):
    mx=f'set_max_delay -datapath_only -from [get_clocks {{{src}}}] -to [get_clocks {{{dst}}}] 8.0'
    mn=f'set_min_delay -from [get_clocks {{{src}}}] -to [get_clocks {{{dst}}}] 0.0'
    pairs.append({'from':src,'to':dst,'max8':allcmd.count(mx)==1,'min0':allcmd.count(mn)==1})
check('all_20_directed_user_pairs_keep_max8_min0',all(d['max8'] and d['min0'] for d in pairs),pairs)
preserved=[]
for bank in [0,1]:
    phy=f'phy_dq_sysclk_{bank}'
    preserved.append(f'set_multicycle_path 2 -from [get_clocks ddrphy_sysclk] -to [get_clocks {phy}]')
    for x,y in [('ddrphy_sysclk',phy),(phy,'ddrphy_sysclk')]:
        preserved.append(f'set_clock_uncertainty {{0.4}} -from [get_clocks {{{x}}}] -to [get_clocks {{{y}}}] -setup -hold')
check('core_divided_phy_multicycle_and_uncertainty_retained',all(allcmd.count(s)==1 for s in preserved),preserved)
expected_routes=[f'def_route -prior_net {{u_ddr3_test_h/u_ddrphy_top/ddrphy_ioclk_gate [{i}]}}' for i in [0,1]]
check('two_vendor_priority_route_clauses',commands(rcf)==expected_routes,commands(rcf))
prep=json.loads((b/'preparation.json').read_text(encoding='utf-8-sig'))
manifest={r['path']:r for r in prep['files']}
for f in [ipfdc,rcf]:
    rel=f.relative_to(b/'native').as_posix();r=manifest.get(rel)
    check('prepared_manifest_hash:'+f.name,r is not None and r.get('compile_sha256')==sha(f),r)

projects=[]
for stage in ['map','route','sta','bitstream']:
    project=b/'stages'/stage/'board1080_top.pds'
    if not project.exists(): pending.append('native PDS not present:'+stage);continue
    try: root=ET.parse(project).getroot()
    except ET.ParseError:
        pending.append('native PDS being written:'+stage);continue
    items=[{'file':str((project.parent/item.attrib['file']).resolve()),'format':item.attrib.get('format')} for item in root.findall('.//inputs/item') if 'file' in item.attrib]
    selected=[i for i in items if Path(i['file']).suffix.lower() in ['.fdc','.rcf']]
    projects.append({'stage':stage,'project':str(project),'constraint_items':selected})
    for f,fmt in [(diag,'fdc'),(ipfdc,'fdc'),(uart,'fdc'),(rcf,'rcf')]:
        matching=[i for i in selected if Path(i['file'])==f.resolve() and i['format']==fmt]
        check(f'native_{stage}_constraint_registered:{f.name}',bool(matching))

route_log=b/'stages/route/prj_tasks/pnr_1/place_route/run_route.log'
route_evidence=[]
priority_resolved=False
if route_log.exists():
    for log in [route_log,b/'stages/route/run.log',b/'stages/route/prj_tasks/pnr_1/place_route/run_place.log',b/'stages/route/prj_tasks/pnr_1/place_route/run_route_optimize.log']:
        if not log.exists(): continue
        lines=log.read_text(encoding='utf8',errors='replace').splitlines()
        route_evidence += [{'file':str(log),'line':i+1,'text':s} for i,s in enumerate(lines) if re.search(r'rcf|prior.?net|prior.?rout|route.?cons|ddrphy_ioclk_gate',s,re.I)]
    route_text=route_log.read_text(encoding='utf8',errors='replace')
    priority_resolved=all(f'Executing : {cmd} successfully.' in route_text for cmd in expected_routes)
    check('route_executed_both_vendor_priority_net_commands',priority_resolved)
else: pending.append('route log not present')
report_db=b/'stages/sta/prj_tasks/pnr_1/report_timing/report_db'
network=report_db/'report_clock_network_slow.db'
clocks=[];interactions=[];compare=None
if network.exists():
    clocks=clock_audit(network)
    check('final_clock_tree_complete',all(c['count_matches'] for c in clocks))
    check('all_required_ip_clocks_exist',IP_DOMAINS<={c['clock'] for c in clocks})
    check('ip_clocks_have_no_user_endpoints',all(c['outside_ip_count']==0 for c in clocks if c['clock'] in IP_DOMAINS))
    interaction_file=report_db/'report_clock_interaction.db'
    interactions=rows(interaction_file)
    preserve=lambda src,dst: src==dst or (src in USER and dst in USER) or ({src,dst}&{'ddrphy_sysclk'} and {src,dst}&{'phy_dq_sysclk_0','phy_dq_sysclk_1'})
    preserved_rows=[r for r in interactions if preserve(r['Launch Clock'],r['Capture Clock'])]
    check('preserved_relations_remain_timed',all('Asynchronous Groups' not in r['Inter-Clock Constrains'] and 'False Path' not in r['Inter-Clock Constrains'] for r in preserved_rows),preserved_rows)
    grouped=[r for r in interactions if r['Launch Clock']!=r['Capture Clock'] and ({r['Launch Clock'],r['Capture Clock']}&set(GROUPS))]
    check('ip_grouped_crossings_use_vendor_relation',all(r['Inter-Clock Constrains']=='Asynchronous Groups' for r in grouped),grouped)
    if a.diagnostic_report_db:
        old=rows(a.diagnostic_report_db/'report_clock_interaction.db')
        indexed={(r['Launch Clock'],r['Capture Clock']):r for r in interactions}
        old_grouped=[r for r in old if r['Launch Clock']!=r['Capture Clock'] and ({r['Launch Clock'],r['Capture Clock']}&set(GROUPS))]
        check('diagnostic_really_removes_inherited_ip_clock_groups',bool(old_grouped) and all(r['Inter-Clock Constrains']!='Asynchronous Groups' for r in old_grouped),old_grouped)
        provenance_path=a.diagnostic_report_db.parents[3]/'diagnostic-provenance.json'
        if provenance_path.exists():
            provenance=json.loads(provenance_path.read_text(encoding='utf8'))
            final_adf=b/'stages/route/prj_tasks/pnr_1/place_route/board1080_top_pnr.adf'
            check('diagnostic_uses_identical_final_routed_adf',provenance.get('input_adf_unchanged') and provenance['inputs'][0]['sha256']==sha(final_adf),provenance)
        else: check('diagnostic_provenance_present',False,str(provenance_path))
        compare=[]
        for r in old:
            key=(r['Launch Clock'],r['Capture Clock'])
            if preserve(*key): compare.append({'from':key[0],'to':key[1],'identical':r==indexed.get(key),'diagnostic':r,'vendor':indexed.get(key)})
        check('same_routed_adf_preserved_rows_identical',all(r['identical'] for r in compare),compare)
else: pending.append('final STA clock network not present')

if a.require_final and pending: errors+=pending
result={'schema':'stable30-ddr-constraint-audit-v1','build':str(b),'candidate_param_id':prep.get('param_id_hex'),'status':'FAIL' if errors else ('PASS_WITH_PENDING_STAGES' if pending else 'PASS'),'errors':errors,'pending':pending,'files':[{'path':str(f),'sha256':sha(f)} for f in files],'checks':checks,'native_projects':projects,'route_log_evidence':route_evidence,'priority_net_resolution_status':'both commands reported successful in route execution' if priority_resolved else 'not yet proven by route execution','clock_endpoints':clocks,'same_adf_comparison':compare,'limitations':['This audit confirms constraint scope and emitted evidence, not hardware reset reliability.','Protected ips2l_rst_sync_v1_3 internal synchronizer depth has not been independently verified.','Board external IO AC timing closure is separate.']}
a.output.write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf8')
print(json.dumps({'status':result['status'],'errors':errors,'pending':pending,'output':str(a.output),'checks':len(checks)},ensure_ascii=False))
raise SystemExit(1 if errors else 0)
