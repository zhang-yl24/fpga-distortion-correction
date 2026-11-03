from pathlib import Path
import collections, hashlib, json, re, xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parent
PACKAGE=Path('D:/f60/delivery/20261103-hdmi-camera-fisheye-60')
source=PACKAGE/'rtl/video_async_fifo.v'
baseline=Path('D:/f60-work/system-final-f-rowpad640-fanout16/compiled/rtl/video_async_fifo.v')
vm=ROOT/'prj_tasks/syn_1/synthesize/fifo_cdc_probe_syn.vm'
mapped=ROOT/'prj_tasks/pnr_1/place_route/fifo_cdc_probe_route_optimize.netlist'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def functional_tokens(p):
    s=re.sub(r'/\*.*?\*/|//[^\n]*|\(\*.*?\*\)','',p.read_text(),flags=re.S)
    return re.findall(r'[A-Za-z_$][\w$]*|\d+|[^\s]',s)
netlist=mapped.read_text()
cells=dict(re.findall(r'^([^;\n]+);(gop\w+)\s*$',netlist,re.M))
syn_text=vm.read_text()
reset_aliases={family:('.'+family+' ({\\capture_size/'+family+" [1], 1'bx})") in syn_text
               for family in ('wr_reset_sync','rd_reset_sync')}
checks=[]
for inst,bits in [('capture_size',7),('display_size',10)]:
    for family,n in [('rd_gray_w1',bits),('rd_gray_w2',bits),('wr_gray_r1',bits),('wr_gray_r2',bits),
                     ('wr_reset_sync',2),('rd_reset_sync',2)]:
        for bit in range(n):
            base=f'{inst}/{family}[{bit}]/'
            physical_base=base
            if inst=='display_size' and family in reset_aliases and reset_aliases[family]:
                physical_base=f'capture_size/{family}[{bit}]/'
            found={name:typ for name,typ in cells.items() if name.startswith(physical_base)}
            checks.append({'register':base[:-1],'mapped':found,'shared_reset_alias':physical_base!=base,
                           'passed':len(found)==1 and list(found.values())==['gopQ']})
root=ET.parse(ROOT/'prj_tasks/syn_1/synthesize/report_db/synthesize_report_cdc_summary.db').getroot()
headers=[x.text for x in root.find('table/column_headers')]
cdc=[]
for row in root.iter('row'):
    data=[x.text or '' for x in row.findall('data')]
    item=dict(zip(headers,data))
    if re.search(r'/(?:rd_gray_w1|wr_gray_r1)\[',item.get('Endpoint','')):
        cdc.append(item)
attribute_pairs=len(re.findall(r'PAP_ASYNC_REG="TRUE", PAP_SRL_STYLE="registers"',syn_text))
compile_log=(ROOT/'prj_tasks/syn_1/compile/run.log').read_text(errors='replace')
report={
    'passed':all(c['passed'] for c in checks) and len(checks)==76 and attribute_pairs==72 and
        functional_tokens(source)==functional_tokens(baseline) and all(r['Category']=='Safe' for r in cdc),
    'scope':'Two FIFO pointer sizes after native PDS compile, ADS synthesis, device map, place, route and report timing. Eight-bit payload reduces probe size; native full-design CDC routing/skew is separate. External probe port IO delays are unconstrained; CDC checks here cover only the internal Gray source-to-first-stage paths.',
    'attributes':'(* PAP_ASYNC_REG=1, syn_srlstyle="registers" *)',
    'syn_preserve_used':False,'expected_gray_flops':68,'logical_reset_flops':8,'physical_reset_flops':4,
    'shared_reset_explanation':'Both probe instances use identical clocks and common reset. Synthesis shares the two complete two-FF local reset chains; display_size consumes capture_size stage-two reset outputs. No chain is reduced below two FFs.',
    'shared_reset_binding_verified':reset_aliases,
    'mapped_flop_checks':checks,'native_attribute_pairs':attribute_pairs,
    'mapped_srl_cells':{k:v for k,v in cells.items() if 'SRL' in v},
    'fifo_functional_tokens_equal_to_f_system':functional_tokens(source)==functional_tokens(baseline),
    'baseline_f_system_fifo_sha256':sha(baseline),'overlay_fifo_sha256':sha(source),
    'f_system_report_sha256':sha(baseline.parents[2]/'system-report.json'),
    'synth_vm_sha256':sha(vm),'mapped_netlist_sha256':sha(mapped),
    'cdc_rows':cdc,'cdc_categories':dict(collections.Counter(r['CDC ID']+' '+r['Description'] for r in cdc)),
    'attribute_rejection':bool(re.search(r'(?:PAP_ASYNC_REG|syn_srlstyle).*not legal|not legal.*(?:PAP_ASYNC_REG|syn_srlstyle)',compile_log)),
    'broad_clock_groups_or_falsepaths_added':False,
}
assert not report['mapped_srl_cells']
assert report['passed'],report
(ROOT/'probe-verification.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k not in ('mapped_flop_checks','cdc_rows')},indent=2))
