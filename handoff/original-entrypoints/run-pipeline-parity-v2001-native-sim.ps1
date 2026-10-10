$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
$work=Join-Path $root 'build\pipeline_parity_v2001_native_sim'
$bin='E:\Vivado\Vivado\2017.4\bin'
Push-Location $work
try {
    $files=@('bilinear_rgb','ddr_remap_sample','mul32_pipe','pixel_inverse_rotation','bounded_brown_inverse_mapper','rotated_remap_core') | ForEach-Object {Join-Path $root ('rtl\'+$_+'.v')}
    $files+=@('ddr_pipeline_parity_cache','ddr_pipeline_serial_cache','pipeline_hit_frame_engine','ddr_adaptive_result_writer') | ForEach-Object {Join-Path $root ('rtl\experimental\'+$_+'.v')}
    $files+=Join-Path $root 'tests\tb_pipeline_twelve_native_regression.sv'
    & (Join-Path $bin 'xvlog.bat') --sv @files *> compile.log
    if($LASTEXITCODE){Get-Content compile.log -Tail 18;throw 'Rotated native compile failed'}
    & (Join-Path $bin 'xelab.bat') tb_pipeline_twelve_native_regression -s tb_pipeline_twelve_native_regression *> elab.log
    if($LASTEXITCODE){Get-Content elab.log -Tail 18;throw 'Rotated native elaboration failed'}
    & (Join-Path $bin 'xsim.bat') tb_pipeline_twelve_native_regression -runall -log simulation.log *> run.log
    $log=Get-Content -Raw simulation.log
    if($LASTEXITCODE -or $log -notmatch '(?m)^PASS pipeline twelve native regression:' -or $log -match '(?im)fatal:|error:'){Get-Content simulation.log -Tail 18;throw 'Rotated native regression failed'}
    ($log -split "`r?`n") | Where-Object {$_ -match '^PASS '}
}finally{Pop-Location}
