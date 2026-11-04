"""Audit C-matched vendor IP, exact constraints and optional native PDS evidence.
Read-only toward sources and implementation; writes the requested JSON report.
"""
from pathlib import Path
import argparse,hashlib,json,re,subprocess,xml.etree.ElementTree as ET
PACKAGE=Path(__file__).resolve().parents[1]
VENDOR='vendor/reference/ddr/2_9_ddr3_test/2_9_ddr3_test/ddr3_test/'
IP_FILES=['ddr3_test.idf','ddr3_test.v','ddr3_test_ddrphy_top.v','rtl/ips2l_rst_sync_v1_3.vp','rtl/ddrphy/ips2l_ddrphy_reset_ctrl_v1_3.vp','rtl/ddrphy/ddr3_test_slice_top_v1_10.v']
GROUPS=['rst_clk','phy_dq_clk_0','phy_dq_clk_1']
IP_DOMAINS=set(GROUPS+['phy_dq_sysclk_0','phy_dq_sysclk_1'])
def digest(b):return hashlib.sha256(b).hexdigest()
def commands(s):return [v.strip() for v in s.splitlines() if v.strip() and not v.lstrip().startswith('#')]
def rows(path):
 table=ET.parse(path).getroot().find('table');headers=[v.text or '' for v in table.find('column_headers').findall('data')]
 return [dict(zip(headers,[v.text or '' for v in r.findall('data')])) for r in table.findall('row')]
def clock_audit(path):
 table=ET.parse(path).getroot().find('table')
 isclock=lambda r:bool(re.match(r'^\S+ \([\d.]+MHZ\) \(drive',r.findtext('data','')))
 def leaves(r):
  children=r.findall('row')
  if not children and not isclock(r):yield r.findtext('data','').rsplit(' (',1)[0]
  for c in children:
   if not isclock(c):yield from leaves(c)
 result=[]
 for r in table.iter('row'):
  if not isclock(r):continue
  label=r.findtext('data');name=label.split()[0];pins=list(leaves(r));count=int(re.search(r'\(drive (\d+) loads\)',label).group(1))
  result.append(dict(clock=name,tool_load_count=count,parsed_load_count=len(pins),count_matches=count==len(pins),unexpected_user_pins=[v for v in pins if not v.startswith('u_ddr3_test_h/')] if name in IP_DOMAINS else [],endpoint_pins_sha256=digest(('\n'.join(pins)+'\n').encode())))
 return result

