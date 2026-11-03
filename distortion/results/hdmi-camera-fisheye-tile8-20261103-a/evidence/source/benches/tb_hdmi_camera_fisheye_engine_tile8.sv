`timescale 1ns/1ps
// Independent coordinate oracle and a one-pixel elastic mock of the unchanged
// fisheye core. The real candidate writer checks all raster DDR pixels/CRC.
module tb_hdmi_camera_fisheye_engine_tile8;
    localparam W=32,H=32,N=W*H;
    reg clk=0,rst_n=0,frame_valid=0,cfg_corrected=1;
    always #4 clk=~clk;
    reg [27:0] source_base=0,output_base=4096;
    reg [31:0] frame_id=40;
    wire frame_ready,arvalid,awvalid,done,failed; wire [7:0] fault;
    wire [27:0] araddr,awaddr,completed_base;
    wire [3:0] arlen,awlen;
    wire [255:0] wdata; wire [31:0] wstrb,completed_id,completed_crc,hits,misses,queries;
    reg awready=0,wready=0,wlast=0;
    hdmi_camera_fisheye_engine_tile8 #(.WIDTH(W),.HEIGHT(H),.TIMEOUT_BITS(12)) dut(
        .clk(clk),.rst_n(rst_n),.frame_valid(frame_valid),.frame_ready(frame_ready),.cfg_corrected(cfg_corrected),
        .source_base(source_base),.output_base(output_base),.frame_id(frame_id),
        .araddr(araddr),.arlen(arlen),.arvalid(arvalid),.arready(1'b0),
        .rdata(256'd0),.rvalid(1'b0),.rlast(1'b0),.rid(4'd0),
        .awaddr(awaddr),.awlen(awlen),.awvalid(awvalid),.awready(awready),
        .wdata(wdata),.wstrb(wstrb),.wready(wready),.wlast(wlast),
        .done(done),.failed(failed),.fault(fault),.completed_base(completed_base),
        .completed_id(completed_id),.completed_crc(completed_crc),.hits(hits),.misses(misses),.completed_queries(queries));
    function [23:0] rgb(input integer tag);
        begin rgb={8'((tag*17+3)%256),8'((tag*7+11)%256),8'((tag*29+5)%256)};end
    endfunction
    function [15:0] expected_pixel(input integer tag);
        reg [23:0] p;
        begin p=rgb(tag);expected_pixel=tag%19==0 ? 0:{p[23:19],p[15:10],p[7:3]};end
    endfunction
    function [31:0] crc_pixel(input [31:0] old,input [15:0] value);
        reg [31:0] c;integer a,b;
        begin c=old;for(a=0;a<2;a=a+1)begin c=c^((value>>(8*a))&255);
            for(b=0;b<8;b=b+1)c=c[0] ? (c>>1)^32'hedb88320:c>>1;end crc_pixel=c;end
    endfunction
    integer cycle=0,issue=0,checked=0,beat=0,frames=0,coordinate_stalls=0,writer_stalls=0;
    integer tile_number,expect_x,expect_y,j;
    reg writing=0,locked_mode=0,held_aw=0,held_w=0;
    reg [27:0] saved_aw;reg [255:0] saved_w;reg [31:0] crc=32'hffffffff;
    always @(negedge clk)begin
        cycle=cycle+1;
        awready=rst_n&&!writing&&cycle%7!=0;
        wready=rst_n&&(writing||(awvalid&&awready))&&cycle%3!=0;
        wlast=wready&&beat==15;
    end
    always @(posedge clk)begin
        if(!rst_n)begin writing=0;beat=0;issue=0;checked=0;crc=32'hffffffff;held_aw=0;held_w=0;end
        else begin
            if(dut.begin_frame)begin
                issue=0;checked=0;crc=32'hffffffff;locked_mode=cfg_corrected;
            end
            if(dut.coordinate_valid&&!dut.coordinate_ready)coordinate_stalls=coordinate_stalls+1;
            if(dut.buffer_valid&&!dut.writer_input_ready)writer_stalls=writer_stalls+1;
            if(dut.coordinate_valid&&dut.coordinate_ready)begin
                if(issue>=N)$fatal(1,"extra coordinate");
                if(locked_mode)begin
                    tile_number=issue/64;
                    expect_x=(tile_number%(W/8))*8+issue%8;
                    expect_y=(tile_number/(W/8))*8+(issue%64)/8;
                end else begin expect_x=issue%W;expect_y=issue/W;end
                if(dut.column!==expect_x||dut.row!==expect_y||dut.raster_tag!==expect_y*W+expect_x||
                   dut.u!==expect_x*256||dut.v!==expect_y*256||dut.tiled_mode!==locked_mode)
                    $fatal(1,"coordinate order/mode mismatch issue=%0d expected=%0d,%0d actual=%0d,%0d tag=%0d",issue,expect_x,expect_y,dut.column,dut.row,dut.raster_tag);
                issue=issue+1;
            end
            if(held_aw&&(!awvalid||awaddr!==saved_aw))$fatal(1,"AW changed under stall");
            if(held_w&&wdata!==saved_w)$fatal(1,"W changed under stall");
            held_aw=awvalid&&!awready;saved_aw=awaddr;
            held_w=writing&&!wready;saved_w=wdata;
            if(awvalid&&awready)begin
                if(writing||awlen!=15||awaddr!==output_base+checked*8)$fatal(1,"raster AW mismatch");
                writing=1;beat=0;
            end
            if(wready&&!failed)begin
                if(!writing||wstrb!==32'hffffffff)$fatal(1,"unexpected W");
                for(j=0;j<16;j=j+1)begin
                    if(wdata[j*16+:16]!==expected_pixel(checked*16+j))$fatal(1,"raster pixel mismatch at %0d",checked*16+j);
                    crc=crc_pixel(crc,expected_pixel(checked*16+j));
                end
                checked=checked+1;
                if(beat==15)begin writing=0;beat=0;end else beat=beat+1;
            end
            if(done)begin
                if(issue!=N||checked!=N/16||writing||dut.buffer_valid||completed_id!==frame_id||completed_base!==output_base||completed_crc!==~crc)
                    $fatal(1,"premature drain/metadata/CRC completion");
                frames=frames+1;
            end
        end
    end
    task automatic reset_all;
        begin @(negedge clk);rst_n=0;frame_valid=0;repeat(5)@(negedge clk);rst_n=1;repeat(5)@(negedge clk);end
    endtask
    task automatic start_frame(input reg mode,input integer id);
        begin wait(frame_ready);@(negedge clk);cfg_corrected=mode;frame_id=id;frame_valid=1;
            @(negedge clk);frame_valid=0;end
    endtask
    task automatic complete_frame(input reg mode,input integer id);
        integer target;
        begin target=frames+1;start_frame(mode,id);wait(issue>100);@(negedge clk);cfg_corrected=!mode;
            wait(frames==target);repeat(3)@(negedge clk);if(failed)$fatal(1,"valid frame failed fault=%h",fault);end
    endtask
    initial begin
        reset_all();complete_frame(1,40);complete_frame(0,41);complete_frame(1,42);
        start_frame(1,43);wait(issue>40);reset_all();complete_frame(0,44);
        if(coordinate_stalls==0||writer_stalls==0)$fatal(1,"backpressure coverage absent");
        source_base=output_base;start_frame(1,45);wait(failed);repeat(3)@(negedge clk);
        if(fault!==8'h40||done||arvalid||awvalid)$fatal(1,"invalid overlap was published");
        $display("PASS tile8 engine: frames=%0d coordinate_stalls=%0d writer_stalls=%0d reset_abort=1 overlap_rejected=1",frames,coordinate_stalls,writer_stalls);
        $finish;
    end
    initial begin #2000000;$fatal(1,"tile8 engine timeout");end
endmodule

module hdmi_camera_fisheye_core #(parameter WIDTH=1920,HEIGHT=1080,TAG_W=24,INDEX_BITS=7,TIMEOUT_BITS=26)(
    input clk,rst_n,input frame_valid,output frame_ready,input [27:0] frame_base,input cfg_corrected,
    input in_valid,output in_ready,input signed [23:0] in_u,in_v,input [TAG_W-1:0] in_tag,
    output reg out_valid,input out_ready,output reg [23:0] out_rgb,output reg [TAG_W-1:0] out_tag,output reg out_masked,
    output [27:0] araddr,output [3:0] arlen,output arvalid,input arready,
    input [255:0] rdata,input rvalid,rlast,input [3:0] rid,
    output failed,output [7:0] fault,output [31:0] hits,misses,completed_queries);
    reg loaded=0;integer cycles=0;
    assign frame_ready=rst_n&&!out_valid;
    assign in_ready=loaded&&!frame_valid&&(!out_valid||out_ready)&&cycles%5!=0;
    assign araddr=0;assign arlen=0;assign arvalid=0;assign failed=0;assign fault=0;
    assign hits=0;assign misses=0;assign completed_queries=0;
    always @(posedge clk)begin
        if(!rst_n)begin loaded<=0;out_valid<=0;out_rgb<=0;out_tag<=0;out_masked<=0;cycles<=0;end
        else begin
            cycles<=cycles+1;
            if(frame_valid&&frame_ready)loaded<=1;
            if(out_valid&&out_ready)out_valid<=0;
            if(in_valid&&in_ready)begin
                out_valid<=1;out_tag<=in_tag;out_masked<=in_tag%19==0;
                out_rgb<={8'((in_tag*17+3)%256),8'((in_tag*7+11)%256),8'((in_tag*29+5)%256)};
            end
        end
    end
endmodule
