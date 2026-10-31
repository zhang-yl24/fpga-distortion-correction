`timescale 1ps/1ps
// A partial startup raster contains two complete lines followed by one short
// line before the next clean frame. The frame-trained candidate must wait;
// the two-line-only observer latches the malformed startup line.
module tb_hdmi_input_frame_training;
    localparam W=8,H=3,HT=16,VT=8,X0=3,Y0=2;
    reg ref_clk=0,pix_clk=0,rst_n=0,source_enable=0,reverse=0,inject_once=0;
    always #18500 ref_clk=~ref_clk;
    always #7000 pix_clk=~pix_clk;
    reg [5:0] x=0,y=0;
    reg vs=0,hs=0,de=0,short_this_line=0;
    integer rasters=0,short_lines=0;
    always @(negedge pix_clk)begin
        if(!rst_n || !source_enable)begin
            x=0;y=0;vs=reverse;hs=reverse;de=0;short_this_line=0;
        end else begin
            vs=(y<1)^reverse;
            hs=(x<2)^reverse;
            short_this_line=inject_once && y==Y0+2;
            de=(y>=Y0 && y<Y0+H && x>=X0 &&
                x<X0+W-(short_this_line?1:0));
            if(x==X0+W-(short_this_line?1:0) && y>=Y0 && y<Y0+H)
                short_lines=short_lines+1;
            if(x==HT-1)begin
                x=0;
                if(y==VT-1)begin y=0;rasters=rasters+1;end
                else y=y+1;
            end else x=x+1;
        end
    end
    wire old_qualified,old_failed,old_known;wire [7:0] old_fault;
    wire [31:0] old_good,old_bad,old_edges;wire [15:0] old_width,old_height;
    hdmi1080_input_status_trained #(.WIDTH(W),.HEIGHT(H),.HTOTAL(HT),.VTOTAL(VT),
        .ACTIVITY_REF_CYCLES(32),.PCLK_WINDOW_MIN(75),.PCLK_WINDOW_MAX(95)) old_observer(
        .ref_clk(ref_clk),.pix_clk(pix_clk),.rst_n(rst_n),.pix_vs(vs),.pix_hs(hs),.pix_de(de),
        .normalized_vs(),.qualified(old_qualified),.failed(old_failed),.fault(old_fault),
        .polarity_known_ref(old_known),.vs_inactive_ref(),.hs_inactive_ref(),
        .good_frames(old_good),.bad_frames(old_bad),.pclk_edges_per_window(old_edges),
        .last_pixels_per_line(old_width),.last_lines(old_height));
    wire new_qualified,new_failed,new_known;wire [7:0] new_fault;
    wire [31:0] new_good,new_bad,new_edges;wire [15:0] new_width,new_height;
    hdmi1080_input_status_frame_trained #(.WIDTH(W),.HEIGHT(H),.HTOTAL(HT),.VTOTAL(VT),
        .ACTIVITY_REF_CYCLES(32),.PCLK_WINDOW_MIN(75),.PCLK_WINDOW_MAX(95)) frame_observer(
        .ref_clk(ref_clk),.pix_clk(pix_clk),.rst_n(rst_n),.pix_vs(vs),.pix_hs(hs),.pix_de(de),
        .normalized_vs(),.qualified(new_qualified),.failed(new_failed),.fault(new_fault),
        .polarity_known_ref(new_known),.vs_inactive_ref(),.hs_inactive_ref(),
        .good_frames(new_good),.bad_frames(new_bad),.pclk_edges_per_window(new_edges),
        .last_pixels_per_line(new_width),.last_lines(new_height));

    integer cycles=0;
    always @(posedge ref_clk)begin
        cycles=cycles+1;
        if(cycles>20000)$fatal(1,"bounded frame-training timeout");
        if(!frame_observer.raster_ready && new_known)
            $fatal(1,"polarity escaped before a complete candidate raster");
    end

    task automatic reset_and_start(input integer polarity,input integer inject);
        begin
            @(negedge ref_clk);rst_n=0;source_enable=0;reverse=polarity;inject_once=inject;
            repeat(12)@(negedge ref_clk);rst_n=1;repeat(8)@(negedge ref_clk);
            @(negedge pix_clk);#1;
            // Begin in active video after the VS boundary, like a reset released
            // halfway through a source frame. The first interval is incomplete.
            x=X0;y=Y0;source_enable=1;
        end
    endtask

    integer pass_count=0;
    initial begin
        reset_and_start(0,1);
        wait(new_qualified || cycles>18000);
        if(!new_qualified || new_failed || new_fault!=0 || !new_known ||
           new_good<2 || new_bad!=0 || new_width!=W || new_height!=H)
            $fatal(1,"frame trained candidate did not recover startup short line fault=%h good=%0d bad=%0d width=%0d height=%0d",new_fault,new_good,new_bad,new_width,new_height);
        if(!old_failed || old_fault!=8'h12 || old_qualified)
            $fatal(1,"two-line baseline did not retain startup short-line fault %h",old_fault);
        if(!frame_observer.raster_ready || short_lines==0)
            $fatal(1,"complete-raster gate or startup short stimulus missing");
        $display("HDMI_FRAME_TRAIN_CASE startup_short_recovered PASS old_fault=%h new_good=%0d rasters=%0d",old_fault,new_good,rasters);
        pass_count=pass_count+1;

        // Reset, then exercise negative sync polarity without a startup defect.
        reset_and_start(1,0);
        wait(new_qualified || cycles>20000);
        if(!new_qualified || new_failed || new_fault!=0 || !new_known ||
           new_good<2 || new_bad!=0 || new_width!=W || new_height!=H ||
           !new_observer.strict_observer.vs_inactive || !new_observer.strict_observer.hs_inactive)
            $fatal(1,"negative sync full-raster candidate failed fault=%h",new_fault);
        $display("HDMI_FRAME_TRAIN_CASE negative_polarity PASS good=%0d",new_good);
        pass_count=pass_count+1;
        if(pass_count!=2)$fatal(1,"frame training suite incomplete");
        $display("PASS hdmi input frame training");
        $finish;
    end
endmodule
