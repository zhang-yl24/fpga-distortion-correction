$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
$work=Join-Path $root 'build\cordic_sim'
$bin='E:\Vivado\Vivado\2017.4\bin'
& 'C:\Users\22955\AppData\Local\Programs\Python\Python313\python.exe' (Join-Path $PSScriptRoot 'prepare-cordic-test.py')
if($LASTEXITCODE){throw 'CORDIC oracle generation failed'}
Push-Location $work
try {
    & (Join-Path $bin 'xvlog.bat') --sv (Join-Path $root 'rtl\cordic_sincos.v') (Join-Path $root 'tests\tb_cordic_sincos.sv') *> compile.log
    if($LASTEXITCODE){Get-Content compile.log -Tail 15;throw 'CORDIC compile failed'}
    & (Join-Path $bin 'xelab.bat') tb_cordic_sincos -s tb_cordic_sincos *> elab.log
    if($LASTEXITCODE){Get-Content elab.log -Tail 15;throw 'CORDIC elaboration failed'}
    & (Join-Path $bin 'xsim.bat') tb_cordic_sincos -runall -log simulation.log *> run.log
    $log=Get-Content -Raw simulation.log
    if($LASTEXITCODE -or $log -notmatch '(?m)^PASS CORDIC:' -or $log -match '(?im)fatal:|error:'){Get-Content simulation.log -Tail 15;throw 'CORDIC regression failed'}
    ($log -split "`r?`n") | Where-Object {$_ -match '^PASS '}
}finally{Pop-Location}
