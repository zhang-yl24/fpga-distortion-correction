param([ValidateSet('heartbeat','bringup','camera_init','camera_diag','camera_capture','camera_sweep','camera_sync','camera2','preview','ddr_check','camera_ddr','live_video','calibration_capture','corrected_video','corrected_capture','corrected_fast','corrected_rotate','corrected_early','corrected_overlap','corrected_tiled','corrected_adaptive','corrected_overlap_route','corrected_adaptive_seed2','corrected_pipeline_hit','corrected_pipeline_cadence_seed4','corrected_pipeline_parity_cadence','corrected_adaptive_cadence','corrected_host','corrected_host_cadence','corrected_gamma','corrected_gamma_d5','gamma_capture','gamma_capture_settled','gamma_capture_settled_d5','gamma_capture_colorbars','gamma_capture_colorbars_d5','camera_isp_probe')][string]$Target='heartbeat',
    [ValidateSet('10MHz','5MHz','1MHz','500KHz','100KHz')][string]$Frequency='5MHz',
    [ValidateRange(0,300)][int]$MinimumIdleSeconds=60,
    [switch]$ValidateOnly)
# Volatile SRAM configuration only. No Flash/eFuse operations.
$ErrorActionPreference='Stop'
$projectRoot=Split-Path -Parent $PSScriptRoot
$buildRoot=Join-Path $projectRoot ('build\'+$Target)
$pdsBin='E:\Pango\PDS_2022.2-SP6.4\bin'
if($Target -in @('gamma_capture','gamma_capture_settled','gamma_capture_settled_d5','gamma_capture_colorbars','gamma_capture_colorbars_d5')) {
    & 'C:\Users\22955\AppData\Local\Programs\Python\Python313\python.exe' (Join-Path $PSScriptRoot 'validate-gamma-capture.py')
    if($LASTEXITCODE -ne 0){throw 'Gamma capture native regression gate failed; refusing hardware access'}
}
if($Target -in @('gamma_capture_settled','gamma_capture_colorbars')) {
    & 'C:\Users\22955\AppData\Local\Programs\Python\Python313\python.exe' (Join-Path $PSScriptRoot 'validate-camera-color-candidate.py') --target $Target
    if($LASTEXITCODE -ne 0){throw 'Isolated camera-color guard failed; refusing hardware access'}
}
if($Target -eq 'camera_isp_probe') {
    & 'C:\Users\22955\AppData\Local\Programs\Python\Python313\python.exe' (Join-Path $PSScriptRoot 'validate-camera-state-probe.py')
    if($LASTEXITCODE -ne 0){throw 'Camera ISP read-only simulation gate failed'}
}
if($Target -eq 'corrected_pipeline_cadence_seed4') {
    & 'C:\Users\22955\AppData\Local\Programs\Python\Python313\python.exe' (Join-Path $PSScriptRoot 'prepare-pipeline-cadence-candidate.py') --validate
    if($LASTEXITCODE -ne 0){throw 'Pipeline candidate regression guard failed'}
}
if($Target -eq 'corrected_pipeline_parity_cadence') {
    & 'C:\Users\22955\AppData\Local\Programs\Python\Python313\python.exe' (Join-Path $PSScriptRoot 'prepare-parity-board-candidate.py') --validate
    if($LASTEXITCODE -ne 0){throw 'Parity candidate full native regression gate failed'}
}
if($Target -in @('gamma_capture_settled_d5','gamma_capture_colorbars_d5','corrected_gamma_d5')) {
    & 'C:\Users\22955\AppData\Local\Programs\Python\Python313\python.exe' (Join-Path $PSScriptRoot 'prepare-d5-fixed-candidates.py') --validate --target $Target
    if($LASTEXITCODE -ne 0){throw 'D5 correction isolation gate failed'}
}
if($Target -in @('corrected_video','corrected_capture','corrected_fast','corrected_rotate','corrected_early','corrected_overlap','corrected_tiled','corrected_adaptive','corrected_overlap_route','corrected_adaptive_seed2','corrected_pipeline_hit','corrected_pipeline_cadence_seed4','corrected_pipeline_parity_cadence','corrected_adaptive_cadence','corrected_host','corrected_host_cadence','corrected_gamma','corrected_gamma_d5','gamma_capture','gamma_capture_settled','gamma_capture_settled_d5','gamma_capture_colorbars','gamma_capture_colorbars_d5','camera_isp_probe')) {
    & (Join-Path $PSScriptRoot 'build-pds.ps1') -Target $Target -ValidateExisting | Out-Null
}
$manifest=Get-Content -Raw (Join-Path $buildRoot 'validated-build.json') | ConvertFrom-Json
$bitFile=Join-Path $buildRoot ('generate_bitstream\'+$Target+'.sbit')
if($manifest.Bitstream -ne $bitFile -or $manifest.SCBV -ne 'High Voltage' -or $manifest.Device -ne 'PG2L100H' -or
    (Get-FileHash -LiteralPath $bitFile).Hash -ne $manifest.SHA256){throw 'Bitstream validation failed'}
$pinReport=Get-Content -Raw (Join-Path $buildRoot ('place_route\'+$Target+'_prr.prt'))
$pins=@{'clk_27m'='D18';'led[0]'='A20';'led[1]'='C18';'led[2]'='C19';'led[3]'='E18';'led[4]'='A17';'led[5]'='A18';'led[6]'='C17';'led[7]'='B17'}
if($Target -in @('bringup','camera_init','camera_diag','camera_capture','camera_sweep','camera_sync','camera2','preview','ddr_check','camera_ddr','live_video','calibration_capture','corrected_video','corrected_capture','corrected_fast','corrected_rotate','corrected_early','corrected_overlap','corrected_tiled','corrected_adaptive','corrected_overlap_route','corrected_adaptive_seed2','corrected_pipeline_hit','corrected_pipeline_cadence_seed4','corrected_pipeline_parity_cadence','corrected_adaptive_cadence','corrected_host','corrected_host_cadence','corrected_gamma','corrected_gamma_d5','gamma_capture','gamma_capture_settled','gamma_capture_settled_d5','gamma_capture_colorbars','gamma_capture_colorbars_d5','camera_isp_probe')) {
    $pins=@{}
    $pinFile=if($Target -in @('camera_capture','camera_sweep','camera_sync','camera2','preview','ddr_check','camera_ddr','live_video','calibration_capture','corrected_video','corrected_capture','corrected_fast','corrected_rotate','corrected_early','corrected_overlap','corrected_tiled','corrected_adaptive','corrected_overlap_route','corrected_adaptive_seed2','corrected_pipeline_hit','corrected_pipeline_cadence_seed4','corrected_pipeline_parity_cadence','corrected_adaptive_cadence','corrected_host','corrected_host_cadence','corrected_gamma','corrected_gamma_d5','gamma_capture','gamma_capture_settled','gamma_capture_settled_d5','gamma_capture_colorbars','gamma_capture_colorbars_d5','camera_isp_probe')){'board\'+$Target+'-pins.json'}else{'board\bringup-pins.json'}
    $pinMap=Get-Content -Raw (Join-Path $projectRoot $pinFile) | ConvertFrom-Json
    foreach($p in $pinMap.PSObject.Properties){$pins[$p.Name]=$p.Value}
    if(!$ValidateOnly -and $pins.ContainsKey('cam_data[5]') -and $pins['cam_data[5]'] -ne 'AA23') {
        throw 'Known D5 mapping defect: old AA22 camera builds are historical validation only; program an AA23 correction target'
    }

}
foreach($port in $pins.Keys){
    if($pinReport -notmatch ('(?m)^'+[regex]::Escape($pins[$port])+'\|[^\r\n]*\|'+[regex]::Escape($port)+'\|')){throw "Missing verified pin: $port"}
}
$timingPath=if($manifest.TimingReport){$manifest.TimingReport}else{Join-Path $buildRoot ('place_route\'+$Target+'_timing_summary_after_hold_fix.txt')}
if($manifest.TimingSHA256 -and (Get-FileHash -LiteralPath $timingPath).Hash -ne $manifest.TimingSHA256){throw 'Timing report hash differs from manifest'}
$timing=Get-Content -Raw $timingPath
if($timing -notmatch 'All Constraints Met'){throw 'Board timing check failed'}
if($ValidateOnly) {
    [pscustomobject]@{Target=$Target;SHA256=$manifest.SHA256;VerifiedPins=$pins.Count;Timing=$timingPath;HardwareAccessed=$false} | ConvertTo-Json
    return
}
$ownedServer=$null
$ownedClient=$null
try{
    $statusFile=Join-Path $projectRoot 'status.json'
    if($Target -ne 'heartbeat' -and (Test-Path -LiteralPath $statusFile)) {
        $restStatus=Get-Content -Raw -Encoding UTF8 $statusFile | ConvertFrom-Json
        if($restStatus.thermal_test_policy -and $restStatus.current_sram_target -eq 'heartbeat') {
            $idleAt=[DateTimeOffset]::Parse($restStatus.current_connection.checked_on).ToUniversalTime()
            $elapsedIdle=([DateTimeOffset]::UtcNow-$idleAt).TotalSeconds
            $remainingIdle=[Math]::Ceiling($MinimumIdleSeconds-$elapsedIdle)
            if($remainingIdle -gt 300){throw 'Idle timestamp is in the future; check clock before hardware test'}
            if($remainingIdle -gt 0) {
                Write-Output "Cooling hold: keep low-load heartbeat for $remainingIdle more seconds before $Target."
                while($remainingIdle -gt 0) {
                    $sleepPart=[Math]::Min(30,$remainingIdle)
                    Start-Sleep -Seconds $sleepPart
                    $remainingIdle-=$sleepPart
                }
            }
        }
    }
    # Use a server owned by this call; avoid interfering with an open PDS GUI.
    # The NetTCPConnection cmdlet depends on CIM access, which may be unavailable
    # in a restricted local session. Query listeners directly without CIM.
    $listeners=[System.Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties().GetActiveTcpListeners()
    if($listeners | Where-Object {$_.Port -eq 65420}){throw 'JTAG server port is occupied'}
    $ownedServer=Start-Process -FilePath (Join-Path $pdsBin 'cdt_js.exe') -ArgumentList @('-port','65420','-work_dir',$buildRoot) -WorkingDirectory $buildRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $buildRoot 'server.out.txt') -RedirectStandardError (Join-Path $buildRoot 'server.err.txt')
    Start-Sleep -Seconds 2
    foreach($stage in @('scan','program')){
        $tcl=if($stage -eq 'scan'){'D:\English\FPGA\hardware_check\scan-only.tcl'}else{Join-Path $projectRoot ('board\program-'+$Target+'.tcl')}
        if($Frequency -ne '1MHz') {
            $slowTcl=Join-Path $buildRoot ($stage+'-'+$Frequency+'.tcl')
            (Get-Content -Raw $tcl).Replace('-freq 1MHz','-freq '+$Frequency) | Set-Content -LiteralPath $slowTcl -Encoding ascii
            $tcl=$slowTcl
        }
        $out=Join-Path $buildRoot ($stage+'.out.txt');$err=Join-Path $buildRoot ($stage+'.err.txt')
        $ownedClient=Start-Process -FilePath (Join-Path $pdsBin 'cdt_cfg_shell.exe') -ArgumentList @('-file',$tcl,'-work_dir',$buildRoot) -WorkingDirectory $buildRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput $out -RedirectStandardError $err
        # Retain the Windows process handle before it exits. Without this,
        # Windows PowerShell can return a null ExitCode for a finished child.
        $null=$ownedClient.Handle
        $timeoutSeconds=if($stage -eq 'scan'){60}else{switch($Frequency){'100KHz'{600};'500KHz'{180};default{90}}}
        $deadline=[DateTime]::UtcNow.AddSeconds($timeoutSeconds)
        while(!$ownedClient.WaitForExit(1000)) {
            if([DateTime]::UtcNow -ge $deadline){throw "JTAG $stage timed out"}
        }
        $log=Get-Content -Raw $out
        if($null -eq $ownedClient.ExitCode -or $ownedClient.ExitCode -ne 0 -or $log -match '(?im)error|failed' -or (Get-Item $err).Length -gt 0){throw "JTAG $stage failed (exit=$($ownedClient.ExitCode), stderr_bytes=$((Get-Item $err).Length)); see $out"}
        if($stage -eq 'scan'){
            $devices=[regex]::Matches($log,'(?m)^PG\w+\s*$')
            if($devices.Count -ne 1 -or $devices[0].Value.Trim() -ne 'PG2L100H' -or $log -notmatch '0x00602899'){throw 'Unexpected JTAG device; refusing configuration'}
        }else{
            if($log -notmatch '(?m)^Executing : cfg_program\b[^\r\n]* successfully\.' -or $log -notmatch 'done bit\): 1'){throw 'Configuration DONE not confirmed'}
            Write-Output $log
            # Keep each verified transfer's evidence before the next run.
            $archive=Join-Path $buildRoot ('program-evidence-'+(Get-Date -Format 'yyyyMMdd-HHmmss')+'-'+$Frequency)
            New-Item -ItemType Directory -Path $archive | Out-Null
            foreach($name in @('scan.out.txt','scan.err.txt','program.out.txt','program.err.txt','validated-build.json')) {
                Copy-Item -LiteralPath (Join-Path $buildRoot $name) -Destination (Join-Path $archive $name)
            }
            $transferCheckedOn=(Get-Date).ToString('o')
            [pscustomobject]@{Frequency=$Frequency;Device=$manifest.Device;SHA256=$manifest.SHA256;Target=$Target;Done=$true;CheckedOn=$transferCheckedOn} |
                ConvertTo-Json | Set-Content -LiteralPath (Join-Path $archive 'transfer.json') -Encoding utf8
            $statusFile=Join-Path $projectRoot 'status.json'
            if(Test-Path -LiteralPath $statusFile) {
                $status=Get-Content -Raw -Encoding UTF8 $statusFile | ConvertFrom-Json
                $status.current_sram_target=$Target
                $status.current_connection.last_programmed_target=$Target
                $status.current_connection.last_programmed_sha256=$manifest.SHA256
                $status.current_connection.checked_on=$transferCheckedOn
                $status.current_connection.available_for_testing=$true
                $status.current_connection.session_state=if($Target -eq 'heartbeat'){'idle_between_tests'}else{'board_connected_user_confirmed_and_programmed'}
                $overTempMatch=[regex]::Match($log,'Bit 27:\s+([01])\s+over_temp')
                if($overTempMatch.Success){$status.current_connection.over_temp_status_bit=[int]$overTempMatch.Groups[1].Value}
                $status.current_connection | Add-Member -NotePropertyName temperature_currently_available -NotePropertyValue $false -Force
                $status | ConvertTo-Json -Depth 40 | Set-Content -LiteralPath $statusFile -Encoding utf8
            }
        }
    }
}finally{
    if($ownedClient -and !$ownedClient.HasExited){Stop-Process -Id $ownedClient.Id -ErrorAction SilentlyContinue}
    if($ownedServer -and !$ownedServer.HasExited){Stop-Process -Id $ownedServer.Id -ErrorAction SilentlyContinue}
}

