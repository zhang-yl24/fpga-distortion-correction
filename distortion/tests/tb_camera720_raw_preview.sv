`timescale 1ns/1ps
// Full synthetic720 byte stream, true preview memory/bank handoff and HDMI scan.
module tb_camera720_raw_preview;
    reg cam_clk=0,pix_clk=0,rst_n=0,cam_ready=0,vsync=0,href=0;
    reg [7:0] data=0;
    always #10.417 cam_clk=~cam_clk;
    always #6.734 pix_clk=~pix_clk;
    wire hs,vs,de,display_valid;wire [7:0] r,g,b;
    camera720_raw_preview dut(.*);
    integer version=0,writes=0,published=0,scanned=0,max_write=0,max_read=0;
    integer bank_version[0:1],bank_writes[0:1];
    reg last_request=0,last_bank=1;integer old_x,old_y;
    integer prior_x=0,prior_y=0,prior_bank=1;reg prior_visible=0,prior_active=0;
    reg [15:0] expected_pixel;reg [23:0] expected_rgb;
    function automatic [15:0] pixel(input integer index,input integer ident);
        pixel=16'h4321^(index*53)^(ident*16'h1111);
    endfunction
    always @(posedge cam_clk) if(rst_n)begin
        if(dut.memory_write)begin
            if(dut.write_address>=14400 || dut.column>=1280 || dut.row>=720 ||
               dut.column%8 || dut.row%8)$fatal(1,"Preview storage/address bound");
            if(dut.write_address!==(dut.row/8)*160+dut.column/8)
                $fatal(1,"Preview decimation address/order");
            if(dut.pixel!==pixel(dut.row*1280+dut.column,version))
                $fatal(1,"Preview pixel byte order/sample");
            if(display_valid && dut.write_bank==dut.read_bank)
                $fatal(1,"Preview overwrote display bank");
            writes=writes+1;bank_writes[dut.write_bank]=bank_writes[dut.write_bank]+1;
            if(dut.write_address>max_write)max_write=dut.write_address;
        end
        #1;
        if(dut.request!=last_request)begin
            if(dut.write_address!=0)$fatal(1,"Publication not at fullframe boundary");
            bank_version[dut.held_bank]=version;published=published+1;
        end
        last_request=dut.request;
    end
    always @(posedge pix_clk)begin
        old_x=dut.x;old_y=dut.y;
        if(rst_n && dut.picture)begin
            if(dut.read_address>=14400)$fatal(1,"Preview read address exceeds stored frame");
            if(dut.read_address>max_read)max_read=dut.read_address;
        end
        #1;
        if(rst_n)begin
            if(dut.read_bank!=last_bank && (old_x!=0 || old_y!=0))
                $fatal(1,"Preview bank switch inside display frame");
            if(de!==prior_active)$fatal(1,"Preview active timing latency");
            if(prior_visible)begin
                expected_pixel=pixel(((prior_y-25)/8)*8*1280+((prior_x-260)/8)*8,
                                     bank_version[prior_bank]);
                expected_rgb={{expected_pixel[15:11],expected_pixel[15:13]},
                              {expected_pixel[10:5],expected_pixel[10:9]},
                              {expected_pixel[4:0],expected_pixel[4:2]}};
                if({r,g,b}!==expected_rgb)$fatal(1,"Preview scanned pixel mismatch x=%d y=%d bank=%d",prior_x,prior_y,prior_bank);
                scanned=scanned+1;
            end else if({r,g,b}!==24'b0)$fatal(1,"Preview black area not black");
        end
        prior_x=old_x;prior_y=old_y;prior_bank=last_bank;
        prior_active=rst_n && old_x>=260 && old_x<1540 && old_y>=25 && old_y<745;
        prior_visible=prior_active && display_valid;
        last_bank=dut.read_bank;
    end
    task pulse;
        begin @(negedge cam_clk);vsync=1;href=0;
            repeat(4)@(negedge cam_clk);vsync=0;repeat(4)@(negedge cam_clk);end
    endtask
    task image(input integer ident,input bit short_line);
        reg [15:0] word;
        begin
            version=ident;
            for(integer y=0;y<720;y=y+1)begin
                href=1;
                for(integer x=0;x<1280-((short_line && y==719)?1:0);x=x+1)begin
                    word=pixel(y*1280+x,ident);data=word[7:0];@(negedge cam_clk);
                    data=word[15:8];@(negedge cam_clk);
                end
                href=0;repeat(4)@(negedge cam_clk);
            end
        end
    endtask
    task check_bank(input integer bank,input integer ident);
        begin
            for(integer y=0;y<90;y=y+1)
                for(integer x=0;x<160;x=x+1)
                    if(dut.memory[bank*16384+y*160+x]!==pixel(y*8*1280+x*8,ident))
                        $fatal(1,"Preview entire memory differs bank=%d index=%d",bank,y*160+x);
            for(integer i=14400;i<16384;i=i+1)
                if(dut.memory[bank*16384+i]!==16'hxxxx)$fatal(1,"Preview wrote unused bank tail");
        end
    endtask
    initial begin
        bank_version[0]=0;bank_version[1]=0;bank_writes[0]=0;bank_writes[1]=0;
        repeat(8)@(negedge cam_clk);rst_n=1;cam_ready=1;
        repeat(8)@(negedge cam_clk);
        pulse();image(0,0);pulse();wait(display_valid);check_bank(0,0);
        repeat(8)@(negedge cam_clk);
        pulse();image(1,0);pulse();wait(dut.read_bank==1);check_bank(1,1);
        repeat(8)@(negedge cam_clk);
        pulse();image(2,0);pulse();wait(dut.read_bank==0);check_bank(0,2);
        repeat(8)@(negedge cam_clk);
        pulse();image(3,1);pulse();
        repeat(1650*750+10)@(negedge pix_clk);
        if(published!=3 || dut.read_bank!=0 || max_write!=14399 || max_read!=14399 || scanned<921600)
            $fatal(1,"Preview publication/coverage totals");
        $display("PASS current720 preview: full1280x720, stored160x90, max14399, three valid publications/bank reuse, malformed frame rejected, exact actual scanned RGB samples=%d",scanned);
        $finish;
    end
    initial begin #250000000;$fatal(1,"Preview timeout");end
endmodule
