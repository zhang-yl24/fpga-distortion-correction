`timescale 1ps/1ps
// TEST ONLY: simulated clocks, DDR UI, TX status. No physical/IP implementation.

// HEADER_BINDING {"Module": "bringup_pll", "Path": "board/bringup_pll.v", "HeaderSHA256": "5a9a80eeff31f8e199e0e142d2cdd97b362756a3142f22961423846aaf1f5012"}
module bringup_pll (
    
    output wire clkout0,
    
    input wire clkin1,
    
    output wire lock           
    );
reg test_lock=0;reg test_clk=0;integer phase=0,delay_ps;
initial begin #1733;forever begin phase=phase+2000000;delay_ps=phase/297;phase=phase%297;#(delay_ps)test_clk=~test_clk;end end
assign clkout0=test_clk;assign lock=test_lock;
endmodule

// HEADER_BINDING {"Module": "hdmi_tx_init", "Path": "board/hdmi_tx_init.v", "HeaderSHA256": "a4852dc2c861c1ee0bd98cd15e330a26f7d931edc322d9ae6482e9444eb001ba"}
module hdmi_tx_init(input clk, input rst_n, inout hd_scl, inout hd_sda,
    output reg ready, output reg [3:0] error);
reg test_ready=0;reg [3:0]test_error=0;
always @* begin ready=rst_n&&test_ready;error=rst_n?test_error:0;end
assign hd_scl=1'bz;assign hd_sda=1'bz;
endmodule
module GTP_INBUFGDS #(parameter IOSTANDARD="DEFAULT",TERM_DIFF="ON")(output O,input I,IB);
assign O=I;
endmodule

// HEADER_BINDING {"Module": "ddr3_test", "Path": "platform/video_base/ipcore/ddr3_test/ddr3_test.v", "HeaderSHA256": "0bc0f913caf04efb66cd7cc4cbdfa8c84ca4483660699e1663ccc47e78e3bf7e"}
module ddr3_test #(
 
   parameter MEM_ROW_WIDTH       = 15          ,
    
   parameter MEM_COLUMN_WIDTH    = 10          ,
   
   parameter MEM_BANK_WIDTH      = 3           ,
  
  parameter MEM_DQ_WIDTH         =  32         ,
  
  parameter MEM_DM_WIDTH         =  4         ,
  
  parameter MEM_DQS_WIDTH        =  4         ,
   
   parameter CTRL_ADDR_WIDTH     = MEM_ROW_WIDTH + MEM_COLUMN_WIDTH + MEM_BANK_WIDTH        
  )(                                                              
   input                              ref_clk                       ,    
   input                              resetn                        ,            
   output                             core_clk                      ,            
   output                             pll_lock                      ,    
   output                             phy_pll_lock                  ,
   output                             gpll_lock                     ,        
   output                             rst_gpll_lock                 ,            
   output                             ddrphy_cpd_lock               ,      
   output                             ddr_init_done                 ,            

   input  [CTRL_ADDR_WIDTH-1:0]       axi_awaddr                    ,
   input                              axi_awuser_ap                 ,
   input  [3:0]                       axi_awuser_id                 ,
   input  [3:0]                       axi_awlen                     ,
   output                             axi_awready                   ,
   input                              axi_awvalid                   ,

   input  [8*MEM_DQ_WIDTH-1:0]        axi_wdata                     ,
   input  [MEM_DQ_WIDTH-1:0]          axi_wstrb                     ,
   output                             axi_wready                    ,
   output [3:0]                       axi_wusero_id                 ,
   output                             axi_wusero_last               ,

   input  [CTRL_ADDR_WIDTH-1:0]       axi_araddr                    ,
   input                              axi_aruser_ap                 ,
   input  [3:0]                       axi_aruser_id                 ,
   input  [3:0]                       axi_arlen                     ,
   output                             axi_arready                   ,
   input                              axi_arvalid                   ,

   output [8*MEM_DQ_WIDTH-1:0]        axi_rdata                     ,
   output [3:0]                       axi_rid                       ,
   output                             axi_rlast                     ,
   output                             axi_rvalid                    ,

   input                              apb_clk                       ,
   input                              apb_rst_n                     ,
   input                              apb_sel                       ,
   input                              apb_enable                    ,
   input  [7:0]                       apb_addr                      ,
   input                              apb_write                     ,
   output                             apb_ready                     ,
   input  [15:0]                      apb_wdata                     ,
   output [15:0]                      apb_rdata                     ,


   output                             mem_cs_n                      ,

   output                             mem_rst_n                     ,                       
   output                             mem_ck                        ,
   output                             mem_ck_n                      ,
   output                             mem_cke                       ,
   output                             mem_ras_n                     ,
   output                             mem_cas_n                     ,
   output                             mem_we_n                      , 
   output                             mem_odt                       ,
   output [MEM_ROW_WIDTH-1:0]         mem_a                         ,   
   output [MEM_BANK_WIDTH-1:0]        mem_ba                        ,   
   inout  [MEM_DQS_WIDTH-1:0]         mem_dqs                       ,
   inout  [MEM_DQS_WIDTH-1:0]         mem_dqs_n                     ,
   inout  [MEM_DQ_WIDTH-1:0]          mem_dq                        ,
   output [MEM_DM_WIDTH-1:0]          mem_dm                        , 

   //debug
   input                              dbg_gate_start                ,
   input                              dbg_cpd_start                 ,
   input                              dbg_ddrphy_rst_n              ,
   input                              dbg_gpll_scan_rst             ,

   input                              samp_position_dyn_adj         ,
   input  [8*MEM_DQS_WIDTH-1:0]       init_samp_position_even       ,
   input  [8*MEM_DQS_WIDTH-1:0]       init_samp_position_odd        ,

   input                              wrcal_position_dyn_adj        ,
   input  [8*MEM_DQS_WIDTH-1:0]       init_wrcal_position           ,
 
   input                              force_read_clk_ctrl           ,
   input  [4*MEM_DQS_WIDTH-1:0]       init_slip_step                ,  
   input  [3*MEM_DQS_WIDTH-1:0]       init_read_clk_ctrl            ,

   output [33:0]                      debug_calib_ctrl              ,
   output [17*MEM_DQS_WIDTH -1:0]     dbg_slice_status              ,
   output [22*MEM_DQS_WIDTH -1:0]     dbg_slice_state               ,
   output [69*MEM_DQS_WIDTH -1:0]     debug_data                    ,
   output [1:0]                       dbg_dll_upd_state             ,
   output [8:0]                       debug_gpll_dps_phase          ,
   
   output [2:0]                       dbg_rst_dps_state             ,
   output [5:0]                       dbg_tran_err_rst_cnt          ,
   output                             dbg_ddrphy_init_fail          , 
   
   input                              debug_cpd_offset_adj          ,
   input                              debug_cpd_offset_dir          ,
   input  [9:0]                       debug_cpd_offset              ,  
   output [9:0]                       debug_dps_cnt_dir0            , 
   output [9:0]                       debug_dps_cnt_dir1            ,

   input                              ck_dly_en                     ,
   input  [7:0]                       init_ck_dly_step              ,
   output [7:0]                       ck_dly_set_bin                ,
  
   output                             align_error                   ,
   output [3:0]                       debug_rst_state               ,
   output [3:0]                       debug_cpd_state               
);

// Small-test DDR UI only: four logical32x16 banks,4B addresses,no B channel.
localparam FB=32,STRIDE=1048576,FU=256;
reg test_pll_lock=0,test_init_done=0,hold_aw=0,hold_w=0,hold_ar=0;
reg test_clk=0;initial begin #571;forever #4000 test_clk=~test_clk;end
assign core_clk=resetn?test_clk:1'b0;
assign pll_lock=test_pll_lock;assign phy_pll_lock=test_pll_lock;
assign gpll_lock=test_pll_lock;assign rst_gpll_lock=test_pll_lock;assign ddrphy_cpd_lock=test_pll_lock;
assign ddr_init_done=test_init_done;
reg awready=0,wready=0,arready=0,rv=0,rl=0;reg[255:0]rd=0;
assign axi_awready=awready;assign axi_wready=wready;assign axi_arready=arready;
assign axi_rvalid=rv;assign axi_rlast=rl;assign axi_rdata=rd;assign axi_rid=0;
assign axi_wusero_id=0;assign axi_wusero_last=wleft==1;
reg[255:0]memory[0:4*FB-1];integer ticks=0,wleft=0,windex=0,rleft=0,rindex=0;
integer wbank=0,rbank=0,bank,off;
integer aw_stalls=0,w_stalls=0,ar_stalls=0,source_writes=0,result_writes=0,read_beats=0;
reg heldaw=0,heldar=0,heldw=0;reg[27:0]save_aw=0,save_ar=0;reg[3:0]save_awlen=0,save_arlen=0;reg[255:0]save_w=0;
always @(negedge core_clk)begin
 ticks=ticks+1;
 awready=resetn&&!hold_aw&&wleft==0&&ticks%9>=3;
 wready=resetn&&!hold_w&&wleft!=0&&ticks%6!=0;
 arready=resetn&&!hold_ar&&rleft==0&&ticks%7>=2;
 rv=resetn&&rleft!=0&&ticks%5!=0;rl=rleft==1;if(rv)rd=memory[rindex];
end
always @(posedge core_clk or negedge resetn)begin
 if(!resetn)begin wleft<=0;rleft<=0;heldaw<=0;heldar<=0;heldw<=0;end
 else begin
  if(heldaw&&(!axi_awvalid||axi_awaddr!==save_aw||axi_awlen!==save_awlen))$fatal(1,"physical modeled AW withdrawn while stalled");
  if(heldar&&(!axi_arvalid||axi_araddr!==save_ar||axi_arlen!==save_arlen))$fatal(1,"physical modeled AR withdrawn while stalled");
  if(heldw&&axi_wdata!==save_w)$fatal(1,"physical modeled W changed while stalled");
  heldaw<=axi_awvalid&&!awready;save_aw<=axi_awaddr;save_awlen<=axi_awlen;
  heldar<=axi_arvalid&&!arready;save_ar<=axi_araddr;save_arlen<=axi_arlen;
  heldw<=wleft!=0&&!wready;save_w<=axi_wdata;
  if(axi_awvalid&&!awready)aw_stalls=aw_stalls+1;
  if(wleft!=0&&!wready)w_stalls=w_stalls+1;
  if(axi_arvalid&&!arready)ar_stalls=ar_stalls+1;
  if(axi_awvalid&&awready)begin
   bank=axi_awaddr/STRIDE;off=axi_awaddr%STRIDE;
   if(wleft!=0||axi_awlen!=15||bank>3||off%128||off+128>FU)$fatal(1,"AW layout overlap");
   wbank<=bank;wleft<=16;windex<=bank*FB+(off>>3);
  end
  if(wready)begin
   if(wleft==0||axi_wstrb!==32'hffffffff)$fatal(1,"W strobe/owner");
   memory[windex]<=axi_wdata;windex<=windex+1;wleft<=wleft-1;
   if(wbank<2)source_writes=source_writes+1;else result_writes=result_writes+1;
  end
  if(axi_arvalid&&arready)begin
   bank=axi_araddr/STRIDE;off=axi_araddr%STRIDE;
   if(rleft!=0||bank>3||off%8||off+(axi_arlen+1)*8>FU)$fatal(1,"AR layout overlap");
   rbank<=bank;rleft<=axi_arlen+1;rindex<=bank*FB+(off>>3);
  end
  if(rv)begin rleft<=rleft-1;rindex<=rindex+1;read_beats=read_beats+1;end
  if(rleft!=0&&wleft!=0&&rbank==wbank)$fatal(1,"model R/W own same bank");
 end
end
assign apb_ready=0;assign apb_rdata=0;
assign mem_rst_n=resetn;assign mem_ck=0;assign mem_ck_n=0;assign mem_cke=0;assign mem_cs_n=0;
assign mem_ras_n=0;assign mem_cas_n=0;assign mem_we_n=0;assign mem_odt=0;assign mem_a=0;assign mem_ba=0;assign mem_dm=0;
assign mem_dqs='z;assign mem_dqs_n='z;assign mem_dq='z;
assign debug_calib_ctrl=0;assign dbg_slice_status=0;assign dbg_slice_state=0;assign debug_data=0;
assign dbg_dll_upd_state=0;assign debug_gpll_dps_phase=0;assign dbg_rst_dps_state=0;assign dbg_tran_err_rst_cnt=0;
assign dbg_ddrphy_init_fail=0;assign debug_dps_cnt_dir0=0;assign debug_dps_cnt_dir1=0;
assign ck_dly_set_bin=0;assign align_error=0;assign debug_rst_state=0;assign debug_cpd_state=0;
endmodule
