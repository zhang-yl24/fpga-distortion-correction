`timescale 1ns/1ps
module cache_full_case #(parameter BITS=7)(output reg finished=0);
localparam N=1920*1080;
reg clk=0; always #4 clk=~clk;
reg rst_n=0,frame_valid=0;
wire frame_ready,in_ready,out_valid,failed,arvalid;
wire [7:0] fault,fx,fy; wire [23:0] p00,p10,p01,p11,out_tag;
wire [27:0] araddr; wire [3:0] arlen;
wire [31:0] hits,misses,completed_queries;
reg [47:0] coords[0:N-1];
integer sent=0,received=0,ticks=0,left=0,beat=0,start_pixel=0;
reg arready=0,rvalid=0,rlast=0,out_ready=0;
reg [255:0] rdata=0;
wire in_valid=rst_n&&!frame_valid&&sent<N;
wire signed [23:0] ix=sent<N ? coords[sent][47:24]:24'd0;
wire signed [23:0] iy=sent<N ? coords[sent][23:0]:24'd0;
ddr_neighbour_cache_scatter16_rowpipe #(.WIDTH(1920),.HEIGHT(1080),.INDEX_BITS(BITS)) dut(
 .clk(clk),.rst_n(rst_n),.frame_valid(frame_valid),.frame_ready(frame_ready),.frame_base(28'd0),
 .in_valid(in_valid),.in_ready(in_ready),.in_x(ix),.in_y(iy),.in_tag(sent[23:0]),
 .out_valid(out_valid),.out_ready(out_ready),.p00(p00),.p10(p10),.p01(p01),.p11(p11),.fx(fx),.fy(fy),.out_tag(out_tag),
 .araddr(araddr),.arlen(arlen),.arvalid(arvalid),.arready(arready),.rdata(rdata),.rvalid(rvalid),.rlast(rlast),.rid(4'd0),
 .failed(failed),.fault(fault),.hits(hits),.misses(misses),.completed_queries(completed_queries));
function automatic [15:0] word_at(input integer pos);
 word_at=(pos*109+(pos>>3)*53+(pos^(pos>>9))*17+16'hac37)&65535;
endfunction
function automatic [23:0] pixel(input integer x,y);
 reg [15:0] p;
 begin if(x<0||x>=1920||y<0||y>=1080)pixel=0;
 else begin p=word_at(y*1920+x);pixel={p[15:11],p[15:13],p[10:5],p[10:9],p[4:0],p[4:2]};end end
endfunction
always @(negedge clk)begin
 arready=rst_n&&left==0&&ticks%7>=2;
 rvalid=rst_n&&left>0&&ticks%5!=0; rlast=left==1;
 out_ready=rst_n&&ticks%11>=3;
 for(integer n=0;n<16;n=n+1)rdata[n*16+:16]=word_at(start_pixel+beat*16+n);
end
integer xx,yy;reg [47:0] c;
always @(posedge clk)begin
 ticks=ticks+1;
 if(rst_n)begin
  if(failed)$fatal(1,"cache failure bits=%0d fault=%h",BITS,fault);
  if(in_valid&&in_ready)sent<=sent+1;
  if(arvalid&&arready)begin
   if(left!=0||arlen!=7||araddr[5:0]!=0)$fatal(1,"invalid DDR burst");
   left<=8;beat<=0;start_pixel<=araddr*2;
  end
  if(rvalid)begin left<=left-1;beat<=beat+1;end
  if(out_valid&&out_ready)begin
   if(out_tag!==received[23:0])$fatal(1,"tag ordering");
   c=coords[received];xx=$signed(c[47:24])>>>8;yy=$signed(c[23:0])>>>8;
   if({p00,p10,p01,p11,fx,fy}!=={pixel(xx,yy),pixel(xx+1,yy),pixel(xx,yy+1),pixel(xx+1,yy+1),c[31:24],c[7:0]})
    $fatal(1,"pixel mismatch bits=%0d query=%0d",BITS,received);
   received<=received+1;
  end
 end
end
initial begin
 $readmemh("coordinates.mem",coords);
 repeat(4)@(negedge clk);rst_n=1;frame_valid=1;
 do @(posedge clk);while(!frame_ready);
 @(negedge clk);frame_valid=0;
 wait(received==N);@(negedge clk);
 if(completed_queries!=N)$fatal(1,"count mismatch");
 $display("PASS FULL bits=%0d pixels=%0d block_reads=%0d cycles=%0d",BITS,received,misses,ticks);finished=1;
end
initial begin #200000000;$fatal(1,"timeout");end
endmodule
module tb_tile8_cache_full;
wire a,b;
cache_full_case #(.BITS(7)) baseline(a);
cache_full_case #(.BITS(8)) candidate(b);
initial begin wait(a&&b);$display("PASS FULL BOTH");$finish;end
endmodule
