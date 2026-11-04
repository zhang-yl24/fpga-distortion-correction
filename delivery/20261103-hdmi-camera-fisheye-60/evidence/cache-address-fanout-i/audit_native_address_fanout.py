from pathlib import Path
import collections,hashlib,json,re

OUT=Path('D:/f60-work/cache/address-fanout-i');OUT.mkdir(exist_ok=True)
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def norm(value):return re.sub(r'\s+','',value).lstrip('\\')
def parse_netlist(version):
    path=Path(f'D:/f60-work/cdc/{version}-netlist/prj_tasks/pnr_1/generate_netlist/hdmi_camera_fisheye_top_sim.v')
    text=path.read_text()
    pattern=r'\\(system/bank_core/engine/lanes\[([01])\]\.worker/core/sampler/cache/inner/(?:even|odd)_pixels_\d+/gopdrm_36k/DRM36K)\s+\((.*?)\);'
    loads=collections.defaultdict(list);pins={};rams=collections.Counter()
    for m in re.finditer(pattern,text,re.S):
        instance,lane,body=m.groups();lane=int(lane);rams[lane]+=1
        for port,expr in re.findall(r'\.(ADDR[AB])\s*\(([^)]+)\)',body):
            elements=expr.strip().strip('{}').split(',')
            for position,element in enumerate(reversed(elements)):
                net=norm(element)
                if not '/core/sampler/cache/inner/' in net:continue
                local=net.rsplit('/',1)[-1]
                mm=re.fullmatch(r'((?:even|odd)_[ab])(?:\[(\d+)\]|_(\d+)_(?:_\d+)?)',local)
                assert mm,(version,instance,port,position,net)
                canonical=mm[1]+'['+(mm[2] or mm[3])+']'
                key=instance+'/'+port+'['+str(position)+']'
                pins[key]={'lane':lane,'canonical':canonical,'net':net}
                loads[net].append(key)
    groups=collections.defaultdict(list)
    for net,pinlist in loads.items():
        sample=pins[pinlist[0]]
        groups[(sample['lane'],sample['canonical'])].append({'net':net,'fanout':len(pinlist),'pins':sorted(pinlist)})
    assert rams=={0:64,1:32},rams
    summary={}
    for lane,bits,fanout in [(0,14,32),(1,13,16)]:
        rows={key[1]:value for key,value in groups.items() if key[0]==lane}
        assert len(rows)==4*bits,(version,lane,len(rows))
        assert all(sum(item['fanout'] for item in copies)==fanout for copies in rows.values())
        summary[str(lane)]={'logical_address_bits':len(rows),'physical_driver_nets':sum(len(x)for x in rows.values()),
            'max_DRM_fanout':max(item['fanout']for copies in rows.values()for item in copies),
            'fanout_histogram':dict(sorted(collections.Counter(item['fanout']for copies in rows.values()for item in copies).items())),
            'DRM_address_connections':sum(item['fanout']for copies in rows.values()for item in copies),'groups':rows}
    return {'path':str(path),'sha256':sha(path),'RAMs_per_lane':dict(rams),'lanes':summary,'pins':pins}

h=parse_netlist('h')
if not Path('D:/f60-work/cdc/i-netlist/prj_tasks/pnr_1/generate_netlist/hdmi_camera_fisheye_top_sim.v').exists():
    (OUT/'h-baseline-address-fanout.json').write_text(json.dumps(h,indent=2)+'\n')
    print(json.dumps({lane:{k:v for k,v in row.items()if k!='groups'}for lane,row in h['lanes'].items()},indent=2))
else:
    i=parse_netlist('i')
    assert h['pins'].keys()==i['pins'].keys()
    mismatches=[{'pin':pin,'h':h['pins'][pin],'i':i['pins'][pin]}for pin in h['pins']
        if (h['pins'][pin]['lane'],h['pins'][pin]['canonical'])!=(i['pins'][pin]['lane'],i['pins'][pin]['canonical'])]
    report={'source_identity':json.loads(Path('D:/f60-run/physical-i/candidate-plan.json').read_text())['source_identity'],
        'baseline_h':h,'candidate_i':i,'connection_mismatches':mismatches,
        'preserved_address_connections':len(i['pins']),'passed':not mismatches and all(row['max_DRM_fanout']<=8 for row in i['lanes'].values()),
        'scope':'Full PNR functional netlists. Exact cache DRM ADDRA/ADDRB pin-to-logical-bit correspondence and per-driver DRM fanout; physical timing is assessed separately.'}
    (OUT/'address-fanout-route-audit.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'passed':report['passed'],'connections':len(i['pins']),
        'h':{lane:{k:v for k,v in row.items()if k!='groups'}for lane,row in h['lanes'].items()},
        'i':{lane:{k:v for k,v in row.items()if k!='groups'}for lane,row in i['lanes'].items()}},indent=2))
    assert report['passed']
