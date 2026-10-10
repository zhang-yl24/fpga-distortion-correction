"""Exercise isolated clock-table readback and rejection; no board changes."""
from pathlib import Path
root = Path(__file__).resolve().parents[1]
tb = (root / 'tests/tb_ov5640_init.sv').read_text()
tb = tb.replace('tb_ov5640_init', 'tb_ov5640_cadence_trial').replace('ov5640_init #(', 'ov5640_cadence_trial_init #(')
tb = tb.replace('bad_pad=0;', 'bad_pad=0, bad_pll=0;')
tb = tb.replace("bad_pad && {hi,lo}==16'h3018 ? 8'h00:value", "(bad_pad && {hi,lo}==16'h3018) || (bad_pll && {hi,lo}==16'h3035) ? 8'h00:value")
anchor = '            // Model one not-yet-effective value, followed by a bounded retry.'
check = '''            if(registers[16'h3035]!==8'h21 || registers[16'h3036]!==8'h60 ||
                registers[16'h3037]!==8'h13 || registers[16'h3108]!==8'h01 ||
                registers[16'h380c]!==8'h07 || registers[16'h380d]!==8'h90 ||
                registers[16'h380e]!==8'h04 || registers[16'h380f]!==8'h40 ||
                registers[16'h3a08]!==8'h00 || registers[16'h3a09]!==8'hf7 ||
                registers[16'h3a0a]!==8'h00 || registers[16'h3a0b]!==8'hcd ||
                registers[16'h3a0e]!==8'h04 || registers[16'h3a0d]!==8'h05)
                $fatal(1,"Wrong clock/exposure candidate or changed geometry");
'''
assert tb.count(anchor) == 1
tb = tb.replace(anchor, check + anchor)
anchor = '        $display("PASS ov5640_init VGA/RGB565/polarity; critical writes read back; wrong ID, unverified NACK and ACKed write mismatches rejected");$finish;'
replacement = '''        reset_camera();bad_pad=0;bad_pll=1;
        register_read(16'h300a,8'h56);register_read(16'h300b,8'h40);
        repeat(251) register_write(1);wait(failed);#1;
        if(ready || error_code!==8'h70 || failed_address!==16'h3035 || commands_written!=250 ||
            observed_value!==8'h00 || expected_value!==8'h21)
            $fatal(1,"System divider readback mismatch was not quarantined");
        $display("PASS camera cadence trial: complete table, preserved geometry, banding values and wrong PLL divider readback rejected; no physical cadence proof");$finish;'''
assert tb.count(anchor) == 1
tb = tb.replace(anchor, replacement).replace('#10000000', '#20000000')
(root / 'tests/tb_ov5640_cadence_trial.sv').write_text(tb)
runner = (root / 'tools/run-camera-init-sim.ps1').read_text()
runner = runner.replace('camera_init_sim', 'camera_cadence_sim').replace('tb_ov5640_init', 'tb_ov5640_cadence_trial')
runner = runner.replace('rtl\\ov5640_init.v', 'rtl\\experimental\\ov5640_cadence_trial_init.v')
(root / 'tools/run-camera-cadence-sim.ps1').write_text(runner)
print('Prepared isolated SCCB cadence test including wrong divider rejection.')
