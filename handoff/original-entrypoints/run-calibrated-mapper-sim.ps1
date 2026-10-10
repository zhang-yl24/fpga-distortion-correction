$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
$work=Join-Path $root 'build\calibrated_mapper_sim'
$bin='E:\Vivado\Vivado\2017.4\bin'
& 'C:\Users\22955\AppData\Local\Programs\Python\Python313\python.exe' (Join-Path $PSScriptRoot 'prepare-calibrated-mapper-test.py')
if($LASTEXITCODE){throw 'Real-parameter reference generation failed'}
Push-Location $work
try {
    & (Join-Path $bin 'xvlog.bat') --sv (Join-Path $root 'rtl\mul32_pipe.v') (Join-Path $root 'rtl\brown_inverse_mapper.v') (Join-Path $root 'tests\tb_calibrated_mapper.sv') *> compile.log
    if($LASTEXITCODE){Get-Content compile.log -Tail 18;throw 'Calibrated mapper compile failed'}
    & (Join-Path $bin 'xelab.bat') tb_calibrated_mapper -s tb_calibrated_mapper *> elab.log
    if($LASTEXITCODE){Get-Content elab.log -Tail 18;throw 'Calibrated mapper elaboration failed'}
    & (Join-Path $bin 'xsim.bat') tb_calibrated_mapper -runall -log simulation.log *> run.log
    $log=Get-Content -Raw simulation.log
    if($LASTEXITCODE -or $log -notmatch '(?m)^PASS ' -or $log -match '(?im)fatal:|error:'){Get-Content simulation.log -Tail 18;throw 'Calibrated mapper simulation failed'}
    ($log -split "`r?`n") | Where-Object {$_ -match '^PASS '}
}finally{Pop-Location}
