$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'check-live-temperature.ps1')
Assert-LiveTemperature 'TV=1 TR=A830 TF=00 TA=003EF0B6 AL=80' 12
Assert-LiveTemperature 'TV=0 TR=0000 TF=00 TA=02000000 AL=00' 2
$invalid=@(
    'TV=1 TR=B7B0 TF=00 TA=00000000 AL=80',
    'TV=1 TR=A830 TF=00 TA=00000000 AL=A0',
    'TV=0 TR=0000 TF=01 TA=00000000 AL=40',
    'TV=1 TR=A830 TF=00 TA=04000000 AL=80',
    'TV=1 TR=A830 TF=00 TA=00000000 AL=00',
    'TV=1 TR=0000 TF=00 TA=00000000 AL=80',
    'TV=1 TR=A830 TF=00 TA=00000000 AL=C0',
    'TV=1 TR=A830 TF=00 TA=00000000',
    'TV=1 TV=1 TR=A830 TF=00 TA=00000000 AL=80'
)
foreach($line in $invalid) {
    $rejected=$false
    try {Assert-LiveTemperature $line 12}catch {$rejected=$true}
    if(!$rejected){throw "Unsafe live telemetry was accepted: $line"}
}
Write-Output 'PASS live temperature guard: measured valid word, startup grace, and nine hot/alarm/fault/stale/zero/flags/incomplete/duplicate cases; no hardware accessed.'
