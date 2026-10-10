$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'team-env.ps1')
$root=Split-Path -Parent $PSScriptRoot
$work=Join-Path $root 'build\frame_period_sim'
$bin=$teamVivadoBin
New-Item -ItemType Directory -Force -Path $work | Out-Null
Push-Location $work
try {
    & (Join-Path $bin 'xvlog.bat') --sv (Join-Path $root 'rtl\camera_frame_period.v') (Join-Path $root 'tests\tb_camera_frame_period.sv') *> compile.log
    if($LASTEXITCODE){throw 'Period monitor compile failed'}
    & (Join-Path $bin 'xelab.bat') tb_camera_frame_period -s tb_camera_frame_period *> elab.log
    if($LASTEXITCODE){throw 'Period monitor elaboration failed'}
    & (Join-Path $bin 'xsim.bat') tb_camera_frame_period -runall -log simulation.log *> run.log
    $log=Get-Content -Raw simulation.log
    if($LASTEXITCODE -or $log -notmatch '(?m)^PASS frame period:' -or $log -match '(?im)fatal:|error:'){Get-Content simulation.log -Tail 12;throw 'Period monitor simulation failed'}
    ($log -split "`r?`n") | Where-Object {$_ -match '^PASS '}
}finally{Pop-Location}
