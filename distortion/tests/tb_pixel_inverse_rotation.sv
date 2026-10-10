`timescale 1ns/1ps
`include "D:/English/FPGA/distortion/build/rotation_sim/counts.vh"
module tb_pixel_inverse_rotation;
    reg clk=0;always #4 clk=~clk;
    reg rst=1,cfg_valid=0,in_valid=0,out_ready=0;
    reg signed [23:0] cfg_cx,cfg_cy,in_u=0,in_v=0;
    reg signed [31:0] cfg_cos,cfg_sin;
    reg [23:0] in_tag=0;wire [23:0] out_tag;
    wire cfg_ready,in_ready,out_valid,out_black;wire signed [23:0] out_u,out_v;
    pixel_inverse_rotation dut(.*);
    reg [111:0] configs[0:`ROT_PHASES-1];reg [99:0] vectors[0:`ROT_TOTAL-1];
    integer ticks=0,received=0,phase=0,q,streak=0,peak=0;
    reg held=0;reg [72:0] held_data;
    always @(posedge clk) begin
        if(rst) begin held<=0;streak<=0;end
        else begin
            ticks<=ticks+1;
            if(in_valid && in_ready) begin streak<=streak+1;if(streak+1>peak) peak<=streak+1;end
            else streak<=0;
            if(held && (!out_valid || {out_black,out_tag,out_u,out_v}!==held_data)) $fatal(1,"Rotation output changed under stall");
            held<=out_valid && !out_ready;held_data<={out_black,out_tag,out_u,out_v};
            if(out_valid && out_ready) begin
                if(out_tag!==received || {out_black,out_u,out_v}!=={vectors[received][48],vectors[received][47:0]})
                    $fatal(1,"Rotation mismatch vector=%0d tag=%0d got=%h golden=%h",received,out_tag,{out_black,out_u,out_v},vectors[received][48:0]);
                received<=received+1;
            end
            if(cfg_valid && cfg_ready && |dut.valid) $fatal(1,"Rotation config changed in flight");
        end
    end
    always @(negedge clk) out_ready=!rst && (received<256 || ticks%29>=7);
    task configure(input integer c);
        begin
            @(negedge clk);cfg_valid=1;{cfg_cx,cfg_cy,cfg_cos,cfg_sin}=configs[c];
            do @(posedge clk);while(!cfg_ready);
            @(negedge clk);cfg_valid=0;
        end
    endtask
    task send(input integer n);
        begin
            @(negedge clk);in_valid=1;in_u=vectors[n][99:76];in_v=vectors[n][75:52];in_tag=n;
            do @(posedge clk);while(!in_ready);
        end
    endtask
    initial begin
        $readmemh("configs.mem",configs);$readmemh("vectors.mem",vectors);
        repeat(8) @(negedge clk);rst=0;
        for(phase=0;phase<`ROT_PHASES;phase=phase+1) begin
            configure(phase);
            for(q=phase*`ROT_N;q<(phase+1)*`ROT_N;q=q+1) send(q);
            @(negedge clk);in_valid=0;
        end
        wait(received==`ROT_TOTAL);
        if(peak<64) $fatal(1,"Rotation pipeline cannot sustain one ray per cycle");
        configure(0);send(0);repeat(2) @(posedge clk);
        @(negedge clk);rst=1;in_valid=0;repeat(8) @(negedge clk);rst=0;received=0;
        if(in_ready) $fatal(1,"Rotation accepted without fresh config after reset");
        configure(0);for(q=0;q<64;q=q+1) send(q);@(negedge clk);in_valid=0;wait(received==64);
        $display("PASS inverse rotation: %0d independent integer vectors, 12 angles, signed overflow black, config drain, one ray per cycle, tagged stalls and reset recovery.",`ROT_TOTAL);$finish;
    end
    initial begin #20000000;$fatal(1,"Rotation test timeout received=%0d",received);end
endmodule
