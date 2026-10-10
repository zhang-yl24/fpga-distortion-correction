$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'team-env.ps1')
$root=Split-Path -Parent $PSScriptRoot
$work=Join-Path $root 'build\early_pack_sim'
$bin=$teamVivadoBin
New-Item -ItemType Directory -Force $work | Out-Null
Push-Location $work
try {
    $files=@('rtl\experimental\rgb565_burst_pack_early.v','tests\tb_rgb565_burst_pack_early.sv') | ForEach-Object {Join-Path $root $_}
    & (Join-Path $bin 'xvlog.bat') --sv @files *> compile.log
    if($LASTEXITCODE){throw 'Burst pack compile failed'}
    & (Join-Path $bin 'xelab.bat') tb_rgb565_burst_pack_early -s tb_rgb565_burst_pack_early *> elab.log
    if($LASTEXITCODE){throw 'Burst pack elaboration failed'}
    & (Join-Path $bin 'xsim.bat') tb_rgb565_burst_pack_early -runall -log simulation.log *> run.log
    $log=Get-Content -Raw simulation.log
    if($LASTEXITCODE -or $log -notmatch '(?m)^PASS ' -or $log -match '(?im)fatal:|error:'){throw 'Burst pack simulation failed'}
    ($log -split "`r?`n") | Where-Object {$_ -match '^PASS '}
}finally{Pop-Location}
