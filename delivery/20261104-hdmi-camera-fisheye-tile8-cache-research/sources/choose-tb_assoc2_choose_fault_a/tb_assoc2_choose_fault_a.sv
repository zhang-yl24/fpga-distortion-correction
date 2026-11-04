`timescale 1ns/1ps
// Public-input-only CHECK/way1 fault boundary. No force or hierarchy writes.
module tb_assoc2_choose_fault_a;
    reg clk=0;always #4 clk=~clk;
    reg rst_n=0,frame_valid=0,in_valid=0;
    reg signed [23:0] in_x=0,in_y=0;
    reg [24:0] in_tag=0;
    wire frame_ready,in_ready,out_valid,failed,arvalid;
    wire [23:0] p00,p10,p01,p11;
    wire [7:0] fx,fy,fault;
    wire [24:0] out_tag;
    wire [27:0] araddr;
    wire [3:0] arlen;
    wire [31:0] hits,misses,completed_queries;
    reg arready=0,rvalid=0,rlast=0;
    reg [3:0] rid=0;
    reg [255:0] rdata=0;
    reg inject=0,injected=0;
    reg [9:0] prior_line;reg [15:0] prior_address;reg prior_hit;
    integer left=0,beat=0,start_pixel=0,received=0;
    integer file_no;
    ddr_neighbour_cache_scatter16_rowpipe #(.WIDTH(128),.HEIGHT(1080),.INDEX_BITS(10),.TAG_W(25),.TIMEOUT_BITS(12)) dut(
      .clk(clk),.rst_n(rst_n),.frame_valid(frame_valid),.frame_ready(frame_ready),.frame_base(28'd0),
      .in_valid(in_valid),.in_ready(in_ready),.in_x(in_x),.in_y(in_y),.in_tag(in_tag),
      .out_valid(out_valid),.out_ready(1'b1),.p00(p00),.p10(p10),.p01(p01),.p11(p11),.fx(fx),.fy(fy),.out_tag(out_tag),
      .araddr(araddr),.arlen(arlen),.arvalid(arvalid),.arready(arready),.rdata(rdata),.rvalid(rvalid),.rlast(rlast),.rid(rid),
      .failed(failed),.fault(fault),.hits(hits),.misses(misses),.completed_queries(completed_queries));
    function automatic [15:0] source(input integer p);source=(p*197+(p>>3)*29+16'h6351)&65535;endfunction
    function automatic [23:0] expand(input [15:0] p);expand={p[15:11],p[15:13],p[10:5],p[10:9],p[4:0],p[4:2]};endfunction
    always @(negedge clk)begin
        arready=rst_n&&left==0;
        rvalid=rst_n&&left>0;rlast=left==1;rid=0;
        for(integer n=0;n<16;n=n+1)rdata[n*16+:16]=source(start_pixel+beat*16+n);
        if(inject&&!injected&&dut.inner.state==11&&dut.inner.selected_hit&&dut.inner.selected_choose_way)begin
            prior_line=dut.inner.selected_line;prior_address=dut.inner.selected_pixel_address;prior_hit=dut.inner.selected_hit_q;
            rvalid=1;rlast=1;rid=0;rdata={256{1'b1}};injected=1;
        end
    end
    always @(posedge clk)begin
        if(!rst_n)begin left<=0;beat<=0;received<=0;end
        else begin
            if(arvalid&&arready)begin
                if(left!=0||arlen!=7)$fatal(1,"fault-boundary responder ownership");
                left<=8;beat<=0;start_pixel<=araddr*2;
            end
            if(left>0&&rvalid)begin left<=left-1;beat<=beat+1;end
            if(out_valid)begin
                if(out_tag==1)begin
                    if({p00,p10,p01,p11}!={expand(source(0)),expand(source(1)),expand(source(128)),expand(source(129))})
                        $fatal(1,"independent setup pixel oracle A");
                end else if(out_tag==2)begin
                    if({p00,p10,p01,p11}!={expand(source(65536)),expand(source(65537)),expand(source(65664)),expand(source(65665))})
                        $fatal(1,"independent setup pixel oracle B");
                end else $fatal(1,"faulted query unexpectedly produced output");
                received<=received+1;
            end
        end
    end
    task automatic send(input integer x,y,tag);
        begin @(negedge clk);in_x=x*256+13;in_y=y*256+37;in_tag=tag;in_valid=1;
            do @(posedge clk);while(!in_ready);
            @(negedge clk);in_valid=0;
        end
    endtask
    initial begin
        repeat(3)@(negedge clk);rst_n=1;frame_valid=1;
        do @(posedge clk);while(!frame_ready);
        @(negedge clk);frame_valid=0;
        send(0,0,1);wait(received==1&&dut.inner.frame_ready);
        send(0,512,2);wait(received==2&&dut.inner.frame_ready);
        if(!dut.inner.valid_lines[0]||!dut.inner.valid_lines[512]||dut.inner.tags[0]!=0||dut.inner.tags[512]!=512)
            $fatal(1,"setup did not install two distinct full tags in same set");
        // Upper row511 is cold, so this is a slow query. Its lower row512
        // reaches CHECK as a way1 hit after that unrelated first miss commits.
        inject=1;send(127,511,3);wait(failed);#1;
        if(!injected||fault!=4||prior_line!=0||dut.inner.selected_line!==prior_line||dut.inner.selected_pixel_address!==prior_address||dut.inner.selected_hit_q!==prior_hit||dut.inner.valid_lines[0]||!dut.inner.valid_lines[512]||dut.inner.tags[512]!=512)
            $fatal(1,"CHECK way1 fault invalidated old way or retained chosen line");
        repeat(20)begin @(posedge clk);#1;
            if(!failed||fault!=4||in_ready||frame_ready||out_valid||dut.inner.fill_write_valid||dut.inner.valid_lines[0])
                $fatal(1,"CHECK boundary failure was not sticky/quarantined");
        end
        file_no=$fopen("choose-way1-fault-summary.json","w");
        $fdisplay(file_no,"{\"Passed\":true,\"IndexBits\":10,\"NormalIndependentPixelOutputs\":2,\"UnownedRAtCHOOSE\":true,\"ChoiceNotCommitted\":true,\"RegisteredWay0Invalidated\":true,\"CandidateWay1Preserved\":true,\"StickyQuarantineCycles\":20,\"HierarchyForced\":false}");
        $fclose(file_no);$display("PASS ASSOC2 CHOOSE unowned R suppresses new choice");$finish;
    end
    initial begin #200000;$fatal(1,"CHECK way1 fault boundary timeout");end
endmodule
