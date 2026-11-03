from pathlib import Path
import collections, hashlib, json, re, xml.etree.ElementTree as ET

BASE=Path('D:/f60-run/physical-e')
OUT=Path('D:/f60-work/cdc')
vm=BASE/'prj_tasks/syn_1/synthesize/hdmi_camera_fisheye_top_syn.vm'
text=vm.read_text(errors='replace')
mods={}
for m in re.finditer(r'(?m)^module (video_async_fifo(?:_\d+)?)\b',text):
    block=text[m.start():text.index('endmodule',m.end())+9]
    (OUT/(m[1]+'-synth.v')).write_text(block)
    sync={}
    for c in re.finditer(r'(?:\(\*([^*]*)\*\)\s*)?(GTP_\w+)\s+#\([^;]*?\)\s+\\((?:rd_gray_w[12]|wr_gray_r[12]|wr_gray|rd_gray|wr_reset_sync|rd_reset_sync)\[\d+\])\s+\((.*?)\);',block,re.S):
        sync[c[3]]={'primitive':c[2],'attributes':c[1] or '',
                    'ports':dict(re.findall(r'\.(\w+)\(([^)]+)\)',c[4]))}
    mods[m[1]]={'sync_cells':sync,'srl_primitives':sorted(set(re.findall(r'\bGTP_\w*SRL\w*\b',block))),
                'async_attribute_present':'async_reg' in block.lower(),
                'register_preserve_attribute_present':'PAP_PRESERVE' in block}

cdcfile=BASE/'prj_tasks/syn_1/synthesize/report_db/synthesize_report_cdc_summary.db'
root=ET.parse(cdcfile).getroot()
headers=[e.text for e in root.find('table/column_headers')]
cdc=[]
for row in root.iter('row'):
    data=[e.text or '' for e in row.findall('data')]
    if any(('system/display_fifo/' in t or '/capture/pixels/' in t) and 'gray' in t for t in data):
        cdc.append(dict(zip(headers,data)))

pathfile=BASE/'prj_tasks/pnr_1/report_timing/report_db/report_timing_slow_path_setup.db'
stack=[];headers=[];paths=[];total=0
for event,elem in ET.iterparse(pathfile,events=('start','end')):
    if event=='start':stack.append(elem);continue
    if elem.tag=='column_headers' and len(stack)==3:
        headers=[e.text for e in elem.findall('data')]
    if elem.tag=='row' and len(stack)==3:
        total+=1;values=[e.text or '' for e in elem.findall('data')]
        row=dict(zip(headers,values))
        if any(('system/display_fifo/' in row.get(k,'') or '/capture/pixels/' in row.get(k,'')) and 'gray' in row.get(k,'') for k in ('Start Point','End Point')):
            arrival=elem.find('.//table[@id="arrival"]')
            names=[e.text for e in arrival.find('column_headers')]
            row['arrival']=[dict(zip(names,[e.text or '' for e in r.findall('data')])) for r in arrival.findall('row')
                            if any('system/' in (e.text or '') for e in r.findall('data'))]
            paths.append(row)
        elem.clear()
    stack.pop()

routefile=BASE/'prj_tasks/pnr_1/place_route/hdmi_camera_fisheye_top_route_optimize.netlist'
mapped_cells={name:primitive for name,primitive in re.findall(r'^(system/(?:display_fifo|input_link/input_dma/capture/pixels)/[^;]+);(gop\w+)$',routefile.read_text(),re.M)
              if any(s in name for s in ('gray_w1','gray_w2','gray_r1','gray_r2','reset_sync'))}
report={'source':str(BASE),'fifo_rtl_sha256':hashlib.sha256((BASE/'compiled/rtl/video_async_fifo.v').read_bytes()).hexdigest(),
        'synthesized_modules':mods,'cdc_rows':cdc,'routed_setup_rows_examined':total,'routed_gray_paths':paths}
report['mapped_synchronizer_cells']=mapped_cells
report['mapped_gray_srl_count']=sum('gray' in k and 'SRL' in v for k,v in mapped_cells.items())
(OUT/'fifo-gray-audit.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'modules':{k:{'cells':len(v['sync_cells']),'srl':v['srl_primitives'],
    'async_attribute_present':v['async_attribute_present'],'preserve_attribute_present':v['register_preserve_attribute_present'],
    'families':dict(collections.Counter(re.sub(r'\[\d+\]','',c) for c in v['sync_cells']))} for k,v in mods.items()},
    'cdc_rows':len(cdc),'cdc_categories':dict(collections.Counter((r['CDC ID']+' '+r['Description']) for r in cdc)),
    'routed_paths':len(paths),'path_pairs':dict(collections.Counter(r['Launch Clock']+' -> '+r['Capture Clock'] for r in paths))},indent=2))
