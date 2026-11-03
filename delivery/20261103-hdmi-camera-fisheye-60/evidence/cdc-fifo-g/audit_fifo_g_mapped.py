from pathlib import Path
import collections, hashlib, json, re, xml.etree.ElementTree as ET

BASE = Path('D:/f60-run/physical-g')
OUT = Path('D:/f60-work/cdc/fifo-g')
SIM = Path('D:/f60-work/cdc/g-netlist/prj_tasks/pnr_1/generate_netlist/hdmi_camera_fisheye_top_sim.v')
ADF = BASE/'prj_tasks/pnr_1/place_route/hdmi_camera_fisheye_top_pnr.adf'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def canon(net):
    return re.sub(r'\s+', '', net).lstrip('\\')

def parse_ffs(text):
    cells = {}
    pattern = r'\b(V_FF\w+)\s*(?:/\*.*?\*/\s*)?(?:#\([^;]*?\)\s*)?\\([^\s]+)\s+\((.*?)\);'
    for m in re.finditer(pattern, text, re.S):
        cells[m[2]] = {'primitive':m[1], 'ports':{p:canon(n) for p,n in re.findall(r'\.(\w+)\s*\(([^)]+)\)', m[3])}}
    return cells

def audit_netlist(path):
    text=path.read_text(errors='replace')
    ffs=parse_ffs(text)
    byq=collections.defaultdict(list)
    for name,c in ffs.items():
        byq[c['ports']['Q']].append(name)
    unary={}
    for m in re.finditer(r'\b(V_INV|V_BUF)\s+\\([^\s]+)\s+\((.*?)\);', text, re.S):
        p={p:canon(n) for p,n in re.findall(r'\.(\w+)\s*\(([^)]+)\)',m[3])}
        unary[p['Z']]={'cell':m[2], 'primitive':m[1], 'input':p['I']}
    def reset_trace(net):
        trace=[];inverted=False;seen=set()
        while net in unary:
            assert net not in seen,net
            seen.add(net);item=unary[net];trace.append({'output':net,**item})
            inverted^=item['primitive']=='V_INV';net=item['input']
        return {'source':net,'inverted':inverted,'trace':trace}
    def ffq(net):
        names=byq[net]
        assert len(names)==1,(net,names)
        return {'name':names[0],**ffs[names[0]]}
    pairs=[]
    for inst,bits,write_clock,read_clock in [
            ('system/display_fifo',10,'core_clk','ntclkbufg_0'),
            ('system/input_link/input_dma/capture/pixels',7,'ntclkbufg_0','core_clk')]:
        for direction,first,second,source_clock,destination_clock in [
                ('wr','wr_gray_r1','wr_gray_r2',write_clock,read_clock),
                ('rd','rd_gray_w1','rd_gray_w2',read_clock,write_clock)]:
            for bit in range(bits):
                srcnet=f'{inst}/{direction}_{"gray" if bit<bits-1 else "binary"}[{bit}]'
                src=ffq(srcnet)
                a=ffq(f'{inst}/{first}[{bit}]');b=ffq(f'{inst}/{second}[{bit}]')
                owner='core_reset[1]' if destination_clock=='core_clk' else 'system/display_fifo/rd_reset_sync[1]'
                checks={
                    'source_q_direct_to_stage1_d':a['ports']['D']==src['ports']['Q'],
                    'stage1_q_direct_to_stage2_d':b['ports']['D']==a['ports']['Q'],
                    'two_independent_sync_ff':a['name']!=b['name'] and a['primitive']==b['primitive']=='V_FFSYN',
                    'correct_clocks':src['ports']['CK']==source_clock and a['ports']['CK']==b['ports']['CK']==destination_clock,
                    'sync_ce_always_enabled':a['ports']['CE']==b['ports']['CE']=="1'b1",
                    'reset_both_from_expected_owner_stage2':all(reset_trace(x['ports']['SR'])['source']==owner and reset_trace(x['ports']['SR'])['inverted'] for x in (a,b)),
                }
                pairs.append({'instance':inst,'direction':direction,'bit':bit,'source':src,'stage1':a,'stage2':b,
                              'expected_reset_owner_stage2':owner,'reset_traces':[reset_trace(x['ports']['SR']) for x in (a,b)],
                              'checks':checks,'passed':all(checks.values())})
    resets=[]
    for owner,clock in [('core_reset','core_clk'),('system/display_fifo/rd_reset_sync','ntclkbufg_0')]:
        a=ffq(owner+'[0]');b=ffq(owner+'[1]')
        checks={'two_independent_async_ff':a['name']!=b['name'] and a['primitive']==b['primitive']=='V_FFASYN',
                'constant_one_first_d':a['ports']['D']=="1'b1",'stage1_q_direct_to_stage2_d':a['ports']['Q']==b['ports']['D'],
                'correct_clock':a['ports']['CK']==b['ports']['CK']==clock,
                'common_async_reset':a['ports']['SR']==b['ports']['SR'],
                'ce_always_enabled':a['ports']['CE']==b['ports']['CE']=="1'b1"}
        resets.append({'owner':owner,'stage1':a,'stage2':b,'checks':checks,'passed':all(checks.values())})
    # Keep verbatim mapped primitives for review without archiving the entire 75 MB netlist.
    selected_names={x[k]['name'] for x in pairs for k in ('source','stage1','stage2')}
    selected_names|={x[k]['name'] for x in resets for k in ('stage1','stage2')}
    excerpts=[]
    for name in sorted(selected_names):
        marker='\\'+name+' '
        pos=text.index(marker)
        start=text.rfind('(*',0,pos)
        end=text.index(');',pos)+2
        excerpts.append(text[start:end])
    (OUT/'fifo-g-mapped-primitives.v').write_text('\n\n'.join(excerpts)+'\n')
    return {'sim_netlist':str(path),'sim_sha256':sha(path),'parsed_ff_count':len(ffs),
            'gray_pair_count':len(pairs),'gray_pairs':pairs,'gray_pairs_passed':len(pairs)==34 and all(x['passed'] for x in pairs),
            'reset_owners':resets,'reset_owners_passed':len(resets)==2 and all(x['passed'] for x in resets)}

