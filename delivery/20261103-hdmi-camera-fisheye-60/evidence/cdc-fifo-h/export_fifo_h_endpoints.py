from pathlib import Path
import json,csv

folder=Path('D:/f60-work/cdc/fifo-h')
report=json.loads((folder/'fifo-h-mapped-audit.json').read_text())
paths=report['slow_setup_paths']['fifo_source_to_stage1_paths']
rows=[]
for pair in report['mapped']['gray_pairs']:
    dest=pair['stage1']['name'].split('/FF')[0]+'/D'
    timing=next((item for item in paths if item['End Point']==dest),None)
    gop_source=next((item['Logical Resource'] for item in timing['arrival'] if item['Delay Type']=='tco'),None) if timing else None
    source_signal=pair['source']['ports']['Q']
    rows.append({'instance':pair['instance'],'direction':pair['direction'],'bit':pair['bit'],
                 'source_signal':source_signal,'source_synth_q':source_signal+'/Q',
                 'source_primitive_q':pair['source']['name']+'/Q',
                 'source_clock':pair['source']['ports']['CK'],
                 'first_synth_d':pair['stage1']['ports']['Q']+'/D',
                 'first_primitive_d':pair['stage1']['name']+'/D','first_gop_d':dest,
                 'second_primitive_d':pair['stage2']['name']+'/D',
                 'source_gop_q_from_setup_report':gop_source or ''})
assert len(rows)==34 and report['mapped']['gray_pairs_passed']
(folder/'gray-constraint-endpoints.json').write_text(json.dumps(rows,indent=2)+'\n')
with (folder/'gray-constraint-endpoints.csv').open('w',newline='') as handle:
    writer=csv.DictWriter(handle,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
print('Exported 34 actual routed source/first/second pin bindings')
