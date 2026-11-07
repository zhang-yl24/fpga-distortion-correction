`timescale 1ns/1ps
// Independent peer test of the final registered RAM edge and fault priority.
module tb_directfill_tagpipe_commit_collision;
    reg clk=0; always #4 clk=~clk;
    reg rst_n=0,frame_valid=0,in_valid=0,out_ready=0;
    reg signed [23:0] in_x=0,in_y=0;
    reg [24:0] in_tag=0;
    wire frame_ready,in_ready,out_valid,failed;
    wire [23:0] p00,p10,p01,p11;
    wire [7:0] fx,fy,fault;
    wire [24:0] out_tag;
    wire [27:0] araddr;
    wire [3:0] arlen;
    wire arvalid;
    reg arready=0,rvalid=0,rlast=0;
    reg [3:0] rid=0;
    reg [255:0] rdata=0;
    wire [31:0] hits,misses,completed_queries;
    ddr_neighbour_cache_scatter16_rowpipe #(
        .WIDTH(1920),.HEIGHT(1080),.INDEX_BITS(9),.TAG_W(25),.TIMEOUT_BITS(8)) dut(
        .clk(clk),.rst_n(rst_n),.frame_valid(frame_valid),.frame_ready(frame_ready),.frame_base(28'd0),
        .in_valid(in_valid),.in_ready(in_ready),.in_x(in_x),.in_y(in_y),.in_tag(in_tag),
        .out_valid(out_valid),.out_ready(out_ready),.p00(p00),.p10(p10),.p01(p01),.p11(p11),
        .fx(fx),.fy(fy),.out_tag(out_tag),.araddr(araddr),.arlen(arlen),.arvalid(arvalid),.arready(arready),
        .rdata(rdata),.rvalid(rvalid),.rlast(rlast),.rid(rid),.failed(failed),.fault(fault),
        .hits(hits),.misses(misses),.completed_queries(completed_queries));
    integer trace,summary,case_no=0,recoveries=0,checked_pixels=0;
    integer line_no=0,waited=0,pattern_salt=0;
    reg [63:0] last_even_a,last_even_b,last_odd_a,last_odd_b;
    function automatic [15:0] source_pixel(input integer p);
        source_pixel=(16'h4b31+p*197+(p>>2)*29+pattern_salt*16'h2345) & 65535;
    endfunction
    function automatic [23:0] expand(input [15:0] p);
        expand={p[15:11],p[15:13],p[10:5],p[10:9],p[4:0],p[4:2]};
    endfunction
    function automatic [255:0] payload(input integer beat);
        reg [255:0] value;
        begin
            for(integer n=0;n<16;n=n+1)value[n*16+:16]=source_pixel(beat*16+n);
            payload=value;
        end
    endfunction
    task automatic sample_edge;
        begin @(posedge clk);#1;end
    endtask
    task automatic common_reset;
        begin
            @(negedge clk);rst_n=0;frame_valid=0;in_valid=0;out_ready=0;
            pattern_salt=pattern_salt+1;
            arready=0;rvalid=0;rlast=0;rid=0;rdata=0;
            repeat(3)@(negedge clk);
            rst_n=1;sample_edge();
            if(failed||out_valid||arvalid||dut.inner.valid_lines!=0||dut.inner.fill_write_valid)
                $fatal(1,"peer reset retained ownership, valid line or output");
        end
    endtask
    task automatic begin_query;
        begin
            @(negedge clk);frame_valid=1;
            waited=0;
            while(!frame_ready)begin sample_edge();@(negedge clk);waited=waited+1;
                if(waited>30)$fatal(1,"frame handshake timeout");end
            sample_edge();@(negedge clk);frame_valid=0;
            // Upper two neighbours are OOB; lower two share one DDR line.
            in_x=31*256+13;in_y=-256+37;in_tag=25'h123abcd;in_valid=1;
            waited=0;
            while(!in_ready)begin sample_edge();@(negedge clk);waited=waited+1;
                if(waited>30)$fatal(1,"query handshake timeout");end
            sample_edge();@(negedge clk);in_valid=0;
            waited=0;
            while(!arvalid)begin sample_edge();@(negedge clk);waited=waited+1;
                if(waited>60)$fatal(1,"query AR timeout");end
            if(araddr!=0||arlen!=7||dut.inner.fill_beat!=0)$fatal(1,"unexpected first-line reservation");
            line_no=dut.inner.selected_line;
        end
    endtask
    task automatic beat(input integer number,input integer error_kind);
        begin
            // begin_query returns at a negedge; all later callers also return
            // at a negedge so the inputs are stable before the active edge.
            arready=number==0;rvalid=1;rdata=payload(number);rid=0;rlast=number==7;
            if(error_kind==1)begin rid=9;rdata=~payload(number);end
            if(error_kind==2)begin rlast=0;rdata=~payload(number);end
            sample_edge();
            if(error_kind==0)begin
                if(failed||!dut.inner.fill_write_valid||dut.inner.fill_write_beat!=number||
                   dut.inner.fill_write_line!=line_no||dut.inner.fill_write_block!=0)
                    $fatal(1,"peer registered receive ownership misaligned beat%0d",number);
                if(dut.inner.valid_lines[line_no])$fatal(1,"peer line published before final actual RAM edge");
            end
            @(negedge clk);
        end
    endtask
    task automatic check_words(input integer pixels);
        begin
            for(integer p=0;p<pixels;p=p+1)begin
                if(p%2==0)begin
                    if(dut.inner.even_pixels[line_no*16+p/8][((p/2)%4)*16+:16]!==source_pixel(p))
                        $fatal(1,"peer even old-payload mismatch pixel%0d",p);
                end else if(dut.inner.odd_pixels[line_no*16+p/8][((p/2)%4)*16+:16]!==source_pixel(p))
                    $fatal(1,"peer odd old-payload mismatch pixel%0d",p);
                checked_pixels=checked_pixels+1;
            end
        end
    endtask
    task automatic save_last_words;
        begin
            last_even_a=dut.inner.even_pixels[line_no*16+14];
            last_even_b=dut.inner.even_pixels[line_no*16+15];
            last_odd_a=dut.inner.odd_pixels[line_no*16+14];
            last_odd_b=dut.inner.odd_pixels[line_no*16+15];
        end
    endtask
    task automatic last_words_unchanged;
        begin
            if(dut.inner.even_pixels[line_no*16+14]!==last_even_a||
               dut.inner.even_pixels[line_no*16+15]!==last_even_b||
               dut.inner.odd_pixels[line_no*16+14]!==last_odd_a||
               dut.inner.odd_pixels[line_no*16+15]!==last_odd_b)
                $fatal(1,"peer malformed/reset final beat reached RAM");
        end
    endtask
    task automatic quarantine(input [7:0] expected_fault);
        begin
            rvalid=0;arready=0;in_valid=1;frame_valid=1;out_ready=1;
            repeat(12)begin
                sample_edge();
                if(!failed||fault!==expected_fault||in_ready||frame_ready||out_valid||
                   dut.inner.valid_lines[line_no]||dut.inner.fill_write_valid)
                    $fatal(1,"peer fault did not quarantine incomplete line expected%h actual%h",expected_fault,fault);
                @(negedge clk);
            end
        end
    endtask
    task automatic recover_and_check;
        begin
            common_reset();begin_query();
            for(integer b=0;b<8;b=b+1)beat(b,0);
            rvalid=0;arready=0;rlast=0;
            sample_edge();
            if(failed||!dut.inner.valid_lines[line_no]||dut.inner.tags[line_no]!=0)
                $fatal(1,"peer legal final commit did not publish after common reset");
            check_words(128);waited=0;
            while(!out_valid)begin sample_edge();waited=waited+1;
                if(waited>40)$fatal(1,"peer legal recovery output timeout");end
            if(p00!==24'd0||p10!==24'd0||p01!==expand(source_pixel(31))||p11!==expand(source_pixel(32))||
               fx!==8'd13||fy!==8'd37||out_tag!==25'h123abcd)
                $fatal(1,"peer independent four-neighbour recovery oracle mismatch");
            repeat(3)begin sample_edge();if(!out_valid||failed)$fatal(1,"peer stalled recovery output unstable");end
            @(negedge clk);out_ready=1;sample_edge();
            if(completed_queries!=1)$fatal(1,"peer recovery completion count mismatch");
            recoveries=recoveries+1;
        end
    endtask
    initial begin
        trace=$fopen("peer-commit-cases.csv","w");
        $fdisplay(trace,"case,kind,checked_pixels,fault,last_valid");
        // At this edge the old owned beat7 must commit even though raw DDR
        // already carries an illegal ninth beat. The fault's later NBA wins.
        common_reset();begin_query();
        for(integer b=0;b<8;b=b+1)beat(b,0);
        if(!dut.inner.write_commit_last||dut.inner.state!=4)$fatal(1,"peer failed to align ninth R with last commit");
        rvalid=1;rid=0;rlast=1;rdata={256{1'b1}};arready=0;
        sample_edge();check_words(128);
        if(!failed||fault!==8'h04||dut.inner.valid_lines[line_no])
            $fatal(1,"peer unexpected ninth R did not override simultaneous publication");
        $fdisplay(trace,"0,ninth_R_vs_last_commit,128,%0d,%0d",fault,dut.inner.valid_lines[line_no]);
        @(negedge clk);quarantine(8'h04);recover_and_check();case_no=case_no+1;
        // Bad RID and missing RLAST occur while the previous valid beat6 is
        // actually writing. The bad final payload must never acquire ownership.
        for(integer kind=1;kind<=2;kind=kind+1)begin
            common_reset();begin_query();
            for(integer b=0;b<7;b=b+1)beat(b,0);
            save_last_words();beat(7,kind);check_words(112);last_words_unchanged();
            if(!failed||fault!==8'h03||dut.inner.fill_write_valid||dut.inner.valid_lines[line_no])
                $fatal(1,"peer malformed final return retained write/valid authority");
            $fdisplay(trace,"%0d,malformed_final_R,112,%0d,%0d",kind,fault,dut.inner.valid_lines[line_no]);
            quarantine(8'h03);last_words_unchanged();recover_and_check();case_no=case_no+1;
        end
        // Common reset exactly cancels the pending final owned RAM edge.
        common_reset();begin_query();
        for(integer b=0;b<8;b=b+1)beat(b,0);
        save_last_words();rst_n=0;rvalid=0;sample_edge();last_words_unchanged();
        if(failed||out_valid||dut.inner.valid_lines!=0||dut.inner.fill_write_valid)
            $fatal(1,"peer reset and last commit collision leaked ownership");
        $fdisplay(trace,"3,common_reset_vs_last_commit,0,%0d,%0d",fault,dut.inner.valid_lines[line_no]);
        recover_and_check();case_no=case_no+1;
        if(case_no!=4||recoveries!=4||checked_pixels!=864)$fatal(1,"peer required collision/oracle coverage missing");
        $fclose(trace);summary=$fopen("peer-commit-summary.json","w");
        $fdisplay(summary,"{\"Passed\":true,\"IndexBits\":9,\"Cases\":4,\"SuccessfulCommonResetRecoveries\":4,\"IndependentRAMPixelsChecked\":864,\"NinthRAndLastCommitCollision\":true,\"MalformedFinalRID\":true,\"MissingFinalRLAST\":true,\"ResetBeforeFinalRAMCommit\":true,\"FaultQuarantineChecked\":true}");
        $fclose(summary);$display("PASS DIRECTFILL PEER real final-commit/fault/reset collisions and independent RAM/pixel oracle");$finish;
    end
    initial begin #1000000;$fatal(1,"peer bounded commit-collision timeout");end
endmodule
