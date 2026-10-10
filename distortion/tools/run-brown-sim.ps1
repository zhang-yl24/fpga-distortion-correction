$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'team-env.ps1')
$root=Split-Path -Parent $PSScriptRoot
$work=Join-Path $root 'build\brown_sim'
$bin=$teamVivadoBin
& $teamPython (Join-Path $PSScriptRoot 'generate-brown-vectors.py')
if($LASTEXITCODE){throw 'Brown golden generation failed'}
Push-Location $work
try {
    & (Join-Path $bin 'xvlog.bat') --sv (Join-Path $root 'rtl\mul32_pipe.v') (Join-Path $root 'rtl\brown_inverse_mapper.v') (Join-Path $root 'tests\tb_brown_inverse_mapper.sv') *> compile.log
    if($LASTEXITCODE){Get-Content compile.log -Tail 20;throw 'Brown compile failed'}
    & (Join-Path $bin 'xelab.bat') tb_brown_inverse_mapper -s tb_brown_inverse_mapper *> elab.log
    if($LASTEXITCODE){Get-Content elab.log -Tail 20;throw 'Brown elaboration failed'}
    & (Join-Path $bin 'xsim.bat') tb_brown_inverse_mapper -runall -log simulation.log *> run.log
    $log=Get-Content -Raw simulation.log
    if($LASTEXITCODE -or $log -notmatch '(?m)^PASS ' -or $log -match '(?im)fatal:|error:'){Get-Content simulation.log -Tail 20;throw 'Brown simulation failed'}
    ($log -split "`r?`n") | Where-Object {$_ -match '^PASS '}
}finally{Pop-Location}
