`timescale 1ps/1ps
// Independent counterexample for frozen RTL. No force of DUT internals.
// Both DUTs receive the identical exact 1080p30 raster, except that the
// transient DUT sees opposite HS/VS for its first DE sample only.
module tb_hdmi_first_de_transient;
    localparam W=1920,H=1080,HT=2200,VT=1125,X0=192,Y0=41;
    reg ref_clk=0,pix_clk=0,rst_n=0,source_enable=0;
    integer ref_phase=0,ref_delay,pix_phase=0,pix_delay;
    initial forever begin
        ref_phase=ref_phase+500000;ref_delay=ref_phase/27;ref_phase=ref_phase%27;
        #(ref_delay)ref_clk=~ref_clk;
    end
    initial begin
        #1777;
        forever begin
            pix_phase=pix_phase+2000000;pix_delay=pix_phase/297;pix_phase=pix_phase%297;
            #(pix_delay)pix_clk=~pix_clk;
        end
    end
    reg pix_vs=0,pix_hs=0,pix_de=0,transient=0,injected=0;
    integer src_x=0,src_y=0,rasters=0,transient_samples=0;
    always @(negedge pix_clk)begin
        if(!rst_n || !source_enable)begin
            src_x=0;src_y=0;pix_vs=0;pix_hs=0;pix_de=0;transient=0;
        end else begin
            pix_vs=src_y<5;pix_hs=src_x<44;
            pix_de=src_y>=Y0 && src_y<Y0+H && src_x>=X0 && src_x<X0+W;
            transient=pix_de && !injected;
            if(transient)injected=1;
            if(src_x==HT-1)begin
                src_x=0;
                if(src_y==VT-1)begin src_y=0;rasters=rasters+1;end
                else src_y=src_y+1;
            end else src_x=src_x+1;
        end
    end
    always @(posedge pix_clk)if(transient)begin
        transient_samples=transient_samples+1;
        if(!pix_de || pix_vs || pix_hs)$fatal(1,"transient must override exactly an inactive sync DE sample");
    end
    wire clean_qualified,clean_failed,clean_known,clean_vi,clean_hi;
    wire bad_qualified,bad_failed,bad_known,bad_vi,bad_hi;
    wire [7:0] clean_fault,bad_fault;
    wire [31:0] clean_good,clean_bad,clean_edges,bad_good,bad_bad,bad_edges;
    wire [15:0] clean_width,clean_height,bad_width,bad_height;
    hdmi1080_input_status_cdc clean(
        .ref_clk(ref_clk),.pix_clk(pix_clk),.rst_n(rst_n),.pix_vs(pix_vs),.pix_hs(pix_hs),.pix_de(pix_de),
        .normalized_vs(),.qualified(clean_qualified),.failed(clean_failed),.fault(clean_fault),
        .polarity_known_ref(clean_known),.vs_inactive_ref(clean_vi),.hs_inactive_ref(clean_hi),
        .good_frames(clean_good),.bad_frames(clean_bad),.pclk_edges_per_window(clean_edges),
        .last_pixels_per_line(clean_width),.last_lines(clean_height));
    hdmi1080_input_status_cdc corrupted(
        .ref_clk(ref_clk),.pix_clk(pix_clk),.rst_n(rst_n),.pix_vs(pix_vs^transient),.pix_hs(pix_hs^transient),.pix_de(pix_de),
        .normalized_vs(),.qualified(bad_qualified),.failed(bad_failed),.fault(bad_fault),
        .polarity_known_ref(bad_known),.vs_inactive_ref(bad_vi),.hs_inactive_ref(bad_hi),
        .good_frames(bad_good),.bad_frames(bad_bad),.pclk_edges_per_window(bad_edges),
        .last_pixels_per_line(bad_width),.last_lines(bad_height));
    integer ref_cycles=0;
    always @(posedge ref_clk)begin
        ref_cycles=ref_cycles+1;
        if(ref_cycles>4100000)$fatal(1,"bounded counterexample timeout");
        if(injected && corrupted.polarity_known &&
           (corrupted.vs_inactive!==1 || corrupted.hs_inactive!==1))
            $fatal(1,"incorrect polarity unexpectedly relearned before reset");
    end
    task automatic check_state(input integer sample);
        begin
            if(!clean_qualified || clean_failed || clean_fault || clean_vi || clean_hi ||
               clean_good<2 || clean_bad || clean_width!=W || clean_height!=H)
                $fatal(1,"clean startup did not qualify: fault%h good%0d bad%0d width%0d height%0d",clean_fault,clean_good,clean_bad,clean_width,clean_height);
            if(bad_qualified || !bad_failed || bad_fault!==8'h15 || !bad_known || !bad_vi || !bad_hi ||
               bad_good || bad_bad<2 || bad_width || bad_height!=H ||
               corrupted.geometry.source_fault!==8'h15 || corrupted.timing_fault!==8'h21)
                $fatal(1,"transient counterexample differs: fault%h good%0d bad%0d width%0d height%0d timing%h",bad_fault,bad_good,bad_bad,bad_width,bad_height,corrupted.timing_fault);
            if(clean_edges<73500 || clean_edges>75000 || bad_edges<73500 || bad_edges>75000)
                $fatal(1,"clock activity must remain admitted for both cases");
            $display("COUNTEREXAMPLE_SAMPLE index=%0d rasters=%0d clean_qualified=%0d clean_fault=%h clean_good=%0d clean_bad=%0d clean_width=%0d clean_height=%0d clean_vs_inactive=%0d clean_hs_inactive=%0d clean_pclk_edges=%0d bad_qualified=%0d bad_fault=%h bad_good=%0d bad_bad=%0d bad_width=%0d bad_height=%0d bad_vs_inactive=%0d bad_hs_inactive=%0d bad_pclk_edges=%0d bad_timing_fault=%h",sample,rasters,clean_qualified,clean_fault,clean_good,clean_bad,clean_width,clean_height,clean_vi,clean_hi,clean_edges,bad_qualified,bad_fault,bad_good,bad_bad,bad_width,bad_height,bad_vi,bad_hi,bad_edges,corrupted.timing_fault);
        end
    endtask
    integer first_clean_good,first_bad_bad,output_file;
    initial begin
        repeat(16)@(negedge ref_clk);
        rst_n=1;
        repeat(20)@(negedge ref_clk);
        source_enable=1;
        wait(rasters>=3);
        repeat(54000)@(negedge ref_clk);
        check_state(1);first_clean_good=clean_good;first_bad_bad=bad_bad;
        wait(rasters>=4);
        repeat(54000)@(negedge ref_clk);
        check_state(2);
        if(transient_samples!=1 || clean_good!=first_clean_good+1 || bad_bad!=first_bad_bad+1)
            $fatal(1,"one transient sample or continuing one-bad-frame-per-raster proof missing");
        output_file=$fopen("counterexample-summary.json","w");
        $fdisplay(output_file,"{\"passed\":true,\"exact_raster\":[2200,1125],\"active_geometry\":[1920,1080],\"transient_samples\":%0d,\"completed_rasters\":%0d,\"clean\":{\"qualified\":true,\"fault\":0,\"good_frames\":%0d,\"bad_frames\":%0d,\"width\":%0d,\"height\":%0d,\"inactive_vs\":0,\"inactive_hs\":0},\"transient\":{\"qualified\":false,\"fault\":21,\"good_frames\":%0d,\"bad_frames\":%0d,\"width\":%0d,\"height\":%0d,\"inactive_vs\":1,\"inactive_hs\":1,\"private_timing_fault\":33},\"continuing_bad_frames_per_raster\":1,\"hardware_verified\":false}",transient_samples,rasters,clean_good,clean_bad,clean_width,clean_height,bad_good,bad_bad,bad_width,bad_height);
        $fclose(output_file);
        $display("PASS first DE one-sample opposite sync permanently learns wrong polarity until reset; subsequent exact1080p30 produces fault15 width0 height1080 good0 and one bad frame per raster");
        $finish;
    end
endmodule
