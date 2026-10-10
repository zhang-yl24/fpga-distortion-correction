`timescale 1ns/1ps
// Lock a complete source bank for this entire transaction. Reserve a whole
// 16-beat DDR burst before receiving its unbackpressurable response. UART may
// stall indefinitely without dropping bytes or issuing another DDR request.
module ddr_uart_frame #(parameter WIDTH=640,HEIGHT=480,TIMEOUT_BITS=26)(
    input clk,rst_n,start,input [27:0] base_address,
    input [31:0] frame_id,source_crc,
    output wire [27:0] araddr,output wire [3:0] arlen,
    output wire arvalid,input arready,
    input [255:0] rdata,input rvalid,rlast,input [3:0] rid,
    output wire byte_valid,input byte_ready,byte_done,output reg [7:0] byte_data,
    output wire idle,output reg done,failed,output reg [7:0] fault
);
    localparam BYTES=WIDTH*HEIGHT*2;
    localparam IDLE=0,HEADER=1,AR=2,READ=3,LOAD=4,DATA=5,TRAILER=6,FINISH=7,COMPLETE=8,FAULT=9;
    reg [3:0] state;
    reg [27:0] base;
    reg [31:0] id,expected_crc,sent,crc,header_crc;
    reg [5:0] header_index;
    reg [3:0] fill_beat,trailer_index;
    reg [8:0] send_byte;
    reg [255:0] burst[0:15],burst_q;
    reg address_pending;
    reg [TIMEOUT_BITS-1:0] watchdog;
    function [31:0] crc_byte(input [31:0] previous,input [7:0] data);
        reg [31:0] c;integer i;
        begin c=previous^{24'b0,data};for(i=0;i<8;i=i+1) c=(c>>1)^ (c[0] ? 32'hEDB88320:0);crc_byte=c;end
    endfunction
    function [7:0] header(input [5:0] index);
        reg [31:0] value;
        begin
            case(index)
                0:header="P";1:header="G";2:header="F";3:header="R";
                4:header="A";5:header="M";6:header="E";7:header="1";
                8:header=WIDTH;9:header=WIDTH>>8;10:header=HEIGHT;11:header=HEIGHT>>8;
                default:begin
                    if(index<16) value=id;
                    else if(index<20) value=BYTES;
                    else if(index<24) value=expected_crc;
                    else if(index<28) value=32'h00005651;
                    else value=~header_crc;
                    header=value >> (index[1:0]*8);
                end
            endcase
        end
    endfunction
    always @* begin
        byte_data=0;
        if(state==HEADER) byte_data=header(header_index);
        else if(state==DATA) byte_data=burst_q[send_byte[4:0]*8+:8];
        else if(state==TRAILER) begin
            case(trailer_index)
                0:byte_data="P";1:byte_data="G";2:byte_data="E";3:byte_data="N";
                4:byte_data="D";5:byte_data="0";6:byte_data="0";7:byte_data="1";
                default:byte_data=(~crc) >> (trailer_index[1:0]*8);
            endcase
        end
    end
    assign byte_valid=!failed && (state==HEADER || state==DATA || (state==TRAILER && ~crc==expected_crc));
    assign araddr=base+(sent>>2);assign arlen=15;assign arvalid=address_pending;
    assign idle=state==IDLE;
    always @(posedge clk) begin
        if(state==READ && rvalid && !failed && rid==0 && rlast==(fill_beat==15)) burst[fill_beat]<=rdata;
        if(state==LOAD) burst_q<=burst[send_byte[8:5]];
    end
    wire progress=(state==AR && arready)||(state==READ && rvalid);
    always @(posedge clk) begin
        if(!rst_n) begin
            state<=IDLE;base<=0;id<=0;expected_crc<=0;sent<=0;crc<=32'hFFFFFFFF;header_crc<=32'hFFFFFFFF;
            header_index<=0;fill_beat<=0;send_byte<=0;trailer_index<=0;address_pending<=0;
            watchdog<=0;done<=0;failed<=0;fault<=0;
        end else begin
            if(address_pending && arready) address_pending<=0;
            if(progress || (state!=AR && state!=READ)) watchdog<=0;else watchdog<=watchdog+1'b1;
            case(state)
                IDLE:if(start) begin base<=base_address;id<=frame_id;expected_crc<=source_crc;state<=HEADER;end
                HEADER:if(byte_valid && byte_ready) begin
                    if(header_index<28) header_crc<=crc_byte(header_crc,byte_data);
                    if(header_index==31) begin state<=AR;address_pending<=1;end
                    else header_index<=header_index+1'b1;
                end
                AR:if(arready) begin state<=READ;fill_beat<=0;end
                READ:if(rvalid) begin
                    if(rid!=0 || rlast!=(fill_beat==15)) begin failed<=1;fault<=8'h03;state<=FAULT;end
                    else if(fill_beat==15) begin state<=LOAD;send_byte<=0;end
                    else fill_beat<=fill_beat+1'b1;
                end
                LOAD:state<=DATA;
                DATA:if(byte_valid && byte_ready) begin
                    crc<=crc_byte(crc,byte_data);sent<=sent+1'b1;send_byte<=send_byte+1'b1;
                    if(send_byte==511) begin
                        if(sent==BYTES-1) begin state<=TRAILER;trailer_index<=0;end
                        else begin state<=AR;address_pending<=1;end
                    end else if(send_byte[4:0]==31) state<=LOAD;
                end
                TRAILER:if(~crc!=expected_crc) begin failed<=1;fault<=8'h14;state<=FAULT;end
                        else if(byte_valid && byte_ready) begin
                            if(trailer_index==11) state<=FINISH;else trailer_index<=trailer_index+1'b1;
                        end
                FINISH:if(byte_done) begin done<=1;state<=COMPLETE;end
                COMPLETE:state<=COMPLETE;
                FAULT:state<=FAULT;
                default:begin failed<=1;fault<=8'hFF;state<=FAULT;end
            endcase
            if(!failed && rvalid && state!=READ) begin failed<=1;fault<=8'h04;state<=FAULT;end
            if(!failed && &watchdog && !progress && (state==AR || state==READ)) begin
                failed<=1;fault<=8'h01;state<=FAULT;
            end
        end
    end
endmodule
