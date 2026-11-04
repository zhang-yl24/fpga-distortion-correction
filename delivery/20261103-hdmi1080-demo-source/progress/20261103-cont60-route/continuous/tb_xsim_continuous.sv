`timescale 1ps/1ps
module tb_xsim_continuous;
 tb_native_continuous #(.CACHE_PROFILE(2),.PIX_HZ(148500000),.FRAMES(3),.TRACE_PIXELS(0),.CHECKER_TEST(0)) test();
 `define EC test.dut.bank_core.engine
 `define RC test.dut.bank_core.engine.core.sampler.runtime_cache.cache
 initial begin
  #1;
  if(`EC.core.INDEX_BITS!=6 || `RC.INDEX_BITS!=6 || `RC.LINES!=64 || `RC.store.INDEX_BITS!=6 ||
     `RC.QUERY_DEPTH!=256 || `RC.LOOKAHEAD!=256 || `RC.TAG_W!=25 || `RC.QID_W!=24 || `RC.REF_W!=9 ||
     `RC.COMPACT_COORDS!=1 || `RC.AREA_PROFILE!=2 || `RC.CANDIDATE_KEY_PIPE!=2 || `RC.HEAD_PREDECODE!=1 || `RC.LOCAL_INFLIGHT_MASK!=1 ||
     `RC.TOKEN_W!=120 || `RC.LEASE_W!=32 || `RC.STORE_TAG_W!=81 ||
     `EC.writer.overlap_raster.implementation.RAM_BUFFER!=1)
    $fatal(1,"continuous INDEX6 exact profile mismatch");
  $display("CONT_INDEX6_PROFILE INDEX6 Q256 HEAD1 MASK1 AREA2 KEY2 COMPACT1 WRITER_RAM1 SOURCE_NOT_PRELOADED THREE_FRAMES_148500000HZ");$fflush();
 end
 `undef EC
 `undef RC
endmodule
