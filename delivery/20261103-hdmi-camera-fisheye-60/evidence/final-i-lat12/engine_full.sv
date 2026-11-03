`timescale 1ns/1ps
module tb_fisheye60;
    parameter TW=8,READ_LATENCY=12,PRESSURE=1,CORRECTED=1;
    localparam W=1920,H=1080,N=W*H,DEST=28'h0200000;
    reg clk=0;always #4 clk=~clk;
    reg rst_n=0,fv=0;wire fr,done,failed;wire[7:0]fault;
    wire[27:0]araddr,awaddr,base;wire[3:0]arlen,awlen;wire arvalid,awvalid;
    wire[255:0]wdata;wire[31:0]wstrb,identity,crc,hits,misses,queries;
    integer cycles=0,start_cycle=0,i,j,fd,stats,reads=0,writes=0,lane0_cycles=0,lane1_cycles=0;
    reg read_busy=0,write_busy=0;integer read_delay=0,ri=0,rn=0,wi=0,wn=0;
    reg[27:0]ra=0,wa=0;reg[255:0]rdata;
    wire arready=!read_busy && (!PRESSURE || cycles%11!=0);
    wire awready=!write_busy && (!PRESSURE || cycles%7!=0);
    // Pressure models finite shared UI service, refresh bubbles and competing
    // capture/display slots. It is an explicit stress envelope, not the DDR IP.
    wire reserved=PRESSURE && (cycles%16<3 || cycles%997<8);
    wire rvalid=read_busy && read_delay==0 && !reserved && (!PRESSURE || cycles%7!=0);
    wire rlast=ri==rn;
    wire wready=write_busy && !reserved && (!PRESSURE || (!rvalid && cycles%5!=0));
    wire wlast=wi==wn;
    reg[15:0] pixels[0:N-1];reg seen[0:N-1];integer at;
    function[15:0] source_pixel;
        input integer index;
        begin source_pixel=((index*13)^(index>>3)^16'h5a31)&16'hffff;end
    endfunction
    always @*begin
        rdata=0;
        for(integer k=0;k<16;k=k+1)rdata[k*16+:16]=source_pixel(ra*2+ri*16+k);
    end
    hdmi_camera_fisheye_engine #(.TILE_W(TW)) dut(
        .clk(clk),.rst_n(rst_n),.frame_valid(fv),.frame_ready(fr),.cfg_corrected(CORRECTED!=0),
        .source_base(28'd0),.output_base(DEST),.frame_id(32'd123),
        .araddr(araddr),.arlen(arlen),.arvalid(arvalid),.arready(arready),
        .rdata(rdata),.rvalid(rvalid),.rlast(rlast),.rid(4'd0),
        .awaddr(awaddr),.awlen(awlen),.awvalid(awvalid),.awready(awready),
        .wdata(wdata),.wstrb(wstrb),.wready(wready),.wlast(wlast),
        .done(done),.failed(failed),.fault(fault),.completed_base(base),.completed_id(identity),.completed_crc(crc),
        .hits(hits),.misses(misses),.completed_queries(queries));
    always @(posedge clk)begin
        cycles<=cycles+1;
        if(rst_n)begin
            if(dut.done_lane[0])lane0_cycles=cycles-start_cycle;
            if(dut.done_lane[1])lane1_cycles=cycles-start_cycle;
            if(arvalid&&arready)begin
                if(araddr*2+(arlen+1)*16>N || araddr[5:0]!=0 || arlen!=7)$fatal(1,"Read extent/alignment");
                read_busy<=1;ra<=araddr;rn<=arlen;ri<=0;read_delay<=READ_LATENCY;reads<=reads+1;
            end else if(read_busy&&read_delay>0)read_delay<=read_delay-1;
            if(rvalid)begin if(ri==rn)read_busy<=0;else ri<=ri+1;end
            if(awvalid&&awready)begin
                if(awaddr<DEST || (awaddr-DEST)*2+(awlen+1)*16>N || awaddr[6:0]!=0 || awlen!=15)$fatal(1,"Write extent/alignment");
                write_busy<=1;wa<=awaddr;wn<=awlen;wi<=0;writes<=writes+1;
            end
            if(wready)begin
                if(wstrb!==32'hffffffff)$fatal(1,"Write strobes");
                for(j=0;j<16;j=j+1)begin
                    at=(wa-DEST)*2+wi*16+j;
                    if(seen[at])$fatal(1,"Duplicate output %0d",at);
                    seen[at]=1;pixels[at]=wdata[j*16+:16];
                end
                if(wi==wn)write_busy<=0;else wi<=wi+1;
            end
            if(failed)$fatal(1,"Engine fault %h cycle %0d",fault,cycles-start_cycle);
            if(cycles>50000000)$fatal(1,"Timeout");
        end
    end
    initial begin
        for(i=0;i<N;i=i+1)seen[i]=0;
        repeat(10)@(negedge clk);rst_n=1;
        wait(fr);@(negedge clk);fv=1;start_cycle=cycles;
        @(negedge clk);fv=0;
        wait(done);@(negedge clk);
        if(base!=DEST || identity!=123 || queries!=N || read_busy || write_busy)$fatal(1,"Completion identity/drain");
        fd=$fopen("output.bin","wb");
        for(i=0;i<N;i=i+1)begin
            if(!seen[i])$fatal(1,"Missing output %0d",i);
            $fwrite(fd,"%c%c",pixels[i][7:0],pixels[i][15:8]);
        end
        $fclose(fd);
        stats=$fopen("engine-result.json","w");
        $fwrite(stats,"{\"cycles\":%0d,\"crc\":%0d,\"pixels\":%0d,\"reads\":%0d,\"writes\":%0d,\"hits\":%0d,\"misses\":%0d,\"tile_width\":%0d,\"read_latency\":%0d,\"pressure\":%0d,\"top_rows\":%0d,\"lane0_cycles\":%0d,\"lane1_cycles\":%0d}\n",cycles-start_cycle,crc,N,reads,writes,hits,misses,TW,READ_LATENCY,PRESSURE,dut.TOP_ROWS,lane0_cycles,lane1_cycles);
        $fclose(stats);
        $display("PASS FULL FISHEYE60 pixels=%0d cycles=%0d crc=%h",N,cycles-start_cycle,crc);$finish;
    end
endmodule
