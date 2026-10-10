$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'team-env.ps1')
$root=Split-Path -Parent $PSScriptRoot
$work=Join-Path $root 'build\frame_store_sim'
$bin=$teamVivadoBin
& $teamPython (Join-Path $PSScriptRoot 'generate-result-writer-test.py')
if($LASTEXITCODE){throw 'Result writer golden generation failed'}
Push-Location $work
try {
    $files=@('rtl\ddr_result_writer.v','rtl\ddr_write_arbiter.v','rtl\ddr_read_arbiter.v','tests\tb_ddr_result_store.sv','tests\tb_ddr_read_arbiter.sv') | ForEach-Object {Join-Path $root $_}
    & (Join-Path $bin 'xvlog.bat') --sv @files *> compile.log
    if($LASTEXITCODE){Get-Content compile.log -Tail 18;throw 'Frame-store compile failed'}
    foreach($top in @('tb_ddr_result_store','tb_ddr_read_arbiter')) {
        & (Join-Path $bin 'xelab.bat') $top -s $top *> "$top-elab.log"
        if($LASTEXITCODE){Get-Content "$top-elab.log" -Tail 18;throw 'Frame-store elaboration failed'}
        & (Join-Path $bin 'xsim.bat') $top -runall -log "$top.log" *> "$top-run.log"
        $log=Get-Content -Raw "$top.log"
        if($LASTEXITCODE -or $log -notmatch '(?m)^PASS ' -or $log -match '(?im)fatal:|error:'){Get-Content "$top.log" -Tail 18;throw 'Frame-store simulation failed'}
        ($log -split "`r?`n") | Where-Object {$_ -match '^PASS '}
    }
}finally{Pop-Location}
