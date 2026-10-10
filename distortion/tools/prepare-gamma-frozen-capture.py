"""Prepare an isolated same-source raw/before/after UART validation prototype.

No board or existing RTL is overwritten. Two bypass processing passes warm the
statistics; the third pass enables Gamma on the identical immutable source.
Packets encode group in bits31:4, kind in bits1:0 and mode in bits3:2.
"""
from pathlib import Path
root=Path(__file__).resolve().parents[1]
source=(root/'rtl/ddr_corrected_capture.v').read_text()
def one(text,old,new):
    assert text.count(old)==1,old
    return text.replace(old,new)
t=one(source,'module ddr_corrected_capture #','module gamma_frozen_capture #')
t=one(t,'HEIGHT=480,BANK_STRIDE=262144','HEIGHT=480,BANK_STRIDE=262144,MAX_RADIUS_Q22=0')
t=one(t,'reg [31:0] pair_id,result_crc;', 'reg [31:0] pair_id,result_crc,frozen_crc;reg [1:0] process_pass,result_mode;')
t=one(t,'wire engine_owner=state==2;','wire engine_owner=state==2;wire [1:0] gamma_mode;wire [31:0] gamma_frames;')
t=one(t,'wire exporter_owner=state>=3 && state<=7;','wire exporter_owner=state==3 || state==4 || state==5 || state==6 || state==7 || state==9 || state==10;')
t=one(t,'remap_frame_engine #(.WIDTH(WIDTH),.HEIGHT(HEIGHT)) engine(', 'adaptive_gamma_frame_engine #(.WIDTH(WIDTH),.HEIGHT(HEIGHT),.MAX_RADIUS_Q22(MAX_RADIUS_Q22)) engine(')
t=one(t,'.clk(core_clk),.rst_n(transaction_rst_n),.frame_valid(engine_start),.frame_ready(engine_ready),',".clk(core_clk),.rst_n(transaction_rst_n),.frame_valid(engine_start),.frame_ready(engine_ready),\n        .gamma_enable(process_pass==2),.gamma_mode(gamma_mode),.gamma_frames(gamma_frames),\n        .cfg_rot_cx(cfg_out_cx),.cfg_rot_cy(cfg_out_cy),.cfg_rot_cos(32'sh40000000),.cfg_rot_sin(32'sd0),")
start=t.index('    always @(posedge core_clk) begin')
t=t[:start]+'''    always @(posedge core_clk) begin
        if(!rst_n) begin
            capture_active<=0;engine_start<=0;export_start<=0;export_enable<=0;state<=0;reset_wait<=0;
            pair_id<=0;result_crc<=0;frozen_crc<=0;process_pass<=0;result_mode<=0;
            export_base<=0;export_id<=0;export_crc<=0;pairs_completed<=0;
        end else begin
            engine_start<=0;export_start<=0;
            case(state)
                0:if(ready) begin
                    if(reset_wait==64) begin
                        capture_active<=1;pair_id<=pair_id+1'b1;process_pass<=0;reset_wait<=0;state<=1;
                    end else reset_wait<=reset_wait+1'b1;
                end
                1:if(writer_done && engine_ready) begin frozen_crc<=source_crc;engine_start<=1;state<=2;end
                2:if(engine_done) begin
                    if(completed_base!=BANK_STRIDE || completed_id!=pair_id) state<=8;
                    else if(process_pass==0) begin process_pass<=1;state<=11;end
                    else if(process_pass==1) begin
                        result_crc<=completed_crc;export_base<=0;export_id<=pair_id<<4;export_crc<=frozen_crc;
                        export_enable<=1;reset_wait<=0;state<=3;
                    end else begin
                        result_crc<=completed_crc;result_mode<=gamma_mode;export_base<=BANK_STRIDE;
                        export_id<=(pair_id<<4)|({30'd0,gamma_mode}<<2)|32'd2;export_crc<=completed_crc;
                        export_enable<=1;reset_wait<=0;state<=9;
                    end
                end
                11:if(engine_ready) begin engine_start<=1;state<=2;end
                3:if(reset_wait==16) begin export_start<=1;state<=4;reset_wait<=0;end else reset_wait<=reset_wait+1'b1;
                4:if(export_done) begin export_enable<=0;state<=5;reset_wait<=0;end
                5:if(reset_wait==64) begin
                    export_enable<=1;export_base<=BANK_STRIDE;export_id<=(pair_id<<4)|1;
                    export_crc<=result_crc;state<=6;reset_wait<=0;
                end else reset_wait<=reset_wait+1'b1;
                6:if(reset_wait==16) begin export_start<=1;state<=7;reset_wait<=0;end else reset_wait<=reset_wait+1'b1;
                7:if(export_done) begin export_enable<=0;process_pass<=2;state<=11;reset_wait<=0;end
                9:if(reset_wait==16) begin export_start<=1;state<=10;reset_wait<=0;end else reset_wait<=reset_wait+1'b1;
                10:if(export_done) begin
                    capture_active<=0;export_enable<=0;state<=0;reset_wait<=0;pairs_completed<=pairs_completed+1'b1;
                end
                8:state<=8;
                default:state<=8;
            endcase
            if(writer_failed || engine_failed || export_failed) begin engine_start<=0;export_start<=0;end
        end
    end
endmodule
'''
t=t.replace('// UART frame IDs encode pair_id*2 (raw) and pair_id*2+1 (corrected).','// Packet ID: group<<4 | mode<<2 | kind (0 raw, 1 bypass, 2 enhanced).')
(root/'rtl/experimental/gamma_frozen_capture.v').write_text(t)
print('Prepared isolated three-packet, one immutable source Gamma capture prototype; no board target generated.')