def timing_paths(path):
    stack=[];headers=[];paths=[];total=0
    for event,elem in ET.iterparse(path,events=('start','end')):
        if event=='start':stack.append(elem);continue
        if elem.tag=='column_headers' and len(stack)==3:headers=[e.text for e in elem.findall('data')]
        if elem.tag=='row' and len(stack)==3:
            total+=1;row=dict(zip(headers,[e.text or '' for e in elem.findall('data')]))
            end=row.get('End Point','')
            if ('system/display_fifo/' in end or '/capture/pixels/' in end) and re.search(r'/(rd_gray_w1|wr_gray_r1)\[',end):
                arrival=elem.find('.//table[@id="arrival"]')
                names=[e.text for e in arrival.find('column_headers')]
                row['arrival']=[dict(zip(names,[e.text or '' for e in r.findall('data')])) for r in arrival.findall('row')]
                paths.append(row)
            elem.clear()
        stack.pop()
    return {'source':str(path),'sha256':sha(path),'report_rows_examined':total,'fifo_source_to_stage1_paths':paths,
            'reported_path_count':len(paths),'clock_pairs':dict(collections.Counter(r['Launch Clock']+' -> '+r['Capture Clock'] for r in paths))}

report={'source_identity':json.loads((BASE/'candidate-plan.json').read_text())['source_identity'],
        'fifo_rtl_sha256':sha(BASE/'compiled/rtl/video_async_fifo.v'),
        'input_pnr_adf':str(ADF),'input_pnr_adf_sha256':sha(ADF),
        'mapped':audit_netlist(SIM),
        'slow_setup_paths':timing_paths(BASE/'prj_tasks/pnr_1/report_timing/report_db/report_timing_slow_path_setup.db'),
        'source_period_limits_ns':{'core_to_pixel':8.0,'pixel_to_core':6.666666667},
        'gray_max_delay_and_bus_skew_signoff':False,
        'limitations':['This script checks FIFO structure and connectivity on the full routed G design.',
            'The existing bounded timing report does not substitute for explicit all-bit max-delay and bus-skew acceptance.',
            'No clock-group, false-path, max-delay or bus-skew constraint was added by this audit.']}
(OUT/'fifo-g-mapped-audit.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'gray_pairs':report['mapped']['gray_pair_count'],'gray_passed':report['mapped']['gray_pairs_passed'],
    'reset_owners_passed':report['mapped']['reset_owners_passed'],
    'reported_gray_paths':report['slow_setup_paths']['reported_path_count'],
    'path_clock_pairs':report['slow_setup_paths']['clock_pairs']},indent=2))
