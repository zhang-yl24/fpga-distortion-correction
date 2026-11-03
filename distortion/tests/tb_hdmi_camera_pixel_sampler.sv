`timescale 1ns/1ps
// Independent raw-pin history, phase perturbation and stopped-reset epochs.
module tb_hdmi_camera_pixel_sampler;
    reg pclk=0,rst_n=0,run_pclk=0;
    reg raw_vs=1,raw_hs=1,raw_de=1;
    reg [23:0] raw_rgb=24'hfac137;
    always begin #3.367;if(run_pclk)pclk=~pclk;else pclk=0;end
    wire sv,sh,sd,valid,vactive,dactive;
    wire [23:0] rgb;
    wire nv,nh,nd,nvalid,nvactive,ndactive;
    wire [23:0] nrgb;
    wire invalid_valid,invalid_vs,invalid_de;
    hdmi_camera_pixel_sampler dut(.pclk(pclk),.rst_n(rst_n),.raw_vs(raw_vs),.raw_hs(raw_hs),.raw_de(raw_de),
        .raw_rgb(raw_rgb),.sampled_vs(sv),.sampled_hs(sh),.sampled_de(sd),.sampled_rgb(rgb),
        .sampled_valid(valid),.vs_active(vactive),.de_active(dactive));
    hdmi_camera_pixel_sampler #(.VS_ACTIVE_LEVEL(0),.DE_ACTIVE_LEVEL(0)) inverted(
        .pclk(pclk),.rst_n(rst_n),.raw_vs(raw_vs),.raw_hs(raw_hs),.raw_de(raw_de),.raw_rgb(raw_rgb),
        .sampled_vs(nv),.sampled_hs(nh),.sampled_de(nd),.sampled_rgb(nrgb),.sampled_valid(nvalid),
        .vs_active(nvactive),.de_active(ndactive));
    hdmi_camera_pixel_sampler #(.VS_ACTIVE_LEVEL(2),.DE_ACTIVE_LEVEL(1)) invalid_polarity(
        .pclk(pclk),.rst_n(rst_n),.raw_vs(raw_vs),.raw_hs(raw_hs),.raw_de(raw_de),.raw_rgb(raw_rgb),
        .sampled_vs(),.sampled_hs(),.sampled_de(),.sampled_rgb(),.sampled_valid(invalid_valid),
        .vs_active(invalid_vs),.de_active(invalid_de));

    // Own reset history; never read the DUT reset pipe or sample-valid hold.
    reg [1:0] model_release=0;
    always @(posedge pclk or negedge rst_n)
        if(!rst_n)model_release<=0;else model_release<={model_release[0],1'b1};
    reg [26:0] expected_bundle;
    reg expected_valid,history_valid=0;
    reg [2:0] first_levels,previous_levels;
    integer checks=0,phase_changes=0,reset_checks=0,i,j;
    integer rises[0:2],falls[0:2];
    real skew;
    always @(posedge pclk)begin
        if(!model_release[1])begin
            expected_bundle=0;expected_valid=0;history_valid=0;
            first_levels=0;previous_levels=0;
            for(j=0;j<3;j=j+1)begin rises[j]=0;falls[j]=0;end
        end else begin expected_bundle={raw_vs,raw_hs,raw_de,raw_rgb};expected_valid=1;end
        #0.001;
        if({sv,sh,sd,rgb}!==expected_bundle || valid!==expected_valid ||
           {nv,nh,nd,nrgb}!==expected_bundle || nvalid!==expected_valid || invalid_valid!==expected_valid)
            $fatal(1,"common sampled bundle differs from independent raw-pin oracle");
        if(vactive!==(valid&&sv) || dactive!==(valid&&sd) ||
           nvactive!==(valid&&!sv) || ndactive!==(valid&&!sd) || invalid_vs!==0 || invalid_de!==0)
            $fatal(1,"valid/polarity normalization differs");
        if(valid)begin
            // This consumer establishes a baseline on the first real sample.
            // First high input never invents rising edges from reset zeros.
            if(!history_valid)begin first_levels={sv,sh,sd};history_valid=1;end
            else for(j=0;j<3;j=j+1)begin
                if(expected_bundle[24+j]&&!previous_levels[j])rises[j]=rises[j]+1;
                if(!expected_bundle[24+j]&&previous_levels[j])falls[j]=falls[j]+1;
            end
            previous_levels={sv,sh,sd};
            for(j=0;j<3;j=j+1)
                if(rises[j]-falls[j]!==int'(previous_levels[j])-int'(first_levels[j]))
                    $fatal(1,"first-sample baseline or edge conservation violated");
        end
        checks=checks+1;
    end
    always @(negedge rst_n)begin
        #0.002;
        if(valid!==0 || nvalid!==0 || vactive!==0 || dactive!==0 || nvactive!==0 || ndactive!==0)
            $fatal(1,"stopped-source reset failed to mask retained data immediately");
        reset_checks=reset_checks+1;
    end
    task cycles(input integer n);
        repeat(n)begin @(negedge pclk);#0.05;end
    endtask
    initial begin
        #20;rst_n=1;#30;
        if(valid!==0)$fatal(1,"unclocked startup became valid");
        run_pclk=1;cycles(6);
        if(!valid || !vactive || !dactive || rises[0]!=0 || rises[1]!=0 || rises[2]!=0)
            $fatal(1,"initial high input invented a baseline edge");
        $display("HDMI_PIXEL_SAMPLER_CASE initial_high_no_fake_edges");
        for(i=0;i<512;i=i+1)begin
            @(negedge pclk);
            case(i%4)0:skew=-0.020;1:skew=0.020;2:skew=-0.002;3:skew=0.002;endcase
            #(3.367+skew);
            raw_vs=(i%13)<5;raw_hs=(i%7)<3;raw_de=(i%11)<8;
            raw_rgb=(24'h1f347b*i)^24'h9ca731;phase_changes=phase_changes+1;
        end
        for(i=0;i<32;i=i+1)begin
            @(negedge pclk);#0.2;
            {raw_vs,raw_hs,raw_de,raw_rgb}=~{raw_vs,raw_hs,raw_de,raw_rgb};
            #0.2;{raw_vs,raw_hs,raw_de,raw_rgb}=~{raw_vs,raw_hs,raw_de,raw_rgb};
            phase_changes=phase_changes+2;
        end
        cycles(5);
        $display("HDMI_PIXEL_SAMPLER_CASE all27bits before_after_pclk unsampled_short_pulses polarity01");
        @(negedge pclk);run_pclk=0;#30;rst_n=0;#30;rst_n=1;
        #100;if(valid!==0 || vactive!==0 || dactive!==0)$fatal(1,"stopped reset republished an old sample");
        raw_vs=1;raw_hs=1;raw_de=1;raw_rgb=24'h81fe73;
        run_pclk=1;cycles(7);
        if(!valid || rises[0]!=0 || rises[1]!=0 || rises[2]!=0)
            $fatal(1,"resumed first high sample invented an edge");
        $display("HDMI_PIXEL_SAMPLER_CASE stopped_clock_common_reset_resume");
        if(checks<520 || phase_changes!=576 || reset_checks<1)$fatal(1,"sampler coverage incomplete");
        $display("HDMI_PIXEL_SAMPLER_PASS checks=%0d phase_changes=%0d reset_checks=%0d",checks,phase_changes,reset_checks);
        $finish;
    end
    initial begin #100000;$fatal(1,"sampler bench timeout");end
endmodule
