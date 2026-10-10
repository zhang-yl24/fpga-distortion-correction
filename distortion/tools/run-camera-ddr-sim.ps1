$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'team-env.ps1')
$root=Split-Path -Parent $PSScriptRoot
$work=Join-Path $root 'build\camera_ddr_sim'
$bin=$teamVivadoBin
New-Item -ItemType Directory -Force $work | Out-Null
Push-Location $work
try {
    $files=@('rtl\dvp_rgb565_capture.v','rtl\rgb565_burst_pack.v','rtl\video_async_fifo.v','rtl\camera_ddr_bridge.v','rtl\ddr_frame_store.v','tests\tb_camera_ddr_store.sv') | ForEach-Object {Join-Path $root $_}
    & (Join-Path $bin 'xvlog.bat') --sv @files *> compile.log
    if($LASTEXITCODE){Get-Content compile.log -Tail 15;throw 'Camera DDR compile failed'}
    & (Join-Path $bin 'xelab.bat') tb_camera_ddr_store -s tb_camera_ddr_store *> elab.log
    if($LASTEXITCODE){Get-Content elab.log -Tail 15;throw 'Camera DDR elaboration failed'}
    & (Join-Path $bin 'xsim.bat') tb_camera_ddr_store -runall -log simulation.log *> run.log
    $log=Get-Content -Raw simulation.log
    if($LASTEXITCODE -or $log -notmatch '(?m)^PASS ' -or $log -match '(?im)fatal:|error:'){Get-Content simulation.log -Tail 15;throw 'Camera DDR simulation failed'}
    ($log -split "`r?`n") | Where-Object {$_ -match '^PASS '}
}finally{Pop-Location}
