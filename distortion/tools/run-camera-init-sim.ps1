$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'team-env.ps1')
$root=Split-Path -Parent $PSScriptRoot
$work=Join-Path $root 'build\camera_init_sim'
$bin=$teamVivadoBin
New-Item -ItemType Directory -Force $work | Out-Null
Push-Location $work
try {
    $files=@('rtl\reg16_i2c.v','rtl\ov5640_init.v','tests\tb_ov5640_init.sv') | ForEach-Object {Join-Path $root $_}
    & (Join-Path $bin 'xvlog.bat') --sv @files *> compile.log
    if($LASTEXITCODE){throw 'Camera init compile failed'}
    & (Join-Path $bin 'xelab.bat') tb_ov5640_init -s tb_ov5640_init *> elab.log
    if($LASTEXITCODE){throw 'Camera init elaboration failed'}
    & (Join-Path $bin 'xsim.bat') tb_ov5640_init -runall -log simulation.log *> run.log
    $log=Get-Content -Raw simulation.log
    if($LASTEXITCODE -or $log -notmatch '(?m)^PASS ' -or $log -match '(?im)fatal:|error:'){throw 'Camera init simulation failed'}
    ($log -split "`r?`n") | Where-Object {$_ -match '^PASS '}
}finally{Pop-Location}
