`timescale 1ns/1ps
module tb_hdmi_camera_fisheye_io;
    reg clk=0;always #4 clk=~clk;
    reg rst_n=0;
    localparam BIT_CYCLES=(125000000+115200/2)/115200;
    reg [31:0] source=6,captured=5,processed=4,presented=3,refresh=30;
    reg mode=1,failed=0;reg [7:0] fault=0;
    wire tx;
    hdmi_camera_fisheye_status_uart #(.SAMPLE_CYCLES(16),
        .BUILD_ID(32'h11030001),.PROFILE_ID(64'hed59f83e3cfbc77b)) status(
        .clk(clk),.rst_n(rst_n),.source_accepted(captured),.processed(processed),.unique_presented(presented),
        .source_frames(source),.scan_refreshes(refresh),.last_process_cycles(32'd5000000),
        .cache_hits(32'd1),.cache_misses(32'd2),.queries(32'd3),
        .scan_good(32'd4),.scan_repeat(32'd5),.scan_blank(32'd6),
        .corrected_requested(mode),.status_valid(1'b1),.failed(failed),.fault(fault),.tx(tx));
    reg qvalid=0,qvs=0,qde=0;reg [23:0] qrgb=0;
    wire qoutvalid,qoutvs,qoutde;wire [23:0] qoutrgb;
    hdmi_camera_rgb565_quantizer quantizer(.clk(clk),.rst_n(rst_n),.in_valid(qvalid),
        .in_vs(qvs),.in_de(qde),.in_rgb(qrgb),.out_valid(qoutvalid),.out_vs(qoutvs),.out_de(qoutde),.out_rgb(qoutrgb));
    integer cycle=0,edges,decoded,i,j,value,byte_value,expected5,expected6;
    reg old_tx=1;reg [23:0] expected_rgb;
    always @(posedge clk)cycle<=cycle+1;
    always @(negedge clk)begin
        if(tx!==1'b0 && tx!==1'b1)$fatal(1,"unknown UART output");
        if(tx!=old_tx)begin $fdisplay(edges,"%0d %0d",cycle,tx);old_tx=tx;end
    end
    initial begin
        edges=$fopen("uart-edges.txt","w");decoded=$fopen("uart-decoded.txt","w");
        repeat(4)@(negedge clk);rst_n=1;
        // Change every counter and flags after the first atomic snapshot.
        repeat(40)@(negedge clk);
        source=32'hfffffff0;captured=32'hfffffff1;processed=32'hfffffff2;
        presented=32'hfffffff3;refresh=32'hfffffff4;mode=0;failed=1;fault=8'h77;
    end
    initial begin
        wait(rst_n);
        for(i=0;i<256;i=i+1)begin
            @(negedge clk);qvalid=1;qvs=(i%3==0);qde=(i%5==0);qrgb={i[7:0],i[7:0],i[7:0]};
            expected5=(i*31+127)/255;expected6=(i*63+127)/255;
            expected_rgb={expected5[4:0],expected5[4:2],expected6[5:0],expected6[5:4],expected5[4:0],expected5[4:2]};
            @(negedge clk);qvalid=0;qvs=0;qde=0;qrgb=0;
            @(negedge clk);
            if(qoutvalid!==1 || qoutvs!==(i%3==0) || qoutde!==(i%5==0) || qoutrgb!==expected_rgb)
                $fatal(1,"quantizer value/timing mismatch v=%0d got=%h expected=%h",i,qoutrgb,expected_rgb);
        end
        $display("QUANTIZER_ALL_256_VALUES_AND_MATCHED_TIMING_PASS");
    end
    initial begin
        wait(rst_n);
        for(value=0;value<96;value=value+1)begin
            @(negedge tx);repeat(BIT_CYCLES/2)@(posedge clk);#1;
            if(tx!==0)$fatal(1,"UART start bit");
            byte_value=0;
            for(j=0;j<8;j=j+1)begin
                repeat(BIT_CYCLES)@(posedge clk);#1;
                if(tx!==0 && tx!==1)$fatal(1,"UART unknown data");
                byte_value=byte_value|(tx<<j);
            end
            repeat(BIT_CYCLES)@(posedge clk);#1;
            if(tx!==1)$fatal(1,"UART stop bit");
            $fdisplay(decoded,"%02x",byte_value);
        end
        repeat(BIT_CYCLES)@(negedge clk);
        $fclose(edges);$fclose(decoded);
        $display("FISHEYE_STATUS_REAL_125MHZ_115200_8N1_PASS bytes=96");
        $finish;
    end
    initial begin repeat(1200000)@(posedge clk);$fatal(1,"timeout");end
endmodule
