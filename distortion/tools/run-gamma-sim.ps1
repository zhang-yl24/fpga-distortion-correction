$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'team-env.ps1')
$root=Split-Path -Parent $PSScriptRoot
$work=Join-Path $root 'build\gamma_sim'
$bin=$teamVivadoBin
Push-Location $work
try {
    $files=@((Join-Path $root 'rtl\experimental\adaptive_gamma_stream.v'),(Join-Path $root 'tests\tb_adaptive_gamma.sv'),(Join-Path $root 'tests\tb_gamma_exhaustive.sv'))
    $deps=$files+@((Join-Path $root 'rtl\experimental\gamma_curves.vh'),(Join-Path $work 'golden.mem'),(Join-Path $work 'reference.json'))
    $hashes=@{};foreach($f in $deps){$hashes[$f.Substring($root.Length+1)]=(Get-FileHash -LiteralPath $f).Hash}
    @{started_at=(Get-Date).ToString('o');source_sha256=$hashes} | ConvertTo-Json -Depth 5 | Set-Content -Encoding utf8 start-proof.json
    & (Join-Path $bin 'xvlog.bat') --sv @files *> compile.log
    if($LASTEXITCODE){Get-Content compile.log -Tail 12;throw 'Gamma compile failed'}
    foreach($top in @('tb_adaptive_gamma','tb_gamma_exhaustive')){
        & (Join-Path $bin 'xelab.bat') $top -s $top *> ($top+'-elab.log')
        if($LASTEXITCODE){throw 'Gamma elaboration failed'}
        & (Join-Path $bin 'xsim.bat') $top -runall -log ($top+'-simulation.log') *> ($top+'-run.log')
        $log=Get-Content -Raw ($top+'-simulation.log')
        if($LASTEXITCODE -or $log -notmatch '(?m)^PASS .*Gamma:' -or $log -match '(?im)fatal:|error:'){Get-Content ($top+'-simulation.log') -Tail 15;throw 'Gamma regression failed'}
        ($log -split "`r?`n") | Where-Object {$_ -match '^PASS '}
    }
    foreach($f in $deps){if((Get-FileHash -LiteralPath $f).Hash -ne $hashes[$f.Substring($root.Length+1)]){throw 'Gamma source changed during simulation'}}
}finally{Pop-Location}
