$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'team-env.ps1')
$root=Split-Path -Parent $PSScriptRoot
$work=Join-Path $root 'build\rotation_sim'
$bin=$teamVivadoBin
& $teamPython (Join-Path $PSScriptRoot 'prepare-rotation-test.py')
if($LASTEXITCODE){throw 'Rotation oracle failed'}
Push-Location $work
try {
    $files=@('rtl\mul32_pipe.v','rtl\pixel_inverse_rotation.v','tests\tb_pixel_inverse_rotation.sv') | ForEach-Object {Join-Path $root $_}
    & (Join-Path $bin 'xvlog.bat') --sv @files *> compile.log
    if($LASTEXITCODE){Get-Content compile.log -Tail 18;throw 'Rotation compile failed'}
    & (Join-Path $bin 'xelab.bat') tb_pixel_inverse_rotation -s tb_pixel_inverse_rotation *> elab.log
    if($LASTEXITCODE){Get-Content elab.log -Tail 18;throw 'Rotation elaboration failed'}
    & (Join-Path $bin 'xsim.bat') tb_pixel_inverse_rotation -runall -log simulation.log *> run.log
    $log=Get-Content -Raw simulation.log
    if($LASTEXITCODE -or $log -notmatch '(?m)^PASS inverse rotation:' -or $log -match '(?im)fatal:|error:'){Get-Content simulation.log -Tail 18;throw 'Rotation regression failed'}
    ($log -split "`r?`n") | Where-Object {$_ -match '^PASS '}
}finally{Pop-Location}
