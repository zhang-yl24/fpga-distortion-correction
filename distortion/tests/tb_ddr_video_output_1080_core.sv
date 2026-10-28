`timescale 1ns/1ps
// Functional reader/FIFO test only; no HDMI electrical or 148.5 MHz timing claim.
// Compile this test and rtl/experimental/ddr_video_output_1080_core.v as SV.
module ddr_video_output_1080_exerciser #(
    parameter integer CASE_ID=0,
    parameter integer WIDTH=1920,HEIGHT=1080,HT=2200,VT=1125,
    parameter integer HS=44,VS=5,X0=192,Y0=41,AW=1920,AH=1080,
    parameter integer FRAMES=1,
    // 0: correct stream; 1: wrong expected CRC; 2: no FIFO service.
    parameter integer MODE=0
)(output reg finished=0);
    localparam integer PIXELS=WIDTH*HEIGHT,BEATS=PIXELS/16;
    localparam integer WX=X0+(AW-WIDTH)/2,WY=Y0+(AH-HEIGHT)/2;
    reg clk=0,rst_n=0;
    always #5 clk=~clk;
    wire request_toggle,fifo_rd_en,hs,vs,de,display_valid,result_toggle;
    reg grant_toggle=0,grant_valid=0,fifo_ready=0,fifo_valid=0;
    reg [31:0] grant_checksum=0;
    reg [255:0] fifo_data=0;
    wire [7:0] r,g,b;
    wire [31:0] completed_frames,underflows,mismatches,last_checksum;
    ddr_video_output_1080_core #(
        .WIDTH(WIDTH),.HEIGHT(HEIGHT),.HT(HT),.VT(VT),.HS(HS),.VS(VS),
        .X0(X0),.Y0(Y0),.AW(AW),.AH(AH)
    ) dut(
        .clk(clk),.rst_n(rst_n),.request_toggle(request_toggle),
        .grant_toggle(grant_toggle),.grant_valid(grant_valid),.grant_checksum(grant_checksum),
        .fifo_ready(fifo_ready),.fifo_valid(fifo_valid),.fifo_data(fifo_data),.fifo_rd_en(fifo_rd_en),
        .hs(hs),.vs(vs),.de(de),.r(r),.g(g),.b(b),.display_valid(display_valid),
        .result_toggle(result_toggle),.completed_frames(completed_frames),
        .underflows(underflows),.mismatches(mismatches),.last_checksum(last_checksum)
    );

    // An independent serial polynomial reference, not the DUT XOR-matrix include.
    function automatic [31:0] crc_byte(input [31:0] previous,input [7:0] value);
        reg [31:0] c;integer k;
        begin
            c=previous^value;
            for(k=0;k<8;k=k+1) c=c[0] ? (c>>1)^32'hEDB88320 : c>>1;
            crc_byte=c;
        end
    endfunction
    function automatic [15:0] source_pixel(input integer index,input integer version);
        begin source_pixel=16'h5A3C^(index*73)^(index>>7)^(version*16'h1111);end
    endfunction
    function automatic [255:0] source_beat(input integer index,input integer version);
        integer k;
        begin
            for(k=0;k<16;k=k+1) source_beat[k*16+:16]=source_pixel(index*16+k,version);
        end
    endfunction
    reg [31:0] expected_crc[0:FRAMES-1];
    reg [31:0] c;
    reg [15:0] p;
    integer init_version,init_pixel;
    initial begin
        if(WIDTH%16!=0 || WIDTH>AW || HEIGHT>AH || X0+AW>HT || Y0+AH>VT)
            $fatal(1,"case %0d invalid test geometry",CASE_ID);
        if($bits(dut.requested_words)<17)
            $fatal(1,"case %0d requested_words is narrower than 17 bits",CASE_ID);
        if(CASE_ID==0 && BEATS!=129600)
            $fatal(1,"full-HD test must issue exactly 129600 reads");
        for(init_version=0;init_version<FRAMES;init_version=init_version+1) begin
            c=32'hFFFFFFFF;
            for(init_pixel=0;init_pixel<PIXELS;init_pixel=init_pixel+1) begin
                p=source_pixel(init_pixel,init_version);
                c=crc_byte(crc_byte(c,p[7:0]),p[15:8]);
            end
            expected_crc[init_version]=~c;
        end
        repeat(6) @(negedge clk);
        rst_n=1;
    end

    // FIFO model: every rd_en is one accepted request, followed by exactly one
    // ordered valid pulse after a fixed nonzero latency. There is no response
    // ready signal in the public interface. Periodic fifo_ready gaps exercise
    // request backpressure without withholding data after it was requested.
    reg [2:0] return_valid=0;
    reg [255:0] return_data[0:2];
    reg request_seen=0;
    integer cycle=0,grants_issued=0,active_version=0;
    integer requests=0,returns=0,consumed=0,seen_completed=0;
    integer finish_wait=-1,idx;
    reg saw_65535=0,saw_65536=0,saw_request_stall=0,saw_result_toggle=0;
    reg expected_de,expected_hs,expected_vs;
    reg [23:0] expected_rgb;
    reg [15:0] expected_pixel;
    reg should_consume;
    always @(posedge clk) begin
        if(!rst_n) begin
            request_seen=0;cycle=0;grants_issued=0;active_version=0;
            requests=0;returns=0;consumed=0;seen_completed=0;finish_wait=-1;
            return_valid<=0;fifo_valid<=0;fifo_ready<=0;
            fifo_data<=0;grant_toggle<=0;grant_valid<=0;grant_checksum<=0;
            return_data[0]<=0;return_data[1]<=0;return_data[2]<=0;
            saw_65535=0;saw_65536=0;saw_request_stall=0;saw_result_toggle=0;
        end else begin
            cycle=cycle+1;
            fifo_ready<=MODE!=2 && cycle%11>=3;
            fifo_valid<=return_valid[2];
            fifo_data<=return_data[2];
            return_valid<={return_valid[1:0],fifo_rd_en};
            return_data[2]<=return_data[1];return_data[1]<=return_data[0];

            if(request_toggle!=request_seen) begin
                request_seen=request_toggle;
                if(grants_issued!=0) begin
                    if(dut.queued!=0 || dut.inflight!=0 || return_valid!=0 || fifo_valid)
                        $fatal(1,"case %0d stale data crossed a frame boundary",CASE_ID);
                    if(MODE!=2 && (requests!=BEATS || returns!=BEATS || consumed!=PIXELS))
                        $fatal(1,"case %0d incomplete frame: reads=%0d returns=%0d pixels=%0d",CASE_ID,requests,returns,consumed);
                end
                grant_toggle<=request_toggle;
                if(grants_issued<FRAMES) begin
                    active_version=grants_issued;
                    grant_checksum<=expected_crc[grants_issued]^(MODE==1 ? 32'h1 : 32'h0);
                    grant_valid<=1;grants_issued=grants_issued+1;
                    requests=0;returns=0;consumed=0;
                end else begin
                    grant_valid<=0;finish_wait=12;
                end
            end
            if(dut.reset_sync[1]) begin
                if(dut.queued>4 || dut.inflight>4 || dut.queued+dut.inflight>4)
                    $fatal(1,"case %0d local slot accounting overflow",CASE_ID);
                if(fifo_rd_en && (!fifo_ready || !dut.frame_active || dut.broken))
                    $fatal(1,"case %0d illegal request handshake",CASE_ID);
                if(dut.frame_active && !fifo_ready) saw_request_stall=1;
                if(fifo_rd_en) begin
                    if(requests>=BEATS || dut.requested_words!=requests)
                        $fatal(1,"case %0d extra/wrapped request at %0d DUT=%0d",CASE_ID,requests,dut.requested_words);
                    return_data[0]<=source_beat(requests,active_version);
                    requests=requests+1;
                end
                if(fifo_valid) begin
                    if(returns>=requests || dut.inflight==0)
                        $fatal(1,"case %0d unsolicited/duplicate FIFO response",CASE_ID);
                    returns=returns+1;
                end
                if(dut.requested_words==65535) saw_65535=1;
                if(dut.requested_words==65536) saw_65536=1;
                should_consume=dut.consume;
                expected_de=(dut.x>=X0 && dut.x<X0+AW && dut.y>=Y0 && dut.y<Y0+AH);
                expected_hs=dut.x<HS;expected_vs=dut.y<VS;
                expected_rgb=0;
                if(should_consume) begin
                    idx=(dut.y-WY)*WIDTH+dut.x-WX;
                    if(idx!=consumed) $fatal(1,"case %0d pixel ordering/centering error idx=%0d expected=%0d",CASE_ID,idx,consumed);
                    expected_pixel=source_pixel(idx,active_version);
                    expected_rgb={{expected_pixel[15:11],expected_pixel[15:13]},
                        {expected_pixel[10:5],expected_pixel[10:9]},
                        {expected_pixel[4:0],expected_pixel[4:2]}};
                    consumed=consumed+1;
                end
                #1;
                if({r,g,b}!==expected_rgb || de!==expected_de || hs!==expected_hs || vs!==expected_vs)
                    $fatal(1,"case %0d registered RGB/raster mismatch at cycle %0d",CASE_ID,cycle);
                if(completed_frames!=seen_completed) begin
                    if(completed_frames!=seen_completed+1 || consumed!=PIXELS ||
                        requests!=BEATS || returns!=BEATS || dut.requested_words!=BEATS)
                        $fatal(1,"case %0d early completion or truncated count",CASE_ID);
                    if(last_checksum!==expected_crc[active_version])
                        $fatal(1,"case %0d CRC differs: got %08x expected %08x",CASE_ID,last_checksum,expected_crc[active_version]);
                    if(result_toggle===saw_result_toggle)
                        $fatal(1,"case %0d completion toggle was lost",CASE_ID);
                    saw_result_toggle=result_toggle;seen_completed=completed_frames;
                end
                if(finish_wait>0) finish_wait=finish_wait-1;
                if(finish_wait==0 && !finished) begin
                    if(fifo_rd_en || dut.queued!=0 || dut.inflight!=0 || fifo_valid || return_valid!=0 || dut.frame_active)
                        $fatal(1,"case %0d did not drain after final grant",CASE_ID);
                    if(!saw_request_stall) $fatal(1,"case %0d did not exercise ready backpressure",CASE_ID);
                    if(MODE==0 && (completed_frames!=FRAMES || underflows!=0 || mismatches!=0 || !display_valid || dut.broken))
                        $fatal(1,"case %0d correct stream failed",CASE_ID);
                    if(MODE==1 && (completed_frames!=1 || underflows!=0 || mismatches!=1 || display_valid || !dut.broken))
                        $fatal(1,"case %0d wrong CRC did not fail closed",CASE_ID);
                    if(MODE==2 && (completed_frames!=0 || underflows!=1 || mismatches!=0 || display_valid || !dut.broken || requests!=0))
                        $fatal(1,"case %0d FIFO starvation did not fail closed",CASE_ID);
                    if(CASE_ID==0 && (!saw_65535 || !saw_65536))
                        $fatal(1,"full-HD counter boundary was not crossed");
                    $display("PASS display case=%0d geometry=%0dx%0d frames=%0d reads=%0d CRC=%08x",CASE_ID,WIDTH,HEIGHT,completed_frames,requests,last_checksum);
                    finished=1;
                end
            end
        end
    end
endmodule

module tb_ddr_video_output_1080_core;
    wire full_done,small_done,crc_done,starve_done;
    ddr_video_output_1080_exerciser full_hd(.finished(full_done));
    ddr_video_output_1080_exerciser #(.CASE_ID(1),.WIDTH(32),.HEIGHT(3),
        .HT(80),.VT(12),.HS(4),.VS(1),.X0(10),.Y0(3),.AW(48),.AH(6),.FRAMES(2))
        small_two_frames(.finished(small_done));
    ddr_video_output_1080_exerciser #(.CASE_ID(2),.WIDTH(32),.HEIGHT(3),
        .HT(80),.VT(12),.HS(4),.VS(1),.X0(10),.Y0(3),.AW(48),.AH(6),.MODE(1))
        bad_crc(.finished(crc_done));
    ddr_video_output_1080_exerciser #(.CASE_ID(3),.WIDTH(32),.HEIGHT(3),
        .HT(80),.VT(12),.HS(4),.VS(1),.X0(10),.Y0(3),.AW(48),.AH(6),.MODE(2))
        starved_fifo(.finished(starve_done));
    initial begin
        wait(full_done && small_done && crc_done && starve_done);
        $display("PASS tb_ddr_video_output_1080_core all four directed cases");
        $finish;
    end
    initial begin
        // One full 2200x1125 raster is 2475000 cycles, plus finite drain.
        #35000000;
        $fatal(1,"display core test exceeded 3500000 pixel cycles");
    end
endmodule
