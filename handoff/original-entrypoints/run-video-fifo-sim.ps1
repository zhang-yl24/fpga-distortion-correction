$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
$work=Join-Path $root 'build\video_fifo_sim'
$bin='E:\Vivado\Vivado\2017.4\bin'
New-Item -ItemType Directory -Force $work | Out-Null
Push-Location $work
try {
    $files=@('rtl\video_async_fifo.v','tests\tb_video_async_fifo.sv') | ForEach-Object {Join-Path $root $_}
    & (Join-Path $bin 'xvlog.bat') --sv @files *> compile.log
    if($LASTEXITCODE){Get-Content compile.log -Tail 12;throw 'Video FIFO compile failed'}
    & (Join-Path $bin 'xelab.bat') tb_video_async_fifo -s tb_video_async_fifo *> elab.log
    if($LASTEXITCODE){Get-Content elab.log -Tail 12;throw 'Video FIFO elaboration failed'}
    & (Join-Path $bin 'xsim.bat') tb_video_async_fifo -runall -log simulation.log *> run.log
    $log=Get-Content -Raw simulation.log
    if($LASTEXITCODE -or $log -notmatch '(?m)^PASS ' -or $log -match '(?im)fatal:|error:'){Get-Content simulation.log -Tail 12;throw 'Video FIFO simulation failed'}
    ($log -split "`r?`n") | Where-Object {$_ -match '^PASS '}
}finally{Pop-Location}
