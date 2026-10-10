param([ValidateSet('baseline','fast')][string]$Cache='baseline')
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
$work=Join-Path $root 'build\corrected_video_sim'
$bin='E:\Vivado\Vivado\2017.4\bin'
if($Cache -eq 'baseline') {
    & 'C:\Users\22955\AppData\Local\Programs\Python\Python313\python.exe' (Join-Path $PSScriptRoot 'generate-frame-engine-test.py')
    if($LASTEXITCODE){throw 'Independent corrected frame references failed'}
}else{$work=Join-Path $root 'build\corrected_video_fast_sim'}
New-Item -ItemType Directory -Force -Path $work | Out-Null
foreach($name in @('source.mem','result.mem','crcs.mem','reference.json')) {
    Copy-Item -LiteralPath (Join-Path $root ('build\frame_engine_sim\'+$name)) -Destination (Join-Path $work $name)
}
Push-Location $work
try {
    $files=@('dvp_rgb565_capture','rgb565_burst_pack','video_async_fifo','camera_live_bridge','ddr_video_writer','ddr_video_reader','ddr_video_output','ddr_corrected_video','remap_frame_engine','ddr_read_arbiter','ddr_write_arbiter','ddr_result_writer','brown_remap_core','brown_inverse_mapper','mul32_pipe','ddr_remap_sample','ddr_neighbour_cache','bilinear_rgb') | ForEach-Object {Join-Path $root ('rtl\'+$_+'.v')}
    if($Cache -eq 'fast') {$files=$files | ForEach-Object {if($_ -eq (Join-Path $root 'rtl\ddr_neighbour_cache.v')){Join-Path $root 'rtl\experimental\ddr_neighbour_cache_fast.v'}else{$_}}}
    $files+=Join-Path $root 'tests\tb_ddr_corrected_video.sv'
    & (Join-Path $bin 'xvlog.bat') --sv @files *> compile.log
    if($LASTEXITCODE){Get-Content compile.log -Tail 18;throw 'Corrected video compile failed'}
    & (Join-Path $bin 'xelab.bat') tb_ddr_corrected_video -s tb_ddr_corrected_video *> elab.log
    if($LASTEXITCODE){Get-Content elab.log -Tail 18;throw 'Corrected video elaboration failed'}
    & (Join-Path $bin 'xsim.bat') tb_ddr_corrected_video -runall -log simulation.log *> run.log
    $log=Get-Content -Raw simulation.log
    if($LASTEXITCODE -or $log -notmatch '(?m)^PASS ' -or $log -match '(?im)fatal:|error:'){Get-Content simulation.log -Tail 18;throw 'Corrected video simulation failed'}
    ($log -split "`r?`n") | Where-Object {$_ -match '^PASS '}
}finally{Pop-Location}