def main():
 p=argparse.ArgumentParser();p.add_argument('--repo',type=Path,default=PACKAGE.parents[1]);p.add_argument('--reference-ref',default='HEAD');p.add_argument('--output',type=Path,required=True)
 p.add_argument('--native-project',type=Path,action='append',default=[]);p.add_argument('--route-log',type=Path);p.add_argument('--report-db',type=Path);p.add_argument('--require-native',action='store_true');a=p.parse_args()
 repo=a.repo.resolve();checks=[];pending=[];result=dict(schema='fisheye60-ddr-audit-v1',hardware_accessed=False,checks=checks,pending=pending)
 def check(name,ok,detail=None):checks.append(dict(name=name,pass_=bool(ok),detail=detail))
 def git(path):return subprocess.check_output(['git','-C',str(repo),'show',a.reference_ref+':'+path])
 ip=repo/'distortion/platform/video_base/ipcore/ddr3_test';reference_files=[]
 for rel in IP_FILES:
  ref=git(VENDOR+'ipcore/ddr3_test/'+rel);actual=(ip/rel).read_bytes()
  reference_files.append(dict(relative=rel,reference_sha256=digest(ref),current_sha256=digest(actual),exact_match=actual==ref))
 check('six_generated_ip_files_exactly_match_vendor',all(v['exact_match'] for v in reference_files),reference_files)
 current=ET.fromstring((ip/'ddr3_test.idf').read_bytes());reference=ET.fromstring(git(VENDOR+'ipcore/ddr3_test/ddr3_test.idf'))
 params=lambda root:{x.findtext('name'):x.findtext('value') for x in root.find('param_list').findall('param')}
 cp,rp=params(current),params(reference);diff=[k for k in cp.keys()|rp.keys() if cp.get(k)!=rp.get(k)]
 check('all_371_idf_parameters_match',len(cp)==371 and not diff,dict(count=len(cp),differences=diff))
 result['ip_header']={x.tag:dict(text=x.text,attributes=x.attrib) for x in current.find('header')}
 fdc=PACKAGE/'constraints/hdmi-camera-fisheye-60-internal.fdc';groups=PACKAGE/'constraints/ddr-ip-clock-relations.fdc';rcf=PACKAGE/'constraints/board1080-ddr-ioclk-priority.rcf'
 main_cmd=commands(fdc.read_text());group_cmd=commands(groups.read_text());route_cmd=commands(rcf.read_text())
 vendor_fdc=git(VENDOR+'ipcore/ddr3_test/pnr/ddr_test.fdc').decode('utf-8-sig')
 vendor_cmd=commands(vendor_fdc.replace('I_ips_ddr_top','u_ddr3_test_h').replace('ref_clk_p','clk_p'))
 ddr_cmd=[v for v in vendor_cmd if v.startswith(('create_generated_clock','set_multicycle_path','set_clock_uncertainty'))]
 check('six_generated_ddr_clocks_and_core_phy_relations_match',len(ddr_cmd)==12 and all(v in main_cmd for v in ddr_cmd),ddr_cmd)
 expected_groups=[f'set_clock_groups -name {v} -asynchronous -group [get_clocks {{{v}}}]' for v in GROUPS]
 check('three_exact_vendor_owned_clock_groups',group_cmd==expected_groups and all(v in vendor_cmd for v in expected_groups),group_cmd)
 check('main_fdc_has_no_broad_exception',not any(v.startswith(('set_false_path','set_clock_groups','set_max_delay','set_min_delay')) for v in main_cmd))
 vendor_route=commands(git(VENDOR+'ipcore/ddr3_test/pnr/ddr3_test.rcf').decode().replace('I_ips_ddr_top','u_ddr3_test_h'))
 check('two_exact_mapped_vendor_route_priorities',route_cmd==vendor_route and len(route_cmd)==2,route_cmd)
 check('forwarded_output_clock_constraint',main_cmd.count('create_generated_clock -name pixel_clk -source [get_ports pixclk_in] -divide_by 1 [get_ports pix_clk]')==1)
 top=(PACKAGE/'rtl/hdmi_camera_fisheye_top.v').read_text();check('source_clock_forwarded_without_video_pll','assign pix_clk=pixclk_in;' in top and 'bringup_pll' not in top and 'video_lock' not in top)
 result['constraint_sha256']={str(v):digest(v.read_bytes()) for v in [fdc,groups,rcf]}
 if not a.native_project:pending.append('native PDS constraint registration')
 for project in a.native_project:
  items=ET.parse(project).getroot().findall('.//inputs/item');loaded=[]
  for item in items:
   if 'file' not in item.attrib:continue
   f=(project.parent/item.attrib['file']).resolve()
   if f.suffix.lower() in ['.fdc','.rcf']:loaded.append(dict(path=str(f),format=item.attrib.get('format'),sha256=digest(f.read_bytes()) if f.exists() else None))
  for f in [fdc,groups,rcf]:check('native_registered:'+str(project)+':'+f.name,any(v['sha256']==digest(f.read_bytes()) and v['format']==f.suffix[1:] for v in loaded),loaded)
 if a.route_log:
  text=a.route_log.read_text(errors='replace');check('route_executed_both_priority_commands',all('Executing : '+v+' successfully.' in text for v in route_cmd))
 else:pending.append('route priority commands resolved/executed')
 if a.report_db:
  clocks=clock_audit(a.report_db/'report_clock_network_slow.db');result['clock_ownership']=clocks
  check('clock_tree_parsing_counts_match',all(v['count_matches'] for v in clocks))
  check('all_ip_domains_present',IP_DOMAINS<={v['clock'] for v in clocks})
  check('ip_clock_endpoints_stay_within_ddr',all(not v['unexpected_user_pins'] for v in clocks if v['clock'] in IP_DOMAINS))
  interactions=rows(a.report_db/'report_clock_interaction.db');user={'board27','cfg_clk','input_pixel','pixel_clk','ddrphy_sysclk'}
  preserved=[v for v in interactions if v['Launch Clock']==v['Capture Clock'] or (v['Launch Clock'] in user and v['Capture Clock'] in user) or ({v['Launch Clock'],v['Capture Clock']}&{'ddrphy_sysclk'} and {v['Launch Clock'],v['Capture Clock']}&{'phy_dq_sysclk_0','phy_dq_sysclk_1'})]
  check('user_and_core_divided_phy_relations_still_timed',bool(preserved) and all('Asynchronous Groups' not in v['Inter-Clock Constrains'] and 'False Path' not in v['Inter-Clock Constrains'] for v in preserved),preserved)
 else:pending.append('final clock ownership and clock interaction reports')
 errors=[v['name'] for v in checks if not v['pass_']]
 if a.require_native:errors+=pending
 result['status']='FAIL' if errors else ('PASS_STATIC_PENDING_NATIVE' if pending else 'PASS');result['errors']=errors
 result['limitations']=['Native audit checks constraint scope, not setup/hold slack closure.','External HDMI IO and physical CDC/reset release need their own acceptance.','Protected vendor reset synchronizer internals are not independently proven.']
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps(dict(status=result['status'],errors=errors,pending=pending,output=str(a.output)),indent=2))
 raise SystemExit(1 if errors else 0)
if __name__=='__main__':main()
