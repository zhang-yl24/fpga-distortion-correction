from pathlib import Path
import collections,hashlib,json,re,xml.etree.ElementTree as ET
ROOT=Path('D:/f60-work/video/writer-beat-fanout-probe-r2')
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def xml_rows(path):
    t=ET.parse(path).getroot().find('table')
    heads=[x.text for x in t.find('column_headers')]
    return [dict(zip(heads,[x.text or '' for x in r])) for r in t.findall('row')]
def tokens(p):
    text=re.sub(r'/\*.*?\*/|//[^\n]*|\(\*.*?\*\)','',p.read_text(),flags=re.S)
    return re.findall(r'[A-Za-z_$][\w$]*|\d+|[^\s]',text)
pattern=re.compile(r'(?P<type>GTP_\w+)\s*(?:#\((?P<params>.*?)\))?\s+(?P<name>\\\S+|\w+)\s*\((?P<pins>.*?)\);',re.S)
result={'scope':'Native isolated writer synthesis and device-map audit. All source differences are one attribute. Same-bit clone register D/CE/CLK/R and INIT/GRS are compared exactly, proving their local synchronous behavior by induction. This is not a whole-device formal equivalence or routed timing pass.',
        'source_tokens_equal':tokens(ROOT/'baseline/writer.v')==tokens(ROOT/'maxfan32/writer.v'),
        'variants':{}}
for kind in ['baseline','maxfan32']:
    d=ROOT/kind;vm=d/'prj_tasks/syn_1/synthesize/writer_probe_syn.vm'
    text=vm.read_text();cells=[];loads=collections.Counter()
    for m in pattern.finditer(text):
        pins={k:re.sub(r'\s+','',v) for k,v in re.findall(r'\.(\w+)\s*\(\s*(.*?)\s*\)',m['pins'],re.S)}
        c={'type':m['type'],'name':m['name'].lstrip('\\'),'params':re.sub(r'\s+','',m['params'] or ''),'pins':pins}
        cells.append(c)
        for pin,net in pins.items():
            if pin not in ['Q','Z','O','CO','F','G']:loads[net]+=1
    families={}
    for bit in range(4):
        ff=[c for c in cells if c['type'].startswith('GTP_DFF') and re.fullmatch(r'beat(?:_copy)?\['+str(bit)+r'\](?:_\d+)?',c['name'])]
        assert ff,(kind,bit)
        base=next(c for c in ff if c['name']==f'beat[{bit}]')
        sig=lambda c:(c['type'],c['params'],{k:v for k,v in c['pins'].items() if k!='Q'})
        signatures_match=all(sig(c)==sig(base) for c in ff)
        detail=[{'instance':c['name'],'q':c['pins']['Q'],'synthesis_loads':loads[c['pins']['Q']]} for c in ff]
        families[str(bit)]={'registers':len(ff),'max_synthesis_fanout':max(r['synthesis_loads'] for r in detail),
                            'sum_synthesis_loads':sum(r['synthesis_loads'] for r in detail),
                            'same_bit_register_signatures_identical':signatures_match,
                            'signature':sig(base),'detail':detail}
    report=d/'prj_tasks/pnr_1/device_map/report_db'
    high=xml_rows(report/'device_map_high_fanout_singnal.db')
    beat_rows=[r for r in high if re.search(r'/beat(?:_copy)?\[|/beat_[0-3]__',r['Net_Name']) and '[3:0]' not in r['Net_Name']]
    resource={r['Logic Utilization']:r['Used'] for r in xml_rows(report/'device_map_resource_usage.db') if r['Logic Utilization'] in ['FF','LUT','DRM']}
    warnings=[]
    for path in [d/'console.log',d/'prj_tasks/syn_1/compile/run.log']:
        for line in path.read_text(errors='replace').splitlines():
            if re.search(r'(?:PAP_MAX_FANOUT|syn_maxfan).*not legal|not legal.*(?:PAP_MAX_FANOUT|syn_maxfan)',line):warnings.append(line)
    result['variants'][kind]={'families':families,'resources':resource,
        'mapped_report_beat_rows':len(beat_rows),'max_reported_mapped_beat_fanout':max(int(r['Fanout']) for r in beat_rows),
        'mapped_beat_rows':beat_rows,'mapped_other_high_fanout':high[:8],
        'hashes':{str(p.relative_to(d)):sha(p) for p in [vm,report/'device_map_high_fanout_singnal.db',report/'device_map_resource_usage.db',d/'console.log']},
        'attribute_rejections':warnings}
result['passed']=result['source_tokens_equal'] and all(
    f['same_bit_register_signatures_identical'] for v in result['variants'].values() for f in v['families'].values()) and all(
    f['max_synthesis_fanout']<=32 for f in result['variants']['maxfan32']['families'].values()) and not result['variants']['maxfan32']['attribute_rejections']
(ROOT/'verification.json').write_text(json.dumps(result,indent=2)+'\n')
assert result['passed']
print(json.dumps({'passed':result['passed'],'source_tokens_equal':result['source_tokens_equal'],
 'variants':{k:{'families':{i:{x:f[x] for x in ['registers','max_synthesis_fanout','sum_synthesis_loads','same_bit_register_signatures_identical']} for i,f in v['families'].items()},'resources':v['resources'],'mapped_max':v['max_reported_mapped_beat_fanout'],'mapped_rows':v['mapped_report_beat_rows']} for k,v in result['variants'].items()}},indent=2))
