param([ValidateSet('corrected_host_cadence','corrected_gamma')][string]$Target='corrected_host_cadence')
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'team-env.ps1')
$root=Split-Path -Parent $PSScriptRoot
$prefix=if($Target -eq 'corrected_gamma'){'gamma'}else{'host-cadence'}
try{
    & (Join-Path $PSScriptRoot 'program-heartbeat.ps1') -Target $Target -Frequency 5MHz
    & $teamPython (Join-Path $PSScriptRoot 'host-angle.py') --auto 1 --execute --observe-seconds 40 --output (Join-Path $root ('results\lab-20261007\'+$prefix+'-auto-transaction.json'))
    if($LASTEXITCODE){throw 'Host automatic rotation test failed; raw transaction retained'}
}finally{
    $state=Get-Content -Raw -Encoding utf8 (Join-Path $root 'status.json') | ConvertFrom-Json
    if($state.current_sram_target -ne 'heartbeat'){
        & (Join-Path $PSScriptRoot 'program-heartbeat.ps1') -Target heartbeat -Frequency 5MHz
    }
}
