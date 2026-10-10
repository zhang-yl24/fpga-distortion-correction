$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
$work=Join-Path $root 'build\burst_pack_sim'
$bin='E:\Vivado\Vivado\2017.4\bin'
New-Item -ItemType Directory -Force $work | Out-Null
Push-Location $work
try {
    $files=@('rtl\rgb565_burst_pack.v','tests\tb_rgb565_burst_pack.sv') | ForEach-Object {Join-Path $root $_}
    & (Join-Path $bin 'xvlog.bat') --sv @files *> compile.log
    if($LASTEXITCODE){throw 'Burst pack compile failed'}
    & (Join-Path $bin 'xelab.bat') tb_rgb565_burst_pack -s tb_rgb565_burst_pack *> elab.log
    if($LASTEXITCODE){throw 'Burst pack elaboration failed'}
    & (Join-Path $bin 'xsim.bat') tb_rgb565_burst_pack -runall -log simulation.log *> run.log
    $log=Get-Content -Raw simulation.log
    if($LASTEXITCODE -or $log -notmatch '(?m)^PASS ' -or $log -match '(?im)fatal:|error:'){throw 'Burst pack simulation failed'}
    ($log -split "`r?`n") | Where-Object {$_ -match '^PASS '}
}finally{Pop-Location}
