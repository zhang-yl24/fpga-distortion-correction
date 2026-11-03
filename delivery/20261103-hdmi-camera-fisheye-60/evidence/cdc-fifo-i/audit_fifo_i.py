from pathlib import Path
import collections,hashlib,json,re,xml.etree.ElementTree as ET
BASE=Path('D:/f60-run/physical-i')
OUT=Path('D:/f60-work/cdc/fifo-i');OUT.mkdir(exist_ok=True)
vm=BASE/'prj_tasks/syn_1/synthesize/hdmi_camera_fisheye_top_syn.vm'
text=vm.read_text(errors='replace')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def cells(block):
    result={}
    pat=r'(?m)^(?:\(\*([^\n]*)\*\)\s*)?\s*(GTP_DFF\w*)\s+#\([^;]*?\)\s+\\([^\s]+)\s+\((.*?)\);'
    for c in re.finditer(pat,block,re.S):
        result[c[3]]={'primitive':c[2],'attributes':c[1] or '',
                      'ports':{k:v.strip() for k,v in re.findall(r'\.(\w+)\s*\(([^)]+)\)',c[4])}}
    return result
modules={}
for m in re.finditer(r'(?m)^module (video_async_fifo(?:_\d+)?)\b',text):
    block=text[m.start():text.index('endmodule',m.end())+9]
    modules[m[1]]={'cells':cells(block),'header':block[:block.index(');')+2]}
    (OUT/(m[1]+'-synth.v')).write_text(block)
pairs=[]
for module,inst,bits in [('video_async_fifo_1','system/display_fifo',10),('video_async_fifo','system/input_link/input_dma/capture/pixels',7)]:
    c=modules[module]['cells']
    for source,first,second in [('wr','wr_gray_r1','wr_gray_r2'),('rd','rd_gray_w1','rd_gray_w2')]:
        for i in range(bits):
            a,b=c[f'{first}[{i}]'],c[f'{second}[{i}]']
            allowed_sources=[f'{source}_gray[{i}]']+([f'{source}_binary[{i}]'] if i==bits-1 else [])
            source_wire=a['ports']['D']
            source_cells={name:cell for name,cell in c.items() if cell['ports'].get('Q')==source_wire}
            pair={'instance':inst,'bit':i,'source_wire':source_wire,'source_cells':source_cells,'first':first,'second':second,
                  'stage1':a,'stage2':b,
                  'direct_source_to_stage1':source_wire in allowed_sources and len(source_cells)==1,
                  'direct_stage1_to_stage2':a['ports']['Q']==b['ports']['D'],
                  'same_destination_clock':a['ports']['CLK']==b['ports']['CLK'],
                  'native_attributes':all('PAP_ASYNC_REG="TRUE"' in x['attributes'] and 'PAP_SRL_STYLE="registers"' in x['attributes'] for x in (a,b))}
            pair['passed']=all(pair[k] for k in ('direct_source_to_stage1','direct_stage1_to_stage2','same_destination_clock','native_attributes'))
            pairs.append(pair)
top_start=re.search(r'(?m)^module hdmi_camera_fisheye_top\b',text).start()
top=cells(text[top_start:text.index('endmodule',top_start)+9])
reset_owners={'core_reset':{f'core_reset[{i}]':top[f'core_reset[{i}]'] for i in (0,1)},
              'system/display_fifo/rd_reset_sync':{f'rd_reset_sync[{i}]':modules['video_async_fifo_1']['cells'][f'rd_reset_sync[{i}]'] for i in (0,1)}}
reset_checks=[]
for owner,regs in reset_owners.items():
    a,b=regs.values()
    reset_checks.append({'owner':owner,'direct_stage1_to_stage2':a['ports']['Q']==b['ports']['D'],
        'stage1_constant_one':a['ports']['D']=="1'b1",'common_clock':a['ports']['CLK']==b['ports']['CLK'],
        'common_async_clear':a['ports']['C']==b['ports']['C'],
        'native_attributes':all('PAP_ASYNC_REG="TRUE"' in c['attributes'] and 'PAP_SRL_STYLE="registers"' in c['attributes'] for c in (a,b))})
binding_strings=[
    '.core_reset_sync ({core_reset[1], 1\'bx})',
    '.wr_reset_sync ({core_reset_sync[1], 1\'bx})',
    '.\\input_dma/capture/pixels/wr_reset_sync  ({\\display_fifo/rd_reset_sync [1], 1\'bx})',
    '.\\capture/pixels/wr_reset_sync  ({\\input_dma/capture/pixels/wr_reset_sync [1], 1\'bx})',
    '.\\pixels/wr_reset_sync  ({\\capture/pixels/wr_reset_sync [1], 1\'bx})',
    '.wr_reset_sync ({\\pixels/wr_reset_sync [1], 1\'bx})']
