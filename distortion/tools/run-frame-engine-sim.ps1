$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'team-env.ps1')
$root=Split-Path -Parent $PSScriptRoot
$work=Join-Path $root 'build\frame_engine_sim'
$bin=$teamVivadoBin
& $teamPython (Join-Path $PSScriptRoot 'generate-frame-engine-test.py')
if($LASTEXITCODE){throw 'Frame engine reference generation failed'}
Push-Location $work
try {
    $files=@('rtl\bilinear_rgb.v','rtl\ddr_neighbour_cache.v','rtl\ddr_remap_sample.v','rtl\mul32_pipe.v','rtl\brown_inverse_mapper.v','rtl\brown_remap_core.v','rtl\ddr_result_writer.v','rtl\ddr_read_arbiter.v','rtl\remap_frame_engine.v','tests\tb_remap_frame_engine.sv') | ForEach-Object {Join-Path $root $_}
    & (Join-Path $bin 'xvlog.bat') --sv @files *> compile.log
    if($LASTEXITCODE){Get-Content compile.log -Tail 18;throw 'Frame engine compile failed'}
    & (Join-Path $bin 'xelab.bat') tb_remap_frame_engine -s tb_remap_frame_engine *> elab.log
    if($LASTEXITCODE){Get-Content elab.log -Tail 18;throw 'Frame engine elaboration failed'}
    & (Join-Path $bin 'xsim.bat') tb_remap_frame_engine -runall -log simulation.log *> run.log
    $log=Get-Content -Raw simulation.log
    if($LASTEXITCODE -or $log -notmatch '(?m)^PASS ' -or $log -match '(?im)fatal:|error:'){Get-Content simulation.log -Tail 18;throw 'Frame engine simulation failed'}
    ($log -split "`r?`n") | Where-Object {$_ -match '^PASS '}
}finally{Pop-Location}
