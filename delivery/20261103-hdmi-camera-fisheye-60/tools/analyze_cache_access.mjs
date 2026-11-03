import fs from 'node:fs';
import path from 'node:path';
if(process.argv.length!==4)throw new Error('Usage: node analyze_cache_access.mjs <native-q8-map.i32> <results.json>');
const raw=fs.readFileSync(path.resolve(process.argv[2]));
if(raw.byteLength!==1920*1080*2*4)throw new Error('Expected complete 1920x1080 int32 x,y map');
const xy=new Int32Array(raw.buffer,raw.byteOffset,raw.byteLength/4);
const W=1920,H=1080,N=W*H;
function simulate(linePixels,indexBits,tw,th,ways=1,startY=0,endY=H){
 const lines=1<<indexBits,sets=lines/ways,mask=sets-1,shift=Math.log2(linePixels);
 const tags=new Int32Array(lines).fill(-1), ages=new Int32Array(lines);
 let misses=0,hitNeighbours=0,slowQueries=0,validNeighbours=0,tick=0;
 const seen=new Set();
 const blocks=new Int32Array(4);
 for(let sy=startY;sy<endY;sy+=th)for(let sx=0;sx<W;sx+=tw)
 for(let y=sy;y<Math.min(sy+th,endY);y++)for(let x=sx;x<Math.min(sx+tw,W);x++){
  const p=(y*W+x)*2,ix=xy[p]>>8,iy=xy[p+1]>>8;
  let allHit=true;
  for(let n=0;n<4;n++){
   let nx=ix+(n&1),ny=iy+(n>>1);
   let b=nx>=0&&nx<W&&ny>=0&&ny<H?((ny*W+nx)>>>shift):-1;
   blocks[n]=b;
   if(b<0)continue;
   validNeighbours++;
   let set=(b&mask)*ways,found=false;
   for(let way=0;way<ways;way++)if(tags[set+way]===b){found=true;break;}
   if(!found)allHit=false;
  }
  if(!allHit)slowQueries++;
  for(let n=0;n<4;n++){
   const b=blocks[n]; if(b<0)continue;
   const set=(b&mask)*ways;
   let hit=-1,oldest=set;
   for(let way=0;way<ways;way++){
    let j=set+way;if(tags[j]===b)hit=j;
    if(ages[j]<ages[oldest])oldest=j;
   }
   tick++;
   if(hit>=0){hitNeighbours++;ages[hit]=tick;}
   else {misses++;tags[oldest]=b;ages[oldest]=tick;seen.add(b);}
  }
 }
 return {line_pixels:linePixels,index_bits:indexBits,ways,cache_bytes:lines*linePixels*2,tile:[tw,th],y_range:[startY,endY],queries:(endY-startY)*W,slow_queries:slowQueries,misses,hit_neighbours:hitNeighbours,valid_neighbours:validNeighbours,compulsory_blocks:seen.size,read_bytes:misses*linePixels*2,read_GBps_at_60:misses*linePixels*2*60/1e9};
}
const configs=[];
for(const ib of [7,8,9])for(const [w,h] of [[1920,1],[8,8],[16,8],[32,8],[64,8],[128,8],[32,16],[64,16],[32,32],[64,1080]])configs.push([128,ib,w,h]);
for(const lp of [32,64])for(const bytes of [32768,65536])for(const [w,h]of[[1920,1],[8,8],[16,8],[32,8],[64,8]])configs.push([lp,Math.log2(bytes/(lp*2)),w,h]);
for(const [w,h]of[[1920,1],[8,8],[32,8]])configs.push([128,7,w,h,2]);
for(const tw of [8,32])for(const [a,b]of[[0,544],[544,1080]])configs.push([128,7,tw,8,1,a,b]);
const out=[];
for(const c of configs){let r=simulate(...c);out.push(r);console.log(JSON.stringify(r));}
fs.writeFileSync(path.resolve(process.argv[3]),JSON.stringify({scope:'Functional cache-access model over the exact generated C Q8 map. No cycle, DDR arbitration, writer, or physical timing model.',results:out},null,2));
