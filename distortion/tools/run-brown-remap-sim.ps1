param([ValidateSet('baseline','fast')][string]$Cache='baseline')
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'team-env.ps1')
$root=Split-Path -Parent $PSScriptRoot
$work=Join-Path $root 'build\brown_remap_sim'
$bin=$teamVivadoBin
if($Cache -eq 'baseline') {
    & $teamPython (Join-Path $PSScriptRoot 'prepare-brown-remap-test.py')
    if($LASTEXITCODE){throw 'Composed Brown golden generation failed'}
} else {
    $baseline=$work
    $work=Join-Path $root 'build\brown_remap_fast_sim'
    New-Item -ItemType Directory -Force -Path $work | Out-Null
    Get-ChildItem -LiteralPath $baseline -Filter '*.mem' | ForEach-Object {Copy-Item -LiteralPath $_.FullName -Destination $work}
    Copy-Item -LiteralPath (Join-Path $baseline 'counts.vh') -Destination $work
}
Push-Location $work
try {
    $files=@('rtl\bilinear_rgb.v','rtl\ddr_neighbour_cache.v','rtl\ddr_remap_sample.v','rtl\mul32_pipe.v','rtl\brown_inverse_mapper.v','rtl\brown_remap_core.v','tests\tb_brown_ddr_remap.sv') | ForEach-Object {Join-Path $root $_}
    if($Cache -eq 'fast') {$files=$files | ForEach-Object {if($_ -eq (Join-Path $root 'rtl\ddr_neighbour_cache.v')){Join-Path $root 'rtl\experimental\ddr_neighbour_cache_fast.v'}else{$_}}}
    & (Join-Path $bin 'xvlog.bat') --sv @files *> compile.log
    if($LASTEXITCODE){Get-Content compile.log -Tail 20;throw 'Composed Brown compile failed'}
    & (Join-Path $bin 'xelab.bat') tb_brown_ddr_remap -s tb_brown_ddr_remap *> elab.log
    if($LASTEXITCODE){Get-Content elab.log -Tail 20;throw 'Composed Brown elaboration failed'}
    & (Join-Path $bin 'xsim.bat') tb_brown_ddr_remap -runall -log simulation.log *> run.log
    $log=Get-Content -Raw simulation.log
    if($LASTEXITCODE -or $log -notmatch '(?m)^PASS ' -or $log -match '(?im)fatal:|error:'){Get-Content simulation.log -Tail 20;throw 'Composed Brown simulation failed'}
    ($log -split "`r?`n") | Where-Object {$_ -match '^PASS |^INFO '}
}finally{Pop-Location}
