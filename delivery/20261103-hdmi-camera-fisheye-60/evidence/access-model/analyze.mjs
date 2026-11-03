import fs from 'node:fs';
import crypto from 'node:crypto';
const DIR='D:/f60-work/cache-options', W=1920,H=1080,LINE_PIXELS=128;
const raw=fs.readFileSync('D:/f60-work/fisheye-c-q8-1920x1080.i32');
const xy=new Int32Array(raw.buffer,raw.byteOffset,raw.byteLength/4);
const hash=b=>crypto.createHash('sha256').update(b).digest('hex');
const provenance=JSON.parse(fs.readFileSync('D:/f60-work/map-generation.json','utf8'));
if(hash(raw)!==provenance.map_sha256)throw Error('map SHA differs');
const maxLine=Math.ceil(W*H/LINE_PIXELS);
function accesses(y0,y1){
 const count=(y1-y0)*W, seq=new Int32Array(count*4), rows=new Int16Array(count*4);
 let i=0,partial=0,empty=0;
 for(let sy=y0;sy<y1;sy+=8)for(let sx=0;sx<W;sx+=8)
  for(let y=sy;y<Math.min(sy+8,y1);y++)for(let x=sx;x<sx+8;x++){
   const p=(y*W+x)*2,ix=xy[p]>>8,iy=xy[p+1]>>8;let valid=0;
   for(let n=0;n<4;n++,i++){
    const nx=ix+(n&1),ny=iy+(n>>1);const ok=nx>=0&&nx<W&&ny>=0&&ny<H;
    seq[i]=ok?((ny*W+nx)>>>7):-1;rows[i]=ok?ny:-1;valid+=+ok;
   }
   if(valid===0)empty++;else if(valid!==4)partial++;
  }
 return {seq,rows,queries:count,y_range:[y0,y1],partial_queries:partial,empty_queries:empty};
}
// Fully associative LRU reference for conventional 3C classification.
function fullyAssociative(a,lines){
 const prev=new Int32Array(maxLine).fill(-1),next=new Int32Array(maxLine).fill(-1),resident=new Uint8Array(maxLine),seen=new Uint8Array(maxLine),missFlags=new Uint8Array(a.seq.length);
 let head=-1,tail=-1,size=0,misses=0,compulsory=0;
 for(let i=0;i<a.seq.length;i++){
  const b=a.seq[i];if(b<0)continue;
  if(!resident[b]){
   misses++;missFlags[i]=1;
   if(!seen[b]){compulsory++;seen[b]=1;}
   if(size===lines){const old=head;head=next[old];if(head>=0)prev[head]=-1;else tail=-1;resident[old]=0;}
   else size++;
   resident[b]=1;
  } else {
   const p=prev[b],n=next[b];if(p<0)head=n;else next[p]=n;if(n<0)tail=p;else prev[n]=p;
  }
  prev[b]=tail;next[b]=-1;if(tail<0)head=b;else next[tail]=b;tail=b;
 }
 return {misses,compulsory,capacity_misses:misses-compulsory,missFlags};
}
const hashes=[['direct',(b,y,s)=>b],...Array.from({length:9},(_,i)=>{const k=i+4;return ['xor_shift_'+k,(b,y,s)=>b^(b>>>k)];}),
 ['xor_index',(b,y,s)=>b^(b>>>s)],['xor_fold4',(b,y,s)=>b^(b>>>4)^(b>>>8)^(b>>>12)],
 ['row_stride16',(b,y,s)=>(y<<4)+(b-y*15)],['row_stride17',(b,y,s)=>(y<<4)+y+(b-y*15)],
 ['row_stride31',(b,y,s)=>(y<<5)-y+(b-y*15)],['row_stride33',(b,y,s)=>(y<<5)+y+(b-y*15)],
 ['row_xor_fold',(b,y,s)=>(y<<4)^(b-y*15)^(y>>>(s-4))],
 ['line_xor_row',(b,y,s)=>b^y],['line_xor_row_shr2',(b,y,s)=>b^(y>>>2)],
 ['row_adjacent_collision_control',(b,y,s)=>y+(b-y*15)],
 ['odd_permutation_control',(b,y,s)=>b*17]];
