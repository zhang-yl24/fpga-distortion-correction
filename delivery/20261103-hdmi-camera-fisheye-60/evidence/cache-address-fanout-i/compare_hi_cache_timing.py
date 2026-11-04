from pathlib import Path
import collections,hashlib,json,re,xml.etree.ElementTree as ET

OUT=Path('D:/f60-work/cache/address-fanout-i')
def scan(version):
    path=Path(f'D:/f60-run/physical-{version}/prj_tasks/pnr_1/report_timing/report_db/report_timing_slow_path_setup.db')
    if not path.exists():return None
    groups=collections.defaultdict(list);headers=[];stack=[];total=0
    for event,elem in ET.iterparse(path,events=('start','end')):
        if event=='start':stack.append(elem);continue
        if elem.tag=='column_headers' and len(stack)==3:headers=[e.text for e in elem]
        if elem.tag=='row' and len(stack)==3:
            total+=1;row=dict(zip(headers,[e.text or ''for e in elem.findall('data')]))
            if row.get('Launch Clock')==row.get('Capture Clock')=='ddrphy_sysclk':
                end=row['End Point'];start=row['Start Point']
                if '/cache/inner/' in end:
                    if re.search(r'/[AO]DD?[AB]\d*\[',end):category='RAM_address'
                    elif '/even_pixels_' in end or '/odd_pixels_' in end:category='RAM_other'
                    else:category='cache_other'
                    if len(groups[category])<12:
                        arrival=elem.find('.//table[@id="arrival"]');h=[e.text for e in arrival.find('column_headers')]
                        row['arrival']=[dict(zip(h,[e.text or ''for e in r.findall('data')]))for r in arrival.findall('row')]
                        groups[category].append(row)
            elem.clear()
        stack.pop()
    return {'source':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'bounded_report_rows':total,
            'worst_reported_per_category':dict(groups)}

result={'h':scan('h'),'i':scan('i'),
        'scope':'Compare reported core-to-core cache paths in bounded slow setup reports. Missing endpoints do not establish per-endpoint slack or complete signoff.'}
(OUT/'hi-cache-timing.json').write_text(json.dumps(result,indent=2)+'\n')
for v in ('h','i'):
    if result[v]:
        for category,rows in result[v]['worst_reported_per_category'].items():
            print(v,category,rows[0]['Slack'],rows[0]['Start Point'],'->',rows[0]['End Point'])
