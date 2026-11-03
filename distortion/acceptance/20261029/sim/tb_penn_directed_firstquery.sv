`timescale 1ps/1ps
module tb_penn_directed;
    `include "config.vh"
    `include "points.vh"
    localparam W=1920,H=1080,N=W*H,S=1048576;
    reg clk=0;always #4000 clk=~clk;
    reg rst_n=0,frame_valid=0,correction_enable=0,in_valid=0,out_ready=0;
    wire frame_ready,in_ready,out_valid,out_masked,failed;
    reg [27:0] frame_base=0;
    reg signed [23:0] in_u=0,in_v=0;
    reg [23:0] in_tag=0;
    wire [23:0] out_rgb,out_tag;wire [7:0] fault;
    reg signed [23:0] ocx,ocy,scx,scy,sfx,sfy,rcx,rcy;
    reg signed [31:0] ifx,ify,k1,k2,k3,p1,p2,rcos,rsin;
    wire [27:0] araddr;wire [3:0] arlen;wire arvalid;
    reg arready=0,rvalid=0,rlast=0;reg [255:0] rdata=0;
    wire [31:0] hits,misses,completed_queries;
    rotated_remap_core_gamma_geometry_bypass_scatter4 #(.WIDTH(W),.HEIGHT(H),.INDEX_BITS(7),.MAX_RADIUS_Q22(VEC_RADIUS_GUARD_Q22)) dut(
        .clk(clk),.rst_n(rst_n),.frame_valid(frame_valid),.frame_ready(frame_ready),.frame_base(frame_base),.correction_enable(correction_enable),
        .cfg_out_cx(ocx),.cfg_out_cy(ocy),.cfg_src_cx(scx),.cfg_src_cy(scy),.cfg_src_fx(sfx),.cfg_src_fy(sfy),
        .cfg_inv_fx(ifx),.cfg_inv_fy(ify),.cfg_k1(k1),.cfg_k2(k2),.cfg_k3(k3),.cfg_p1(p1),.cfg_p2(p2),
        .cfg_rot_cx(rcx),.cfg_rot_cy(rcy),.cfg_rot_cos(rcos),.cfg_rot_sin(rsin),
        .in_valid(in_valid),.in_ready(in_ready),.in_u(in_u),.in_v(in_v),.in_tag(in_tag),
        .out_valid(out_valid),.out_ready(out_ready),.out_rgb(out_rgb),.out_tag(out_tag),.out_masked(out_masked),
        .araddr(araddr),.arlen(arlen),.arvalid(arvalid),.arready(arready),.rdata(rdata),.rvalid(rvalid),.rlast(rlast),.rid(4'd0),
        .failed(failed),.fault(fault),.hits(hits),.misses(misses),.completed_queries(completed_queries));
    reg [15:0] source[0:N-1];reg [71:0] requests[0:POINTS-1];
    reg [48:0] expected[0:2*POINTS-1];reg [48:0] mapped[0:POINTS-1];
    reg [7:0] coverage[0:POINTS-1];
    integer phase_start=0,first_wait_cycles=0,first_accept_tag=-1,first_miss=0,zero_weight_checked=0;
    integer phase=0,ticks=0,sent=0,received=0,maps=0,samples=0,total=0,rleft=0,rindex=0;
    integer ar_stall=0,out_stall=0,input_stall=0,partial_checked=0,masked_checked=0,black_checked=0,different_checked=0;
    integer j,f,i,off,read_bursts=0,summary;
    reg held_ar=0,held_out=0;reg [31:0] saved_ar;reg [48:0] saved_out;
    wire [48:0] out_bundle={out_masked,out_tag,out_rgb};
    task automatic configure;
        begin
            ocx=VEC_OUT_CX;ocy=VEC_OUT_CY;scx=VEC_SRC_CX;scy=VEC_SRC_CY;sfx=VEC_SRC_FX;sfy=VEC_SRC_FY;
            ifx=VEC_INV_FX;ify=VEC_INV_FY;k1=VEC_K1;k2=VEC_K2;k3=VEC_K3;p1=VEC_P1;p2=VEC_P2;
            rcx=VEC_OUT_CX;rcy=VEC_OUT_CY;rcos=32'sd1073741824;rsin=0;
        end
    endtask
    always @(negedge clk)begin
        ticks=ticks+1;if(ticks>500000)$fatal(1,"directed finite cycle limit");
        arready=rst_n&&rleft==0&&ticks%7>=3;
        rvalid=rst_n&&rleft!=0&&ticks%5!=0;rlast=rleft==1;
        if(rvalid)for(j=0;j<16;j=j+1)rdata[16*j+:16]=source[rindex*16+j];
        out_ready=rst_n&&ticks%17>=10&&!(phase==1&&ticks-phase_start<128);
    end
    always @(posedge clk)if(rst_n)begin
        if(failed)$fatal(1,"realpoint DUT fault %h",fault);
        if(held_ar&&(!arvalid||{arlen,araddr}!==saved_ar))$fatal(1,"directed AR hold");
        if(held_out&&(!out_valid||out_bundle!==saved_out))$fatal(1,"directed RGB/tag/mask hold");
        held_ar<=arvalid&&!arready;saved_ar<={arlen,araddr};
        held_out<=out_valid&&!out_ready;saved_out<=out_bundle;
        if(arvalid&&!arready)ar_stall=ar_stall+1;
        if(out_valid&&!out_ready)out_stall=out_stall+1;
        if(in_valid&&!in_ready)input_stall=input_stall+1;
        if(in_valid&&in_ready)begin
            if(in_tag!=sent||{in_u,in_v,in_tag}!==requests[sent])$fatal(1,"directed request tag/order");
            sent=sent+1;
        end
        if(arvalid&&arready)begin
            off=araddr-frame_base;
            if(rleft!=0||araddr<frame_base||arlen!=7||off%64||off+64>N/2)$fatal(1,"directed actual DDR burst/bank/bounds");
            rleft<=8;rindex<=off/8;read_bursts=read_bursts+1;
        end
        if(rvalid)begin rleft<=rleft-1;rindex<=rindex+1;end
        if(dut.mapped_valid&&dut.mapped_ready)begin
            if(phase!=1||dut.mapped_tag!=maps||{dut.mapped_black,dut.mapped_x,dut.mapped_y}!==mapped[maps])$fatal(1,"exact13 mapped/guard/tag point=%0d",maps);
            maps=maps+1;
        end
        if(dut.sample_valid&&dut.sample_ready)begin
            if(dut.sample_tag!=samples||dut.sample_mask!==expected[phase*POINTS+samples][48])$fatal(1,"sample mask/order");
            if(phase==0&&{dut.sample_x,dut.sample_y}!==requests[samples][71:24])$fatal(1,"raw sampler coordinates");
            if(phase==1&&{dut.sample_x,dut.sample_y}!==mapped[samples][47:0])$fatal(1,"corrected sampler coordinates");
            samples=samples+1;
        end
        if(phase==1&&!first_miss&&dut.sampler.cache.inner.query_valid&&dut.sampler.cache.inner.state==0&&(|dut.sampler.cache.inner.in_bounds))begin
            if(dut.sampler.cache.inner.accept_query)begin
                if(dut.sampler.cache.inner.accept_fast||!dut.sampler.cache.inner.accept_slow)$fatal(1,"first supported accepted fast/stale");
                first_miss=1;first_accept_tag=dut.sampler.cache.inner.query_tag[23:0];
            end else begin
                if(!(dut.sampler.cache.inner.v0||dut.sampler.cache.inner.v1))$fatal(1,"query wait lacks actual old fast stages");
                first_wait_cycles=first_wait_cycles+1;
            end
        end
        if(out_valid&&out_ready)begin
            if(received>=POINTS||out_bundle!==expected[phase*POINTS+received])$fatal(1,"realpoint RGB24/mask/tag phase=%0d point=%0d expected=%h got=%h",phase,received,expected[phase*POINTS+received],out_bundle);
            if(phase==1)begin
                if(coverage[received][3])begin if(!out_masked||mapped[received][23:0]!==24'hffff00)$fatal(1,"y=-256 weightzero geometry boundary");zero_weight_checked=zero_weight_checked+1;end
                if(coverage[received][0])begin if(out_masked||out_rgb==0)$fatal(1,"partial neighbour wrongly fully black");partial_checked=partial_checked+1;end
                if(coverage[received][1])begin if(!out_masked||out_rgb!=0)$fatal(1,"fulloutside mask missing");masked_checked=masked_checked+1;end
                if(coverage[received][2])begin if(out_masked||out_rgb!=0)$fatal(1,"real black misclassified as mask");black_checked=black_checked+1;end
                if(expected[received][23:0]!=out_rgb)different_checked=different_checked+1;
            end
            received=received+1;total=total+1;
        end
    end
    initial begin
        if(VEC_WIDTH!=W||VEC_HEIGHT!=H||VEC_RADIUS_GUARD_Q22!=1387217||POINTS<256)$fatal(1,"native exact contract");
        $readmemh("source1.mem",source);$readmemh("requests.mem",requests);$readmemh("point_expected0.mem",expected,0,POINTS-1);
        $readmemh("point_expected1.mem",expected,POINTS,2*POINTS-1);$readmemh("point_maps.mem",mapped);$readmemh("point_coverage.mem",coverage);
        configure();repeat(12)@(negedge clk);rst_n=1;
        for(f=0;f<2;f=f+1)begin
            @(negedge clk);phase=f;phase_start=ticks;sent=0;received=0;samples=0;maps=0;
            configure();frame_base=f*S;correction_enable=f;frame_valid=1;
            do @(posedge clk);while(!frame_ready);
            #1;if(dut.sampler.cache.inner.valid_lines!==128'd0||dut.sampler.cache.inner.base!==frame_base)$fatal(1,"directed actual epoch clear/base");
            @(negedge clk);frame_valid=0;
            // Live mode/config no longer belong to the accepted frame.
            correction_enable=!f;ocx=-12345;ocy=65432;k1=-765432;k2=1234567;rcos=-456789;rsin=345678;
            for(i=0;i<POINTS;i=i+1)begin
                @(negedge clk);{in_u,in_v,in_tag}=requests[i];in_valid=1;
                do @(posedge clk);while(!in_ready);
                @(negedge clk);in_valid=0;
            end
            wait(received==POINTS);
            wait(frame_ready&&rleft==0&&!arvalid&&!out_valid&&dut.sampler.cache.queue_count==0&&dut.sampler.cache.inner.state==0&&!dut.sampler.cache.inner.v0&&!dut.sampler.cache.inner.v1);
            repeat(8)@(negedge clk);
            if(sent!=POINTS||samples!=POINTS||maps!=(f==1?POINTS:0)||completed_queries!=(f+1)*POINTS)$fatal(1,"directed count/drain");
            $display("PASS PENN_POINTS phase=%0d points=%0d sent=%0d maps=%0d samples=%0d output=%0d",f,POINTS,sent,maps,samples,received);
        end
        if(first_wait_cycles==0||first_miss!=1||first_accept_tag!=4||zero_weight_checked!=1)$fatal(1,"firstquery wait/miss/boundary coverage");
        if(total!=2*POINTS||partial_checked==0||masked_checked==0||black_checked==0||different_checked==0||ar_stall==0||out_stall==0||input_stall==0||read_bursts==0)$fatal(1,"realpoint coverage missing");
        summary=$fopen("summary.json","w");
        $fdisplay(summary,"{\"passed\":true,\"points_each_mode\":%0d,\"outputs\":%0d,\"cycles\":%0d,\"partial\":%0d,\"full_mask\":%0d,\"real_black\":%0d,\"changed\":%0d,\"ar_stall\":%0d,\"out_stall\":%0d,\"input_stall\":%0d,\"read_bursts\":%0d,\"first_wait_cycles\":%0d,\"first_accept_tag\":%0d,\"zero_weight_boundary\":%0d,\"final_drain\":true}",POINTS,total,ticks,partial_checked,masked_checked,black_checked,different_checked,ar_stall,out_stall,input_stall,read_bursts,first_wait_cycles,first_accept_tag,zero_weight_checked);
        $fclose(summary);$display("PASS PENN_DIRECTED: exact13 source240 nativecoords raw/corrected partial/fullmask/realblack backpressure drain cycles=%0d",ticks);$finish;
    end
endmodule
