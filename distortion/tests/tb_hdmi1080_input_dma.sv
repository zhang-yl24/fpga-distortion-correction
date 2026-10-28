`timescale 1ns/1ps
// Only the two new input modules. Independent RGB/CRC oracle, no old RTL oracle.
module tb_hdmi1080_input_dma;
    localparam W=32,H=16,N=W*H,FB=N/16,STRIDE=1048576;
    reg sys_clk=0,pix_clk=0;always #4 sys_clk=~sys_clk;always #7 pix_clk=~pix_clk;
    reg rst_n=0,enable=0,vs=0,de=0;reg [23:0] rgb=0;
    reg source_ready=0,release_valid=0,release_bank=0;
    reg [1:0] core_owned=0;
    wire source_valid,source_bank,failed,write_active;
    wire [31:0] source_id,source_crc,source_pixels,accepted,dropped,overflowed,no_free;
    wire [7:0] fault,last_drop;wire [1:0] reserved;
    wire [1:0] writable=~(core_owned | (source_valid ? (source_bank ? 2'b10:2'b01):2'b00));
    wire [27:0] awaddr;wire [3:0] awlen;wire awvalid;
    reg awready=0,wready=0,wlast=0;
    wire [255:0] wdata;wire [31:0] wstrb;
    hdmi1080_input_dma #(.WIDTH(W),.HEIGHT(H),.BANK_STRIDE(STRIDE),.FIFO_ADDR_BITS(2)) dut(
        .pix_clk(pix_clk),.sys_clk(sys_clk),.rst_n(rst_n),.enable(enable),
        .pix_vsync_active(vs),.pix_de(de),.pix_rgb(rgb),
        .source_writable(writable),.source_released(release_valid),.released_bank(release_bank),
        .source_valid(source_valid),.source_ready(source_ready),.source_bank(source_bank),
        .source_id(source_id),.source_crc(source_crc),.source_pixels(source_pixels),.capture_reserved(reserved),
        .awaddr(awaddr),.awlen(awlen),.awvalid(awvalid),.awready(awready),
        .wdata(wdata),.wstrb(wstrb),.wready(wready),.wlast(wlast),.write_active(write_active),
        .failed(failed),.fault(fault),.accepted_frames(accepted),.dropped_frames(dropped),
        .overflow_frames(overflowed),.no_free_frames(no_free),.last_drop_fault(last_drop));
    integer total_ticks=0,seed=0,wleft=0,wbank=0,woffset=0,windex=0,aw_count=0,w_count=0;
    integer frame_written[0:1];reg [15:0] memory[0:2*N-1];
    reg force_ddr_stall=0,force_w_stall=0,check_pixels=1,allow_failed=0;
    integer cov_aw_stall=0,cov_w_stall=0,cov_commit_stall=0,cov_banks=0,cov_no_free=0;
    integer cov_short_line=0,cov_long_line=0,cov_short_frame=0,cov_long_frame=0;
    integer cov_overflow=0,cov_drain_before_drop=0,cov_reset_half=0,cov_release_reject=0,cov_recovery=0;
    integer cov_aw_first_w=0,cov_aw_delayed_w=0;
    reg aw_held=0,w_held=0,commit_held=0;reg [31:0] saved_aw,saved_id,saved_crc,saved_pixels;
    reg saved_bank;reg [255:0] saved_w;
    function automatic [23:0] texture(input integer x,input integer y,input integer k);
        reg [7:0] r,g,b;
        begin r=x*19+y*7+k*31;g=x*3+y*29+k*17;b=x*11+y*13+k*47;texture={r,g,b};end
    endfunction
    function automatic [15:0] expected565(input integer p,input integer k);
        reg [23:0] c;begin c=texture(p%W,p/W,k);expected565={c[23:19],c[15:10],c[7:3]};end
    endfunction
    function automatic [31:0] crc_byte(input [31:0] c,input [7:0] b);
        reg [31:0] a;integer j;
        begin a=c^b;for(j=0;j<8;j=j+1)a=a[0] ? (a>>1)^32'hedb88320:a>>1;crc_byte=a;end
    endfunction
    function automatic [31:0] expected_crc(input integer k);
        reg [31:0] c;reg [15:0] p;integer n;
        begin c=32'hffffffff;for(n=0;n<N;n=n+1)begin
            p=expected565(n,k);c=crc_byte(crc_byte(c,p[7:0]),p[15:8]);end expected_crc=~c;end
    endfunction
    always @(negedge sys_clk)begin
        total_ticks=total_ticks+1;
        if(total_ticks>=2000000)$fatal(1,"input DMA bounded2M system-cycle timeout");
        awready=rst_n && !force_ddr_stall && wleft==0 && total_ticks%7>=2;
        // Both legal shim cases: even-numbered bursts accept beat0 with AW,
        // odd-numbered bursts only accept W on a later cycle. Never hide the
        // existing arbiter's zero-latency first-beat contract behind the model.
        wready=rst_n && !force_ddr_stall && !force_w_stall &&
            (wleft!=0 || (awvalid && awready && aw_count%2==0)) && total_ticks%5!=0;
        wlast=wleft==1;
    end
    integer b,off,lane,pos,transfer_bank,transfer_offset,transfer_index;reg first_write;
    always @(posedge sys_clk)begin
        if(!rst_n)begin
            wleft<=0;windex<=0;aw_count<=0;w_count<=0;core_owned<=0;
            frame_written[0]<=0;frame_written[1]<=0;aw_held<=0;w_held<=0;commit_held<=0;
        end else begin
            if(failed && !allow_failed)$fatal(1,"Unexpected input DMA fault%h",fault);
            if(aw_held && (!awvalid || {awaddr,awlen}!==saved_aw))$fatal(1,"AW reservation changed while stalled");
            if(w_held && (!write_active || wdata!==saved_w))$fatal(1,"W payload changed while stalled");
            if(commit_held && (!source_valid || {source_bank,source_id,source_crc,source_pixels}!==
                {saved_bank,saved_id,saved_crc,saved_pixels}))$fatal(1,"commit metadata changed while stalled");
            aw_held<=awvalid&&!awready;saved_aw<={awaddr,awlen};
            w_held<=write_active&&!wready;saved_w<=wdata;
            commit_held<=source_valid&&!source_ready;
            saved_bank<=source_bank;saved_id<=source_id;saved_crc<=source_crc;saved_pixels<=source_pixels;
            if(awvalid&&!awready)cov_aw_stall=cov_aw_stall+1;
            if(write_active&&!wready)cov_w_stall=cov_w_stall+1;
            if(source_valid&&!source_ready)cov_commit_stall=cov_commit_stall+1;
            if(awvalid&&awready)begin
                b=awaddr/STRIDE;off=awaddr%STRIDE;
                if(wleft!=0 || awlen!=15 || b>1 || off%128 || off+128>N/2 ||
                   !reserved[b] || core_owned[b] || (source_valid && source_bank==b) || dut.buffered!=16)
                    $fatal(1,"input AW not full16beat or source-bank ownership/range overlaps");
                if(off==0)frame_written[b]<=0;
                wleft<=16;windex<=0;wbank<=b;woffset<=off*2;aw_count<=aw_count+1;
                if(write_active && wready)cov_aw_first_w=cov_aw_first_w+1;
                else cov_aw_delayed_w=cov_aw_delayed_w+1;
            end
            if(write_active&&wready)begin
                first_write=wleft==0 && awvalid && awready;
                transfer_bank=first_write ? b:wbank;
                transfer_offset=first_write ? off*2:woffset;
                transfer_index=first_write ? 0:windex;
                if((wleft==0 && !first_write) || wstrb!==32'hffffffff ||
                   wlast!=(!first_write && wleft==1) || core_owned[transfer_bank])
                    $fatal(1,"input W underflow/strobes/last/committed-bank write");
                for(lane=0;lane<16;lane=lane+1)begin
                    pos=transfer_offset+transfer_index*16+lane;
                    if(pos>=N || (check_pixels && wdata[lane*16+:16]!==expected565(pos,seed)))
                        $fatal(1,"input independent RGB565 lane%0d pixel%0d mismatch",lane,pos);
                    memory[transfer_bank*N+pos]<=wdata[lane*16+:16];
                end
                wleft<=first_write ? 15:wleft-1;windex<=transfer_index+1;w_count<=w_count+1;
                if(first_write && off==0)frame_written[transfer_bank]<=1;
                else frame_written[transfer_bank]<=frame_written[transfer_bank]+1;
            end
            if(source_valid)begin
                if(wleft!=0 || write_active || awvalid || source_pixels!=N ||
                   source_crc!==expected_crc(seed) || frame_written[source_bank]!=FB || !reserved[source_bank])
                    $fatal(1,"partial/non-drained/CRC-mismatched frame was published");
                for(integer n=0;n<N;n=n+1)
                    if(memory[source_bank*N+n]!==expected565(n,seed))$fatal(1,"commit native-memory oracle mismatch%0d",n);
            end
            if(source_valid&&source_ready)begin
                if(core_owned[source_bank])$fatal(1,"duplicate commit into core-owned bank");
                core_owned[source_bank]<=1;cov_banks=cov_banks|(1<<source_bank);
            end
            if(release_valid && core_owned[release_bank])core_owned[release_bank]<=0;
        end
    end
    task automatic reset_all;
        begin
            @(negedge sys_clk);rst_n=0;enable=0;source_ready=0;release_valid=0;
            @(negedge pix_clk);de=0;vs=0;rgb=0;
            force_ddr_stall=0;force_w_stall=0;allow_failed=0;check_pixels=1;
            repeat(8)@(negedge sys_clk);rst_n=1;repeat(8)@(negedge pix_clk);
            if(reserved!=0 || source_valid || failed || write_active)$fatal(1,"coordinated reset resurrected transaction/ownership");
        end
    endtask
    task automatic frame_start;
        begin
            @(negedge pix_clk);de=0;vs=1;repeat(2)@(negedge pix_clk);vs=0;
            repeat(8)@(negedge pix_clk);
        end
    endtask
    task automatic rows(input integer lines,input integer kind);
        integer y,x,line_width;
        begin
            for(y=0;y<lines;y=y+1)begin
                line_width=W;if(y==0 && kind==1)line_width=W-1;if(y==0 && kind==2)line_width=W+1;
                for(x=0;x<line_width;x=x+1)begin @(negedge pix_clk);de=1;rgb=texture(x,y,seed);end
                @(negedge pix_clk);de=0;repeat(4)@(negedge pix_clk);
            end
        end
    endtask
    task automatic frame_end;
        begin repeat(3)@(negedge pix_clk);vs=1;repeat(2)@(negedge pix_clk);vs=0;end
    endtask
    task automatic send_frame(input integer kind);
        integer lines;
        begin
            lines=H;if(kind==3)lines=H-1;if(kind==4)lines=H+1;
            frame_start();rows(lines,kind);frame_end();
        end
    endtask
    task automatic accept_commit;
        begin
            wait(source_valid);repeat(11)@(negedge sys_clk);
            if(core_owned[source_bank] || wleft!=0)$fatal(1,"held offer already owned or W not drained");
            source_ready=1;@(negedge sys_clk);source_ready=0;repeat(3)@(negedge sys_clk);
        end
    endtask
    task automatic release_owned(input integer bank);
        begin @(negedge sys_clk);release_bank=bank;release_valid=1;@(negedge sys_clk);release_valid=0;end
    endtask
    task automatic good_frame(input integer k);
        begin
            seed=k;check_pixels=1;@(negedge sys_clk);enable=1;wait(dut.active);
            send_frame(0);enable=0;accept_commit();
        end
    endtask
    task automatic bad_frame(input integer kind);
        begin
            reset_all();seed=10+kind;check_pixels=0;@(negedge sys_clk);enable=1;wait(dut.active);
            send_frame(kind);enable=0;wait(dropped==1);repeat(8)@(negedge sys_clk);
            if(source_valid || accepted!=0 || reserved!=0 || wleft!=0 || write_active || last_drop==0)
                $fatal(1,"malformed frame was published or reservation released before drain kind%0d",kind);
            case(kind)
                1:cov_short_line=cov_short_line+1;2:cov_long_line=cov_long_line+1;
                3:cov_short_frame=cov_short_frame+1;4:cov_long_frame=cov_long_frame+1;
            endcase
        end
    endtask
    integer before_aw,before_no_free;
    initial begin
        reset_all();good_frame(1);good_frame(2);
        if(accepted!=2 || core_owned!=3 || reserved!=3)$fatal(1,"both committed banks not retained until core release");
        before_aw=aw_count;before_no_free=no_free;seed=3;enable=1;send_frame(0);enable=0;
        repeat(12)@(negedge sys_clk);
        if(no_free<=before_no_free || aw_count!=before_aw || accepted!=2 || reserved!=3)
            $fatal(1,"unthrottled no-freebank frame was not wholly discarded");
        cov_no_free=cov_no_free+1;release_owned(0);good_frame(4);
        if(accepted!=3 || core_owned!=3)$fatal(1,"released bank was not reusable");
        cov_recovery=cov_recovery+1;
        $display("PASS HDMI input normal async RGB565/CRC, two-bank ownership, stable commit, no-free whole-frame drop and release/reuse");

        bad_frame(1);bad_frame(2);bad_frame(3);bad_frame(4);
        $display("PASS HDMI input short/long line and short/long frame never publish partial DDR");

        reset_all();seed=20;check_pixels=0;force_ddr_stall=1;enable=1;wait(dut.active);
        send_frame(0);enable=0;wait(dut.end_seen);repeat(8)@(negedge sys_clk);
        if(!awvalid || dropped!=0 || reserved!=1 || source_valid || dut.end_fault[3]!==1'b1)
            $fatal(1,"overflow reservation/announced AW released before DDR drain");
        force_ddr_stall=0;wait(dropped==1);repeat(8)@(negedge sys_clk);
        if(overflowed!=1 || reserved!=0 || wleft!=0 || w_count!=16 || aw_count!=1 || source_valid)
            $fatal(1,"overflow whole-frame quarantine did not drain exact announced16beat burst");
        cov_overflow=cov_overflow+1;cov_drain_before_drop=cov_drain_before_drop+1;
        cov_recovery=cov_recovery+1;
        $display("PASS HDMI input FIFO overflow drops whole frame only after outstanding AW/W drain");

        reset_all();seed=30;force_w_stall=1;enable=1;wait(dut.active);
        frame_start();rows(10,0);enable=0;
        if(!write_active || wleft!=16 || source_valid)$fatal(1,"half-reset test did not reach accepted AW with held W");
        cov_reset_half=cov_reset_half+1;reset_all();good_frame(31);cov_recovery=cov_recovery+1;
        $display("PASS HDMI input coordinated half-frame/DDR reset clears stale data/ownership and next full frame recovers");

        reset_all();allow_failed=1;enable=1;wait(dut.active);enable=0;
        release_owned(0);repeat(4)@(negedge sys_clk);
        if(!failed || fault!=8'h82 || reserved!=1)$fatal(1,"release illegally freed an uncommitted reservation");
        cov_release_reject=cov_release_reject+1;
        reset_all();allow_failed=1;release_owned(1);repeat(4)@(negedge sys_clk);
        if(!failed || fault!=8'h82 || reserved!=0)$fatal(1,"unowned-bank release not rejected");
        cov_release_reject=cov_release_reject+1;
        if(cov_banks!=3 || cov_aw_stall==0 || cov_w_stall==0 || cov_commit_stall==0 || cov_no_free==0 ||
           cov_short_line==0 || cov_long_line==0 || cov_short_frame==0 || cov_long_frame==0 ||
           cov_overflow==0 || cov_drain_before_drop==0 || cov_reset_half==0 || cov_release_reject!=2 || cov_recovery<3 ||
           cov_aw_first_w==0 || cov_aw_delayed_w==0)
            $fatal(1,"input DMA mandatory coverage was vacuous");
        $display("HDMI_INPUT_COVERAGE aw_stall=%0d w_stall=%0d commit_stall=%0d banks=%0d no_free=%0d short_line=%0d long_line=%0d short_frame=%0d long_frame=%0d overflow=%0d drained_drop=%0d half_reset=%0d reject_release=%0d recovery=%0d",
            cov_aw_stall,cov_w_stall,cov_commit_stall,cov_banks,cov_no_free,cov_short_line,cov_long_line,
            cov_short_frame,cov_long_frame,cov_overflow,cov_drain_before_drop,cov_reset_half,cov_release_reject,cov_recovery);
        $display("HDMI_INPUT_AW_W_COVERAGE first_W_with_AW=%0d delayed_first_W=%0d",cov_aw_first_w,cov_aw_delayed_w);
        $display("PASS hdmi1080_input_dma directed small async development regression; no1080/30fps/chip-lock/pin/STA/hardware claim");
        $finish;
    end
    initial begin #15999990;$fatal(1,"input DMA bounded elapsed simulation timeout");end
endmodule
