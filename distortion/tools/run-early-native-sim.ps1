$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'team-env.ps1')
$root=Split-Path -Parent $PSScriptRoot
$work=Join-Path $root 'build\early_native_sim'
$bin=$teamVivadoBin
& python (Join-Path $PSScriptRoot 'prepare-early-native-test.py')
if($LASTEXITCODE){throw 'Native references failed'}
Push-Location $work
try {
    $files=@('rtl\experimental\rgb565_burst_pack_early.v','rtl\experimental\camera_live_bridge_early.v','rtl\dvp_rgb565_capture.v','rtl\video_async_fifo.v','rtl\ddr_video_writer.v','tests\tb_early_native_capture.sv') | ForEach-Object {Join-Path $root $_}
    & (Join-Path $bin 'xvlog.bat') --sv @files *> compile.log
    if($LASTEXITCODE){throw 'Native capture compile failed'}
    & (Join-Path $bin 'xelab.bat') tb_early_native_capture -s tb_early_native_capture *> elab.log
    if($LASTEXITCODE){throw 'Native capture elaboration failed'}
    & (Join-Path $bin 'xsim.bat') tb_early_native_capture -runall -log simulation.log *> run.log
    $log=Get-Content -Raw simulation.log
    if($LASTEXITCODE -or $log -notmatch '(?m)^PASS early native capture:' -or $log -match '(?im)fatal:|error:'){Get-Content simulation.log -Tail 18;throw 'Native early capture simulation failed'}
    ($log -split "`r?`n") | Where-Object {$_ -match '^PASS '}
}finally{Pop-Location}
