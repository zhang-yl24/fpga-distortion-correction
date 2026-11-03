`timescale 1ns/1ps
module tb_cache_priority;
    localparam WIDTH=256,HEIGHT=128;
    reg clk=0;always #4 clk=~clk;
    reg rst_n=0,frame_valid=0,in_valid=0,out_ready=1;
    reg [27:0] frame_base=0;
    reg signed [23:0] in_x=0,in_y=0;
    reg [24:0] in_tag=0;
    wire frame_ready,in_ready,out_valid,failed;
    wire [23:0] p00,p10,p01,p11;
    wire [7:0] fx,fy,fault;
    wire [24:0] out_tag;
    wire [27:0] araddr;wire [3:0] arlen;wire arvalid;
    reg arready=0,rvalid=0,rlast=0;reg [255:0] rdata=0;reg [3:0] rid=0;
    wire [31:0] hits,misses,completed_queries;
    reg ar_allow=1,auto_returns=1,inject_r=0;
    integer beats_left=0,reservations=0,outputs=0;
    integer checks=0,old_reservations;
    reg [27:0] stalled_address;
    ddr_neighbour_cache_scatter4_tag_prefetch_local #(
        .WIDTH(WIDTH),.HEIGHT(HEIGHT),.TAG_W(25),.INDEX_BITS(7),.TIMEOUT_BITS(5)) dut(
        .clk(clk),.rst_n(rst_n),.frame_valid(frame_valid),.frame_ready(frame_ready),.frame_base(frame_base),
        .in_valid(in_valid),.in_ready(in_ready),.in_x(in_x),.in_y(in_y),.in_tag(in_tag),
        .out_valid(out_valid),.out_ready(out_ready),.p00(p00),.p10(p10),.p01(p01),.p11(p11),
        .fx(fx),.fy(fy),.out_tag(out_tag),.araddr(araddr),.arlen(arlen),.arvalid(arvalid),.arready(arready),
        .rdata(rdata),.rvalid(rvalid),.rlast(rlast),.rid(rid),.failed(failed),.fault(fault),
        .hits(hits),.misses(misses),.completed_queries(completed_queries));

    always @(negedge clk)begin
        arready=rst_n && ar_allow && beats_left==0;
        rvalid=rst_n && (inject_r || (auto_returns && beats_left>0));
        rlast=beats_left==1;
        rdata={16{16'h5a69}};
    end
    always @(posedge clk)begin
        if(!rst_n)begin beats_left<=0;reservations<=0;outputs<=0;end
        else begin
            if(arvalid&&arready)begin beats_left<=8;reservations<=reservations+1;end
            if(rvalid&&beats_left>0)beats_left<=beats_left-1;
            if(out_valid&&out_ready)outputs<=outputs+1;
        end
    end
    task automatic reset_all;
        begin
            @(negedge clk);#1;
            rst_n=0;frame_valid=0;in_valid=0;inject_r=0;ar_allow=1;auto_returns=1;
            repeat(3)@(posedge clk);
            @(negedge clk);#1;rst_n=1;
            repeat(2)@(posedge clk);
        end
    endtask
    task automatic frame;
        begin
            @(negedge clk);#1;frame_valid=1;
            do @(posedge clk);while(!frame_ready);
            @(negedge clk);#1;frame_valid=0;
        end
    endtask
    task automatic query(input integer x,input integer y);
        begin
            @(negedge clk);#1;in_x=x*256+3;in_y=y*256+7;in_valid=1;in_tag=in_tag+1;
            do @(posedge clk);while(!in_ready);
            @(negedge clk);#1;in_valid=0;
        end
    endtask
    task automatic drain;
        begin
            wait(out_valid);@(posedge clk);#2;
            wait(dut.inner.state==0 && !dut.inner.v0 && !dut.inner.v1 && !dut.inner.query_valid && dut.queue_count==0);
            @(negedge clk);#1;
        end
    endtask
    task automatic expect_fault(input [7:0] expected);
        begin
            @(posedge clk);#2;
            if(!failed || fault!==expected || out_valid || frame_ready || in_ready ||
               dut.inner.valid_lines[dut.inner.selected_line]!==1'b0)
                $fatal(1,"priority fault mismatch expected=%h got=%h",expected,fault);
            checks=checks+1;
        end
    endtask

    initial begin
        // Warm line, clear validity on a same-bank frame, retain matching tag.
        // This explicitly covers the only state where write0 becomes hold0.
        reset_all();frame();query(17,0);drain();
        old_reservations=reservations;frame();query(17,0);
        wait(dut.inner.state==9);#1;
        if(dut.inner.valid_lines[dut.inner.selected_line]!==0 ||
           dut.inner.tags[dut.inner.selected_line]!==dut.inner.selected_block)
            $fatal(1,"invalid matching-tag branch was not reached");
        @(posedge clk);#2;
        if(dut.inner.valid_lines[dut.inner.selected_line]!==0 || !arvalid)
            $fatal(1,"invalid matching-tag query did not keep invalid and issue miss");
        drain();if(reservations<=old_reservations)$fatal(1,"matching-tag invalid line failed to refill");
        checks=checks+1;

        // A conflicting valid line reaches CHECK. An unsolicited response on
        // that edge overrides state and clear, while the new AR stays pending.
        query(17,64);wait(dut.inner.state==9);#1;
        if(!dut.inner.valid_lines[dut.inner.selected_line] ||
           dut.inner.tags[dut.inner.selected_line]===dut.inner.selected_block)
            $fatal(1,"valid mismatching-tag branch was not reached");
        inject_r=1;ar_allow=0;
        @(negedge clk);expect_fault(8'h04);
        if(!arvalid)$fatal(1,"CHECK same-edge fault withdrew reserved AR");
        inject_r=0;stalled_address=araddr;
        repeat(3)begin @(posedge clk);#2;if(!arvalid || araddr!==stalled_address)$fatal(1,"fault AR did not hold");end
        ar_allow=1;wait(arready);@(posedge clk);#2;
        if(arvalid)$fatal(1,"fault pending AR did not retire on handshake");
        checks=checks+1;

        // The fault write must win over final SCATTER publication on one edge.
        reset_all();frame();query(17,0);
        wait(dut.inner.state==4 && dut.inner.scatter_group==15);#1;inject_r=1;
        @(negedge clk);expect_fault(8'h04);
        if(dut.inner.valid_lines!==128'd0)$fatal(1,"last SCATTER fault published a line");

        // Common reset wins over CHECK and a simultaneous unsolicited return.
        reset_all();frame();query(17,0);wait(dut.inner.state==9);#1;
        rst_n=0;inject_r=1;
        @(posedge clk);#2;
        if(failed || arvalid || dut.inner.valid_lines!==128'd0 || dut.inner.state!==0)
            $fatal(1,"reset did not dominate CHECK/error");
        checks=checks+1;

        // AR timeout leaves a pending address stable until its real handshake.
        reset_all();frame();ar_allow=0;query(17,0);wait(arvalid);stalled_address=araddr;
        wait(failed);#2;
        if(fault!==8'h01 || !arvalid || araddr!==stalled_address)$fatal(1,"AR timeout changed reservation");
        repeat(4)begin @(posedge clk);#2;if(!arvalid || araddr!==stalled_address)$fatal(1,"timed-out AR withdrew");end
        ar_allow=1;wait(arready);@(posedge clk);#2;
        if(arvalid || !failed || fault!==8'h01)$fatal(1,"AR timeout handshake retirement incorrect");
        checks=checks+1;

        // A missing return times out FILL without exposing a partially valid line.
        reset_all();frame();auto_returns=0;query(17,0);wait(dut.inner.state==3);wait(failed);#2;
        if(fault!==8'h01 || dut.inner.valid_lines!==128'd0 || out_valid || arvalid)
            $fatal(1,"FILL timeout published state");
        checks=checks+1;
        if(checks!=7)$fatal(1,"priority coverage count wrong");
        $display("PASS CACHE PRIORITY checks=%0d matching-invalid/conflicting-valid/CHECK-error/final-scatter-error/reset/AR-timeout/FILL-timeout",checks);
        $finish;
    end
    initial begin #200000;$fatal(1,"priority test bounded timeout");end
    wire [0:0] ref_frame_ready;
    wire [0:0] ref_in_ready;
    wire [0:0] ref_out_valid;
    wire [23:0] ref_p00;
    wire [23:0] ref_p10;
    wire [23:0] ref_p01;
    wire [23:0] ref_p11;
    wire [7:0] ref_fx;
    wire [7:0] ref_fy;
    wire [24:0] ref_out_tag;
    wire [27:0] ref_araddr;
    wire [3:0] ref_arlen;
    wire [0:0] ref_arvalid;
    wire [0:0] ref_failed;
    wire [7:0] ref_fault;
    wire [31:0] ref_hits;
    wire [31:0] ref_misses;
    wire [31:0] ref_completed_queries;
    ddr_neighbour_cache_scatter4_tag_prefetch_local_reference #(
        .WIDTH(WIDTH),.HEIGHT(HEIGHT),.TAG_W(25),.INDEX_BITS(7),.TIMEOUT_BITS(5)) reference_dut(
        .clk(clk),.rst_n(rst_n),.frame_valid(frame_valid),.frame_ready(ref_frame_ready),.frame_base(frame_base),
        .in_valid(in_valid),.in_ready(ref_in_ready),.in_x(in_x),.in_y(in_y),.in_tag(in_tag),
        .out_valid(ref_out_valid),.out_ready(out_ready),.p00(ref_p00),.p10(ref_p10),.p01(ref_p01),.p11(ref_p11),
        .fx(ref_fx),.fy(ref_fy),.out_tag(ref_out_tag),.araddr(ref_araddr),.arlen(ref_arlen),.arvalid(ref_arvalid),.arready(arready),
        .rdata(rdata),.rvalid(rvalid),.rlast(rlast),.rid(rid),.failed(ref_failed),.fault(ref_fault),
        .hits(ref_hits),.misses(ref_misses),.completed_queries(ref_completed_queries));
    // Both implementations receive identical inputs. Compare after NBA on
    // every cycle, including reset/fault and invalid output cycles.
    integer differential_cycles=0;
    integer known_valid_checks=0;
    always @(posedge clk)begin
        #1;
        differential_cycles=differential_cycles+1;
        if({frame_ready,in_ready,out_valid,p00,p10,p01,p11,fx,fy,out_tag,araddr,arlen,arvalid,failed,fault,hits,misses,completed_queries} !== {ref_frame_ready,ref_in_ready,ref_out_valid,ref_p00,ref_p10,ref_p01,ref_p11,ref_fx,ref_fy,ref_out_tag,ref_araddr,ref_arlen,ref_arvalid,ref_failed,ref_fault,ref_hits,ref_misses,ref_completed_queries})
            $fatal(1,"LOCKSTEP output mismatch cycle=%0d state=%0d",differential_cycles,dut.inner.state);
        if({dut.frame_loaded,dut.queue_count,dut.read_pointer,dut.write_pointer,
             dut.inner.state,dut.inner.valid_lines,dut.inner.selected_line,
             dut.inner.selected_block,dut.inner.address_pending,
             dut.inner.scatter_group,dut.inner.fill_beat,dut.inner.watchdog,
             dut.inner.query_valid,dut.inner.v0,dut.inner.v1} !==
           {reference_dut.frame_loaded,reference_dut.queue_count,reference_dut.read_pointer,reference_dut.write_pointer,
             reference_dut.inner.state,reference_dut.inner.valid_lines,reference_dut.inner.selected_line,
             reference_dut.inner.selected_block,reference_dut.inner.address_pending,
             reference_dut.inner.scatter_group,reference_dut.inner.fill_beat,reference_dut.inner.watchdog,
             reference_dut.inner.query_valid,reference_dut.inner.v0,reference_dut.inner.v1})
            $fatal(1,"LOCKSTEP internal state/valid-lines mismatch cycle=%0d",differential_cycles);
        if(rst_n && dut.inner.state==9 && dut.inner.valid_lines[dut.inner.selected_line])begin
            known_valid_checks=known_valid_checks+1;
            if((^dut.inner.tags[dut.inner.selected_line])===1'bx)
                $fatal(1,"valid line used an uninitialized tag");
        end
    end

    final begin
        $display("LOCKSTEP cycles=%0d known_valid_checks=%0d",differential_cycles,known_valid_checks);
    end

endmodule