function simulate(a,ib,ways,method,policy,fa){
 const lines=1<<ib,sets=lines/ways,s=Math.log2(sets),mask=sets-1;
 const tags=new Int32Array(lines).fill(-1),ages=new Int32Array(lines),plru=new Uint8Array(sets),seen=new Uint8Array(maxLine);
 const f=hashes.find(v=>v[0]===method)[1];
 const indices=new Int32Array(maxLine);
 for(let b=0;b<maxLine;b++)indices[b]=f(b,Math.floor(b/15),s)&mask;
 let misses=0,hits=0,slow=0,comp=0,cap=0,conf=0,tick=0,selfConflictQueries=0,maxSetDemand=0,valid=0;
 const selfExamples=[];
 const demandSet=new Int32Array(4),demandBlock=new Int32Array(4);
 for(let i=0;i<a.seq.length;i+=4){
  let allHit=true,unique=0,selfConflict=false;
  for(let n=0;n<4;n++){
   const b=a.seq[i+n];if(b<0)continue;valid++;
   const set=indices[b],off=set*ways;let found=false;
   for(let way=0;way<ways;way++)if(tags[off+way]===b){found=true;break;}
   if(!found)allHit=false;
   let duplicate=false;for(let q=0;q<unique;q++)if(demandBlock[q]===b)duplicate=true;
   if(!duplicate){demandBlock[unique]=b;demandSet[unique++]=set;}
  }
  for(let n=0;n<unique;n++){
   let demand=0;for(let q=0;q<unique;q++)if(demandSet[q]===demandSet[n])demand++;
   if(demand>maxSetDemand)maxSetDemand=demand;
   if(demand>ways)selfConflict=true;
  }
  if(selfConflict){selfConflictQueries++;if(selfExamples.length<4)selfExamples.push({query:i/4,blocks:Array.from(a.seq.slice(i,i+4)),sets:Array.from(a.seq.slice(i,i+4),b=>b<0?-1:indices[b])});}
  if(!allHit)slow++;
  // Exact RTL slow path snapshots each neighbour before proceeding, so even
  // within-query replacement cannot cause a retry loop or deadlock.
  for(let n=0;n<4;n++){
   const at=i+n,b=a.seq[at];if(b<0)continue;
   const set=indices[b],off=set*ways;let hit=-1,victim=off;
   for(let w=0;w<ways;w++){if(tags[off+w]===b)hit=off+w;if(ages[off+w]<ages[victim])victim=off+w;}
   tick++;
   if(hit>=0){hits++;victim=hit;}
   else {
    if(policy==='plru'){
     let empty=-1;for(let w=0;w<ways;w++)if(tags[off+w]<0){empty=off+w;break;}
     if(empty>=0)victim=empty;
     else {const bits=plru[set];victim=off+((bits&1)===0?((bits>>>1)&1):2+((bits>>>2)&1));}
    }
    misses++;if(!seen[b]){comp++;seen[b]=1;}else if(fa.missFlags[at])cap++;else conf++;
    tags[victim]=b;
   }
   ages[victim]=tick;
   if(policy==='plru'){
    const way=victim-off;let bits=plru[set];
    if(way<2){bits|=1;if(way===0)bits|=2;else bits&=~2;}
    else {bits&=~1;if(way===2)bits|=4;else bits&=~4;}
    plru[set]=bits;
   }
  }
 }
 return {index_bits:ib,ways,sets,hash:method,replacement:policy,y_range:a.y_range,cache_bytes:lines*256,queries:a.queries,misses,hits,valid_neighbours:valid,slow_queries:slow,compulsory_misses:comp,capacity_misses:cap,conflict_misses:conf,noncompulsory_misses:misses-comp,fully_associative_lru_misses:fa.misses,excess_misses_over_fa:misses-fa.misses,read_bytes:misses*256,query_set_capacity_conflicts:selfConflictQueries,max_distinct_lines_per_query_in_one_set:maxSetDemand,self_conflict_examples:selfExamples,completion:'Current serial-neighbour slow path always completes with finite responding DDR; all-hit-only retry design would livelock for query_set_capacity_conflicts > 0.'};
}
const report={scope:'Exact Q8 coordinate stream, 8x8 tile order, 128-pixel/8-beat cache lines, cold cache each frame. Functional cache model only; no cycle/arbitration/metadata timing model.',map_sha256:hash(raw),reference_rtl_cache9_total_misses:31147,lanes:[],results:[]};
for(const [y0,y1]of [[0,544],[544,1080]]){
 const a=accesses(y0,y1),lane={y_range:a.y_range,queries:a.queries,partial_queries:a.partial_queries,empty_queries:a.empty_queries,fa:[]};report.lanes.push(lane);
 for(const ib of [8,9,10]){
  const fa=fullyAssociative(a,1<<ib);lane.fa.push({index_bits:ib,cache_bytes:(1<<ib)*256,misses:fa.misses,compulsory:fa.compulsory,capacity_misses:fa.capacity_misses});
  const configs=[];
  for(const [name]of hashes)if(ib!==10 || ['direct','xor_index','row_stride17','row_xor_fold'].includes(name))configs.push([1,name,'lru']);
  if(ib!==10)for(const ways of [2,4])for(const name of ['direct','xor_index','row_stride17','row_xor_fold']){
   configs.push([ways,name,'lru']);if(ways===4)configs.push([ways,name,'plru']);
  }
  for(const [ways,name,policy]of configs){const r=simulate(a,ib,ways,name,policy,fa);report.results.push(r);console.log(JSON.stringify(r));}
 }
}
const baseline=report.results.filter(v=>v.index_bits===9&&v.ways===1&&v.hash==='direct');
report.cache9_baseline_model_matches_rtl=baseline.reduce((x,r)=>x+r.misses,0)===31147;
if(!report.cache9_baseline_model_matches_rtl)throw Error('cache9 model differs from complete RTL run');
fs.writeFileSync(DIR+'/results.json',JSON.stringify(report,null,2));
