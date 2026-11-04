`timescale 1ns/1ps
// Port-feasibility shim, NOT a complete cache or production engine replacement.
// A directory/scout must only admit resident query footprints and grant a fill
// lease after all earlier queries needing the victim line have read their RAM
// words. fill_safe is that explicit external contract, not an internal proof.
// Four (source y parity, x parity) 1R1W arrays permit a query each clock while
// another line refills. Optional64/128-bit words reduce depth at constant
// logical payload. Physical RAM count and selector timing require Map/STA.
// WIDTH must be a multiple of128 so a source DDR block never straddles rows.
module quad_parity_prefetch_store #(
    parameter WIDTH=1920,HEIGHT=1080,INDEX_BITS=7,TAG_W=24,TIMEOUT_BITS=16,SCATTER16=0,STREAM_FILL=0,SCATTER8=0
)(
    input clk,rst_n,
    input in_valid,output wire in_ready,input signed [23:0] in_x,in_y,
    input [TAG_W-1:0] in_tag,
    output wire out_valid,input out_ready,output wire [23:0] p00,p10,p01,p11,
    output wire [7:0] fx,fy,output wire [TAG_W-1:0] out_tag,
    input fill_valid,output wire fill_ready,input fill_safe,
    input [27:0] fill_base,input [12:0] fill_row,fill_col_block,
    input [31:0] fill_ticket,
    output wire fill_busy,output reg fill_done,
    output reg [24:0] completed_block,output reg [31:0] completed_ticket,
    output wire [27:0] araddr,output wire [3:0] arlen,output wire arvalid,input arready,
    input [255:0] rdata,input rvalid,rlast,input [3:0] rid,
    output reg failed,output reg [7:0] fault
);
    localparam BLOCKS_PER_ROW=WIDTH/128,LOCAL_LINES=1<<(INDEX_BITS-1);
    localparam ADDRESS_BITS=INDEX_BITS+(SCATTER8 ? 2:(SCATTER16 ? 3:4));
    localparam WORD_BITS=SCATTER8 ? 128:(SCATTER16 ? 64:32);
    localparam WORDS_PER_LINE=SCATTER8 ? 8:(SCATTER16 ? 16:32);
    localparam IDLE=0,AR=1,FILL=2,SCATTER=3,FAULT=4;
    reg [2:0] state;
    reg [27:0] base;
    reg [24:0] selected_block;
    reg [INDEX_BITS-2:0] selected_local_line;
    reg selected_y_parity,address_pending;
    reg [31:0] selected_ticket;
    reg [2:0] fill_beat;
    reg [3:0] received_beats;
    reg [4:0] scatter_word;
    (* ram_style="registers" *) reg [255:0] fill_buffer[0:7];
    reg [TIMEOUT_BITS-1:0] watchdog;
    wire legal_request=WIDTH>=128 && WIDTH%128==0 && HEIGHT>=2 &&
        INDEX_BITS>=2 && INDEX_BITS<=10 && fill_row<HEIGHT && fill_col_block<BLOCKS_PER_ROW &&
        fill_base[6:0]==0 && ({1'b0,fill_base}+WIDTH*HEIGHT/2)<=29'h10000000;
    assign fill_ready=state==IDLE && !failed && fill_safe;
    wire accept_fill=fill_valid && fill_ready;
    assign fill_busy=state!=IDLE;
    assign araddr=base+({3'b0,selected_block}<<6);
    assign arlen=7;
    assign arvalid=address_pending;
    wire accept_ar=address_pending && arready;
    wire receiving=state==FILL || (state==AR && accept_ar);
    wire progress=accept_ar || (state==FILL && rvalid);
    // Never consume a beat arriving on this same edge: received_beats refers
    // only to already committed buffer words. Receiver and scatter therefore
    // touch different buffer indices when both transfer on an edge.
    wire [2:0] scatter_source_beat=SCATTER8 ? scatter_word[2:0]:
        (SCATTER16 ? scatter_word[3:1]:scatter_word[4:2]);
    wire scatter_data_ready=!STREAM_FILL || received_beats>{1'b0,scatter_source_beat};
    wire scatter_write=rst_n && !failed && (state==SCATTER ||
        (STREAM_FILL && state==FILL)) && scatter_data_ready;
    wire [ADDRESS_BITS-1:0] write_address;
    wire [WORD_BITS-1:0] even_write,odd_write;
    generate if(SCATTER8)begin: packed16_pixels
        wire [255:0] beat=fill_buffer[scatter_word[2:0]];
        assign write_address={selected_local_line,scatter_word[2:0]};
        assign even_write={beat[239:224],beat[207:192],beat[175:160],beat[143:128],
            beat[111:96],beat[79:64],beat[47:32],beat[15:0]};
        assign odd_write={beat[255:240],beat[223:208],beat[191:176],beat[159:144],
            beat[127:112],beat[95:80],beat[63:48],beat[31:16]};
    end else if(SCATTER16)begin: packed8_pixels
        wire [127:0] octet=fill_buffer[scatter_word[3:1]][scatter_word[0]*128+:128];
        assign write_address={selected_local_line,scatter_word[3:0]};
        assign even_write={octet[111:96],octet[79:64],octet[47:32],octet[15:0]};
        assign odd_write={octet[127:112],octet[95:80],octet[63:48],octet[31:16]};
    end else begin: original4_pixels
        wire [63:0] quad=fill_buffer[scatter_word[4:2]][scatter_word[1:0]*64+:64];
        assign write_address={selected_local_line,scatter_word};
        assign even_write={quad[47:32],quad[15:0]};
        assign odd_write={quad[63:48],quad[31:16]};
    end endgenerate

    // Registered-ready input boundary: neither coordinates nor memory hit/
    // collision decisions feed the external mapper's ready/clock-enable cone.
    reg [1:0] count;
    reg rp,wp;
    reg signed [23:0] qx[0:1],qy[0:1];
    reg [TAG_W-1:0] qt[0:1];
    assign in_ready=!failed && count<2;
    wire push=in_valid && in_ready;
    wire signed [16:0] x0=$signed(qx[rp][23:8]),y0=$signed(qy[rp][23:8]);
    wire [1:0] base_parity={y0[0],x0[0]};
    wire [3:0] bounds;
    wire [ADDRESS_BITS-1:0] sample_address[0:3];
    wire [3:0] sample_half;
    wire [7:0] sample_quarter;
    wire [11:0] sample_eighth;
    genvar n;
    generate for(n=0;n<4;n=n+1)begin: decode
        wire signed [16:0] x=x0+(n%2),y=y0+(n/2);
        wire [31:0] local_line=((y>>>1)*BLOCKS_PER_ROW+(x>>>7));
        if(SCATTER8)begin: widest_word_address
            assign sample_address[n]={local_line[INDEX_BITS-2:0],x[6:4]};
        end else if(SCATTER16)begin: wide_word_address
            assign sample_address[n]={local_line[INDEX_BITS-2:0],x[6:3]};
        end else begin: narrow_word_address
            assign sample_address[n]={local_line[INDEX_BITS-2:0],x[6:2]};
        end
        assign sample_quarter[n*2+:2]=x[2:1];
        assign sample_eighth[n*3+:3]=x[3:1];
        assign sample_half[n]=x[1];
        assign bounds[n]=x>=0 && x<WIDTH && y>=0 && y<HEIGHT;
    end endgenerate
    wire [ADDRESS_BITS-1:0] addr0=sample_address[base_parity^2'd0];
    wire [ADDRESS_BITS-1:0] addr1=sample_address[base_parity^2'd1];
    wire [ADDRESS_BITS-1:0] addr2=sample_address[base_parity^2'd2];
    wire [ADDRESS_BITS-1:0] addr3=sample_address[base_parity^2'd3];
    // Avoid any dependence on a primitive's same-address read/write mode.
    // A bad external lease can still evict needed data: this collision check
    // is a port safeguard and must never be described as a cache-tag proof.
    wire collision=scatter_write && (selected_y_parity ?
        ((bounds[base_parity^2'd2] && addr2==write_address) ||
         (bounds[base_parity^2'd3] && addr3==write_address)):
        ((bounds[base_parity^2'd0] && addr0==write_address) ||
         (bounds[base_parity^2'd1] && addr1==write_address)));
    // A separate registered halfword stage keeps the 2:1/4:1/8:1 lane choice out of
    // the following 4:1 parity permutation. It adds latency, never a second
    // pixel arithmetic lane or a new combinational external-ready path.
    reg v0,v1,v2;
    wire ready2=!v2 || out_ready,ready1=!v1 || ready2,ready0=!v0 || ready1;
    wire read_fire=count!=0 && !failed && ready0 && !collision;
    wire pop=read_fire;
    (* ram_style="block" *) reg [WORD_BITS-1:0] bank00[0:LOCAL_LINES*WORDS_PER_LINE-1];
    (* ram_style="block" *) reg [WORD_BITS-1:0] bank01[0:LOCAL_LINES*WORDS_PER_LINE-1];
    (* ram_style="block" *) reg [WORD_BITS-1:0] bank10[0:LOCAL_LINES*WORDS_PER_LINE-1];
    (* ram_style="block" *) reg [WORD_BITS-1:0] bank11[0:LOCAL_LINES*WORDS_PER_LINE-1];
    reg [WORD_BITS-1:0] rd0,rd1,rd2,rd3;
    always @(posedge clk)if(read_fire && bounds[base_parity^2'd0])rd0<=bank00[addr0];
    always @(posedge clk)if(read_fire && bounds[base_parity^2'd1])rd1<=bank01[addr1];
    always @(posedge clk)if(read_fire && bounds[base_parity^2'd2])rd2<=bank10[addr2];
    always @(posedge clk)if(read_fire && bounds[base_parity^2'd3])rd3<=bank11[addr3];
    always @(posedge clk)if(scatter_write && !selected_y_parity)bank00[write_address]<=even_write;
    always @(posedge clk)if(scatter_write && !selected_y_parity)bank01[write_address]<=odd_write;
    always @(posedge clk)if(scatter_write && selected_y_parity)bank10[write_address]<=even_write;
    always @(posedge clk)if(scatter_write && selected_y_parity)bank11[write_address]<=odd_write;
    reg [3:0] bounds0,half0;
    reg [7:0] quarter0;
    reg [11:0] eighth0;
    reg [1:0] parity0,parity1;
    reg [3:0] bounds1;
    reg [15:0] half_words[0:3];
    reg [7:0] fx0,fy0,fx1,fy1,fx2,fy2;
    reg [TAG_W-1:0] tag0,tag1,tag2;
    reg [23:0] pixels[0:3];
    wire [WORD_BITS-1:0] read_words[0:3];
    assign read_words[0]=rd0;assign read_words[1]=rd1;
    assign read_words[2]=rd2;assign read_words[3]=rd3;
    function [23:0] expand565(input [15:0] p);
        expand565={p[15:11],p[15:13],p[10:5],p[10:9],p[4:0],p[4:2]};
    endfunction
    assign out_valid=v2 && !failed;
    assign p00=pixels[0];assign p10=pixels[1];assign p01=pixels[2];assign p11=pixels[3];
    assign fx=fx2;assign fy=fy2;assign out_tag=tag2;
    integer i;
    always @(posedge clk)begin
        if(!rst_n)begin
            count<=0;rp<=0;wp<=0;v0<=0;v1<=0;v2<=0;bounds0<=0;half0<=0;quarter0<=0;eighth0<=0;parity0<=0;
            parity1<=0;bounds1<=0;fx0<=0;fy0<=0;fx1<=0;fy1<=0;fx2<=0;fy2<=0;
            tag0<=0;tag1<=0;tag2<=0;
            for(i=0;i<4;i=i+1)begin pixels[i]<=0;half_words[i]<=0;end
        end else begin
            case({push,pop})
                2'b10:count<=count+1'b1;
                2'b01:count<=count-1'b1;
                default:count<=count;
            endcase
            if(push)begin qx[wp]<=in_x;qy[wp]<=in_y;qt[wp]<=in_tag;wp<=!wp;end
            if(pop)rp<=!rp;
            if(ready0)v0<=read_fire;
            if(read_fire)begin
                bounds0<=bounds;half0<=sample_half;quarter0<=sample_quarter;
                eighth0<=sample_eighth;parity0<=base_parity;
                fx0<=qx[rp][7:0];fy0<=qy[rp][7:0];tag0<=qt[rp];
            end
            if(ready1)begin
                v1<=v0;fx1<=fx0;fy1<=fy0;tag1<=tag0;
                bounds1<=bounds0;parity1<=parity0;
                if(v0)for(i=0;i<4;i=i+1)begin
                    if(SCATTER8)
                        half_words[i]<=read_words[i][eighth0[(parity0^i)*3+:3]*16+:16];
                    else if(SCATTER16)
                        half_words[i]<=read_words[i][quarter0[(parity0^i)*2+:2]*16+:16];
                    else half_words[i]<=half0[parity0^i] ? read_words[i][31:16]:read_words[i][15:0];
                end
            end
            if(ready2)begin
                v2<=v1;fx2<=fx1;fy2<=fy1;tag2<=tag1;
                if(v1)for(i=0;i<4;i=i+1)
                    pixels[i]<=bounds1[i] ? expand565(half_words[parity1^i]):24'd0;
            end
        end
    end
    always @(posedge clk)begin
        if(!rst_n)begin
            state<=IDLE;base<=0;selected_block<=0;selected_local_line<=0;selected_y_parity<=0;
            address_pending<=0;selected_ticket<=0;fill_beat<=0;received_beats<=0;scatter_word<=0;watchdog<=0;
            fill_done<=0;completed_block<=0;completed_ticket<=0;failed<=0;fault<=0;
        end else begin
            fill_done<=0;
            if(accept_ar)address_pending<=0;
            if(progress || (state!=AR && state!=FILL))watchdog<=0;
            else watchdog<=watchdog+1'b1;
            case(state)
                IDLE:if(accept_fill)begin
                    if(!legal_request)begin failed<=1;fault<=8'h40;state<=FAULT;end
                    else begin
                        base<=fill_base;selected_block<=fill_row*BLOCKS_PER_ROW+fill_col_block;
                        selected_local_line<=(fill_row>>1)*BLOCKS_PER_ROW+fill_col_block;
                        selected_y_parity<=fill_row[0];selected_ticket<=fill_ticket;
                        fill_beat<=0;received_beats<=0;scatter_word<=0;address_pending<=1;state<=AR;
                    end
                end
                AR:if(accept_ar)state<=FILL;
                FILL:begin end
                SCATTER:begin end
                FAULT:state<=FAULT;
                default:begin failed<=1;fault<=8'hff;state<=FAULT;end
            endcase
            if(scatter_write)begin
                if(scatter_word==WORDS_PER_LINE-1)begin
                    // The last scatter needs beat7 already accepted. Legal
                    // RLAST has therefore moved the receiver to SCATTER.
                    fill_done<=1;completed_block<=selected_block;completed_ticket<=selected_ticket;state<=IDLE;
                end else scatter_word<=scatter_word+1'b1;
            end
            if(!failed && rvalid)begin
                if(!receiving)begin
                    failed<=1;fault<=8'h04;state<=FAULT;fill_done<=0;
                    // Do not create a new address after an unsolicited R on
                    // the same edge as fill acceptance. Already asserted AR
                    // remains held until handshake, including quarantine.
                    if(!address_pending)address_pending<=0;
                end else if(rid!=0 || rlast!=(fill_beat==7))begin
                    failed<=1;fault<=8'h03;state<=FAULT;fill_done<=0;
                end
                else begin
                    fill_buffer[fill_beat]<=rdata;received_beats<=received_beats+1'b1;
                    if(fill_beat==7)begin
                        if(!STREAM_FILL)scatter_word<=0;
                        state<=SCATTER;
                    end
                    else fill_beat<=fill_beat+1'b1;
                end
            end
            if(!failed && &watchdog && !progress && (state==AR || state==FILL))begin
                failed<=1;fault<=8'h01;state<=FAULT;
            end
        end
    end
endmodule
