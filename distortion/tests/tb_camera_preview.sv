`timescale 1ns/1ps
module tb_camera_preview;
    reg cam_clk=0,pix_clk=0;
    always #7 cam_clk=~cam_clk;always #5 pix_clk=~pix_clk;
    reg rst_n=0,cam_ready=0,vsync=0,href=0;reg [7:0] data=0;
    wire hs,vs,de,display_valid;wire [7:0] r,g,b;
    camera_preview #(.SRC_W(8),.SRC_H(8),.HT(24),.VT(16),.HS(2),.VS(2),
        .X0(4),.Y0(4),.AW(12),.AH(8)) dut(.*);
    integer white=0,red=0,green=0;
    reg last_bank=1;integer old_x,old_y;
    always @(posedge pix_clk) begin
        old_x=dut.x;old_y=dut.y;
        #1;
        if(rst_n) begin
            if(dut.read_bank!=last_bank && (old_x!=0 || old_y!=0))
                $fatal(1,"Display bank changed inside a frame");
            if(de && {r,g,b}===24'hffffff) white=white+1;
            if(de && {r,g,b}===24'hff0000) red=red+1;
            if(de && {r,g,b}===24'h00ff00) green=green+1;
        end
        last_bank=dut.read_bank;
    end
    always @(posedge cam_clk) begin
        #1;if(rst_n && dut.writing && display_valid && dut.write_bank==dut.read_bank)
            $fatal(1,"Writer overwrites displayed bank");
    end
    task automatic frame_pulse;
        begin @(negedge cam_clk);vsync=1;href=0;
            repeat(3) @(negedge cam_clk);vsync=0;repeat(3) @(negedge cam_clk);end
    endtask
    task automatic send_image(input [15:0] color,input bit short_line);
        begin
            for(integer y=0;y<8;y=y+1) begin
                href=1;
                for(integer x=0;x<(short_line && y==0 ? 7:8);x=x+1) begin
                    data=color[7:0];@(negedge cam_clk);
                    data=color[15:8];@(negedge cam_clk);
                end
                href=0;repeat(4) @(negedge cam_clk);
            end
        end
    endtask
    initial begin
        repeat(5) @(negedge cam_clk);rst_n=1;cam_ready=1;
        repeat(8) @(negedge cam_clk);
        frame_pulse();send_image(16'hffff,0);frame_pulse();
        wait(display_valid);wait(white>=8);
        if(dut.read_bank!==0 || dut.memory[0]!==16'hffff || dut.memory[3]!==16'hffff)
            $fatal(1,"First downsampled frame incorrect");
        repeat(8) @(negedge cam_clk);
        frame_pulse();send_image(16'hf800,0);frame_pulse();
        wait(dut.read_bank==1);wait(red>=8);
        if(dut.memory[32768]!==16'hf800 || dut.memory[32771]!==16'hf800)
            $fatal(1,"RGB565 low-byte-first or second bank incorrect");
        repeat(8) @(negedge cam_clk);
        frame_pulse();send_image(16'h07e0,1);frame_pulse();
        repeat(800) @(negedge pix_clk);
        if(dut.read_bank!==1 || green!=0) $fatal(1,"Malformed frame published");
        $display("PASS camera_preview async bank handoff at display boundary, no read-bank overwrite, low-byte-first white/red, downsample and short-line rejection");$finish;
    end
    initial begin #1000000;$fatal(1,"Preview timeout");end
endmodule
