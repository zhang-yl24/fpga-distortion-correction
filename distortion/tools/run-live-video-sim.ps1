param([switch]$Wide)
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'team-env.ps1')
$root=Split-Path -Parent $PSScriptRoot
$top=if($Wide){'tb_ddr_live_video_wide'}else{'tb_ddr_live_video'}
$work=Join-Path $root $(if($Wide){'build\live_video_wide_sim'}else{'build\live_video_sim'})
$bin=$teamVivadoBin
New-Item -ItemType Directory -Force $work | Out-Null
Push-Location $work
try {
    $files=@('rtl\dvp_rgb565_capture.v','rtl\rgb565_burst_pack.v','rtl\video_async_fifo.v','rtl\camera_live_bridge.v','rtl\ddr_video_writer.v','rtl\ddr_video_reader.v','rtl\ddr_video_output.v','rtl\ddr_live_video.v',('tests\'+$top+'.sv')) | ForEach-Object {Join-Path $root $_}
    & (Join-Path $bin 'xvlog.bat') --sv @files *> compile.log
    if($LASTEXITCODE){Get-Content compile.log -Tail 18;throw 'Live video compile failed'}
    & (Join-Path $bin 'xelab.bat') $top -s $top *> elab.log
    if($LASTEXITCODE){Get-Content elab.log -Tail 18;throw 'Live video elaboration failed'}
    & (Join-Path $bin 'xsim.bat') $top -runall -log simulation.log *> run.log
    $log=Get-Content -Raw simulation.log
    if($LASTEXITCODE -or $log -notmatch '(?m)^PASS ' -or $log -match '(?im)fatal:|error:'){Get-Content simulation.log -Tail 18;throw 'Live video simulation failed'}
    ($log -split "`r?`n") | Where-Object {$_ -match '^PASS '}
}finally{Pop-Location}
