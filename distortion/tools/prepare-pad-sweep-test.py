from pathlib import Path
root=Path(__file__).resolve().parents[1]
t=(root/'tests/tb_ov5640_init.sv').read_text()
t=t[:t.index('    task automatic configure_success;')]+'''
    task automatic configure_trial;
        begin
            register_read(16'h300a,8'h56);register_read(16'h300b,8'h40);
            repeat(263) register_write(1);
            register_read(16'h3808,registers[16'h3808]);register_read(16'h3809,registers[16'h3809]);
            register_read(16'h380a,registers[16'h380a]);register_read(16'h380b,registers[16'h380b]);
            register_read(16'h4300,registers[16'h4300]);register_read(16'h501f,registers[16'h501f]);
            register_read(16'h4740,registers[16'h4740]);
            register_write(1);
            register_read(16'h3808,registers[16'h3808]);register_read(16'h3809,registers[16'h3809]);
            register_read(16'h380a,registers[16'h380a]);register_read(16'h380b,registers[16'h380b]);
            register_read(16'h4300,registers[16'h4300]);register_read(16'h501f,registers[16'h501f]);
            register_read(16'h4740,registers[16'h4740]);
        end
    endtask
    reg [15:0] expected_masks[0:13];
    initial begin
        expected_masks[0]=16'h0000;expected_masks[1]=16'h1000;expected_masks[2]=16'h2000;
        expected_masks[3]=16'h4000;expected_masks[4]=16'h7000;expected_masks[5]=16'h7100;
        expected_masks[6]=16'h7200;expected_masks[7]=16'h7400;expected_masks[8]=16'h7800;
        expected_masks[9]=16'h7010;expected_masks[10]=16'h7020;expected_masks[11]=16'h7040;
        expected_masks[12]=16'h7080;expected_masks[13]=16'h7ff0;
        #100;reset_camera();
        for(integer n=0;n<14;n=n+1) begin
            configure_trial();wait(ready);#1;
            if(failed || commands_written!==264 || sensor_id!==16'h5640 || trial!==n ||
                registers[16'h3017]!==expected_masks[n][15:8] || registers[16'h3018]!==expected_masks[n][7:0])
                $fatal(1,"Trial %0d mask/reset/readback incorrect",n);
            @(negedge cam_rst_n);
        end
        wait(trial==0);#1;
        if(ready || failed) $fatal(1,"Prior trial status not cleared after wrap");
        // No slave response: bounded NACK failure then next independent trial.
        wait(failed);if(error_code!==8'h11) $fatal(1,"Expected ID address NACK");
        @(negedge cam_rst_n);wait(trial==1);#1;
        if(ready || failed) $fatal(1,"Failure not cleared at next reset");
        $display("PASS pad_sweep all 14 masks on real I2C RTL, reset per trial, failure progression and wrap");$finish;
    end
    initial begin #60000000;$fatal(1,"Sweep timeout");end
endmodule
'''
t=t.replace('module tb_ov5640_init;', 'module tb_ov5640_pad_sweep;')
t=t.replace('reg [15:0] trial_pad_mask=16\'h7ff0;', 'wire [3:0] trial;wire [15:0] pad_mask;')
t=t.replace('ov5640_init #(', 'ov5640_pad_sweep #(.GAP_CYCLES(10),.HOLD_CYCLES(1000),.WATCHDOG_CYCLES(200000),')
t=t.replace('dut.checkable_write', 'dut.camera.checkable_write')
(root/'tests/tb_ov5640_pad_sweep.sv').write_text(t)
runner=(root/'tools/run-camera-init-sim.ps1').read_text(encoding='utf-8-sig')
runner=runner.replace('camera_init_sim','pad_sweep_sim').replace("'rtl\\ov5640_init.v',", "'rtl\\ov5640_init.v','rtl\\ov5640_pad_sweep.v',")
runner=runner.replace('tb_ov5640_init','tb_ov5640_pad_sweep')
(root/'tools/run-pad-sweep-sim.ps1').write_text(runner,encoding='utf-8-sig')
