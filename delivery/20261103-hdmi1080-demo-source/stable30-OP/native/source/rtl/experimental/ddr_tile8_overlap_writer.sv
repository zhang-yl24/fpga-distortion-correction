`timescale 1ns/1ps
// Candidate only. Accept adjacent 8x8 tiles in tile-x/tile-y order, while
// retaining GLOBAL RASTER pixel tags and RGB565/raster CRC semantics.
// Two 16x8 banks overlap collection with eight discontiguous one-beat writes.
// The project DDR UI requests W beats and supplies WLAST; there is no B port.
// AWLEN0 is handled by the existing arbiter, but hard-IP support still needs
// independent vendor/digital-IP verification before this profile is enabled.
module ddr_tile8_overlap_writer #(
    parameter WIDTH=1920,HEIGHT=1080,TAG_W=24,TIMEOUT_BITS=26
)(
    input clk,rst_n,input frame_valid,frame_tiled,output frame_ready,
    input [27:0] frame_base,input [31:0] frame_id,
    input in_valid,output in_ready,input [23:0] in_rgb,input [TAG_W-1:0] in_tag,
    output [27:0] awaddr,output [3:0] awlen,output awvalid,input awready,
    output [255:0] wdata,output [31:0] wstrb,input wready,wlast,
    output reg done,failed,output reg [7:0] fault,
    output reg [31:0] accepted_pixels,written_beats,last_checksum,completed_id
);
    localparam FRAME_PIXELS=WIDTH*HEIGHT,FRAME_BEATS=FRAME_PIXELS/16;
    localparam STRIPE_PIXELS=WIDTH*8,STRIPES=HEIGHT/8;
    localparam TX_IDLE=0,TX_ADDRESS=1,TX_WRITE=2;
    `include "source/rtl/video_crc32.vh"

    // Constant elaboration-time GF(2) matrix, reflected IEEE CRC32.
    // Runtime folds one input bit per edge, not a 32x32 combinational XOR tree.
    function automatic [31:0] matrix_times;
        input [1023:0] matrix;input [31:0] value;
        integer m;begin
            matrix_times=0;
            for(m=0;m<32;m=m+1)if(value[m])
                matrix_times=matrix_times^matrix[m*32+:32];
        end
    endfunction
    function automatic [1023:0] shift_matrix;
        input integer bits_to_shift;
        reg [1023:0] power,result,squared;
        reg [31:0] column;integer c,remaining;
        begin
            for(c=0;c<32;c=c+1)begin
                column=32'b1<<c;
                result[c*32+:32]=column;
                power[c*32+:32]=(column>>1)^(column[0] ? 32'hEDB88320:32'b0);
            end
            remaining=bits_to_shift;
            while(remaining>0)begin
                if(remaining&1)begin
                    for(c=0;c<32;c=c+1)
                        squared[c*32+:32]=matrix_times(power,result[c*32+:32]);
                    result=squared;
                end
                for(c=0;c<32;c=c+1)
                    squared[c*32+:32]=matrix_times(power,power[c*32+:32]);
                power=squared;remaining=remaining>>1;
            end
            shift_matrix=result;
        end
    endfunction
    localparam [1023:0] ROW_SHIFT=shift_matrix(WIDTH*16);

    reg frame_active,collect_done,collect_bank,next_tx_bank,tx_bank;
    reg [1:0] bank_busy,bank_full;
    reg seal_valid,seal_bank;
    reg [6:0] slot;
    reg [31:0] expected_tag,pair_first,pair_x,stripe_slot,identity;
    reg [27:0] base,bank_address[0:1],tx_address;
    reg [1:0] tx_state;
    reg [2:0] tx_row;
    reg writes_complete,drain_pending;
    reg [5:0] drain;
    reg [TIMEOUT_BITS-1:0] watchdog;

    // Each row is accumulated in increasing x order with CRC init0. The rows
    // arrive interleaved, so keep eight states; alternate whole-stripe banks.
    // Concatenation: raw_crc(A || row) = SHIFT(raw_crc(A)) XOR raw_crc0(row).
    reg [31:0] row_crc[0:15];
    reg [1:0] crc_owned,crc_full;
    reg crc_collect_bank,crc_next_bank,crc_bank,crc_busy,crc_complete;
    reg [2:0] crc_row;
    reg [4:0] crc_column;
    reg [31:0] crc_global,crc_mix,crc_stripes_done;
    wire [31:0] fold_next=crc_mix^(crc_global[crc_column] ?
        ROW_SHIFT[crc_column*32+:32]:32'b0);

    wire layout_ok=WIDTH>=16 && WIDTH<=8192 && WIDTH%16==0 &&
        HEIGHT>=8 && HEIGHT<=8192 && HEIGHT%8==0 && FRAME_PIXELS>0 &&
        FRAME_PIXELS<=16777216 && TAG_W>=1 && TAG_W<=32 &&
        FRAME_PIXELS<=(64'd1<<TAG_W) &&
        frame_base[6:0]==0 && ({1'b0,frame_base}+FRAME_PIXELS/2)<=29'h10000000;
    assign frame_ready=!frame_active && !failed && tx_state==TX_IDLE &&
        bank_busy==0 && bank_full==0 && !seal_valid && !drain_pending && !crc_busy;
    wire frame_fire=frame_valid && frame_ready;
    assign in_ready=frame_active && !failed && !collect_done && !drain_pending &&
        (slot!=0 || !bank_busy[collect_bank]) &&
        (stripe_slot!=0 || !crc_owned[crc_collect_bank]);
    wire pixel_fire=in_valid && in_ready;
    wire bad_tag=pixel_fire && in_tag!=expected_tag;
    wire good_pixel=pixel_fire && !bad_tag;
    wire [15:0] pixel={in_rgb[23:19],in_rgb[15:10],in_rgb[7:3]};
    wire [3:0] row_crc_address={crc_collect_bank,slot[5:3]};
    wire row_start=pair_x==0 && !slot[6] && slot[2:0]==0;
    wire accepted_aw=tx_state==TX_ADDRESS && awready;
    wire transfer=(tx_state==TX_WRITE || accepted_aw) && wready;
    wire bad_wlast=transfer && !wlast;
    wire timed_out=tx_state==TX_WRITE && (&watchdog) && !wready;
    wire abandon=failed || bad_tag || bad_wlast || timed_out;
    assign awaddr=tx_address;assign awlen=0;
    assign awvalid=tx_state==TX_ADDRESS; // Held even after a concurrent fault.
    assign wstrb=32'hFFFFFFFF;

    always @(posedge clk)begin
        if(!rst_n)begin
            frame_active<=0;collect_done<=0;collect_bank<=0;next_tx_bank<=0;tx_bank<=0;
            bank_busy<=0;bank_full<=0;seal_valid<=0;seal_bank<=0;slot<=0;
            expected_tag<=0;pair_first<=0;pair_x<=0;stripe_slot<=0;identity<=0;base<=0;
            tx_state<=TX_IDLE;tx_row<=0;tx_address<=0;writes_complete<=0;
            drain_pending<=0;drain<=0;watchdog<=0;done<=0;failed<=0;fault<=0;
            accepted_pixels<=0;written_beats<=0;last_checksum<=0;completed_id<=0;
            crc_owned<=0;crc_full<=0;crc_collect_bank<=0;crc_next_bank<=0;
            crc_bank<=0;crc_busy<=0;crc_complete<=0;crc_row<=0;crc_column<=0;
            crc_global<=32'hFFFFFFFF;crc_mix<=0;crc_stripes_done<=0;
        end else begin
            done<=0;
            if(tx_state==TX_WRITE && !wready)watchdog<=watchdog+1'b1;else watchdog<=0;
            if(frame_fire)begin
                if(!layout_ok || !frame_tiled)begin failed<=1;fault<=8'h08;end
                else begin
                    frame_active<=1;collect_done<=0;collect_bank<=0;next_tx_bank<=0;tx_bank<=0;
                    bank_busy<=0;bank_full<=0;seal_valid<=0;slot<=0;
                    expected_tag<=0;pair_first<=0;pair_x<=0;stripe_slot<=0;
                    identity<=frame_id;base<=frame_base;tx_state<=TX_IDLE;tx_row<=0;
                    writes_complete<=0;drain_pending<=0;drain<=0;watchdog<=0;
                    accepted_pixels<=0;written_beats<=0;
                    crc_owned<=0;crc_full<=0;crc_collect_bank<=0;crc_next_bank<=0;
                    crc_busy<=0;crc_complete<=0;crc_row<=0;crc_column<=0;
                    crc_global<=32'hFFFFFFFF;crc_mix<=0;crc_stripes_done<=0;
                end
            end else begin
                seal_valid<=0;
                if(seal_valid && !failed && !bad_tag)bank_full[seal_bank]<=1;
                if(good_pixel)begin
                    if(slot==0)begin
                        bank_busy[collect_bank]<=1;
                        bank_address[collect_bank]<=base+(pair_first>>1);
                    end
                    accepted_pixels<=accepted_pixels+1'b1;
                    if(accepted_pixels==FRAME_PIXELS-1)collect_done<=1;
                    slot<=slot+1'b1;
                    if(slot[2:0]!=7)expected_tag<=expected_tag+1'b1;
                    else if(slot[5:3]!=7)expected_tag<=expected_tag+WIDTH-7;
                    else if(slot[6] && pair_x==WIDTH-16)expected_tag<=expected_tag+1'b1;
                    else expected_tag<=expected_tag-7*WIDTH+1;
                    if(slot==127)begin
                        seal_valid<=1;seal_bank<=collect_bank;collect_bank<=!collect_bank;
                        if(pair_x==WIDTH-16)begin
                            pair_x<=0;pair_first<=pair_first+7*WIDTH+16;
                        end else begin pair_x<=pair_x+16;pair_first<=pair_first+16;end
                    end
                    if(stripe_slot==0)crc_owned[crc_collect_bank]<=1;
                    if(stripe_slot==STRIPE_PIXELS-1)begin
                        crc_full[crc_collect_bank]<=1;crc_collect_bank<=!crc_collect_bank;stripe_slot<=0;
                    end else stripe_slot<=stripe_slot+1'b1;
                end

                // The final pixel command commits on this seal edge; only then
                // can a full bank be selected and synchronously read for W0.
                case(tx_state)
                    TX_IDLE:if(frame_active && !abandon && bank_full[next_tx_bank])begin
                        tx_bank<=next_tx_bank;tx_row<=0;
                        tx_address<=bank_address[next_tx_bank];tx_state<=TX_ADDRESS;
                    end
                    TX_ADDRESS:if(awready)tx_state<=TX_WRITE;
                    TX_WRITE:begin end
                    default:begin failed<=1;fault<=8'h08;end
                endcase
                if(transfer)begin
                    written_beats<=written_beats+1'b1;
                    if(tx_row==7 || abandon)begin
                        tx_state<=TX_IDLE;bank_busy[tx_bank]<=0;bank_full[tx_bank]<=0;
                        next_tx_bank<=!next_tx_bank;
                    end else begin
                        tx_row<=tx_row+1'b1;tx_address<=tx_address+WIDTH/2;
                        tx_state<=TX_ADDRESS;
                    end
                    if(written_beats==FRAME_BEATS-1 && !abandon)begin
                        if(accepted_pixels!=FRAME_PIXELS)begin failed<=1;fault<=8'h08;end
                        else writes_complete<=1;
                    end
                end

                // Eight rows, 32 matrix-column folds each =256 active cycles.
                // Next-stripe collection uses the other row-CRC bank. For very
                // small WIDTH the ownership guard may backpressure at a stripe
                // boundary; no claim of 1px/clk for every parameter shape.
                if(!failed && !bad_tag)begin
                    if(!crc_busy && crc_full[crc_next_bank])begin
                        crc_busy<=1;crc_bank<=crc_next_bank;crc_row<=0;crc_column<=0;crc_mix<=0;
                    end else if(crc_busy)begin
                        if(crc_column==31)begin
                            crc_global<=fold_next^row_crc[{crc_bank,crc_row}];
                            crc_mix<=0;crc_column<=0;
                            if(crc_row==7)begin
                                crc_busy<=0;crc_owned[crc_bank]<=0;crc_full[crc_bank]<=0;
                                crc_next_bank<=!crc_next_bank;crc_stripes_done<=crc_stripes_done+1'b1;
                                if(crc_stripes_done==STRIPES-1)crc_complete<=1;
                            end else crc_row<=crc_row+1'b1;
                        end else begin crc_mix<=fold_next;crc_column<=crc_column+1'b1;end
                    end
                end
                if(frame_active && writes_complete && crc_complete && !drain_pending && !abandon)begin
                    drain_pending<=1;drain<=0;
                end
                if(drain_pending && !abandon)begin
                    if(drain==31)begin
                        last_checksum<=~crc_global;completed_id<=identity;done<=1;
                        frame_active<=0;drain_pending<=0;
                    end else drain<=drain+1'b1;
                end
                // A first fault stops admission and unissued AW. An asserted
                // AW / its ONE W beat still drains; later rows were not issued.
                // Bad WLAST is protocol isolation, not proof that corrupt IP
                // protocol state can physically drain. Reset must be coordinated.
                if(!failed)begin
                    if(bad_wlast)begin failed<=1;fault<=8'h02;end
                    else if(bad_tag)begin failed<=1;fault<=8'h32;end
                    else if(timed_out)begin failed<=1;fault<=8'h01;end
                end
            end
        end
    end

    // No reset of payload or row-CRC memory. Publication/first-row write seed
    // guards ensure every meaningful read was initialized in this frame.
    always @(posedge clk)if(rst_n && good_pixel)
        row_crc[row_crc_address]<=video_crc32_pixel(row_start ? 32'b0:row_crc[row_crc_address],pixel);

    // Canonical full-word16-bit write / synchronous read lane RAM organization.
    // No vendor primitive or inference claim. Total payload 16 lanes*16*16b=4096b.
    reg write_pending;
    reg [3:0] write_word,write_lane;
    reg [15:0] write_pixel;
    wire [3:0] command_word={collect_bank,slot[5:3]};
    wire [3:0] command_lane={slot[6],slot[2:0]};
    always @(posedge clk)begin
        if(!rst_n || failed)write_pending<=0;
        else begin
            write_pending<=good_pixel;
            if(good_pixel)begin write_word<=command_word;write_lane<=command_lane;write_pixel<=pixel;end
        end
    end
    wire read_first=tx_state==TX_IDLE && frame_active && !abandon && bank_full[next_tx_bank];
    wire read_next=transfer && tx_row!=7 && !abandon;
    wire read_enable=rst_n && (read_first || read_next);
    wire [3:0] read_word=read_first ? {next_tx_bank,3'b0}:{tx_bank,(tx_row+3'd1)};
    genvar lane;
    generate for(lane=0;lane<16;lane=lane+1)begin: pixel_lane
        reg [15:0] pixels[0:15];
        reg [15:0] read_pixel;
        always @(posedge clk)if(write_pending && write_lane==lane)
            pixels[write_word]<=write_pixel;
        always @(posedge clk)if(read_enable)read_pixel<=pixels[read_word];
        assign wdata[lane*16+:16]=read_pixel;
    end endgenerate
endmodule
