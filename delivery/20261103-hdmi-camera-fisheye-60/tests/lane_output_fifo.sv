`timescale 1ns/1ps
// Lane boundary unit: controlled core/writer doubles create sustained full,
// simultaneous push/pop, masked pixels, interrupted frames and sticky faults.
// Real core/cache/writer behavior is checked by system_contention.sv separately.
module tb_lane_output_fifo;
    reg clk=0,rst_n=0,frame_valid=0,cfg_corrected=0;
    reg [31:0] frame_id=0;
    reg [27:0] source_base=0,output_base=8192;
    wire frame_ready,done,failed;
    wire [7:0] fault;
    wire [31:0] completed_id;
    wire [27:0] completed_base;
    always #4 clk=!clk;
    hdmi_camera_fisheye_lane #(.WIDTH(32),.HEIGHT(32),.Y_START(8),.LANE_HEIGHT(16)) dut(
        .clk(clk),.rst_n(rst_n),.frame_valid(frame_valid),.frame_ready(frame_ready),.cfg_corrected(cfg_corrected),
        .source_base(source_base),.output_base(output_base),.frame_id(frame_id),
        .arready(1'b0),.rdata(256'd0),.rvalid(1'b0),.rlast(1'b0),.rid(4'd0),
        .awready(1'b0),.wready(1'b0),.wlast(1'b0),
        .done(done),.failed(failed),.fault(fault),.completed_id(completed_id),.completed_base(completed_base));
    reg [23:0] expected_rgb[0:4095],expected_tag[0:4095];
    integer head=0,tail=0,full_cycles=0,full_pop=0,refills=0,masked=0,checked=0;
    integer completed=0,resets_occupied=0,initializations=0,start_resets=0,coordinates=0,layout_faults=0;
    reg pending_initialization=0,descriptor_active=0;
    reg [27:0] expected_source,expected_destination;
    reg [31:0] expected_id;
    reg expected_cfg;
    always @(posedge clk)begin
        if(!rst_n)begin pending_initialization=0;descriptor_active=0;end
        else begin
            if(dut.begin_frame!==pending_initialization)$fatal(1,"launch must follow acceptance by one edge");
            if(dut.begin_frame)begin
                if(frame_ready || dut.coordinate_valid || !dut.core_frame_ready || !dut.writer_frame_ready)
                    $fatal(1,"initialization overlaps readiness or first coordinate");
                initializations=initializations+1;pending_initialization=0;descriptor_active=1;
            end
            if(descriptor_active)begin
                if(dut.core.frame_base!==expected_source || dut.core.cfg_corrected!==expected_cfg ||
                   dut.writer.frame_base!==expected_destination || dut.writer.frame_id!==expected_id)
                    $fatal(1,"descriptor changed after upstream handshake");
            end
            if(dut.coordinate_valid && dut.coordinate_ready)begin
                if(!descriptor_active || dut.core.in_u!==((dut.raster_tag%32)<<8) ||
                   dut.core.in_v!==((dut.raster_tag/32+8)<<8))$fatal(1,"global coordinate/tag pairing");
                coordinates=coordinates+1;
            end
            if(done)begin
                if(completed_id!==expected_id || completed_base!==expected_destination || dut.buffer_count!=0)
                    $fatal(1,"completed descriptor or FIFO drain mismatch");
                descriptor_active=0;
            end
            if(frame_valid && frame_ready && dut.valid_layout)begin
                expected_source=source_base;expected_destination=output_base;expected_id=frame_id;expected_cfg=cfg_corrected;
                pending_initialization=1;
            end
        end
    end
    always @(posedge clk)begin
        if(!rst_n || dut.failed || dut.begin_frame)begin
            if(rst_n && dut.begin_frame && dut.buffer_count!=0)$fatal(1,"frame boundary retained pixels");
            head=0;tail=0;
        end else begin
            if(dut.buffer_count!==tail-head)$fatal(1,"FIFO occupancy mismatch");
            if(dut.result_ready!==(dut.buffer_count<2 && !dut.failed))$fatal(1,"ready depends on downstream");
            if(dut.buffer_count==2)begin
                full_cycles=full_cycles+1;
                if(dut.writer_input_ready)begin
                    full_pop=full_pop+1;
                    if(dut.result_ready)$fatal(1,"full+pop bypass enabled");
                end
            end
            if(dut.buffer_pop)begin
                if(head==tail)$fatal(1,"empty pop");
                if(dut.writer.in_rgb!==expected_rgb[head] || dut.writer.in_tag!==expected_tag[head])
                    $fatal(1,"pixel/tag pairing or ordering");
                head=head+1;checked=checked+1;
            end
            if(dut.buffer_push)begin
                expected_rgb[tail]=dut.result_masked ? 24'd0:dut.result_rgb;
                expected_tag[tail]=dut.result_tag;tail=tail+1;
                if(dut.result_masked)masked=masked+1;
            end
            if(dut.buffer_push && dut.buffer_pop)refills=refills+1;
        end
    end
    task reset_all;
        begin @(negedge clk);rst_n=0;frame_valid=0;repeat(3)@(negedge clk);rst_n=1;end
    endtask
    task launch(input [31:0] id);
        begin
            wait(frame_ready);@(negedge clk);frame_id=id;source_base=id[7:0]*512;
            output_base=16384+id[7:0]*1024;cfg_corrected=id[0];frame_valid=1;
            @(negedge clk);frame_valid=0;
            // The producer owns these pins again immediately after acceptance.
            source_base=28'hfffffff;output_base=28'hfffffff;frame_id=~id;cfg_corrected=!cfg_corrected;
        end
    endtask
    task finish_frame(input [31:0] id);
        begin wait(done || failed);if(failed || completed_id!=id)$fatal(1,"frame completion");
            completed=completed+1;@(negedge clk);end
    endtask
    initial begin
        reset_all();launch(1);finish_frame(1);launch(2);finish_frame(2);
        launch(3);wait(dut.buffer_count==2);resets_occupied=resets_occupied+1;reset_all();
        launch(4);finish_frame(4);
        launch(32'h80000005);wait(failed);repeat(3)@(negedge clk);
        if(fault!=8'h75 || dut.buffer_count!=0 || dut.result_ready)$fatal(1,"fault did not quarantine FIFO");
        reset_all();launch(6);finish_frame(6);
        // Cancel a captured descriptor before its START edge initializes children.
        launch(7);
        if(!dut.begin_frame || dut.coordinate_valid)$fatal(1,"missing pending START reset window");
        rst_n=0;start_resets=start_resets+1;repeat(3)@(negedge clk);rst_n=1;
        launch(8);finish_frame(8);
        // A rejected overlap must never initialize either child.
        wait(frame_ready);@(negedge clk);source_base=0;output_base=0;frame_valid=1;
        @(negedge clk);frame_valid=0;
        if(!failed || fault!==8'h40 || dut.begin_frame)$fatal(1,"bad layout initialized child");
        layout_faults=layout_faults+1;reset_all();launch(9);finish_frame(9);
        if(completed!=6 || initializations!=8 || start_resets!=1 || layout_faults!=1 ||
           full_cycles<10 || full_pop<4 || refills<100 || masked<100 || checked<3072)
            $fatal(1,"FIFO coverage incomplete");
        $display("PASS LANE FIFO2 frames=%0d checked=%0d full_cycles=%0d full_pop=%0d simultaneous=%0d masked=%0d reset_occupied=%0d",completed,checked,full_cycles,full_pop,refills,masked,resets_occupied);
        $display("PASS LANE LAUNCH initializations=%0d coordinates=%0d reset_start=%0d bad_layout=%0d",initializations,coordinates,start_resets,layout_faults);
        $finish;
    end
    initial begin repeat(30000)@(posedge clk);$fatal(1,"watchdog");end
endmodule

module hdmi_camera_fisheye_core #(
    parameter WIDTH=32,HEIGHT=16,INDEX_BITS=7,TIMEOUT_BITS=26,ROW_PADDED_INDEX=0
)(
    input clk,rst_n,frame_valid,output frame_ready,input[27:0]frame_base,input cfg_corrected,
    input in_valid,output in_ready,input signed[23:0]in_u,in_v,input[23:0]in_tag,
    output reg out_valid,input out_ready,output reg[23:0]out_rgb,out_tag,output reg out_masked,
    output[27:0]araddr,output[3:0]arlen,output arvalid,input arready,
    input[255:0]rdata,input rvalid,rlast,input[3:0]rid,
    output failed,output[7:0]fault,output[31:0]hits,misses,completed_queries
);
    assign frame_ready=!out_valid;
    assign in_ready=!out_valid || out_ready;
    assign araddr=0;assign arlen=0;assign arvalid=0;assign failed=0;assign fault=0;
    assign hits=0;assign misses=0;assign completed_queries=0;
    always @(posedge clk)begin
        if(!rst_n || frame_valid)begin out_valid<=0;out_rgb<=0;out_tag<=0;out_masked<=0;end
        else if(in_ready)begin
            out_valid<=in_valid;
            if(in_valid)begin out_tag<=in_tag;out_rgb<=(in_tag*24'h12345)^24'h55aa33;out_masked<=in_tag%17==0;end
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
    output reg done,failed,output reg[7:0]fault,output reg[31:0]accepted_pixels,
    output[31:0]written_beats,last_checksum,output reg[31:0]completed_id
);
    reg active;reg[31:0]id;integer age;
    integer expected,tx,ty,sx,sy;reg[23:0]rgb;
    assign frame_ready=!active && !failed;
    assign in_ready=active && !failed && age>20 && age%11<7 && !(age>=96 && age<123);
    assign awaddr=0;assign awlen=0;assign awvalid=0;assign wdata=0;assign wstrb=0;
    assign written_beats=accepted_pixels/16;assign last_checksum=32'h13579bdf;
    always @(posedge clk)begin
        if(!rst_n)begin active<=0;age<=0;id<=0;done<=0;failed<=0;fault<=0;accepted_pixels<=0;completed_id<=0;end
        else begin
            done<=0;if(active)age<=age+1;
            if(frame_valid && frame_ready)begin active<=1;age<=0;id<=frame_id;accepted_pixels<=0;end
            if(in_valid && in_ready)begin
                tx=accepted_pixels%TILE_W;ty=(accepted_pixels/TILE_W)%TILE_H;
                sx=((accepted_pixels/(TILE_W*TILE_H))%(WIDTH/TILE_W))*TILE_W;
                sy=(accepted_pixels/(WIDTH*TILE_H))*TILE_H;
                expected=(sy+ty)*WIDTH+sx+tx;
                rgb=expected%17==0 ? 24'd0:((expected*24'h12345)^24'h55aa33);
                if(in_tag!==expected || in_rgb!==rgb)$fatal(1,"writer independent tile/pixel oracle");
                accepted_pixels<=accepted_pixels+1;
                if(id[31] && accepted_pixels==4)begin failed<=1;fault<=8'h75;end
                else if(accepted_pixels==WIDTH*HEIGHT-1)begin active<=0;done<=1;completed_id<=id;end
            end
        end
    end
endmodule
