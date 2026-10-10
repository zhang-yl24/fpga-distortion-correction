$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
$work=Join-Path $root 'build\mul32_sim'
$bin='E:\Vivado\Vivado\2017.4\bin'
New-Item -ItemType Directory -Force $work | Out-Null
Push-Location $work
try {
    & (Join-Path $bin 'xvlog.bat') --sv (Join-Path $root 'rtl\mul32_pipe.v') (Join-Path $root 'tests\tb_mul32_pipe.sv') *> compile.log
    if($LASTEXITCODE){Get-Content compile.log -Tail 20;throw 'Multiplier compile failed'}
    & (Join-Path $bin 'xelab.bat') tb_mul32_pipe -s tb_mul32_pipe *> elab.log
    if($LASTEXITCODE){Get-Content elab.log -Tail 20;throw 'Multiplier elaboration failed'}
    & (Join-Path $bin 'xsim.bat') tb_mul32_pipe -runall -log simulation.log *> run.log
    $log=Get-Content -Raw simulation.log
    if($LASTEXITCODE -or $log -notmatch '(?m)^PASS ' -or $log -match '(?im)fatal:|error:'){Get-Content simulation.log -Tail 20;throw 'Multiplier simulation failed'}
    ($log -split "`r?`n") | Where-Object {$_ -match '^PASS '}
}finally{Pop-Location}
