`timescale 1ns/1ps
module hdmi_fisheye_mapper_case #(parameter W=32,H=16,NATIVE=0);
    reg clk=0;always #4 clk=~clk; //125 MHz processing domain
    reg rst=1,cfg_valid=0,cfg_corrected=0,in_valid=0,in_black=0,out_ready=0;
    wire cfg_ready,in_ready,out_valid,out_black;
    reg signed [23:0] in_u=0,in_v=0;
    reg [23:0] in_tag=0;
    wire signed [23:0] out_x,out_y;wire [23:0] out_tag;
    hdmi_camera_fisheye_mapper #(.WIDTH(W),.HEIGHT(H)) dut(.*);
    reg [97:0] record;
    reg [48:0] offered_expected;
    reg [48:0] expected[0:63];reg [23:0] expected_tag[0:63];
    integer qwrite=0,qread=0,sent=0,received=0,cycles=0,stall_cycles=0,hold_checks=0;
    integer phase=0,phase_count=0,running=0,pulse_left=0,pulse_done=0,blocked_configs=0;
    integer longest_run=0,consecutive=0,first_accept=-1,first_output=-1;
    integer vector_file,status,j,target;
    reg [31:0] rng=32'h6a09e667;
    reg previous_stall=0;reg [72:0] previous_output;
    always @(negedge clk)begin
        rng={rng[30:0],rng[31]^rng[21]^rng[1]^rng[0]};
        if(rst)out_ready=0;
        else out_ready=(sent<64 || rng[3:0]!=0) && !(running && rng[8:5]==1);
        if(running && phase==0 && sent>=100 && !pulse_done)begin
            cfg_valid=1;cfg_corrected=0;pulse_done=1;pulse_left=2;
        end else if(pulse_left>0)begin
            pulse_left=pulse_left-1;if(pulse_left==0)cfg_valid=0;
        end
    end
    always @(posedge clk)begin
        cycles=cycles+1;
        if(!rst)begin
            if(previous_stall)begin
                if(!out_valid || {out_black,out_x,out_y,out_tag}!==previous_output)
                    $fatal(1,"output/tag changed under backpressure");
                hold_checks=hold_checks+1;
            end
            previous_stall=out_valid && !out_ready;
            previous_output={out_black,out_x,out_y,out_tag};
            if(cfg_valid && !cfg_ready)blocked_configs=blocked_configs+1;
            if(in_valid && in_ready)begin
                if(qwrite-qread>=64) $fatal(1,"oracle FIFO overflow");
                expected[qwrite%64]=offered_expected;expected_tag[qwrite%64]=in_tag;
                qwrite=qwrite+1;sent=sent+1;consecutive=consecutive+1;
                if(consecutive>longest_run)longest_run=consecutive;
                if(first_accept<0)first_accept=cycles;
            end else consecutive=0;
            if(out_valid && !out_ready)stall_cycles=stall_cycles+1;
            if(out_valid && out_ready)begin
                if(qread>=qwrite) $fatal(1,"unexpected output with no accepted coordinate");
                if({out_black,out_x,out_y}!==expected[qread%64] || out_tag!==expected_tag[qread%64])
                    $fatal(1,"coordinate mismatch index=%0d tag=%h got=%h/%h/%b expected=%h",received,out_tag,out_x,out_y,out_black,expected[qread%64]);
                qread=qread+1;received=received+1;
                if(first_output<0)first_output=cycles;
            end
        end
    end
    task configure(input bit mode);
        begin
            @(negedge clk);in_valid=0;
            while(!cfg_ready)@(negedge clk);
            cfg_corrected=mode;cfg_valid=1;
            @(posedge clk);
            @(negedge clk);cfg_valid=0;
        end
    endtask
    task stream(input [255:0] name,input integer count,input bit mode,input integer phase_number);
        begin
            configure(mode);phase=phase_number;running=1;
            vector_file=$fopen(name,"r");if(vector_file==0)$fatal(1,"missing coordinate fixture");
            target=sent+count;
            for(j=0;j<count;j=j+1)begin
                status=$fscanf(vector_file,"%h\n",record);if(status!=1)$fatal(1,"truncated coordinate fixture");
                @(negedge clk);
                if(j>=64 && rng[12:9]==2)begin in_valid=0;@(negedge clk);end
                in_valid=1;{in_black,in_u,in_v}=record[97:49];offered_expected=record[48:0];in_tag=sent;
                @(posedge clk);while(!in_ready)@(posedge clk);
            end
            @(negedge clk);in_valid=0;running=0;$fclose(vector_file);
            while(received<target)@(negedge clk);
            while(!cfg_ready)@(negedge clk);
            if(qwrite!=qread)$fatal(1,"frame did not fully drain");
        end
    endtask
    initial begin
        repeat(6)@(negedge clk);rst=0;
        if(in_ready || out_valid)$fatal(1,"unconfigured mapper accepted input");
        stream("corrected.mem",W*H,1,0);
        stream("identity.mem",4096,0,1);
        stream("domain.mem",1024,1,2);
        if(longest_run<32 || blocked_configs<2 || stall_cycles<10 || hold_checks<10 ||
            received!=W*H+5120 || first_output-first_accept!=23)
            $fatal(1,"missing pipeline/configuration/backpressure coverage latency=%0d",first_output-first_accept);
        $display("FISHEYE_MAPPER_PASS native=%0d corrected=%0d identity=4096 domain=1024 matched=%0d stalls=%0d stable_holds=%0d rejected_busy_configs=%0d longest_input_run=%0d enabled_latency=23",
            NATIVE,W*H,received,stall_cycles,hold_checks,blocked_configs,longest_run);
        $finish;
    end
    initial begin #200000000; $fatal(1,"mapper regression timeout");end
endmodule
module tb_hdmi_camera_fisheye_mapper_small;
    hdmi_fisheye_mapper_case test_case();
endmodule
module tb_hdmi_camera_fisheye_mapper_native;
    hdmi_fisheye_mapper_case #(.W(1920),.H(1080),.NATIVE(1)) test_case();
endmodule
