`timescale 1ns/1ps
module tb_hierarchy #(parameter PACK=1);
board1080_top #(.AF_AA_ORDINAL_TAG_PACK(PACK)) dut();
`define CACHE dut.system.bank_core.engine.core.sampler.runtime_cache.cache
initial begin
 #1;
 if(dut.AF_AA_ORDINAL_TAG_PACK!=PACK || dut.system.AF_AA_ORDINAL_TAG_PACK!=PACK || dut.system.bank_core.AF_AA_ORDINAL_TAG_PACK!=PACK || dut.system.bank_core.engine.AF_AA_ORDINAL_TAG_PACK!=PACK || dut.system.bank_core.engine.core.AF_AA_ORDINAL_TAG_PACK!=PACK || dut.system.bank_core.engine.core.sampler.AF_AA_ORDINAL_TAG_PACK!=PACK || `CACHE.AF_AA_ORDINAL_TAG_PACK!=PACK)$fatal(1,"propagation");
 if(`CACHE.TOKEN_W!=(PACK ? 54:63) || `CACHE.TAG_W!=25 || `CACHE.QUERY_DEPTH!=4096 || `CACHE.HEAD_PREDECODE!=0 || `CACHE.CACHE_ROW_STRIDE!=2 || `CACHE.INDEX_BITS!=7)$fatal(1,"actual AA cache binding");
 if(dut.R34_ENABLE_GAMMA!=0 || dut.system.RATIONAL_BROWN_PROFILE!=1 || dut.system.MACRO_TILE_HEIGHT!=32 || dut.system.TILE8_GROUP_WIDTH!=64)$fatal(1,"actual AA mode binding");
 $display("PASS_HIERARCHY pack=%0d token=%0d depth=%0d",PACK,`CACHE.TOKEN_W,`CACHE.QUERY_DEPTH);$finish;
end
endmodule
