`timescale 1ns/1ps
// DEVELOPMENT: nominal10MHz cfg clock;1000000 FULL eligible periods =100ms.
// LOCK is qualified only as observed through this cfg-domain two-stage chain.
// Once released, a lock change never locally restarts configuration/DDR epochs.
module cfg100_startup_hold #(
    parameter integer SETTLE_CYCLES=1000000
)(input cfg_clk,input chip_reset_n,input cfg_locked,output reg cfg_reset_n=0);
    localparam integer CW=(SETTLE_CYCLES<=1)?1:$clog2(SETTLE_CYCLES);
    generate if(SETTLE_CYCLES<1 || SETTLE_CYCLES>1073741824)begin:invalid_parameter
        CFG_SETTLE_CYCLES_MUST_BE_POSITIVE_AND_BOUNDED invalid_configuration();
    end endgenerate
    (* async_reg="true" *) reg [1:0] release_sync=0,lock_sync=0;
    reg [CW-1:0] elapsed=0;
    reg armed=0;
    always @(posedge cfg_clk or negedge chip_reset_n)begin
        if(!chip_reset_n)begin release_sync<=0;lock_sync<=0;end
        else begin release_sync<={release_sync[0],1'b1};lock_sync<={lock_sync[0],cfg_locked};end
    end
    always @(posedge cfg_clk or negedge chip_reset_n)begin
        if(!chip_reset_n)begin elapsed<=0;armed<=0;cfg_reset_n<=0;end
        else if(!cfg_reset_n)begin
            if(!release_sync[1] || !lock_sync[1])begin elapsed<=0;armed<=0;end
            else if(!armed)begin armed<=1;elapsed<=0;end
            else if(elapsed==SETTLE_CYCLES-1)cfg_reset_n<=1;
            else elapsed<=elapsed+1'b1;
        end
    end
endmodule
