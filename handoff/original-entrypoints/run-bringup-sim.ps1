$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
$work=Join-Path $root 'build\bringup_sim'
$bin='E:\Vivado\Vivado\2017.4\bin'
New-Item -ItemType Directory -Force $work | Out-Null
Push-Location $work
try {
    $files=@('rtl\reg16_i2c.v','rtl\uart_tx.v','rtl\video_pattern.v','rtl\camera_id_probe.v',
        'tests\tb_reg16_i2c.sv','tests\tb_uart_tx.sv','tests\tb_video_pattern.sv','tests\tb_camera_probe.sv') | ForEach-Object {Join-Path $root $_}
    & (Join-Path $bin 'xvlog.bat') --sv @files *> compile.log
    if($LASTEXITCODE){throw 'RTL compile failed'}
    foreach($top in @('tb_reg16_i2c','tb_sccb_stop','tb_uart_tx','tb_video_pattern','tb_i2c_le','tb_video_720p','tb_camera_probe')) {
        & (Join-Path $bin 'xelab.bat') $top -s $top *> ($top+'.elab.log')
        if($LASTEXITCODE){throw "Elaboration failed: $top"}
        & (Join-Path $bin 'xsim.bat') $top -runall -log ($top+'.log') *> ($top+'.run.log')
        $log=Get-Content -Raw ($top+'.log')
        if($LASTEXITCODE -or $log -notmatch '(?m)^PASS ' -or $log -match '(?im)fatal:|error:'){throw "Simulation failed: $top"}
        ($log -split "`r?`n") | Where-Object {$_ -match '^PASS '}
    }
}finally {Pop-Location}
