param([string]$OutputDirectory='', [switch]$NativeVga)
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'team-env.ps1')
$root=Split-Path -Parent $PSScriptRoot
$approved=[System.IO.Path]::GetFullPath((Join-Path $root 'build\offline-20261024'))
if(!(Test-Path -LiteralPath $approved -PathType Container)){throw 'Approved offline scratch root must already exist'}
if(!$OutputDirectory){$OutputDirectory=Join-Path $approved ('raw-camera-capture-sim-'+(Get-Date -Format 'yyyyMMdd-HHmmss-fff'))}
$work=[System.IO.Path]::GetFullPath($OutputDirectory)
if(!$work.StartsWith($approved+[System.IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)){
    throw 'Simulation output must stay below the approved offline-20261024 scratch directory'
}
if(Test-Path -LiteralPath $work){throw 'Choose a new scratch output; previous evidence is append-only'}
New-Item -ItemType Directory -Path $work | Out-Null
$names=@('rtl\raw_camera_capture.v','rtl\camera_live_bridge.v','rtl\dvp_rgb565_capture.v',
    'rtl\rgb565_burst_pack.v','rtl\video_async_fifo.v','rtl\ddr_video_writer.v','rtl\ddr_uart_frame.v',
    'rtl\video_crc32.vh','rtl\ov5640_init.v','rtl\reg16_i2c.v','rtl\uart_tx.v',
    'board\ov5640_commands.vh','board\raw_camera_capture_top.v','tests\tb_raw_camera_capture.sv',
    'tools\run-raw-camera-capture-sim.ps1')
$hashes=@{}
foreach($name in $names){$hashes[$name]=(Get-FileHash -LiteralPath (Join-Path $root $name) -Algorithm SHA256).Hash}
$report=[ordered]@{Passed=$false;HardwareAccessed=$false;SyntheticOnly=$true;SourceSHA256=$hashes;
    SourceFiles=$names;OutputDirectory=$work;ImageSize=$(if($NativeVga){@(640,480)}else{@(32,16)});
    Limits='Core RTL simulation only; abstract board wrapper syntax checked. No new-module pinout, timing, stereo synchronization or optical validation.'}
Push-Location $work
try{
    $compile=$names | Where-Object {$_ -match '\.(v|sv)$'} | ForEach-Object {Join-Path $root $_}
    & (Join-Path $teamVivadoBin 'xvlog.bat') --sv @compile *> compile.log
    if($LASTEXITCODE){Get-Content compile.log -Tail 30;throw 'Raw capture compile failed'}
    $parameters=@()
    if($NativeVga){$parameters=@('-generic_top','"WIDTH=640"','-generic_top','"HEIGHT=480"','-generic_top','"VGA_ONLY=1"')}
    & (Join-Path $teamVivadoBin 'xelab.bat') tb_raw_camera_capture -s tb_raw_camera_capture @parameters *> elab.log
    if($LASTEXITCODE){Get-Content elab.log -Tail 30;throw 'Raw capture elaboration failed'}
    & (Join-Path $teamVivadoBin 'xsim.bat') tb_raw_camera_capture -runall -log simulation.log *> run.log
    $log=Get-Content -Raw simulation.log
    $passPattern=if($NativeVga){'(?m)^PASS raw camera capture native VGA:'}else{'(?m)^PASS raw camera capture regression:'}
    if($LASTEXITCODE -or $log -notmatch $passPattern -or $log -match '(?im)fatal:|error:'){
        Get-Content simulation.log -Tail 35;throw 'Raw capture simulation failed'
    }
    foreach($name in $names){if((Get-FileHash -LiteralPath (Join-Path $root $name)).Hash -ne $hashes[$name]){throw 'Source changed during simulation'}}
    $report.Passed=$true
    $report.SimulationLogSHA256=(Get-FileHash -LiteralPath 'simulation.log').Hash
    $report.SyntheticStreamSHA256=(Get-FileHash -LiteralPath 'raw-camera-capture-synthetic-stream.bin').Hash
    ($log -split "`r?`n") | Where-Object {$_ -match '^PASS '}
}finally{
    $report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $work 'raw-capture-simulation.json') -Encoding utf8
    Pop-Location
}
Write-Output ('Evidence: '+(Join-Path $work 'raw-capture-simulation.json'))
