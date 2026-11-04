`timescale 1ns/1ps
module tb_cache_registered_return;
    reg clk=0,rst_n=0,frame_valid=0,in_valid=0,out_ready=1;
    always #4 clk=~clk;
    reg signed [23:0] in_x=0,in_y=0;
    reg [23:0] in_tag=0;
    wire [1:0] frame_ready,in_ready,out_valid,arvalid,failed;
    wire [23:0] p00[0:1],p10[0:1],p01[0:1],p11[0:1],out_tag[0:1];
    wire [7:0] fx[0:1],fy[0:1],fault[0:1];
    wire [27:0] araddr[0:1];
    wire [3:0] arlen[0:1];
    wire [31:0] hits[0:1],misses[0:1],completed[0:1];
    reg arready=0,raw_valid=0,raw_last=0;
    reg [3:0] raw_id=0;
    reg [255:0] raw_data=0;
    reg returned_valid=0,returned_last=0;
    reg [3:0] returned_id=0;
    reg [255:0] returned_data=0;
    // Exactly the lane's complete one-cycle return bundle, including bubbles.
    always @(posedge clk)begin
        returned_data<=raw_data;returned_id<=raw_id;returned_last<=raw_last;
        if(!rst_n)returned_valid<=0;else returned_valid<=raw_valid;
    end
    genvar g;
    generate for(g=0;g<2;g=g+1)begin: candidate
        ddr_neighbour_cache_scatter4_rowpipe #(.WIDTH(1920),.HEIGHT(1080),.INDEX_BITS(10),
            .ROW_PADDED_INDEX(1),.TIMEOUT_BITS(16),.REGISTERED_RETURN(g)) dut(
            .clk(clk),.rst_n(rst_n),.frame_valid(frame_valid),.frame_ready(frame_ready[g]),.frame_base(28'd0),
            .in_valid(in_valid),.in_ready(in_ready[g]),.in_x(in_x),.in_y(in_y),.in_tag(in_tag),
            .out_valid(out_valid[g]),.out_ready(out_ready),.p00(p00[g]),.p10(p10[g]),.p01(p01[g]),.p11(p11[g]),
            .fx(fx[g]),.fy(fy[g]),.out_tag(out_tag[g]),.araddr(araddr[g]),.arlen(arlen[g]),.arvalid(arvalid[g]),.arready(arready),
            .rdata(returned_data),.rvalid(returned_valid),.rlast(returned_last),.rid(returned_id),
            .failed(failed[g]),.fault(fault[g]),.hits(hits[g]),.misses(misses[g]),.completed_queries(completed[g]));
    end endgenerate
    integer ticks=0,left=0,beat=0,block_pixel=0,mode=0;
    reg stall_ar=0,gaps=0,immediate=1,check_outputs=1,compare_modes=1;
    integer sent=0,received=0,ar_first=0,ar_stalls=0,r_gaps=0,final_beats=0;
    integer bundle_edges=0,equivalent_edges=0,checked_pixels=0,reset_pending=0,errors=0,early_contract=0;
    integer expected_x[0:255],expected_y[0:255];
    reg [23:0] expected_tag[0:255];
    reg [7:0] expected_fx[0:255],expected_fy[0:255];
    function [15:0] memory_pixel(input integer n);
        begin memory_pixel=(n*37)^(n>>5)^16'h6b31;end
    endfunction
    function [23:0] rgb(input integer x,y);
        reg [15:0] p;
        begin
            p=memory_pixel(y*1920+x);
            rgb=(x<0 || x>=1920 || y<0 || y>=1080) ? 24'd0:
                {p[15:11],p[15:13],p[10:5],p[10:9],p[4:0],p[4:2]};
        end
    endfunction
    integer raw_block,raw_beat;
    always @(negedge clk)begin
        arready=rst_n && !stall_ar && left==0;
        raw_valid=rst_n && left>0 && (!gaps || ticks%3!=0);
        raw_last=left==1;raw_id=(mode==1 && beat==3)?4'h7:0;
        if(mode==2 && beat==3)raw_last=1;
        if(mode==3 && left==1)raw_last=0;
        raw_block=block_pixel;raw_beat=beat;
        if(immediate && arvalid[0] && arready)begin
            raw_valid=1;raw_last=0;raw_id=0;raw_block=araddr[0]*2;raw_beat=0;
        end
        if(mode==4 && rst_n && left==0)begin raw_valid=1;raw_last=1;raw_id=0;end
        if(mode==5 && rst_n && left==0)begin raw_valid=1;raw_last=0;raw_id=0;end
        for(integer j=0;j<16;j=j+1)raw_data[j*16+:16]=memory_pixel(raw_block+16*raw_beat+j);
    end
    reg [255:0] sampled_data;
    reg [3:0] sampled_id;
    reg sampled_valid,sampled_last;
    always @(posedge clk)begin
        sampled_data=raw_data;sampled_id=raw_id;sampled_last=raw_last;sampled_valid=rst_n&&raw_valid;
        if(!rst_n)begin
            if(returned_valid)reset_pending=reset_pending+1;
            left=0;beat=0;block_pixel=0;sent=0;received=0;
        end else begin
            ticks=ticks+1;
            if(compare_modes && {frame_ready[0],in_ready[0],out_valid[0],arvalid[0],araddr[0],arlen[0],failed[0],fault[0],hits[0],misses[0],completed[0]} !==
               {frame_ready[1],in_ready[1],out_valid[1],arvalid[1],araddr[1],arlen[1],failed[1],fault[1],hits[1],misses[1],completed[1]})
                $fatal(1,"Registered-return mode changed a protocol edge or miss-cycle count");
            if(compare_modes)equivalent_edges=equivalent_edges+1;
            if(compare_modes && returned_valid && candidate[1].dut.inner.state==candidate[1].dut.inner.AR)
                $fatal(1,"Legal registered return unexpectedly reached AR state");
            if(compare_modes && out_valid[0] && {p00[0],p10[0],p01[0],p11[0],fx[0],fy[0],out_tag[0]} !==
                               {p00[1],p10[1],p01[1],p11[1],fx[1],fy[1],out_tag[1]})
                $fatal(1,"Registered-return output differs from default mode");
            if(arvalid[0]&&!arready)ar_stalls=ar_stalls+1;
            if(left>0&&!raw_valid)r_gaps=r_gaps+1;
            if(arvalid[0]&&arready)begin
                if(left!=0 || arlen[0]!=7)$fatal(1,"Invalid AR reservation");
                left=8;beat=0;block_pixel=araddr[0]*2;
                if(raw_valid)ar_first=ar_first+1;
            end
            if(raw_valid && mode!=4 && mode!=5)begin
                if(left==0)$fatal(1,"Raw R without reservation");
                left=left-1;beat=beat+1;
            end
            if(returned_valid && returned_last)final_beats=final_beats+1;
            if(check_outputs)begin
                if(failed[1])$fatal(1,"Unexpected registered-return failure");
                if(in_valid&&in_ready[1])begin
                    expected_x[sent]=$signed(in_x)>>>8;expected_y[sent]=$signed(in_y)>>>8;
                    expected_fx[sent]=in_x[7:0];expected_fy[sent]=in_y[7:0];expected_tag[sent]=in_tag;sent=sent+1;
                end
                if(out_valid[1]&&out_ready)begin
                    if(received>=sent || p00[1]!==rgb(expected_x[received],expected_y[received]) ||
                       p10[1]!==rgb(expected_x[received]+1,expected_y[received]) ||
                       p01[1]!==rgb(expected_x[received],expected_y[received]+1) ||
                       p11[1]!==rgb(expected_x[received]+1,expected_y[received]+1) ||
                       {fx[1],fy[1],out_tag[1]}!=={expected_fx[received],expected_fy[received],expected_tag[received]})
                        $fatal(1,"Independent four-neighbour data/tag mismatch query=%0d",received);
                    received=received+1;checked_pixels=checked_pixels+4;
                end
            end
        end
        #1;
        if({returned_valid,returned_last,returned_id,returned_data}!=={sampled_valid,sampled_last,sampled_id,sampled_data})
            $fatal(1,"Return bundle fields lost their common one-cycle alignment");
        bundle_edges=bundle_edges+1;
    end
    task reset_cache;
        begin
            @(negedge clk);rst_n=0;in_valid=0;frame_valid=0;mode=0;out_ready=1;stall_ar=0;
            repeat(4)@(negedge clk);rst_n=1;repeat(2)@(negedge clk);
            frame_valid=1;do @(posedge clk);while(!(&frame_ready));
            @(negedge clk);frame_valid=0;
        end
    endtask
    task query(input integer x,y,input integer tag);
        begin
            @(negedge clk);in_valid=1;in_x=x;in_y=y;in_tag=tag;
            do @(posedge clk);while(!(&in_ready));
            @(negedge clk);in_valid=0;
        end
    endtask
    task drain;
        begin wait(received==sent);repeat(2)@(negedge clk);end
    endtask
    integer n;
    initial begin
        reset_cache();stall_ar=1;
        query(127*256+19,37,1);wait(arvalid[1]);repeat(7)@(negedge clk);stall_ar=0;drain();
        query(1919*256+11,1079*256+73,2);drain();
        gaps=1;
        query(120*256+41,23*256+47,3);query(-1*256+63,10*256+9,4);
        query(-1*256+5,-1*256+7,5);query(127*256,64*256,6);drain();
        out_ready=0;
        for(n=0;n<4;n=n+1)query((120+n)*256+5,23*256+7,20+n);
        repeat(17)@(negedge clk);out_ready=1;drain();
        // Reset with the final external beat already captured by the lane.
        check_outputs=0;reset_cache();immediate=1;gaps=0;
        query(0,0,60);wait(raw_valid&&raw_last);@(posedge clk);#1;
        if(!returned_valid || !returned_last)$fatal(1,"Final return reset setup missing");
        @(negedge clk);rst_n=0;repeat(3)@(negedge clk);
        reset_cache();check_outputs=1;query(0,0,61);drain();
        for(n=1;n<=4;n=n+1)begin
            check_outputs=0;reset_cache();mode=n;gaps=1;
            if(n!=4)query(127*256+7,13,70+n);
            wait(failed[1]);repeat(5)@(negedge clk);
            if(fault[1]!=(n==4 ? 8'h04:8'h03) || in_ready[1] || out_valid[1])
                $fatal(1,"Registered malformed/unsolicited return not quarantined");
            errors=errors+1;
        end
        // Deliberately violate the registered-return contract: capture an R
        // before AR is accepted, then let that buffered R arrive on AR's edge.
        // Mode 1 must quarantine it; generic mode 0 retains AR-edge acceptance.
        reset_cache();stall_ar=1;compare_modes=0;
        query(0,0,90);wait(arvalid[1]);@(negedge clk);mode=5;
        wait(raw_valid);@(posedge clk);#1;mode=0;stall_ar=0;
        @(posedge clk);
        if(!returned_valid || !arready || candidate[1].dut.inner.receiving || candidate[1].dut.inner.scatter_write)
            $fatal(1,"Early-return contract test did not hit strict AR rejection");
        #1;if(!failed[1] || fault[1]!=8'h04 || failed[0])$fatal(1,"REGISTERED_RETURN contract mode was not enforced");
        early_contract=early_contract+1;
        if(ar_first<8 || ar_stalls<7 || r_gaps==0 || reset_pending==0 || errors!=4 || checked_pixels<44)
            $fatal(1,"Registered return coverage vacuous");
        $display("METRIC registered_return equivalent_edges=%0d bundle_edges=%0d AR_first=%0d AR_stalls=%0d R_gaps=%0d final=%0d pixels=%0d pending_reset=%0d errors=%0d early_contract=%0d",equivalent_edges,bundle_edges,ar_first,ar_stalls,r_gaps,final_beats,checked_pixels,reset_pending,errors,early_contract);
        $display("PASS REGISTERED_RETURN exact-cycle legacy comparison, whole-bundle protocol, pixel/tag/boundary/reset/fault");$finish;
    end
    initial begin #4000000;$fatal(1,"Registered return test timeout");end
endmodule
