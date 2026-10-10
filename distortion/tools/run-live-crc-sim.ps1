$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'team-env.ps1')
$root=Split-Path -Parent $PSScriptRoot
& $teamPython (Join-Path $PSScriptRoot 'prepare-crc-vectors.py')
if($LASTEXITCODE){throw 'CRC vector generation failed'}
$work=Join-Path $root 'build\live_crc_sim'
$bin=$teamVivadoBin
Push-Location $work
try {
    & (Join-Path $bin 'xvlog.bat') --sv (Join-Path $root 'tests\tb_video_crc32.sv') *> compile.log
    if($LASTEXITCODE){throw 'CRC compile failed'}
    & (Join-Path $bin 'xelab.bat') tb_video_crc32 -s tb_video_crc32 *> elab.log
    if($LASTEXITCODE){throw 'CRC elaboration failed'}
    & (Join-Path $bin 'xsim.bat') tb_video_crc32 -runall -log simulation.log *> run.log
    $log=Get-Content -Raw simulation.log
    if($LASTEXITCODE -or $log -notmatch '(?m)^PASS ' -or $log -match '(?im)fatal:|error:'){Get-Content simulation.log -Tail 12;throw 'CRC simulation failed'}
    ($log -split "`r?`n") | Where-Object {$_ -match '^PASS '}
}finally{Pop-Location}
