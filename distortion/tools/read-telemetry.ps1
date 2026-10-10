param([string]$Port='COM5',[int]$Seconds=6,[ValidateSet('bringup','camera_init','camera_diag','camera_capture','camera_sweep','camera_sync','camera2','preview','ddr_check','camera_ddr','live_video','corrected_video','corrected_fast','corrected_rotate','corrected_early','corrected_overlap','corrected_tiled','corrected_adaptive','corrected_overlap_route','corrected_adaptive_seed2','corrected_pipeline_hit','corrected_pipeline_cadence_seed4','corrected_pipeline_parity_cadence','corrected_adaptive_cadence','corrected_host','corrected_host_cadence','corrected_gamma','corrected_gamma_d5')][string]$Target='bringup')
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot 'check-live-temperature.ps1')
$work=Join-Path $root ('build\'+$Target)
$serial=[System.IO.Ports.SerialPort]::new($Port,115200,[System.IO.Ports.Parity]::None,8,[System.IO.Ports.StopBits]::One)
$serial.ReadTimeout=500
$serial.DtrEnable=$false
$serial.RtsEnable=$false
$samples=[System.Collections.Generic.List[object]]::new()
$pendingLine=''
$captureStarted=[DateTime]::UtcNow
try {
    $serial.Open()
    $limit=[DateTime]::UtcNow.AddSeconds($Seconds)
    $text=''
    while([DateTime]::UtcNow -lt $limit) {
        $chunk=$serial.ReadExisting()
        if($chunk){
            $text+=$chunk
            $pendingLine+=$chunk
            while($pendingLine.Contains("`n")){
                $newline=$pendingLine.IndexOf("`n")
                $line=$pendingLine.Substring(0,$newline).TrimEnd("`r")
                $pendingLine=$pendingLine.Substring($newline+1)
                if($line.StartsWith('CAM=')){
                    $samples.Add([pscustomobject]@{ReceivedUtc=[DateTime]::UtcNow.ToString('o');Line=$line})
                    if($Target -in @('corrected_rotate','corrected_early','corrected_overlap','corrected_tiled','corrected_adaptive','corrected_overlap_route','corrected_adaptive_seed2','corrected_pipeline_hit','corrected_pipeline_cadence_seed4','corrected_pipeline_parity_cadence','corrected_adaptive_cadence','corrected_host','corrected_host_cadence','corrected_gamma','corrected_gamma_d5')) {
                        Assert-LiveTemperature -Line $line -ElapsedSeconds ([DateTime]::UtcNow-$captureStarted).TotalSeconds
                    }
                }
            }
            Write-Output $chunk
            $text | Set-Content -LiteralPath (Join-Path $work 'telemetry.txt') -Encoding utf8
        }
        Start-Sleep -Milliseconds 100
    }
    if(!$text){throw "No UART telemetry received on $Port"}
    $text | Set-Content -LiteralPath (Join-Path $work 'telemetry.txt') -Encoding utf8
} finally {
    # Preserve a partial capture if the user powers off or swaps the hardware.
    if($text){$text | Set-Content -LiteralPath (Join-Path $work 'telemetry.txt') -Encoding utf8}
    [pscustomobject]@{Port=$Port;StartedUtc=$captureStarted.ToString('o');EndedUtc=[DateTime]::UtcNow.ToString('o');Samples=@($samples.ToArray())} |
        ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $work 'telemetry-timed.json') -Encoding utf8
    if($serial.IsOpen){$serial.Close()}; $serial.Dispose()
    # User laboratory policy (2026-10-07): stop heavy FPGA logic between
    # finite tests. Closing the COM port alone does not stop the FPGA.
    # Replace volatile SRAM with the proved, low-load LED heartbeat target.
    & (Join-Path $PSScriptRoot 'program-heartbeat.ps1') -Target heartbeat -Frequency 5MHz *> (Join-Path $work 'idle-after-test.log')
    $idleTransfers=Get-ChildItem -LiteralPath (Join-Path $root 'build\heartbeat') -Directory -Filter 'program-evidence-*' |
        Sort-Object LastWriteTime | Select-Object -Last 1
    $idleProof=Get-Content -Raw (Join-Path $idleTransfers.FullName 'transfer.json') | ConvertFrom-Json
    if(!$idleProof.Done -or $idleProof.Target -ne 'heartbeat'){throw 'Idle SRAM transfer was not verified'}
    $idleProof | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $work 'idle-after-test.json') -Encoding utf8
    Write-Output 'Test finished: FPGA is running the low-load heartbeat; DDR/remap/video logic is stopped.'
}
