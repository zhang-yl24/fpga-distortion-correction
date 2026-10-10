param([double]$Angle=13.7,[ValidateRange(0,30)][int]$ObserveSeconds=16,
    [ValidateSet('corrected_host','corrected_host_cadence','corrected_gamma')][string]$Target='corrected_host')
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
$tag=$Angle.ToString('0.###',[Globalization.CultureInfo]::InvariantCulture).Replace('.','_').Replace('-','minus')
if($Target -eq 'corrected_host_cadence'){$tag='cadence_'+$tag}
if($Target -eq 'corrected_gamma'){$tag='gamma_'+$tag}
$report=Join-Path $root ('results\lab-20261007\host-angle-'+$tag+'-transaction.json')
try {
    & (Join-Path $PSScriptRoot 'program-heartbeat.ps1') -Target $Target -Frequency 5MHz
    & 'C:\Users\22955\AppData\Local\Programs\Python\Python313\python.exe' (Join-Path $PSScriptRoot 'host-angle.py') --angle $Angle --execute --observe-seconds $ObserveSeconds --output $report
    if($LASTEXITCODE){throw 'Host angle command or finite observation failed; see saved transaction'}
}finally{
    $state=Get-Content -Raw -Encoding utf8 (Join-Path $root 'status.json') | ConvertFrom-Json
    if($state.current_sram_target -ne 'heartbeat'){
        & (Join-Path $PSScriptRoot 'program-heartbeat.ps1') -Target heartbeat -Frequency 5MHz
    }
}
