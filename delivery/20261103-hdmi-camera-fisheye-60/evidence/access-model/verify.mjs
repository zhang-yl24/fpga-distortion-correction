import fs from 'node:fs';
import crypto from 'node:crypto';
const dir='D:/f60-work/cache-options';
const report=JSON.parse(fs.readFileSync(dir+'/results.json','utf8'));
const ext=JSON.parse(fs.readFileSync(dir+'/expanded-results.json','utf8'));
const raw=fs.readFileSync('D:/f60-work/fisheye-c-q8-1920x1080.i32');
const xy=new Int32Array(raw.buffer,raw.byteOffset,raw.byteLength/4);
const checks=[];
function check(name,ok,details){checks.push({name,passed:!!ok,details});if(!ok)throw Error(name);}
const baseline=report.results.filter(v=>v.index_bits===9&&v.ways===1&&v.hash==='direct');
const rtl=JSON.parse(fs.readFileSync('D:/f60-run/e8-cache9-pressure12/sim/engine-result.json','utf8'));
check('direct_index9_matches_complete_RTL_reads_and_hits',baseline.reduce((n,v)=>n+v.misses,0)===rtl.misses&&baseline.reduce((n,v)=>n+v.hits,0)===rtl.hits,{rtl,model:baseline.map(v=>({y_range:v.y_range,misses:v.misses,hits:v.hits}))});
check('three_C_components_sum_to_each_miss_total',[...report.results,...ext.results].every(v=>v.misses===v.compulsory_misses+v.capacity_misses+v.conflict_misses));
check('compulsory_count_invariant_across_ways_hash_capacity',[...report.results,...ext.results].every(v=>v.compulsory_misses===(v.y_range[0]===0?7257:7542)));
for(const ib of [8,9])for(const y0 of [0,544]){
 const a=report.results.find(v=>v.index_bits===ib&&v.y_range[0]===y0&&v.ways===1&&v.hash==='direct');
 const b=report.results.find(v=>v.index_bits===ib&&v.y_range[0]===y0&&v.hash==='odd_permutation_control');
 check('odd_set_permutation_preserves_miss_trace_'+ib+'_'+y0,a.misses===b.misses&&a.slow_queries===b.slow_queries);
}
// Separate compact implementation: coordinate-based index; no set simulator,
// precomputed access stream, hash registry, neighbour precheck, or LRU arrays.
for(const [y0,y1] of [[0,544],[544,1080]])for(const ib of [9,10])for(const mode of ['direct','row_stride16','row_stride7']){
 const tags=new Int32Array(1<<ib).fill(-1),mask=(1<<ib)-1;let miss=0;
 for(let ty=y0;ty<y1;ty+=8)for(let tx=0;tx<1920;tx+=8)for(let dy=0;dy<8;dy++)for(let dx=0;dx<8;dx++){
  let at=((ty+dy)*1920+tx+dx)*2;let x=xy[at]>>8,y=xy[at+1]>>8;
  for(let ny=y;ny<=y+1;ny++)for(let nx=x;nx<=x+1;nx++){
   if(nx<0||nx>=1920||ny<0||ny>=1080)continue;
   let block=ny*15+(nx>>7),index=mode==='direct'?block:(ny*(mode==='row_stride16'?16:7)+(nx>>7));index&=mask;
   if(tags[index]!==block){tags[index]=block;miss++;}
  }
 }
 const expected=ext.results.find(v=>v.index_bits===ib&&v.y_range[0]===y0&&v.ways===1&&v.hash===mode);
 check('independent_coordinate_model_'+y0+'_'+ib+'_'+mode,miss===expected.misses,{misses:miss});
}
const provenance={map_sha256:crypto.createHash('sha256').update(raw).digest('hex'),sources:{},checks};
for(const name of ['analyze.mjs','expanded.mjs','verify.mjs'])provenance.sources[name]=crypto.createHash('sha256').update(fs.readFileSync(dir+'/'+name)).digest('hex');
provenance.passed=checks.every(v=>v.passed);
fs.writeFileSync(dir+'/verification.json',JSON.stringify(provenance,null,2));
console.log(JSON.stringify({passed:provenance.passed,checks:checks.length}));
