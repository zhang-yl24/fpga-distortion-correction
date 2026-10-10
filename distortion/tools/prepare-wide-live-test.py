from pathlib import Path
root=Path(__file__).resolve().parents[1]
s=(root/'tests/tb_ddr_live_video.sv').read_text().replace('module tb_ddr_live_video;', 'module tb_ddr_live_video_wide;')
replacements={
    '.WIDTH(16),.HEIGHT(32),.BANK_STRIDE(512)':'.WIDTH(64),.HEIGHT(192),.BANK_STRIDE(8192)',
    '.HT(48),.VT(48),.HS(4),.VS(2),.X0(6),.Y0(4),.AW(32),.AH(40)':'.HT(160),.VT(224),.HS(4),.VS(2),.X0(6),.Y0(4),.AW(128),.AH(208)',
    'memory[0:127]':'memory[0:2047]', 'awaddr>=768':'awaddr>=14336','araddr>=768':'araddr>=14336',
    'wbase/64':'wbase/1024','rbase/64':'rbase/1024',
    'row<32':'row<192','col<16-':'col<64-','row==31':'row==191','row*16+col':'row*64+col',
    'x-14':'x-38','y-8':'y-12','front_bank ? 64:0':'front_bank ? 1024:0',
    'py*16+px':'py*64+px','12*512':'12*12288','ticks<300000':'ticks<3000000',
    '#20000000':'#50000000',
    'PASS live DDR video:':'PASS wide live DDR video (768 beats per frame > 512 FIFO depth):'
}
for a,b in replacements.items():
    assert a in s,a
    s=s.replace(a,b)
(root/'tests/tb_ddr_live_video_wide.sv').write_text(s)
print('Prepared wide streaming stress: 64x192, 768 beats/frame exceed 512 FIFO depth, native pixel comparison and error/recovery phases.')
