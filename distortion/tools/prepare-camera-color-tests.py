"""Prepare the isolated sensor-pattern SCCB/readback regression."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
text=(ROOT/'tests/tb_ov5640_cadence_trial.sv').read_text()
text=text.replace('tb_ov5640_cadence_trial','tb_ov5640_colorbars').replace('ov5640_cadence_trial_init','ov5640_colorbars_init')
text=text.replace('bad_pll=0;','bad_pll=0,bad_pattern=0;',1)
text=text.replace("(bad_pll && {hi,lo}==16'h3035)","(bad_pll && {hi,lo}==16'h3035) || (bad_pattern && {hi,lo}==16'h503d)")
text=text.replace('repeat(262) register_write(1);','repeat(263) register_write(1);')
text=text.replace('commands_written!==264','commands_written!==265')
text=text.replace('if(failed || commands_written',"if(registers[16'h503d]!==8'h80) $fatal(1,\"Colorbar setting not written\");\n        if(failed || commands_written",1)
marker='        $display("PASS camera cadence trial:'
position=text.index(marker)
text=text[:position]+'''        reset_camera();bad_pll=0;bad_pattern=1;
        register_read(16'h300a,8'h56);register_read(16'h300b,8'h40);
        repeat(264) register_write(1);wait(failed);#1;
        if(ready || error_code!==8'h70 || failed_address!==16'h503d || commands_written!=263 ||
            expected_value!==8'h80 || observed_value!==8'h00)
            $fatal(1,"Colorbar readback mismatch was not quarantined");
'''+text[position:]
text=text.replace('PASS camera cadence trial:','PASS camera colorbars:').replace(
    'complete table, preserved geometry, banding values and wrong PLL divider readback rejected; no physical cadence proof',
    '265 writes, preserved RGB565, test-pattern readback and wrong-ID/NACK/pad/PLL/format/test-pattern failures rejected')
(ROOT/'tests/tb_ov5640_colorbars.sv').write_text(text)
runner=(ROOT/'tools/run-camera-cadence-sim.ps1').read_text().replace('camera_cadence_sim','camera_colorbars_sim').replace(
    'ov5640_cadence_trial_init.v','ov5640_colorbars_init.v').replace('tb_ov5640_cadence_trial','tb_ov5640_colorbars')
# Bind the inputs before invoking the native tools.
marker='Push-Location $work'
runner=runner.replace(marker,'''$hashes=@{}
foreach($name in @('rtl/reg16_i2c.v','rtl/experimental/ov5640_colorbars_init.v','board/ov5640_colorbars_commands.vh','tests/tb_ov5640_colorbars.sv')) {
    $hashes[$name]=(Get-FileHash -LiteralPath (Join-Path $root $name)).Hash
}
$hashes | ConvertTo-Json | Set-Content -Encoding utf8 (Join-Path $work 'source-sha256.json')
'''+marker)
(ROOT/'tools/run-camera-colorbars-sim.ps1').write_text(runner)
print('Prepared colorbar initialization and mismatch rejection simulation.')
