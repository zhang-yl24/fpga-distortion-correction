`timescale 1ns/1ps
// Validation mode: one camera frame -> arithmetic remap -> raw/result UART
// pair. Both banks remain immutable until both CRC-checked packets finish.
// UART frame IDs encode pair_id*2 (raw) and pair_id*2+1 (corrected).
module ddr_corrected_capture #(parameter WIDTH=640,HEIGHT=480,BANK_STRIDE=262144)(
    input cam_clk,core_clk,rst_n,ready,input vsync,href,input [7:0] data,
    input signed [23:0] cfg_out_cx,cfg_out_cy,cfg_src_cx,cfg_src_cy,cfg_src_fx,cfg_src_fy,
    input signed [31:0] cfg_inv_fx,cfg_inv_fy,cfg_k1,cfg_k2,cfg_k3,cfg_p1,cfg_p2,
    output [27:0] awaddr,araddr,output [3:0] awlen,arlen,output awvalid,arvalid,input awready,arready,
    output [255:0] wdata,output [31:0] wstrb,input wready,wlast,
    input [255:0] rdata,input rvalid,rlast,input [3:0] rid,
    output byte_valid,input byte_ready,byte_done,output [7:0] byte_data,
    output failed,output [7:0] fault,output reg [31:0] pairs_completed
);
    reg capture_active,engine_start,export_start,export_enable;
    reg [3:0] state;reg [6:0] reset_wait;reg [31:0] pair_id,result_crc;
    reg [27:0] export_base;reg [31:0] export_id,export_crc;
    wire transaction_rst_n=rst_n && ready;
    wire [9:0] available;wire fifo_ready,fifo_valid,pop,source_done,source_valid;
    wire [257:0] fifo_data;wire [31:0] source_crc;
    camera_live_bridge #(.WIDTH(WIDTH),.HEIGHT(HEIGHT)) bridge(
        .cam_clk(cam_clk),.ddr_clk(core_clk),.rst_n(rst_n && capture_active),.arm(ready),
        .vsync(vsync),.href(href),.data(data),.fifo_rd_en(pop),.fifo_data(fifo_data),
        .fifo_valid(fifo_valid),.fifo_ready(fifo_ready),.fifo_available(available),
        .source_done(source_done),.source_valid(source_valid),.source_checksum(source_crc));
    wire [27:0] camera_awaddr,engine_awaddr,engine_araddr,export_araddr;
    wire [3:0] camera_awlen,engine_awlen,engine_arlen,export_arlen;
    wire camera_awvalid,engine_awvalid,engine_arvalid,export_arvalid;
    wire [255:0] camera_wdata,engine_wdata;wire [31:0] camera_wstrb,engine_wstrb;
    wire writer_done,writer_failed,engine_done,engine_failed,export_done,export_failed,engine_ready;
    wire [7:0] writer_fault,engine_fault,export_fault;
    wire [31:0] completed_crc,completed_id;wire [27:0] completed_base;
    wire camera_owner=state==1;
    wire engine_owner=state==2;
    wire exporter_owner=state>=3 && state<=7;
    assign awaddr=camera_owner ? camera_awaddr:engine_awaddr;
    assign awlen=camera_owner ? camera_awlen:engine_awlen;
    assign awvalid=(camera_owner && camera_awvalid)||(engine_owner && engine_awvalid);
    assign wdata=camera_owner ? camera_wdata:engine_wdata;
    assign wstrb=camera_owner ? camera_wstrb:engine_wstrb;
    assign araddr=engine_owner ? engine_araddr:export_araddr;
    assign arlen=engine_owner ? engine_arlen:export_arlen;
    assign arvalid=(engine_owner && engine_arvalid)||(exporter_owner && export_arvalid);
    assign failed=writer_failed || engine_failed || export_failed || state==8;
    assign fault=writer_failed ? writer_fault:engine_failed ? engine_fault:export_failed ? export_fault:state==8 ? 8'h71:0;
    ddr_video_writer #(.FRAME_BEATS(WIDTH*HEIGHT/16)) writer(
        .clk(core_clk),.rst_n(transaction_rst_n && capture_active),.base_address(28'b0),
        .fifo_available(available),.fifo_ready(fifo_ready),.fifo_rd_en(pop),.fifo_valid(fifo_valid),.fifo_data(fifo_data),
        .source_done(source_done),.source_valid(source_valid),.source_checksum(source_crc),
        .awaddr(camera_awaddr),.awlen(camera_awlen),.awvalid(camera_awvalid),.awready(awready && camera_owner),
        .wdata(camera_wdata),.wstrb(camera_wstrb),.wready(wready && camera_owner),.wlast(wlast),
        .state(),.done(writer_done),.failed(writer_failed),.fault(writer_fault),.written_beats(),.write_checksum());
    remap_frame_engine #(.WIDTH(WIDTH),.HEIGHT(HEIGHT)) engine(
        .clk(core_clk),.rst_n(transaction_rst_n),.frame_valid(engine_start),.frame_ready(engine_ready),
        .source_base(28'b0),.output_base(BANK_STRIDE),.frame_id(pair_id),
        .cfg_out_cx(cfg_out_cx),.cfg_out_cy(cfg_out_cy),.cfg_src_cx(cfg_src_cx),.cfg_src_cy(cfg_src_cy),
        .cfg_src_fx(cfg_src_fx),.cfg_src_fy(cfg_src_fy),.cfg_inv_fx(cfg_inv_fx),.cfg_inv_fy(cfg_inv_fy),
        .cfg_k1(cfg_k1),.cfg_k2(cfg_k2),.cfg_k3(cfg_k3),.cfg_p1(cfg_p1),.cfg_p2(cfg_p2),
        .araddr(engine_araddr),.arlen(engine_arlen),.arvalid(engine_arvalid),.arready(arready && engine_owner),
        .rdata(rdata),.rvalid(rvalid && engine_owner),.rlast(rlast),.rid(rid),
        .awaddr(engine_awaddr),.awlen(engine_awlen),.awvalid(engine_awvalid),.awready(awready && engine_owner),
        .wdata(engine_wdata),.wstrb(engine_wstrb),.wready(wready && engine_owner),.wlast(wlast),
        .done(engine_done),.failed(engine_failed),.fault(engine_fault),.completed_base(completed_base),
        .completed_id(completed_id),.completed_crc(completed_crc),.hits(),.misses(),.completed_queries());
    ddr_uart_frame #(.WIDTH(WIDTH),.HEIGHT(HEIGHT)) exporter(
        .clk(core_clk),.rst_n(transaction_rst_n && export_enable),.start(export_start),
        .base_address(export_base),.frame_id(export_id),.source_crc(export_crc),
        .araddr(export_araddr),.arlen(export_arlen),.arvalid(export_arvalid),.arready(arready && exporter_owner),
        .rdata(rdata),.rvalid(rvalid && exporter_owner),.rlast(rlast),.rid(rid),
        .byte_valid(byte_valid),.byte_ready(byte_ready),.byte_done(byte_done),.byte_data(byte_data),
        .idle(),.done(export_done),.failed(export_failed),.fault(export_fault));
    always @(posedge core_clk) begin
        if(!rst_n) begin
            capture_active<=0;engine_start<=0;export_start<=0;export_enable<=0;state<=0;reset_wait<=0;
            pair_id<=0;result_crc<=0;export_base<=0;export_id<=0;export_crc<=0;pairs_completed<=0;
        end else begin
            engine_start<=0;export_start<=0;
            case(state)
                0:if(ready) begin
                    if(reset_wait==64) begin capture_active<=1;pair_id<=pair_id+1'b1;reset_wait<=0;state<=1;end
                    else reset_wait<=reset_wait+1'b1;
                end
                1:if(writer_done && engine_ready) begin engine_start<=1;state<=2;end
                2:if(engine_done) begin
                    if(completed_base!=BANK_STRIDE || completed_id!=pair_id) state<=8;
                    else begin
                        result_crc<=completed_crc;export_base<=0;export_id<=pair_id<<1;export_crc<=source_crc;
                        export_enable<=1;reset_wait<=0;state<=3;
                    end
                end
                3:if(reset_wait==16) begin export_start<=1;state<=4;reset_wait<=0;end else reset_wait<=reset_wait+1'b1;
                4:if(export_done) begin export_enable<=0;state<=5;reset_wait<=0;end
                5:if(reset_wait==64) begin
                    export_enable<=1;export_base<=BANK_STRIDE;export_id<=(pair_id<<1)|1;export_crc<=result_crc;state<=6;reset_wait<=0;
                end else reset_wait<=reset_wait+1'b1;
                6:if(reset_wait==16) begin export_start<=1;state<=7;reset_wait<=0;end else reset_wait<=reset_wait+1'b1;
                7:if(export_done) begin capture_active<=0;export_enable<=0;state<=0;reset_wait<=0;pairs_completed<=pairs_completed+1'b1;end
                8:state<=8;
                default:state<=8;
            endcase
            // Keep the current bus owner on a module fault: no new transactions
            // start, and an already visible address cannot be withdrawn.
            if(writer_failed || engine_failed || export_failed) begin engine_start<=0;export_start<=0;end
        end
    end
endmodule
