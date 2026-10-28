param([string]$OutputDirectory='')
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'team-env.ps1')
$root=Split-Path -Parent $PSScriptRoot
$approved=[System.IO.Path]::GetFullPath((Join-Path $root 'build\offline-20261024'))
if(!(Test-Path -LiteralPath $approved -PathType Container)){throw 'Approved scratch root must exist'}
if(!$OutputDirectory){$OutputDirectory=Join-Path $approved ('thermal-idle-sim-'+(Get-Date -Format 'yyyyMMdd-HHmmss-fff'))}
$work=[System.IO.Path]::GetFullPath($OutputDirectory)
if(!$work.StartsWith($approved+[System.IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase) -or (Test-Path -LiteralPath $work)){throw 'Use a new output below approved scratch'}
New-Item -ItemType Directory -Path $work | Out-Null
$stub=Join-Path $root 'build\temperature_monitor_sim\digital-adc-stub.sv'
if(!(Test-Path -LiteralPath $stub)){throw 'Reviewed digital ADC fixture is absent; do not invent an analog model'}
Copy-Item -LiteralPath $stub -Destination (Join-Path $work 'digital-adc-stub.sv')
$names=@('rtl\thermal_idle_telemetry.v','rtl\logos2_temperature_monitor.v','rtl\adc_temperature_reader.v','rtl\uart_tx.v',
    'board\thermal_idle.v','tests\tb_thermal_idle_telemetry.sv','tests\tb_adc_temperature_reader.sv','tests\tb_logos2_temperature_monitor.sv',
    'tools\verify_thermal_idle_sim.py','tools\run-thermal-idle-sim.ps1')
$hashes=@{};foreach($name in $names){$hashes[$name]=(Get-FileHash -LiteralPath (Join-Path $root $name)).Hash}
$report=[ordered]@{Passed=$false;HardwareAccessed=$false;AnalogAccuracyVerified=$false;ThermalSafetyVerified=$false;
    SourceSHA256=$hashes;DigitalADCStubSHA256=(Get-FileHash -LiteralPath $stub).Hash;OutputDirectory=$work}
Push-Location $work
try{
    $files=@((Join-Path $work 'digital-adc-stub.sv'))+@($names | Where-Object {$_ -match '\.(v|sv)$'} | ForEach-Object {Join-Path $root $_})
    & (Join-Path $teamVivadoBin 'xvlog.bat') --sv @files *> compile.log
    if($LASTEXITCODE){Get-Content compile.log -Tail 25;throw 'Thermal idle compile failed'}
    foreach($top in @('tb_adc_temperature_reader','tb_logos2_temperature_monitor','tb_thermal_idle_telemetry')){
        & (Join-Path $teamVivadoBin 'xelab.bat') $top -s $top *> ($top+'-elab.log')
        if($LASTEXITCODE){Get-Content ($top+'-elab.log') -Tail 25;throw ('Thermal idle elaboration failed: '+$top)}
        & (Join-Path $teamVivadoBin 'xsim.bat') $top -runall -log ($top+'-simulation.log') *> ($top+'-run.log')
        $log=Get-Content -Raw ($top+'-simulation.log')
        if($LASTEXITCODE -or $log -notmatch '(?m)^PASS ' -or $log -match '(?im)fatal:|error:'){
            Get-Content ($top+'-simulation.log') -Tail 25;throw ('Thermal idle regression failed: '+$top)
        }
        ($log -split "`r?`n") | Where-Object {$_ -match '^PASS '}
    }
    $oldBytecode=$env:PYTHONDONTWRITEBYTECODE;$env:PYTHONDONTWRITEBYTECODE='1'
    try{& $teamPython (Join-Path $root 'tools\verify_thermal_idle_sim.py') (Join-Path $work 'thermal-idle-synthetic-lines.txt') --output (Join-Path $work 'thermal-idle-uart-readback.json')}
    finally{$env:PYTHONDONTWRITEBYTECODE=$oldBytecode}
    if($LASTEXITCODE){throw 'Independent UART snapshot/CRC readback failed'}
    foreach($name in $names){if((Get-FileHash -LiteralPath (Join-Path $root $name)).Hash -ne $hashes[$name]){throw 'Source changed during thermal simulation'}}
    $report.Passed=$true
    $report.LogSHA256=@{};foreach($log in Get-ChildItem -Filter '*-simulation.log'){$report.LogSHA256[$log.Name]=(Get-FileHash -LiteralPath $log.FullName).Hash}
}finally{
    $report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $work 'thermal-idle-simulation.json') -Encoding utf8
    Pop-Location
}
Write-Output ('Thermal simulation evidence: '+(Join-Path $work 'thermal-idle-simulation.json'))
