from pathlib import Path
root=Path(__file__).resolve().parents[1]
text=(root/'tests/tb_stripe_result_writer.sv').read_text().replace('tb_stripe_result_writer','tb_adaptive_result_writer').replace('ddr_stripe_result_writer #','ddr_adaptive_result_writer #').replace('stripe_writer_sim','adaptive_writer_sim')
text=text.replace('reg clk=0,rst_n=0,frame_valid=0,in_valid=0;', 'reg clk=0,rst_n=0,frame_valid=0,in_valid=0,frame_tiled=1;')
text=text.replace('.frame_base(28\'d1024),', '.frame_tiled(frame_tiled),.frame_base(28\'d1024),')
text=text.replace('reset_system();begin_frame();send_frame();check_frame();', 'frame_tiled=1;reset_system();begin_frame();frame_tiled=0;send_frame();check_frame();',1)
text=text.replace('reset_system();begin_frame();send_pixel(1);', 'frame_tiled=1;reset_system();begin_frame();send_pixel(1);')
text=text.replace('        $display("PASS stripe reorder:', '''        mode=0;frame_tiled=0;reset_system();begin_frame();frame_tiled=1;
        for(n=0;n<1536;n=n+1) send_pixel(n);
        check_frame();
        $display("PASS adaptive writer: locked raster/tile selection, ''')
(root/'tests/tb_adaptive_result_writer.sv').write_text(text,encoding='utf-8')
runner=(root/'tools/run-stripe-writer-sim.ps1').read_text().replace('stripe_writer_sim','adaptive_writer_sim').replace('ddr_stripe_result_writer.v','ddr_adaptive_result_writer.v').replace('tb_stripe_result_writer','tb_adaptive_result_writer').replace('PASS stripe reorder:','PASS adaptive writer:')
(root/'tools/run-adaptive-writer-sim.ps1').write_text(runner,encoding='utf-8')
print('Prepared raster/tile locked-mode, multi-burst and fault tests.')
