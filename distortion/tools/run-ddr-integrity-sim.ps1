$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'team-env.ps1')
$root=Split-Path -Parent $PSScriptRoot
$work=Join-Path $root 'build\ddr_integrity_sim'
$bin=$teamVivadoBin
New-Item -ItemType Directory -Force $work | Out-Null
Push-Location $work
try {
    $files=@('rtl\ddr_integrity_test.v','tests\tb_ddr_integrity_test.sv') | ForEach-Object {Join-Path $root $_}
    & (Join-Path $bin 'xvlog.bat') --sv @files *> compile.log
    if($LASTEXITCODE){Get-Content compile.log -Tail 12;throw 'DDR test compile failed'}
    & (Join-Path $bin 'xelab.bat') tb_ddr_integrity_test -s tb_ddr_integrity_test *> elab.log
    if($LASTEXITCODE){Get-Content elab.log -Tail 12;throw 'DDR test elaboration failed'}
    & (Join-Path $bin 'xsim.bat') tb_ddr_integrity_test -runall -log simulation.log *> run.log
    $log=Get-Content -Raw simulation.log
    if($LASTEXITCODE -or $log -notmatch '(?m)^PASS ' -or $log -match '(?im)fatal:|error:'){Get-Content simulation.log -Tail 12;throw 'DDR test simulation failed'}
    ($log -split "`r?`n") | Where-Object {$_ -match '^PASS '}
}finally{Pop-Location}
