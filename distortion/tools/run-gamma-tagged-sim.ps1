$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'team-env.ps1')
$root=Split-Path -Parent $PSScriptRoot
$work=Join-Path $root 'build\gamma_tagged_sim'
New-Item -ItemType Directory -Force -Path $work | Out-Null
$bin=$teamVivadoBin
$files=@('rtl\experimental\adaptive_gamma_stream.v','rtl\experimental\adaptive_gamma_tagged.v','tests\tb_gamma_tagged.sv')
$deps=$files+@('rtl\experimental\gamma_curves.vh','build\gamma_sim\golden.mem')
$hashes=@{}
foreach($f in $deps){$hashes[$f]=(Get-FileHash -LiteralPath (Join-Path $root $f)).Hash}
Copy-Item -LiteralPath (Join-Path $root 'build\gamma_sim\golden.mem') -Destination (Join-Path $work 'golden.mem')
@{started_at=(Get-Date).ToString('o');source_sha256=$hashes} | ConvertTo-Json -Depth 5 | Set-Content -Encoding utf8 (Join-Path $work 'start-proof.json')
foreach($f in $deps){
    $dest=Join-Path $work ('source-snapshot\'+$f)
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $dest) | Out-Null
    Copy-Item -LiteralPath (Join-Path $root $f) -Destination $dest
}
Push-Location $work
try{
    $paths=$files | ForEach-Object {Join-Path $root $_}
    & (Join-Path $bin 'xvlog.bat') --sv @paths *> compile.log
    if($LASTEXITCODE){throw 'Tagged Gamma compile failed'}
    & (Join-Path $bin 'xelab.bat') tb_gamma_tagged -s tb_gamma_tagged *> elab.log
    if($LASTEXITCODE){throw 'Tagged Gamma elaboration failed'}
    & (Join-Path $bin 'xsim.bat') tb_gamma_tagged -runall -log simulation.log *> run.log
    $log=Get-Content -Raw simulation.log
    if($LASTEXITCODE -or $log -notmatch '(?m)^PASS tagged Gamma:' -or $log -match '(?im)fatal:|error:'){Get-Content simulation.log -Tail 15;throw 'Tagged Gamma simulation failed'}
    foreach($f in $deps){if((Get-FileHash -LiteralPath (Join-Path $root $f)).Hash -ne $hashes[$f]){throw 'Tagged Gamma dependency changed'}}
    $log -split "`r?`n" | Where-Object {$_ -match '^PASS '}
}finally{Pop-Location}