reset_bindings={s:s in text for s in binding_strings}
root=ET.parse(BASE/'prj_tasks/syn_1/synthesize/report_db/synthesize_report_cdc_summary.db').getroot()
headers=[x.text for x in root.find('table/column_headers')]
cdc=[]
for r in root.iter('row'):
    item=dict(zip(headers,[x.text or '' for x in r.findall('data')]))
    end=item.get('Endpoint','')
    if ('system/display_fifo/' in end or '/capture/pixels/' in end) and re.search(r'/(?:rd_gray_w1|wr_gray_r1)\[',end):cdc.append(item)
route=BASE/'prj_tasks/pnr_1/place_route/hdmi_camera_fisheye_top_route_optimize.netlist'
dmr=BASE/'prj_tasks/pnr_1/device_map/hdmi_camera_fisheye_top.dmr'
dmr_text=dmr.read_text()
devmap_attributes={}
for p in pairs:
    for stage in ('first','second'):
        register=f"{p['instance']}/{p[stage]}[{p['bit']}]"
        devmap_attributes[register]=bool(re.search(r'\| i:'+re.escape(register)+r'\s+\| PAP_ASYNC_REG\s+\| TRUE',dmr_text))
for owner in reset_owners:
    for i in (0,1):
        register=f'{owner}[{i}]'
        devmap_attributes[register]=bool(re.search(r'\| i:'+re.escape(register)+r'\s+\| PAP_ASYNC_REG\s+\| TRUE',dmr_text))
mapped=[];mapped_reset=[];srl={}
if route.exists():
    all_cells=dict(re.findall(r'^([^;\n]+);(gop\w+)\s*$',route.read_text(),re.M))
    for p in pairs:
        for stage in ('first','second'):
            prefix=f"{p['instance']}/{p[stage]}[{p['bit']}]/"
            found={k:v for k,v in all_cells.items() if k.startswith(prefix)}
            mapped.append({'register':prefix[:-1],'mapped':found,'passed':len(found)==1 and list(found.values())==['gopQ']})
    srl={k:v for k,v in all_cells.items() if ('system/display_fifo/' in k or '/capture/pixels/' in k) and 'SRL' in v}
    for owner in reset_owners:
        for i in (0,1):
            prefix=f'{owner}[{i}]/';found={k:v for k,v in all_cells.items() if k.startswith(prefix)}
            mapped_reset.append({'register':prefix[:-1],'mapped':found,'passed':len(found)==1 and list(found.values())==['gopQ']})
report={'source_identity':json.loads((BASE/'candidate-plan.json').read_text())['source_identity'],
        'source_fifo_sha256':sha(BASE/'compiled/rtl/video_async_fifo.v'),'synth_vm_sha256':sha(vm),
        'synthesis_gray_pairs':pairs,'synthesis_gray_pair_count':len(pairs),
        'synthesis_gray_passed':len(pairs)==34 and all(p['passed'] for p in pairs),
        'synthesis_reset_cells':{m:{n:c for n,c in v['cells'].items() if 'reset_sync' in n} for m,v in modules.items()},
        'synthesis_fifo_headers':{m:v['header'] for m,v in modules.items()},
        'cdc_rows':cdc,'cdc_categories':dict(collections.Counter(r['CDC ID']+' '+r['Description'] for r in cdc)),
        'route_available':route.exists(),'mapped_gray_registers':mapped,'mapped_fifo_srl_cells':srl,
        'route_netlist_sha256':sha(route) if route.exists() else None,
        'device_map_report_sha256':sha(dmr),'device_map_native_attributes':devmap_attributes,
        'device_map_native_attributes_passed':len(devmap_attributes)==72 and all(devmap_attributes.values()),
        'mapped_gray_passed':len(mapped)==68 and all(c['passed'] for c in mapped) and not srl,
        'reset_owner_cells':reset_owners,'reset_owner_checks':reset_checks,'reset_shared_connection_bindings':reset_bindings,
        'synthesis_reset_shared_passed':all(all(v for k,v in c.items() if k!='owner') for c in reset_checks) and all(reset_bindings.values()),
        'mapped_reset_owners':mapped_reset,'mapped_reset_passed':len(mapped_reset)==4 and all(c['passed'] for c in mapped_reset),
        'gray_max_delay_and_bus_skew_signoff':None,
        'limitations':['Gray source-to-first-stage max-delay/skew binding and routed results are assessed in the separate I precise-constraint report.','Final routed pair wiring is checked by companion fifo-i-mapped-audit.json.','Device-map stage records all 72 native attributes. The G tool-capability probe rejected _map.adf with Flow-0013, so this audit uses device-map attributes and final routed connectivity.']}
(OUT/'fifo-i-audit.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k not in ('synthesis_gray_pairs','synthesis_fifo_headers','cdc_rows','mapped_gray_registers')},indent=2))
