$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'team-env.ps1')
$root=Split-Path -Parent $PSScriptRoot
$work=Join-Path $root 'build\preview_sim'
$bin=$teamVivadoBin
New-Item -ItemType Directory -Force $work | Out-Null
Push-Location $work
try {
    $files=@('rtl\dvp_rgb565_capture.v','rtl\camera_preview.v','tests\tb_camera_preview.sv') | ForEach-Object {Join-Path $root $_}
    & (Join-Path $bin 'xvlog.bat') --sv @files *> compile.log
    if($LASTEXITCODE){throw 'Preview compile failed'}
    & (Join-Path $bin 'xelab.bat') tb_camera_preview -s tb_camera_preview *> elab.log
    if($LASTEXITCODE){throw 'Preview elaboration failed'}
    & (Join-Path $bin 'xsim.bat') tb_camera_preview -runall -log simulation.log *> run.log
    $log=Get-Content -Raw simulation.log
    if($LASTEXITCODE -or $log -notmatch '(?m)^PASS ' -or $log -match '(?im)fatal:|error:'){Get-Content simulation.log -Tail 12;throw 'Preview simulation failed'}
    ($log -split "`r?`n") | Where-Object {$_ -match '^PASS '}
}finally{Pop-Location}
