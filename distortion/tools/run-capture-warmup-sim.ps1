$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
$work=Join-Path $root 'build\capture_warmup_sim'
New-Item -ItemType Directory -Force -Path $work | Out-Null
$hashes=@{}
foreach($name in @('rtl\experimental\capture_warmup.v','tests\tb_capture_warmup.sv')) {
    $hashes[$name]=(Get-FileHash -LiteralPath (Join-Path $root $name)).Hash
}
$hashes | ConvertTo-Json | Set-Content -Encoding utf8 (Join-Path $work 'source-sha256.json')
Push-Location $work
try {
    & 'E:\Vivado\Vivado\2017.4\bin\xvlog.bat' --sv (Join-Path $root 'rtl\experimental\capture_warmup.v') (Join-Path $root 'tests\tb_capture_warmup.sv') *> compile.log
    if($LASTEXITCODE){throw 'Warmup compile failed'}
    & 'E:\Vivado\Vivado\2017.4\bin\xelab.bat' tb_capture_warmup -s tb_capture_warmup *> elab.log
    if($LASTEXITCODE){throw 'Warmup elaboration failed'}
    & 'E:\Vivado\Vivado\2017.4\bin\xsim.bat' tb_capture_warmup -runall -log simulation.log *> run.log
    $log=Get-Content -Raw simulation.log
    if($LASTEXITCODE -or $log -notmatch '(?m)^PASS capture warmup:' -or $log -match '(?i)fatal:|error:'){throw 'Warmup simulation failed'}
    foreach($name in $hashes.Keys){if((Get-FileHash -LiteralPath (Join-Path $root $name)).Hash -ne $hashes[$name]){throw 'Warmup source changed during simulation'}}
    $log -split "`r?`n" | Where-Object {$_ -match '^PASS '}
}finally{Pop-Location}
