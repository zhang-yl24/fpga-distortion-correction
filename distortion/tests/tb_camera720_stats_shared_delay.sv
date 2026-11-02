`timescale 1ps/1ps
// Actual vendor functional models; no physical timing or sensor assumptions.
module tb_camera720_stats_shared_delay;
    reg [9:0] pad = 0;
    wire [7:0] delayed_data;
    wire delayed_href, delayed_vsync;
    wire [9:0] capture = {delayed_vsync,delayed_href,delayed_data};
    reg pclk=0;
    reg [9:0] sampled_capture=0;
    reg [1:0] sampled_monitor=0;
    raw_camera_input_delay camera_data_delay(.pad_data(pad[7:0]),.capture_data(delayed_data));
    raw_camera_control_input_delay camera_control_delay(.pad_href(pad[8]),.pad_vsync(pad[9]),
        .capture_href(delayed_href),.capture_vsync(delayed_vsync));
    always @(posedge pclk) begin
        sampled_capture <= capture;
        sampled_monitor <= {delayed_vsync,delayed_href};
    end
    integer values, phase, lane, checks=0, edge_checks=0, fd, boundary, summary;
    integer offsets[0:7];
    integer rises[0:9];
    integer falls[0:9];
    reg [9:0] old_pad, next_pad, expected;
    initial begin
        offsets[0]=1;offsets[1]=100;offsets[2]=1000;offsets[3]=1499;
        offsets[4]=1501;offsets[5]=2000;offsets[6]=8000;offsets[7]=15000;
        for(lane=0;lane<10;lane=lane+1)begin rises[lane]=0;falls[lane]=0;end
        fd=$fopen("transitions.csv","w");boundary=$fopen("sampling.csv","w");
        if(!fd || !boundary)$fatal(1,"cannot open observations");
        $fdisplay(fd,"index,previous,driven,before1500ps,after1500ps,stable");
        $fdisplay(boundary,"index,offset_ps,previous,driven,sampled_capture,sampled_delayed_monitor");
        #2000;
        if(capture!==0)$fatal(1,"initial vendor pipeline did not settle");
        for(values=0;values<1024;values=values+1)begin
            old_pad=pad;next_pad=values[9:0]^10'h2a5;pad=next_pad;
            for(lane=0;lane<10;lane=lane+1)begin
                if(!old_pad[lane] && next_pad[lane])rises[lane]=rises[lane]+1;
                if(old_pad[lane] && !next_pad[lane])falls[lane]=falls[lane]+1;
            end
            #1499;
            if(capture!==old_pad)$fatal(1,"lane skew or early transition, value %0d",values);
            $fwrite(fd,"%0d,%03x,%03x,%03x,",values,old_pad,next_pad,capture);checks=checks+1;
            #2;
            if(capture!==next_pad)$fatal(1,"late transition or ctrl/data mismatch, value %0d",values);
            $fwrite(fd,"%03x,",capture);checks=checks+1;
            #2499;
            if(capture!==next_pad)$fatal(1,"extra register/cycle or unstable tuple");
            $fdisplay(fd,"%03x",capture);checks=checks+1;
        end
        // Input transition at t=0; sample on either side of nominal 1500ps.
        // A true extra sampling cycle or control/data shift fails these tuples.
        for(phase=0;phase<32;phase=phase+1)begin
            old_pad=pad;next_pad=~old_pad;pad=next_pad;
            #(offsets[phase%8]);pclk=1;
            #1;
            expected=(offsets[phase%8]<1500)?old_pad:next_pad;
            if(sampled_capture!==expected)$fatal(1,"sample boundary tuple wrong phase=%0d",phase);
            if(sampled_monitor!==expected[9:8])$fatal(1,"shared control monitor differs from delayed capture");
            $fdisplay(boundary,"%0d,%0d,%03x,%03x,%03x,%01x",phase,offsets[phase%8],old_pad,next_pad,sampled_capture,sampled_monitor);
            edge_checks=edge_checks+1;
            pclk=0;#(16000-offsets[phase%8]-1);
            if(capture!==next_pad)$fatal(1,"one full PCLK cycle delay detected");
        end
        for(lane=0;lane<10;lane=lane+1)
            if(rises[lane]==0 || falls[lane]==0)$fatal(1,"missing lane polarity %0d",lane);
        if(checks!=3072 || edge_checks!=32)$fatal(1,"incomplete tuple/boundary coverage");
        $fclose(fd);$fclose(boundary);
        summary=$fopen("summary.json","w");
        $fdisplay(summary,"{\"Passed\":true,\"Lanes\":10,\"NominalDelayPS\":1500,\"AllTupleValues\":1024,\"Checks\":3072,\"SampleBoundaryChecks\":32,\"BothPolaritiesEveryLane\":true}");
        $fclose(summary);
        $display("CAMERA720_STATS_SHARED_DELAY_PASS lanes=10 tuples=1024 checks=3072 sampling=32 nominal_delay_ps=1500");
        $finish;
    end
    initial begin #5000000;$fatal(1,"control/data delay test timed out");end
endmodule
