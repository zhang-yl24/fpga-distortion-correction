$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
$work=Join-Path $root 'build\camera_state_scan_sim'
New-Item -ItemType Directory -Force -Path $work | Out-Null
$hashes=@{}
foreach($name in @('rtl/experimental/ov5640_state_scan.v','tests/tb_camera_state_scan.sv')) {
    $hashes[$name]=(Get-FileHash -LiteralPath (Join-Path $root $name)).Hash
}
$hashes | ConvertTo-Json | Set-Content -Encoding utf8 (Join-Path $work 'source-sha256.json')
Push-Location $work
try {
    & 'E:\Vivado\Vivado\2017.4\bin\xvlog.bat' --sv (Join-Path $root 'rtl/experimental/ov5640_state_scan.v') (Join-Path $root 'tests/tb_camera_state_scan.sv') *> compile.log
    if($LASTEXITCODE){throw 'Read-only scan compile failed'}
    & 'E:\Vivado\Vivado\2017.4\bin\xelab.bat' tb_camera_state_scan -s tb_camera_state_scan *> elab.log
    if($LASTEXITCODE){throw 'Read-only scan elaboration failed'}
    & 'E:\Vivado\Vivado\2017.4\bin\xsim.bat' tb_camera_state_scan -runall -log simulation.log *> run.log
    $log=Get-Content -Raw simulation.log
    if($LASTEXITCODE -or $log -notmatch '(?m)^PASS camera state scan:' -or $log -match '(?i)fatal:|error:'){
        Get-Content simulation.log -Tail 12;throw 'Read-only scanner regression failed'
    }
    ($log -split "`r?`n") | Where-Object {$_ -match '^PASS '}
}finally{Pop-Location}
