import collections,csv,io,json,zlib
MARKER='PASS DMA_DESCRIPTOR2 dataframes=6 descriptors=3 beats=96 poppush=1 resetfull=1 resetreserved=1'
def words(seed):return [((seed*0x1357)^(i*0x25)^(i<<3))&0xffff for i in range(256)]
def crc(seed):return zlib.crc32(b''.join(x.to_bytes(2,'little') for x in words(seed)))&0xffffffff
def rows(text):return list(csv.DictReader(io.StringIO(text)))
def check(events,writes,descriptors,aws,log):
 assert log.splitlines().count(MARKER)==1 and 'FATAL' not in log
 ee=collections.defaultdict(list)
 for r in rows(events):ee[r['event']].append({k:int(v) for k,v in r.items() if k!='event'})
 assert len(ee['TERMINAL'])==len(ee['RESET_FULL'])==len(ee['RESET_RESERVED'])==len(ee['POP_PUSH'])==1
 assert len(ee['RESET_CLEARED'])==3 and len(ee['PREFETCH_WITH_HEAD'])>=4
 for r in ee['RESET_CLEARED']:assert all(r[k]==0 for k in ['head','tail','reserved','owned','accepted']) and r['credit']==1
 for event,expect in [('RESET_FULL',(1,1,0,0)),('RESET_RESERVED',(1,0,1,1)),('POP_PUSH',(1,0,1,1))]:
  r=ee[event][0];assert tuple(r[k] for k in ['head','tail','reserved','credit'])==expect
 for r in ee['PREFETCH_WITH_HEAD']:assert (r['head'],r['tail'],r['reserved'],r['owned'],r['credit'])==(1,0,1,3,1)
 r=ee['POP_PUSH'][0];assert r['phase']==1 and r['id']==2 and r['active_id']==3
 ww=rows(writes);assert len(ww)==96
 for seed in range(1,7):
  chunk=[r for r in ww if int(r['seed'])==seed];assert len(chunk)==16
  expected=words(seed)
  for beat,r in enumerate(chunk):
   assert int(r['beat'])==beat and int(r['phase'])==(0 if seed<=2 else 1 if seed<=5 else 2)
   got=int(r['data'],16).to_bytes(32,'little');want=b''.join(x.to_bytes(2,'little') for x in expected[beat*16:(beat+1)*16]);assert got==want
 aa=rows(aws);assert len(aa)==6
 for seed,r in enumerate(aa,1):
  bank=1 if seed in [2,4] else 0
  assert (int(r['seed']),int(r['bank']),int(r['address']),int(r['len']))==(seed,bank,bank*1048576,15)
 dd=rows(descriptors);assert len(dd)==3
 for r,(phase,ident,seed,bank) in zip(dd,[(1,1,3,0),(1,2,4,1),(2,1,6,0)]):
  assert (int(r['phase']),int(r['id']),int(r['bank']),int(r['pixels']),int(r['crc'],16))==(phase,ident,bank,256,crc(seed))
 return {'DataFrames':6,'DDRBeats':96,'IndependentPixels':1536,'AcceptedDescriptors':3,'ResetDiscardedSeeds':[1,2,5],
  'FullReset':1,'ReservedReset':1,'SameCyclePopPush':1,'StalledHeadPrefetchWitnesses':len(ee['PREFETCH_WITH_HEAD']),'CRCs':[crc(s) for s in range(1,7)]}
def encode(rr):
 s=io.StringIO();w=csv.DictWriter(s,fieldnames=list(rr[0]),lineterminator='\n');w.writeheader();w.writerows(rr);return s.getvalue()
def synthetic():
 es=[]
 for phase in range(3):es.append(dict(event='RESET_CLEARED',phase=phase,time_ps=phase*100000,head=0,tail=0,reserved=0,id=0,active_id=0,owned=0,credit=1,accepted=0))
 for phase,ident,active in [(0,1,2),(1,1,2),(1,2,3),(1,3,4)]:es.append(dict(event='PREFETCH_WITH_HEAD',phase=phase,time_ps=1,head=1,tail=0,reserved=1,id=ident,active_id=active,owned=3,credit=1,accepted=0))
 for event,phase,h,t,res,credit,ident,active in [('RESET_FULL',0,1,1,0,0,1,2),('POP_PUSH',1,1,0,1,1,2,3),('RESET_RESERVED',1,1,0,1,1,3,4),('TERMINAL',2,0,0,0,1,1,1)]:es.append(dict(event=event,phase=phase,time_ps=2,head=h,tail=t,reserved=res,id=ident,active_id=active,owned=3 if h else 0,credit=credit,accepted=0))
 ws=[];aa=[];ds=[]
 for seed in range(1,7):
  bank=1 if seed in [2,4] else 0;phase=0 if seed<=2 else 1 if seed<=5 else 2
  aa.append(dict(phase=phase,seed=seed,address=bank*1048576,len=15,bank=bank,time_ps=seed*100))
  w=words(seed)
  for b in range(16):ws.append(dict(phase=phase,seed=seed,beat=b,data=b''.join(x.to_bytes(2,'little') for x in w[b*16:(b+1)*16])[::-1].hex(),time_ps=seed*100+b))
 for phase,ident,seed,bank in [(1,1,3,0),(1,2,4,1),(2,1,6,0)]:ds.append(dict(phase=phase,id=ident,bank=bank,crc=f'{crc(seed):08x}',pixels=256,time_ps=1))
 return [encode(es),encode(ws),encode(ds),encode(aa),MARKER+'\n']
def self_test():
 good=synthetic();check(*good);bad={}
 for name,index,row,field,value in [('capacity',0,0,'owned','3'),('badpayload',1,0,'data','0'),('badcrc',2,0,'crc','0'),('badid',2,0,'id','9'),('badbank',2,0,'bank','1'),('badcount',2,0,'pixels','255'),('badaddress',3,0,'address','1')]:
  rr=rows(good[index]);rr[row][field]=value;args=list(good);args[index]=encode(rr);bad[name]=args
 for name,event,field,value in [('fullcredit','RESET_FULL','credit','1'),('poppush','POP_PUSH','active_id','2'),('resetreservation','RESET_CLEARED','reserved','1')]:
  rr=rows(good[0]);next(r for r in rr if r['event']==event)[field]=value;args=list(good);args[0]=encode(rr);bad[name]=args
 bad['missingbeat']=[good[0],encode(rows(good[1])[:-1]),*good[2:]]
 bad['missingterminal']=[*good[:-1],'']
 rejected=[]
 for name,args in bad.items():
  try:check(*args)
  except AssertionError:rejected.append(name)
  else:raise AssertionError('unit oracle accepted '+name)
 return {'Positive':1,'RejectedMutations':rejected,'HDL':'NOT_RUN'}
if __name__=='__main__':print(json.dumps(self_test()))
