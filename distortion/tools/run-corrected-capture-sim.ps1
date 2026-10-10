$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'team-env.ps1')
$root=Split-Path -Parent $PSScriptRoot
$work=Join-Path $root 'build\corrected_capture_sim'
$bin=$teamVivadoBin
$python=$teamPython
& $python (Join-Path $PSScriptRoot 'generate-frame-engine-test.py')
if($LASTEXITCODE){throw 'Independent frame references failed'}
New-Item -ItemType Directory -Force -Path $work | Out-Null
foreach($name in @('source.mem','result.mem','crcs.mem','reference.json')) {
    Copy-Item -LiteralPath (Join-Path $root ('build\frame_engine_sim\'+$name)) -Destination (Join-Path $work $name)
}
Push-Location $work
try {
    $files=@('dvp_rgb565_capture','rgb565_burst_pack','video_async_fifo','camera_live_bridge','ddr_video_writer','ddr_corrected_capture','ddr_uart_frame','remap_frame_engine','ddr_result_writer','brown_remap_core','brown_inverse_mapper','mul32_pipe','ddr_remap_sample','ddr_neighbour_cache','bilinear_rgb') | ForEach-Object {Join-Path $root ('rtl\'+$_+'.v')}
    $files+=Join-Path $root 'tests\tb_ddr_corrected_capture.sv'
    & (Join-Path $bin 'xvlog.bat') --sv @files *> compile.log
    if($LASTEXITCODE){Get-Content compile.log -Tail 18;throw 'Pair capture compile failed'}
    & (Join-Path $bin 'xelab.bat') tb_ddr_corrected_capture -s tb_ddr_corrected_capture *> elab.log
    if($LASTEXITCODE){Get-Content elab.log -Tail 18;throw 'Pair capture elaboration failed'}
    & (Join-Path $bin 'xsim.bat') tb_ddr_corrected_capture -runall -log simulation.log *> run.log
    $log=Get-Content -Raw simulation.log
    if($LASTEXITCODE -or $log -notmatch '(?m)^PASS ' -or $log -match '(?im)fatal:|error:'){Get-Content simulation.log -Tail 18;throw 'Pair capture simulation failed'}
    ($log -split "`r?`n") | Where-Object {$_ -match '^PASS '}
    & $python (Join-Path $PSScriptRoot 'check-corrected-capture-sim.py')
    if($LASTEXITCODE){throw 'Independent host packet verification failed'}
}finally{Pop-Location}
