$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
$work=Join-Path $root 'build\pipeline_hit_video_sim'
$bin='E:\Vivado\Vivado\2017.4\bin'
Push-Location $work
try {
    $files=@('dvp_rgb565_capture','video_async_fifo','ddr_video_writer','ddr_video_reader','ddr_video_output','ddr_read_arbiter','ddr_write_arbiter','rotated_remap_core','bounded_brown_inverse_mapper','pixel_inverse_rotation','mul32_pipe','ddr_remap_sample','bilinear_rgb') | ForEach-Object {Join-Path $root ('rtl\'+$_+'.v')}
    $files+=@('ddr_pipeline_hit_cache','ddr_pipeline_serial_cache','pipeline_hit_frame_engine','ddr_adaptive_result_writer','rgb565_burst_pack_early','camera_live_bridge_early','ddr_pipeline_hit_video') | ForEach-Object {Join-Path $root ('rtl\experimental\'+$_+'.v')}
    $files+=Join-Path $root 'tests\tb_ddr_pipeline_hit_video.sv'
    & (Join-Path $bin 'xvlog.bat') --sv @files *> compile.log
    if($LASTEXITCODE){Get-Content compile.log -Tail 18;throw 'Rotated video compile failed'}
    & (Join-Path $bin 'xelab.bat') tb_ddr_pipeline_hit_video -s tb_ddr_pipeline_hit_video *> elab.log
    if($LASTEXITCODE){Get-Content elab.log -Tail 18;throw 'Rotated video elaboration failed'}
    & (Join-Path $bin 'xsim.bat') tb_ddr_pipeline_hit_video -runall -log simulation.log *> run.log
    $log=Get-Content -Raw simulation.log
    if($LASTEXITCODE -or $log -notmatch '(?m)^PASS pipeline hit DDR video:' -or $log -match '(?im)fatal:|error:'){Get-Content simulation.log -Tail 18;throw 'Rotated video simulation failed'}
    ($log -split "`r?`n") | Where-Object {$_ -match '^PASS '}
}finally{Pop-Location}
