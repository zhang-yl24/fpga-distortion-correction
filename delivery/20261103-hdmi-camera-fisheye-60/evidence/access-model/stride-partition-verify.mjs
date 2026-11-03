import fs from 'node:fs';
import crypto from 'node:crypto';
const dir='D:/f60-work/cache-stride-sweep';
const model=JSON.parse(fs.readFileSync(dir+'/results.json','utf8'));
const raw=fs.readFileSync('D:/f60-work/fisheye-c-q8-1920x1080.i32');
const xy=new Int32Array(raw.buffer,raw.byteOffset,raw.byteLength/4);
const sha=b=>crypto.createHash('sha256').update(b).digest('hex');
if(sha(raw)!==model.map_sha256)throw Error('map differs');
// Separate coordinate-driven implementation: no shared access array, hash
// registry, precomputed block indices, replacement ages or 3C bookkeeping.
function reference(y0,y1,bits,stride){
 const tags=new Int32Array(1<<bits).fill(-1),mask=tags.length-1;
 const blocks=new Int32Array(4),slots=new Int32Array(4);
 let misses=0,slow=0;
 for(let ty=y0;ty<y1;ty+=8)for(let tx=0;tx<1920;tx+=8)
  for(let dy=0;dy<8;dy++)for(let dx=0;dx<8;dx++){
   const at=((ty+dy)*1920+tx+dx)*2,x=xy[at]>>8,y=xy[at+1]>>8;
   let allHit=true;
   for(let n=0;n<4;n++){
    const nx=x+(n&1),ny=y+(n>>1);
    if(nx<0||nx>=1920||ny<0||ny>=1080){blocks[n]=-1;continue;}
    blocks[n]=ny*15+(nx>>7);slots[n]=(ny*stride+(nx>>7))&mask;
    if(tags[slots[n]]!==blocks[n])allHit=false;
   }
   if(!allHit)slow++;
   for(let n=0;n<4;n++)if(blocks[n]>=0&&tags[slots[n]]!==blocks[n]){
    misses++;tags[slots[n]]=blocks[n];
   }
  }
 return {misses,slow_queries:slow};
}
const checks=[];
function check(name,got,want){
 const passed=got.misses===want.misses&&got.slow_queries===want.slow_queries;
 checks.push({name,passed,actual:got,expected:{misses:want.misses,slow_queries:want.slow_queries}});
 if(!passed)throw Error(name+' differs');
}
for(const stride of [7,15,16,20])check('bottom544_stride'+stride,reference(544,1080,9,stride),model.stride_results.find(v=>v.stride===stride));
for(const split of [640,664,688]){
 const row=model.partition_results.find(v=>v.top_rows===split);
 check('top'+split,reference(0,split,10,16),row.lanes[0]);
 check('bottom'+split,reference(split,1080,9,15),row.lanes[1]);
}
const report={passed:checks.every(v=>v.passed),scope:'Cache-access model cross-check only; no cycles or FPS prediction.',map_sha256:sha(raw),
 source_sha256:{'analyze.mjs':sha(fs.readFileSync(dir+'/analyze.mjs')),'verify.mjs':sha(fs.readFileSync(dir+'/verify.mjs'))},checks};
fs.writeFileSync(dir+'/verification.json',JSON.stringify(report,null,2));
console.log(JSON.stringify({passed:report.passed,independent_checks:checks.length}));
