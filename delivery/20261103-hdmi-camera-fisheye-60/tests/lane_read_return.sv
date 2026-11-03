`timescale 1ns/1ps
// Exercise the actual lane register boundary with an owned, checked eight-beat
// core double. Whole-system tests retain the real arbiters/cache separately.
module tb_lane_read_return;
    reg clk=0,rst_n=0,frame_valid=0,arready=0,rvalid=0,rlast=0;
    reg [255:0] rdata=0;
    reg [3:0] rid=0;
    wire frame_ready,arvalid,failed;
    wire [7:0] fault;
    always #4 clk=!clk;
    hdmi_camera_fisheye_lane #(.WIDTH(32),.HEIGHT(32),.LANE_HEIGHT(16)) dut(
        .clk(clk),.rst_n(rst_n),.frame_valid(frame_valid),.frame_ready(frame_ready),.cfg_corrected(1'b1),
        .source_base(28'd0),.output_base(28'd8192),.frame_id(32'd123),
        .arvalid(arvalid),.arready(arready),.rdata(rdata),.rvalid(rvalid),.rlast(rlast),.rid(rid),
        .awready(1'b0),.wready(1'b0),.wlast(1'b0),.failed(failed),.fault(fault));
    reg observed=0,previous_valid=0,previous_last;
    reg [255:0] previous_data;
    reg [3:0] previous_id;
    integer payload_checks=0,valid_checks=0,bubbles=0,first_same_ar=0,last_beats=0,resets_pending=0,faults=0;
    always @(posedge clk)begin
        if(observed)begin
            if(dut.core.rdata!==previous_data || dut.core.rid!==previous_id || dut.core.rlast!==previous_last)
                $fatal(1,"Return payload is not exactly one cycle delayed");
            payload_checks=payload_checks+1;
            if(rst_n)begin
                if(dut.core.rvalid!==previous_valid)$fatal(1,"Return valid offset/reset mismatch");
                if(previous_valid)begin valid_checks=valid_checks+1;if(previous_last)last_beats=last_beats+1;end
                else bubbles=bubbles+1;
            end
        end
        if(rst_n && arvalid && arready && rvalid)first_same_ar=first_same_ar+1;
        previous_valid=rst_n && rvalid;previous_data=rdata;previous_id=rid;previous_last=rlast;observed=1;
    end
    task reset_all;
        begin
            @(negedge clk);rst_n=0;frame_valid=0;arready=0;rvalid=0;rlast=0;
            repeat(3)@(negedge clk);rst_n=1;
        end
    endtask
    task launch;
        begin wait(frame_ready);@(negedge clk);frame_valid=1;@(negedge clk);frame_valid=0;wait(arvalid);end
    endtask
    task beat(input integer n,input integer fault_kind);
        begin
            @(negedge clk);arready=1;rvalid=1;rdata={8{32'h12340000+n}};
            rid=fault_kind==1 ? 4'h3:4'h0;rlast=(n==7 && fault_kind!=3) || fault_kind==2;
            @(negedge clk);arready=0;rvalid=0;rdata=~rdata;rid=4'hf;rlast=~rlast;
        end
    endtask
    task complete_burst;
        integer n;
        begin
            launch();
            for(n=0;n<8;n=n+1)begin
                beat(n,0);
                if(n==2 || n==5)repeat(4)begin @(negedge clk);rdata=rdata+256'd321;rid=rid+1'b1;rlast=!rlast;end
            end
            repeat(3)@(negedge clk);
            if(failed || dut.core.received!=8)$fatal(1,"Clean burst lost or duplicated a beat");
        end
    endtask
    integer n,kind;
    initial begin
        reset_all();complete_burst();
        reset_all();launch();
        @(negedge clk);arready=1;rvalid=1;rdata=256'hbadbeef;rid=0;rlast=0;
        @(negedge clk);
        if(!dut.returned_valid)$fatal(1,"Reset case lacks pending captured beat");
        rst_n=0;rvalid=0;arready=0;resets_pending=resets_pending+1;
        repeat(3)@(negedge clk);rst_n=1;
        repeat(3)@(negedge clk);
        if(dut.core.received || dut.core.rvalid)$fatal(1,"Reset pending beat leaked into new epoch");
        complete_burst();
        for(kind=1;kind<=3;kind=kind+1)begin
            reset_all();launch();
            for(n=0;n<(kind==3 ? 7:2);n=n+1)beat(n,0);
            beat(kind==3 ? 7:2,kind);
            repeat(3)@(negedge clk);
            if(!failed || fault!==(kind==1 ? 8'h71:kind==2 ? 8'h73:8'h74))$fatal(1,"Delayed core error not propagated");
            faults=faults+1;
        end
        if(first_same_ar!=6 || resets_pending!=1 || faults!=3 || bubbles<20 || payload_checks<80)
            $fatal(1,"Return boundary coverage incomplete");
        $display("PASS LANE RETURN payload=%0d valid=%0d bubbles=%0d first_AR_R=%0d last=%0d reset_pending=%0d faults=%0d",payload_checks,valid_checks,bubbles,first_same_ar,last_beats,resets_pending,faults);$finish;
    end
    initial begin repeat(20000)@(posedge clk);$fatal(1,"watchdog");end
endmodule

module hdmi_camera_fisheye_core #(
    parameter WIDTH=32,HEIGHT=32,INDEX_BITS=7,TIMEOUT_BITS=26,ROW_PADDED_INDEX=0
)(
    input clk,rst_n,frame_valid,output frame_ready,input[27:0]frame_base,input cfg_corrected,
    input in_valid,output in_ready,input signed[23:0]in_u,in_v,input[23:0]in_tag,
    output out_valid,input out_ready,output[23:0]out_rgb,out_tag,output out_masked,
    output[27:0]araddr,output[3:0]arlen,output reg arvalid,input arready,
    input[255:0]rdata,input rvalid,rlast,input[3:0]rid,
    output reg failed,output reg[7:0]fault,output[31:0]hits,misses,completed_queries
);
    reg active;integer received;
    assign frame_ready=!active && !failed;assign in_ready=0;
    assign out_valid=0;assign out_rgb=0;assign out_tag=0;assign out_masked=0;
    assign araddr=frame_base;assign arlen=7;assign hits=0;assign misses=0;assign completed_queries=0;
    always @(posedge clk)begin
        if(!rst_n)begin active<=0;arvalid<=0;failed<=0;fault<=0;received<=0;end
        else begin
            if(frame_valid && frame_ready)begin active<=1;arvalid<=1;received<=0;end
            if(arvalid && arready)arvalid<=0;
            if(rvalid && !failed)begin
                if(!active)begin failed<=1;fault<=8'h70;end
                else if(rid!=0)begin failed<=1;fault<=8'h71;end
                else if(rlast && received!=7)begin failed<=1;fault<=8'h73;end
                else if(!rlast && received==7)begin failed<=1;fault<=8'h74;end
                else received<=received+1;
            end
        end
    end
endmodule

module ddr_adaptive_result_writer #(
    parameter WIDTH=32,HEIGHT=16,TILE_W=8,TILE_H=8,TIMEOUT_BITS=26
)(
    input clk,rst_n,frame_valid,frame_tiled,output frame_ready,input[27:0]frame_base,input[31:0]frame_id,
    input in_valid,output in_ready,input[23:0]in_rgb,in_tag,
    output[27:0]awaddr,output[3:0]awlen,output awvalid,input awready,
    output[255:0]wdata,output[31:0]wstrb,input wready,wlast,
    output done,failed,output[7:0]fault,output[31:0]accepted_pixels,written_beats,last_checksum,completed_id
);
    assign frame_ready=1;assign in_ready=0;assign awaddr=0;assign awlen=0;assign awvalid=0;
    assign wdata=0;assign wstrb=0;assign done=0;assign failed=0;assign fault=0;
    assign accepted_pixels=0;assign written_beats=0;assign last_checksum=0;assign completed_id=0;
endmodule
