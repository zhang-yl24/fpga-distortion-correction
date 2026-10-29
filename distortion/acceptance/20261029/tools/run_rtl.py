"""Explicit future RTL replay of a prepared case; never run by Git delivery."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,csv,hashlib,json,os,re,time
from owned_tools import tool
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--work',type=Path,required=True);ap.add_argument('--execute-offline-rtl',action='store_true');a=ap.parse_args()
    if not a.execute_offline_rtl:ap.error('explicit offline execution and an exclusive heavy-tool slot are required')
    w=a.work.resolve();c=json.loads((w/'commands.json').read_text(encoding='utf-8'))
    if c['Case'] not in ('control','real-directed','real-native'):raise ValueError('RTL cases only')
    if (w/'replay-result.json').exists() or any(w.glob('*-stdout.log')):raise ValueError('fresh prepared directory only')
    for p,h in c['InputsSHA256'].items():assert sha(p)==h,p
    for n,h in c['WorkFilesSHA256'].items():assert sha(w/n)==h,n
    start=time.monotonic();budget=c['MaximumTotalSeconds'];deadline=start+budget-30
    env=os.environ.copy();temp=w/'compiler-temp';temp.mkdir();env['TEMP']=env['TMP']=str(temp)
    r={'Case':c['Case'],'FunctionalPassed':False,'StartedUtc':datetime.now(timezone.utc).isoformat(),'MaximumSeconds':budget,'CleanupReserveSeconds':30,'GateState':c['GateState'],'Commands':[],'HardwareAccessed':False}
    try:
        for command in c['Commands']:
            item=dict(command,ExitCode=None);r['Commands'].append(item)
            try:tool(Path(c['VivadoBin']),command['Exe'],command['Args'],w,deadline,command['Stage'],env);item['ExitCode']=0
            except Exception as e:
                m=re.search(r'exit=(-?\d+)',str(e));item['ExitCode']=int(m[1]) if m else None;raise
        text=(w/'simulation.log').read_text(encoding='utf-8',errors='replace')
        assert c['PassMarker'] in text and not re.search(r'(?im)^\s*(fatal|error):',text)
        if c['Case']!='control':
            s=json.loads((w/'summary.json').read_text(encoding='utf-8'));r['Summary']=s
            assert s['passed'] and s['final_drain']
            if c['Case']=='real-directed':
                assert s['outputs']==514 and s['points_each_mode']==257
                for k in ('partial','full_mask','real_black','changed','ar_stall','out_stall','input_stall','read_bursts','first_wait_cycles','zero_weight_boundary'):assert s[k]>0,k
            else:
                for k in ('source_beats','result_beats','display_beats'):assert s[k]==129600,k
                assert s['total_scanned_pixels']==2073600
                for k in ('repeat_frames','underflows','crc_mismatches','dropped_frames','overflow_frames','no_free_frames'):assert s[k]==0,k
                assert s['first_query_wait_cycles']>0
                with (w/'frames.csv').open(encoding='utf-8',newline='') as f:frames=list(csv.DictReader(f))
                with (w/'layers.csv').open(encoding='utf-8',newline='') as f:layers=list(csv.DictReader(f))
                with (w/'scans.csv').open(encoding='utf-8',newline='') as f:scans=list(csv.DictReader(f))
                assert len(frames)==len(layers)==len(scans)==1
                fr=frames[0];la=layers[0]
                assert fr['source_crc32']=='c14e962f' and fr['scan_crc32']==scans[0]['crc32']=='2aee1c42'
                assert (int(fr['frame_id']),int(fr['source_bank']),int(fr['result_bank']))==(1,0,2)
                for k in ('coordinate','rotation','map','sample','raw','tone'):assert int(la[k])==2073600,k
                for k in ('cache_epoch','outer_epoch','first_query_miss','writer_done','engine_done','reader_done'):assert int(la[k])==1,k
                assert int(la['prevalid'])==0
                for k in ('commits','releases','publishes','unique_scans'):assert int(fr[k])==1,k
                ts=[int(fr[k]) for k in ('input_first_ps','input_last_ps','commit_ps','source_release_ps','publish_ps','scan_start_ps','scan_last_pixel_ps','scan_done_ps')]
                assert ts[0]<ts[1]<ts[2]<ts[3]<=ts[4]<=ts[5]<ts[6]<=ts[7]
                r['CommitToReleaseCycles']=(ts[3]-ts[2])/8000
        r['FunctionalPassed']=True
    except Exception as e:r['Error']=type(e).__name__+': '+str(e)
    finally:
        r['InputsStable']=all(sha(p)==h for p,h in c['InputsSHA256'].items()) and all(sha(w/n)==h for n,h in c['WorkFilesSHA256'].items())
        r['ElapsedSeconds']=time.monotonic()-start;r['EndedUtc']=datetime.now(timezone.utc).isoformat()
        if not r['InputsStable'] or r['ElapsedSeconds']>budget:r['FunctionalPassed']=False
        r['LogsSHA256']={p.name:sha(p) for p in w.glob('*.log')}
        with (w/'replay-result.json').open('x',encoding='utf-8') as f:json.dump(r,f,indent=2);f.write('\n')
    print(json.dumps({'FunctionalPassed':r['FunctionalPassed'],'Error':r.get('Error'),'GateState':r['GateState']}))
    return 0 if r['FunctionalPassed'] else 1
if __name__=='__main__':raise SystemExit(main())
