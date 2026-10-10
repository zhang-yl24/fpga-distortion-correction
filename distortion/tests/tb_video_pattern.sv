`timescale 1ns/1ps
module tb_video_pattern #(parameter MODE_720P=0);
    reg clk=0; always #5 clk=~clk;
    reg rst_n=0; wire hs,vs,de; wire [7:0] r,g,b;
    video_pattern #(.MODE_720P(MODE_720P)) dut(.*);
    localparam HT=MODE_720P ? 1650:2200, VT=MODE_720P ? 750:1125;
    localparam WIDTH=MODE_720P ? 1280:1920, HEIGHT=MODE_720P ? 720:1080;
    localparam HS_WIDTH=MODE_720P ? 40:44;
    integer active_count=0, hs_count=0, vs_count=0;
    integer color_count[0:7];
    integer line_count=0;
    reg old_de=0;
    initial begin
        for(integer i=0;i<8;i=i+1) color_count[i]=0;
        repeat(4) @(negedge clk); rst_n=1;
        for(integer p=0;p<HT*VT;p=p+1) begin
            @(negedge clk);
            if(hs) hs_count++;
            if(vs) vs_count++;
            if(de && !old_de) line_count++;
            old_de=de;
            if(de) begin
                active_count++;
                case({r,g,b})
                    24'hffffff:color_count[0]++;
                    24'hffff00:color_count[1]++;
                    24'h00ffff:color_count[2]++;
                    24'h00ff00:color_count[3]++;
                    24'hff00ff:color_count[4]++;
                    24'hff0000:color_count[5]++;
                    24'h0000ff:color_count[6]++;
                    24'h000000:color_count[7]++;
                    default:$fatal(1,"Unexpected color");
                endcase
            end else if({r,g,b}!==0) $fatal(1,"Blanking nonzero");
        end
        if(active_count!=WIDTH*HEIGHT || line_count!=HEIGHT) $fatal(1,"Incorrect active rectangle");
        if(hs_count!=HS_WIDTH*VT || vs_count!=5*HT) $fatal(1,"Incorrect sync width");
        for(integer i=0;i<8;i=i+1) if(color_count[i]!=(WIDTH/8)*HEIGHT) $fatal(1,"Color bar width");
        $display("PASS video_pattern %0dx%0d active, sync widths, 8 aligned bars",WIDTH,HEIGHT);
        $finish;
    end
endmodule

module tb_video_720p;
    tb_video_pattern #(.MODE_720P(1)) test();
endmodule
