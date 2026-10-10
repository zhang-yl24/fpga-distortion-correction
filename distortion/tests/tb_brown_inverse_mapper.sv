`timescale 1ns/1ps
`include "D:/English/FPGA/distortion/build/brown_sim/counts.vh"
module tb_brown_inverse_mapper;
    localparam N=`BROWN_N,TOTAL=`BROWN_TOTAL;
    reg clk=0;always #4 clk=~clk;
    reg rst=1,cfg_valid=0,in_valid=0,out_ready=0;
    wire cfg_ready,in_ready,out_valid,out_black;
    reg signed [23:0] cfg_out_cx,cfg_out_cy,cfg_src_cx,cfg_src_cy,cfg_src_fx,cfg_src_fy;
    reg signed [31:0] cfg_inv_fx,cfg_inv_fy,cfg_k1,cfg_k2,cfg_k3,cfg_p1,cfg_p2;
    reg signed [23:0] in_u=0,in_v=0;wire signed [23:0] out_x,out_y;
    reg [23:0] in_tag=0;wire [23:0] out_tag;
    brown_inverse_mapper dut(.*);
    reg [367:0] configs[0:3];reg [96:0] vectors[0:TOTAL-1];
    integer ticks=0,received=0,phase=0,q=0,streak=0,peak_streak=0;reg held=0;
    reg [72:0] held_data;
    always @(posedge clk) begin
        if(rst) begin ticks<=0;held<=0;end
        else begin
            ticks<=ticks+1;
            if(in_valid && in_ready) begin
                streak<=streak+1;
                if(streak+1>peak_streak) peak_streak<=streak+1;
            end else streak<=0;
            if(held && (!out_valid || {out_black,out_tag,out_x,out_y}!==held_data))
                $fatal(1,"Mapper output changed during backpressure");
            held<=out_valid && !out_ready;held_data<={out_black,out_tag,out_x,out_y};
            if(out_valid && out_ready) begin
                if(out_tag!==received || {out_black,out_x,out_y}!==vectors[received][48:0])
                    $fatal(1,"Mapper mismatch tag=%0d expected tag=%0d got=%h expected=%h",out_tag,received,{out_black,out_x,out_y},vectors[received][48:0]);
                received<=received+1;
            end
            if(cfg_valid && cfg_ready && |dut.valid) $fatal(1,"Configuration changed an in-flight frame");
        end
    end
    always @(negedge clk) out_ready=!rst && (received<256 || ticks%31>=8);
    task configure(input integer c);
        begin
            @(negedge clk);cfg_valid=1;
            {cfg_out_cx,cfg_out_cy,cfg_src_cx,cfg_src_cy,cfg_src_fx,cfg_src_fy,cfg_inv_fx,cfg_inv_fy,cfg_k1,cfg_k2,cfg_k3,cfg_p1,cfg_p2}=configs[c];
            do @(posedge clk);while(!cfg_ready);
            @(negedge clk);cfg_valid=0;
        end
    endtask
    task send(input integer index);
        begin
            @(negedge clk);in_valid=1;in_u=vectors[index][96:73];in_v=vectors[index][72:49];in_tag=index;
            do @(posedge clk);while(!in_ready);
        end
    endtask
    initial begin
        $readmemh("configs.mem",configs);$readmemh("vectors.mem",vectors);
        repeat(6) @(posedge clk);@(negedge clk);rst=0;
        for(phase=0;phase<4;phase=phase+1) begin
            // Next configuration is offered while prior output can still be
            // stalled; handshake must wait until all prior tagged rays drain.
            configure(phase);
            for(q=phase*N;q<(phase+1)*N;q=q+1) send(q);
            @(negedge clk);in_valid=0;
        end
        wait(received==TOTAL);
        if(peak_streak<64) $fatal(1,"No sustained one-query-per-cycle mapper segment");
        // Mid-pipeline reset abandons outstanding tags and configuration.
        send(0);repeat(3) @(posedge clk);@(negedge clk);rst=1;in_valid=0;
        repeat(6) @(posedge clk);@(negedge clk);rst=0;received=0;
        if(in_ready) $fatal(1,"Mapper accepted a query without fresh configuration");
        configure(0);for(q=0;q<64;q=q+1) send(q);@(negedge clk);in_valid=0;wait(received==64);
        $display("PASS Brown inverse mapper: %0d integer Python golden rays, identity/radial/tangential/overflow, signed Q9.22 math, explicit black domain, configuration drain, tagged output backpressure and mid-pipeline reset recovery.",TOTAL);
        $finish;
    end
    initial begin #10000000;$fatal(1,"Brown mapper timeout received=%0d",received);end
endmodule
