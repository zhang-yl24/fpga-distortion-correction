$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
$work=Join-Path $root 'build\camera_colorbars_sim'
$bin='E:\Vivado\Vivado\2017.4\bin'
New-Item -ItemType Directory -Force $work | Out-Null
$hashes=@{}
foreach($name in @('rtl/reg16_i2c.v','rtl/experimental/ov5640_colorbars_init.v','board/ov5640_colorbars_commands.vh','tests/tb_ov5640_colorbars.sv')) {
    $hashes[$name]=(Get-FileHash -LiteralPath (Join-Path $root $name)).Hash
}
$hashes | ConvertTo-Json | Set-Content -Encoding utf8 (Join-Path $work 'source-sha256.json')
Push-Location $work
try {
    $files=@('rtl\reg16_i2c.v','rtl\experimental\ov5640_colorbars_init.v','tests\tb_ov5640_colorbars.sv') | ForEach-Object {Join-Path $root $_}
    & (Join-Path $bin 'xvlog.bat') --sv @files *> compile.log
    if($LASTEXITCODE){throw 'Camera init compile failed'}
    & (Join-Path $bin 'xelab.bat') tb_ov5640_colorbars -s tb_ov5640_colorbars *> elab.log
    if($LASTEXITCODE){throw 'Camera init elaboration failed'}
    & (Join-Path $bin 'xsim.bat') tb_ov5640_colorbars -runall -log simulation.log *> run.log
    $log=Get-Content -Raw simulation.log
    if($LASTEXITCODE -or $log -notmatch '(?m)^PASS ' -or $log -match '(?im)fatal:|error:'){throw 'Camera init simulation failed'}
    ($log -split "`r?`n") | Where-Object {$_ -match '^PASS '}
}finally{Pop-Location}
