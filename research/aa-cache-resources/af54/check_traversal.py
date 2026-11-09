import json
W,H,G,M=1920,1080,64,32
c=r=t=sy=mx=my=mf=ms=tag=0;last=24;seen=bytearray(W*H);final_count=0
for ordinal in range(W*H):
 assert 0<=c<W and 0<=r<H
 assert tag==r*W+c and tag<2**21
 assert not seen[tag];seen[tag]=1
 assert tag&63==(((ordinal>>6)&7)<<3)|(ordinal&7),(ordinal,tag)
 final_count+=r>=1056
 if c%8!=7:c,tag=c+1,tag+1
 elif r%8!=7:c,r,tag=t,r+1,tag+W-7
 elif t!=mx+G-8:t,c,r,tag=t+8,t+8,sy,tag-7*W+1
 elif sy!=last:sy,t,c,r,tag=sy+8,mx,mx,sy+8,tag+W-G+1
 elif mx!=W-G:mx,t,c,sy,r,mf,tag=mx+G,mx+G,mx+G,my,my,mf+G,mf+G
 else:mx,my,t,c,sy,r,ms,mf,last,tag=0,my+M,0,0,my+M,r+1,ms+M*W,ms+M*W,my+2*M-8 if my+2*M<=H else H-8,tag+1
assert sum(seen)==W*H
print(json.dumps({'accepted':sum(seen),'maximum_tag':W*H-1,'final24_rows':final_count,'ordinal_low6_mapping':True,'post_last_invalid_tag':tag,'post_last_invalid_row':r}))
