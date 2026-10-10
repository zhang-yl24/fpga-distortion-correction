$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'team-env.ps1')
$root=Split-Path -Parent $PSScriptRoot
$work=Join-Path $root 'build\remap_sim'
$bin=$teamVivadoBin
& $teamPython (Join-Path $PSScriptRoot 'generate-remap-vectors.py')
if($LASTEXITCODE){throw 'Remap golden generation failed'}
Push-Location $work
try {
    $files=@('rtl\bilinear_rgb.v','rtl\ddr_neighbour_cache.v','rtl\ddr_remap_sample.v','tests\tb_ddr_remap_sample.sv') | ForEach-Object {Join-Path $root $_}
    & (Join-Path $bin 'xvlog.bat') --sv @files *> compile.log
    if($LASTEXITCODE){Get-Content compile.log -Tail 20;throw 'Remap compile failed'}
    & (Join-Path $bin 'xelab.bat') tb_ddr_remap_sample -s tb_ddr_remap_sample *> elab.log
    if($LASTEXITCODE){Get-Content elab.log -Tail 20;throw 'Remap elaboration failed'}
    & (Join-Path $bin 'xsim.bat') tb_ddr_remap_sample -runall -log simulation.log *> run.log
    $log=Get-Content -Raw simulation.log
    if($LASTEXITCODE -or $log -notmatch '(?m)^PASS ' -or $log -match '(?im)fatal:|error:'){Get-Content simulation.log -Tail 20;throw 'Remap simulation failed'}
    ($log -split "`r?`n") | Where-Object {$_ -match '^PASS |^INFO '}
}finally{Pop-Location}
