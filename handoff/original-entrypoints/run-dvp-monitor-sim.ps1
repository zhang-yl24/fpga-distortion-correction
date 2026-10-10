$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
$work=Join-Path $root 'build\dvp_monitor_sim'
$bin='E:\Vivado\Vivado\2017.4\bin'
New-Item -ItemType Directory -Force $work | Out-Null
Push-Location $work
try {
    $files=@('rtl\dvp_rgb565_capture.v','rtl\dvp_monitor.v','tests\tb_dvp_monitor.sv','tests\tb_dvp_counter_carry.sv') | ForEach-Object {Join-Path $root $_}
    & (Join-Path $bin 'xvlog.bat') --sv @files *> compile.log
    if($LASTEXITCODE){throw 'DVP monitor compile failed'}
    foreach($top in @('tb_dvp_monitor','tb_dvp_counter_carry')) {
        & (Join-Path $bin 'xelab.bat') $top -s $top *> ($top+'.elab.log')
        if($LASTEXITCODE){throw "DVP elaboration failed: $top"}
        & (Join-Path $bin 'xsim.bat') $top -runall -log ($top+'.log') *> ($top+'.run.log')
        $log=Get-Content -Raw ($top+'.log')
        if($LASTEXITCODE -or $log -notmatch '(?m)^PASS ' -or $log -match '(?im)fatal:|error:'){throw "DVP simulation failed: $top"}
        ($log -split "`r?`n") | Where-Object {$_ -match '^PASS '}
    }
}finally{Pop-Location}
