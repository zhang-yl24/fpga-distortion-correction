$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'team-env.ps1')
$root=Split-Path -Parent $PSScriptRoot
$work=Join-Path $root 'build\rotated_video_sim'
$bin=$teamVivadoBin
& $teamPython (Join-Path $PSScriptRoot 'prepare-rotated-video.py')
if($LASTEXITCODE){throw 'Rotated video reference generation failed'}
Push-Location $work
try {
    $files=@('dvp_rgb565_capture','rgb565_burst_pack','video_async_fifo','camera_live_bridge','ddr_video_writer','ddr_video_reader','ddr_video_output','ddr_rotated_video','rotated_frame_engine','ddr_read_arbiter','ddr_write_arbiter','ddr_result_writer','rotated_remap_core','bounded_brown_inverse_mapper','pixel_inverse_rotation','mul32_pipe','ddr_remap_sample','bilinear_rgb') | ForEach-Object {Join-Path $root ('rtl\'+$_+'.v')}
    $files+=Join-Path $root 'rtl\experimental\ddr_neighbour_cache_fast.v'
    $files+=Join-Path $root 'tests\tb_ddr_rotated_video.sv'
    & (Join-Path $bin 'xvlog.bat') --sv @files *> compile.log
    if($LASTEXITCODE){Get-Content compile.log -Tail 18;throw 'Rotated video compile failed'}
    & (Join-Path $bin 'xelab.bat') tb_ddr_rotated_video -s tb_ddr_rotated_video *> elab.log
    if($LASTEXITCODE){Get-Content elab.log -Tail 18;throw 'Rotated video elaboration failed'}
    & (Join-Path $bin 'xsim.bat') tb_ddr_rotated_video -runall -log simulation.log *> run.log
    $log=Get-Content -Raw simulation.log
    if($LASTEXITCODE -or $log -notmatch '(?m)^PASS rotated DDR video:' -or $log -match '(?im)fatal:|error:'){Get-Content simulation.log -Tail 18;throw 'Rotated video simulation failed'}
    ($log -split "`r?`n") | Where-Object {$_ -match '^PASS '}
}finally{Pop-Location}
