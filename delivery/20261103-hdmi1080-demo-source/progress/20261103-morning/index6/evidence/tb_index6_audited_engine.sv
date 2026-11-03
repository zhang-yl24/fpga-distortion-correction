`timescale 1ns/1ps
// Passive audit only. Original complete-engine bench, source, clocks, valid,
// ready, DDR responses, delays and assertions are unchanged.
module tb_index6_audited_engine;
  tb_native_correction_engine #(.CACHE_PROFILE(2),.FRAMES(1),.TRACE_WRITES(0),.PILOT_PIXELS(0)) test();
  localparam N=2073600;
  `define RC test.dut.core.sampler.runtime_cache.cache
  reg [47:0] audit_coords[0:N-1];
  integer fd,bytes_read;
  initial begin
    fd=$fopen("coords.bin","rb");if(!fd)$fatal(1,"raw cache audit coordinate file missing");
    bytes_read=$fread(audit_coords,fd,0,N);$fclose(fd);
    if(bytes_read!=6*N || audit_coords[0]!==48'hffebaefff525 || audit_coords[N-1]!==48'h07935b04430c)
      $fatal(1,"raw audit coordinate size/endian mismatch");
    $display("INDEX6_RAW_AUDIT_FIXTURE queries=%0d bytes=%0d",N,bytes_read);$fflush();
    #1;
    if(test.dut.core.INDEX_BITS!=6 || `RC.INDEX_BITS!=6 || `RC.LINES!=64 || `RC.store.INDEX_BITS!=6 ||
       `RC.QUERY_DEPTH!=256 || `RC.LOOKAHEAD!=256 || `RC.TAG_W!=25 || `RC.QID_W!=24 || `RC.REF_W!=9 || `RC.BLOCK_W!=14 ||
       `RC.COMPACT_COORDS!=1 || `RC.AREA_PROFILE!=2 || `RC.CANDIDATE_KEY_PIPE!=2 || `RC.HEAD_PREDECODE!=1 || `RC.LOCAL_INFLIGHT_MASK!=1 ||
       `RC.TOKEN_W!=120 || `RC.LEASE_W!=32 || `RC.STORE_TAG_W!=81 || `RC.KEY_W!=31 || `RC.HEAD_META_W!=57 ||
       $bits(`RC.local_inflight_owned)!=64 || `RC.GROUPS!=8 || `RC.registered_selection.MID_COUNT!=4 ||
       test.dut.writer.overlap_raster.implementation.RAM_BUFFER!=1)
      $fatal(1,"actual engine INDEX6/HEAD1/MASK1/AREA2/KEY2/writerRAM1 shape mismatch");
    $display("INDEX6_ENGINE_PROFILE INDEX6 LINES64 Q256 TAG25 QID24 REF9 BLOCK14 KEY2 HEAD1 MASK1 AREA2 COMPACT1 WRITER_RAM1 TOKEN120 LEASE32 STORE_TAG81 KEY_W31 HEAD_META57");$fflush();
  end
  function automatic [15:0] source_pixel(input integer absolute_pixel);
    reg [31:0] z;begin z=absolute_pixel*32'd109+32'h529b;z=z^(absolute_pixel>>3)^((absolute_pixel>>10)*32'h1f2d);source_pixel=z[15:0];end
  endfunction
  function automatic [23:0] expand_pixel(input [15:0] p);
    expand_pixel={p[15:11],p[15:13],p[10:5],p[10:9],p[4:0],p[4:2]};
  endfunction
  function automatic [23:0] neighbour(input integer xq,yq,dx,dy);
    integer x,y;begin x=(xq>>>8)+dx;y=(yq>>>8)+dy;
      if(x<0||x>=1920||y<0||y>=1080)neighbour=0;else neighbour=expand_pixel(source_pixel(y*1920+x));end
  endfunction
  function automatic mask_for(input integer xq,yq);
    mask_for=xq<=-256||yq<=-256||xq>=1920*256||yq>=1080*256;
  endfunction
  function automatic integer ref_count(input integer xq,yq);
    integer x,y,j;begin x=xq>>>8;y=yq>>>8;ref_count=0;for(j=0;j<4;j=j+1)
      if(x+j%2>=0&&x+j%2<1920&&y+j/2>=0&&y+j/2<1080)ref_count=ref_count+1;end
  endfunction
  integer admitted=0,retired=0,expected_refs=0,input_stalls=0,output_stalls=0,generation_stalls=0;
  integer fill_starts=0,fill_completions=0,max_fifo_total=0,oracle_x,oracle_y,audit_csv;
  reg input_held=0,output_held=0;reg [72:0] saved_input;reg [136:0] saved_output;
  wire [72:0] input_tuple={`RC.in_tag,`RC.in_x,`RC.in_y};
  wire [136:0] output_tuple={test.dut.core.sampler.sample_tag,test.dut.core.sampler.fx,test.dut.core.sampler.fy,
                            test.dut.core.sampler.p00,test.dut.core.sampler.p10,test.dut.core.sampler.p01,test.dut.core.sampler.p11};
  always @(posedge test.clk)begin
    if(!test.rst_n)begin admitted=0;retired=0;expected_refs=0;input_held=0;output_held=0;end
    else begin
      if(input_held&&(!`RC.in_valid||input_tuple!==saved_input))$fatal(1,"raw cache input tuple moved under stall");
      if(output_held&&(!test.dut.core.sampler.sample_valid||output_tuple!==saved_output))$fatal(1,"raw cache output tuple moved under stall");
      input_held=`RC.in_valid&&!`RC.in_ready;saved_input=input_tuple;
      output_held=test.dut.core.sampler.sample_valid&&!test.dut.core.sampler.sample_ready;saved_output=output_tuple;
      if(input_held)input_stalls=input_stalls+1;if(output_held)output_stalls=output_stalls+1;
      if(`RC.generation_blocked)generation_stalls=generation_stalls+1;
      if(`RC.query_fifo.total>max_fifo_total)max_fifo_total=`RC.query_fifo.total;
      if(`RC.fill_accept)begin
        if(`RC.active_valid[`RC.job_line]&&`RC.active_refs[`RC.job_line]!=0)$fatal(1,"fullstream victim before lease drain");
        fill_starts=fill_starts+1;
      end
      if(`RC.store.scatter_write&&`RC.store.scatter_word==31)fill_completions=fill_completions+1;
      if(`RC.in_valid&&`RC.in_ready)begin
        if(admitted>=N)$fatal(1,"raw cache too many admitted queries");
        oracle_x=$signed(audit_coords[admitted][47:24]);oracle_y=$signed(audit_coords[admitted][23:0]);
        if(`RC.in_x!==audit_coords[admitted][47:24]||`RC.in_y!==audit_coords[admitted][23:0]||
           `RC.in_tag!=={mask_for(oracle_x,oracle_y),admitted[23:0]})$fatal(1,"raw cache coordinate/tag admission mismatch index%0d",admitted);
        expected_refs=expected_refs+ref_count(oracle_x,oracle_y);admitted=admitted+1;
      end
      if(test.dut.core.sampler.sample_valid&&test.dut.core.sampler.sample_ready)begin
        if(retired>=admitted||retired>=N)$fatal(1,"raw cache output without accepted query");
        oracle_x=$signed(audit_coords[retired][47:24]);oracle_y=$signed(audit_coords[retired][23:0]);
        if(test.dut.core.sampler.sample_tag!=={mask_for(oracle_x,oracle_y),retired[23:0]}||
           test.dut.core.sampler.fx!==audit_coords[retired][31:24]||test.dut.core.sampler.fy!==audit_coords[retired][7:0]||
           test.dut.core.sampler.p00!==neighbour(oracle_x,oracle_y,0,0)||test.dut.core.sampler.p10!==neighbour(oracle_x,oracle_y,1,0)||
           test.dut.core.sampler.p01!==neighbour(oracle_x,oracle_y,0,1)||test.dut.core.sampler.p11!==neighbour(oracle_x,oracle_y,1,1))
          $fatal(1,"raw cache independent full tuple mismatch index%0d x%0d y%0d",retired,oracle_x,oracle_y);
        retired=retired+1;
      end
      #2;
      if(test.done)begin
        if(admitted!=N||retired!=N||expected_refs!=7945462||fill_starts!=test.ar_bursts||fill_completions!=test.ar_bursts||
           `RC.admitted_count!=N||`RC.retired_count!=N||`RC.issued_count!=N)
          $fatal(1,"raw cache final query/reference/fill conservation");
        audit_csv=$fopen("raw_cache_audit.csv","w");if(!audit_csv)$fatal(1,"raw cache audit CSV open");
        $fdisplay(audit_csv,"admitted,retired,neighbour_pixels_checked,expected_inbounds_refs,input_stalls,output_stalls,generation_stalls,fill_starts,fill_completions,max_fifo_total");
        $fdisplay(audit_csv,"%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d,%0d",admitted,retired,retired*4,expected_refs,input_stalls,output_stalls,generation_stalls,fill_starts,fill_completions,max_fifo_total);$fclose(audit_csv);
        $display("PASS_INDEX6_RAW_CACHE_AUDIT admitted=%0d retired=%0d neighbour_pixels=%0d refs=%0d generation_stalls=%0d fills=%0d",admitted,retired,retired*4,expected_refs,generation_stalls,fill_completions);$fflush();
      end
    end
  end
  `undef RC
endmodule
