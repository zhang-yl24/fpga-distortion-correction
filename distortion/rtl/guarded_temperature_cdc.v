`timescale 1ns/1ps
// Fail-closed 27MHz ADC -> core crossing. The multi-bit bus is held from
// request until acknowledgement. A separate core timer detects a stopped
// source clock even when the last source-domain healthy level remains high.
module guarded_temperature_cdc #(
    parameter SNAPSHOT_CYCLES=2700000,
    parameter [31:0] SOURCE_MAX_AGE=54000000,CORE_MAX_AGE=125000000,
    parameter [11:0] MIN_CODE=1913,MAX_CODE=2732
)(
    input source_clk,core_clk,arst_n,
    input sample_valid,failed,input [7:0] fault,
    input [15:0] raw_word,input [11:0] code12,
    input [31:0] sample_age,samples,conversions,
    input over_temp,input [4:0] alarm,input [95:0] source_extra,
    output wire healthy,output reg snapshot_valid,output reg snapshot_event,
    output reg [31:0] snapshot_age,
    output wire held_valid,held_failed,output wire [7:0] held_fault,
    output wire [15:0] held_raw,output wire [11:0] held_code,
    output wire [31:0] held_age,held_samples,held_conversions,
    output wire held_over_temp,output wire [4:0] held_alarm,output wire [95:0] held_extra
);
    (* async_reg="true" *) reg [1:0] source_reset=0,core_reset=0;
    always @(posedge source_clk or negedge arst_n)
        if(!arst_n)source_reset<=0;else source_reset<={source_reset[0],1'b1};
    always @(posedge core_clk or negedge arst_n)
        if(!arst_n)core_reset<=0;else core_reset<={core_reset[0],1'b1};
    reg source_healthy=0;
    (* async_reg="true" *) reg [1:0] healthy_sync=0;
    reg request_toggle=0,ack_toggle=0;
    (* async_reg="true" *) reg [1:0] request_sync=0,ack_sync=0;
    reg [31:0] period_count=0;
    reg [236:0] source_bus=0,core_bus=0;
    wire held_healthy;
    assign {held_extra,held_valid,held_failed,held_fault,held_raw,held_code,held_age,
        held_samples,held_conversions,held_over_temp,held_alarm,held_healthy}=core_bus;
    assign healthy=core_reset[1] && healthy_sync[1] && snapshot_valid &&
        snapshot_age<CORE_MAX_AGE && held_healthy && held_valid && !held_failed &&
        held_age<SOURCE_MAX_AGE && held_samples>=2 && held_code>=MIN_CODE &&
        held_code<=MAX_CODE && held_code==held_raw[15:4] && !held_over_temp && held_alarm==0;
    always @(posedge source_clk or negedge arst_n)begin
        if(!arst_n)begin
            source_healthy<=0;request_toggle<=0;ack_sync<=0;period_count<=0;source_bus<=0;
        end else if(!source_reset[1])begin
            source_healthy<=0;request_toggle<=0;ack_sync<=0;period_count<=0;source_bus<=0;
        end else begin
            // Register the complete multi-bit comparison before synchronizing
            // one bit; no combinational ADC comparator drives a CDC input.
            source_healthy<=sample_valid && !failed && sample_age<SOURCE_MAX_AGE &&
                code12>=MIN_CODE && code12<=MAX_CODE && samples>=2 && !over_temp && alarm==0;
            ack_sync<={ack_sync[0],ack_toggle};
            if(period_count<SNAPSHOT_CYCLES-1)period_count<=period_count+1'b1;
            if(period_count==SNAPSHOT_CYCLES-1 && request_toggle==ack_sync[1])begin
                period_count<=0;
                source_bus<={source_extra,sample_valid,failed,fault,raw_word,code12,sample_age,
                    samples,conversions,over_temp,alarm,source_healthy};
                request_toggle<=!request_toggle;
            end
        end
    end
    always @(posedge core_clk or negedge arst_n)begin
        if(!arst_n)begin
            request_sync<=0;healthy_sync<=0;ack_toggle<=0;core_bus<=0;
            snapshot_valid<=0;snapshot_event<=0;snapshot_age<=32'hFFFFFFFF;
        end else if(!core_reset[1])begin
            request_sync<=0;healthy_sync<=0;ack_toggle<=0;core_bus<=0;
            snapshot_valid<=0;snapshot_event<=0;snapshot_age<=32'hFFFFFFFF;
        end else begin
            request_sync<={request_sync[0],request_toggle};
            healthy_sync<={healthy_sync[0],source_healthy};
            snapshot_event<=0;
            if(snapshot_age!=32'hFFFFFFFF)snapshot_age<=snapshot_age+1'b1;
            if(request_sync[1]!=ack_toggle)begin
                core_bus<=source_bus;ack_toggle<=request_sync[1];
                snapshot_valid<=1;snapshot_event<=1;snapshot_age<=0;
            end
        end
    end
endmodule
