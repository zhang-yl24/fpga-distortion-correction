`timescale 1ns/1ps
module tb_capacity_native_shape;
    parameter EXPECT_INDEX_BITS=6;
    pipeline_gamma_frame_engine_1080_geometry_bypass #(.WIDTH(1920),.HEIGHT(1080),
        .CACHE_PROFILE(2),.RASTER_DOUBLE_BUFFER(1)) dut(
        .clk(1'b0),.rst_n(1'b0),.frame_valid(1'b0),.gamma_enable(1'b0),.correction_enable(1'b1));
    initial begin
        #1;
        if(dut.core.INDEX_BITS!=EXPECT_INDEX_BITS ||
           dut.core.sampler.runtime_cache.cache.INDEX_BITS!=EXPECT_INDEX_BITS ||
           dut.core.sampler.runtime_cache.cache.LINES!=(1<<EXPECT_INDEX_BITS) ||
           dut.core.sampler.runtime_cache.cache.store.INDEX_BITS!=EXPECT_INDEX_BITS ||
           dut.core.sampler.runtime_cache.cache.QUERY_DEPTH!=256 ||
           dut.core.sampler.runtime_cache.cache.LOOKAHEAD!=256 ||
           dut.core.sampler.runtime_cache.cache.TAG_W!=25 ||
           dut.core.sampler.runtime_cache.cache.QID_W!=24 ||
           dut.core.sampler.runtime_cache.cache.BLOCK_W!=14 ||
           dut.core.sampler.runtime_cache.cache.REF_W!=9 ||
           dut.core.sampler.runtime_cache.cache.COMPACT_COORDS!=1 ||
           dut.core.sampler.runtime_cache.cache.AREA_PROFILE!=2 ||
           dut.core.sampler.runtime_cache.cache.CANDIDATE_KEY_PIPE!=2 ||
           dut.core.sampler.runtime_cache.cache.HEAD_PREDECODE!=1 ||
           dut.core.sampler.runtime_cache.cache.LOCAL_INFLIGHT_MASK!=1 ||
           dut.core.sampler.runtime_cache.cache.TOKEN_W!=(96+4*EXPECT_INDEX_BITS) ||
           $bits(dut.core.sampler.runtime_cache.cache.local_inflight_owned)!=(1<<EXPECT_INDEX_BITS) ||
           dut.core.sampler.runtime_cache.cache.GROUPS!=((1<<EXPECT_INDEX_BITS)/8) ||
           dut.core.sampler.runtime_cache.cache.registered_selection.MID_COUNT!=4 ||
           $bits(dut.core.sampler.runtime_cache.cache.registered_selection.root_key)!=(25+EXPECT_INDEX_BITS) ||
           dut.writer.overlap_raster.implementation.RAM_BUFFER!=1)
            $fatal(1,"wrong real native capacity profile/lease/pipeline/writer parameters");
        $display("PASS_CAPACITY_NATIVE_SHAPE INDEX%0d Q256 TAG25 QID24 REF9 BLOCK14 KEY2 HEAD1 MASK1 AREA2 COMPACT1 WRITER_RAM1",EXPECT_INDEX_BITS);
        $finish;
    end
endmodule
