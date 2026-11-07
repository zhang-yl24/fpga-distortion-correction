"use strict";
// Pure ECMAScript bounded model proof. Not an RTL simulator or Map/STA result.
// Run: node verify_native_head_model.js
(function () {
 const WIDTH=1920,HEIGHT=1080,INDEX_BITS=7;
 const fail=(s)=>{throw new Error(s);};
 const line=(x,y)=>((y&1)<<6)|((((y>>1)*2)+(x>>7))&63);
 let footprints=0,pairChecks=0,encodings=0;
 for(let y=-1;y<HEIGHT;y++)for(let x=-1;x<WIDTH;x++){
   const n=[0,1,2,3].map(i=>{const xx=x+(i&1),yy=y+(i>>1);return {ok:xx>=0&&xx<WIDTH&&yy>=0&&yy<HEIGHT,block:yy*15+(xx>>7),line:line(xx,yy)};});
   let oldMask=0,newMask=0;
   for(let h=0;h<4;h++){
     let ou=n[h].ok,nu=n[h].ok;
     for(let z=0;z<h;z++)if(n[h].ok&&n[z].ok){
       pairChecks++;
       if((n[h].block===n[z].block)!==(n[h].line===n[z].line))fail("alias "+x+","+y);
       if(n[h].block===n[z].block)ou=false;
       if(n[h].line===n[z].line)nu=false;
     }
     if(ou)oldMask|=1<<h;if(nu)newMask|=1<<h;
   }
   if(oldMask!==newMask)fail("lease-mask");
   // The candidate forwards the exact decoded bounds and line bits, not a
   // coordinate-derived approximation. Verify token layout using BigInt.
   let lines=0n,bounds=0n;
   n.forEach((v,i)=>{lines|=BigInt(v.line)<<(7n*BigInt(i));if(v.ok)bounds|=1n<<BigInt(i);});
   const payload=BigInt((x+1)*1081+(y+1));
   const baseBits=63n; // actual AA cache: COMPACT_COORDS=1, TAG_W=25 (24 + mask)
   const packed=(((bounds<<28n)|lines)<<baseBits)|payload;
   if((packed&((1n<<baseBits)-1n))!==payload)fail("payload");
   if(((packed>>(baseBits+28n))&15n)!==bounds)fail("bounds");
   for(let i=0;i<4;i++)if(Number((packed>>(baseBits+7n*BigInt(i)))&127n)!==n[i].line)fail("line");
   footprints++;encodings++;
 }
 // Arbitrary four-bit masks cover invalid neighbour patterns independently.
 for(let y=0;y<HEIGHT;y++)for(let bx=0;bx<15;bx++)for(let mask=0;mask<16;mask++){
   const x=bx*128+127;
   for(let h=0;h<4;h++)for(let z=0;z<h;z++)if((mask&(1<<h))&&(mask&(1<<z))){
     const xh=x+(h&1),yh=y+(h>>1),xz=x+(z&1),yz=y+(z>>1);
     if(xh<WIDTH&&xz<WIDTH&&yh<HEIGHT&&yz<HEIGHT&&
       ((yh*15+(xh>>7)===yz*15+(xz>>7))!==(line(xh,yh)===line(xz,yz))))fail("masked boundary");
   }
 }
 // Full-width payload preservation, including metadata boundary bit 62.
 for(let bit=0n;bit<63n;bit++){
   const payload=1n<<bit,bounds=15n,lines=(1n<<28n)-1n;
   const packed=(((bounds<<28n)|lines)<<63n)|payload;
   if((packed&((1n<<63n)-1n))!==payload)fail("walking payload");
 }
 const result={status:"PASS_BOUNDED_NATIVE_HEAD_MODEL",footprints,pairChecks,encodings,
   width:WIDTH,height:HEIGHT,indexBits:INDEX_BITS,oldTokenBits:124,newTokenBits:95,
   queryDepth:4096,logicalBitsRemoved:118784,
   scope:"Native bounded-neighbour identity and token packing only; no RTL, FIFO-cycle, full-frame, PDS or board claim"};
 if(typeof emit==="function")emit(result);else console.log(JSON.stringify(result,null,2));
})();