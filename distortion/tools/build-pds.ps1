param([ValidateSet('heartbeat','core','bringup','camera_init','camera_diag','camera_capture','camera_sweep','camera_sync','camera2','preview','ddr_check','camera_ddr','live_video','calibration_capture','corrected_video','corrected_capture','corrected_fast','corrected_rotate','corrected_early','corrected_overlap','corrected_tiled','corrected_adaptive','corrected_overlap_route','corrected_adaptive_seed2','corrected_pipeline_hit','corrected_pipeline_cadence_seed4','corrected_pipeline_parity_cadence','corrected_adaptive_cadence','corrected_host','corrected_host_cadence','corrected_gamma','corrected_gamma_d5','gamma_capture','gamma_capture_settled','gamma_capture_settled_d5','gamma_capture_colorbars','gamma_capture_colorbars_d5','camera_isp_probe')][string]$Target='heartbeat',[switch]$ValidateExisting)
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'team-env.ps1')
$projectRoot=Split-Path -Parent $PSScriptRoot
$buildRoot=Join-Path $projectRoot ('build\'+$Target)
$tcl=Join-Path $projectRoot $(if($Target -eq 'core'){'board\synthesize-core.tcl'}else{'board\build-'+$Target+'.tcl'})
New-Item -ItemType Directory -Force -Path $buildRoot | Out-Null
$buildStart=Get-Date
$pdsExit=0
$startedSources=@{}
$previousManifest=$null
if($ValidateExisting -and (Test-Path -LiteralPath (Join-Path $buildRoot 'validated-build.json'))) {
    $previousManifest=Get-Content -Raw (Join-Path $buildRoot 'validated-build.json') | ConvertFrom-Json
}
if(!$ValidateExisting){
    # This PDS release can retain cached compile/synthesis status even when
    # -force_to_run is present. Start real builds in an empty work directory.
    if(Test-Path -LiteralPath (Join-Path $buildRoot ($Target+'.pds'))) {
        $workspaceBuild=[System.IO.Path]::GetFullPath((Join-Path $projectRoot 'build'))
        $absoluteBuild=[System.IO.Path]::GetFullPath($buildRoot)
        $preservedBuild=Join-Path $workspaceBuild ('preserved-'+$Target+'-'+(Get-Date -Format 'yyyyMMdd-HHmmss-fff'))
        if(!$absoluteBuild.StartsWith($workspaceBuild+[System.IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase) -or
           !$preservedBuild.StartsWith($workspaceBuild+[System.IO.Path]::DirectorySeparatorChar,[StringComparison]::OrdinalIgnoreCase)){throw 'Build preservation path escaped workspace'}
        Move-Item -LiteralPath $absoluteBuild -Destination $preservedBuild
        New-Item -ItemType Directory -Path $buildRoot | Out-Null
    }
    if($Target -in @('corrected_fast','corrected_rotate','corrected_early','corrected_overlap','corrected_tiled','corrected_adaptive','corrected_overlap_route','corrected_adaptive_seed2','corrected_pipeline_hit','corrected_pipeline_cadence_seed4','corrected_pipeline_parity_cadence','corrected_adaptive_cadence','corrected_host','corrected_host_cadence','corrected_gamma','corrected_gamma_d5','gamma_capture','gamma_capture_settled','gamma_capture_settled_d5','gamma_capture_colorbars','gamma_capture_colorbars_d5','camera_isp_probe')) {
        $startedDependencies=Get-Content -Raw (Join-Path $projectRoot ('board\'+$Target+'-sources.json')) | ConvertFrom-Json
        foreach($src in $startedDependencies){$startedSources[$src]=(Get-FileHash -LiteralPath (Join-Path $projectRoot $src)).Hash}
    }
    # Keep original design files and their hashes intact; relocate paths only
    # in an effective build recipe stored with the resulting build.
    $portableTcl=Join-Path $buildRoot 'portable-build.tcl'
    $portableWorkspace=(Split-Path -Parent $projectRoot).Replace('\','/')
    (Get-Content -Raw -LiteralPath $tcl).Replace('D:/English/FPGA',$portableWorkspace) |
        Set-Content -LiteralPath $portableTcl -Encoding utf8
    & (Join-Path $teamPdsBin 'pds_shell.exe') -file $portableTcl -work_dir $buildRoot -project_name $Target *> (Join-Path $buildRoot 'build.log')
    $pdsExit=$LASTEXITCODE
}
$buildLog=Get-Content -Raw (Join-Path $buildRoot 'build.log')
$expected=if($Target -ne 'core'){'(?m)^Executing : gen_bit_stream\b[^\r\n]* successfully\.'}else{'(?m)^Executing : dev_map\b[^\r\n]* successfully\.'}
if($pdsExit -ne 0 -or $buildLog -match '(?m)^E:' -or $buildLog -notmatch $expected){
    Get-Content (Join-Path $buildRoot 'build.log') -Tail 40
    throw "PDS build failed: $Target"
}
if($Target -ne 'core'){
    $timingPath=$null
    $timingSHA=$null
    $bitFile=Get-Item -LiteralPath (Join-Path $buildRoot ('generate_bitstream\'+$Target+'.sbit'))
    if($previousManifest -and (Get-FileHash -LiteralPath $bitFile.FullName).Hash -ne $previousManifest.SHA256){throw 'Existing bitstream differs from its saved validation manifest'}
    if(!$ValidateExisting -and $bitFile.LastWriteTime -lt $buildStart){throw 'Bitstream is stale'}
    $sources=if($Target -eq 'heartbeat'){@('board\heartbeat.v','board\heartbeat.fdc','board\build-heartbeat.tcl')}else{
        @('board\bringup.v','board\bringup.fdc','board\build-bringup.tcl','board\hdmi_tx_init.v','board\ms7210_commands.vh','board\bringup_pll.v',
          'rtl\reg16_i2c.v','rtl\uart_tx.v','rtl\video_pattern.v','rtl\camera_id_probe.v')}
    foreach($src in $sources){
        if(!$ValidateExisting -and (Get-Item (Join-Path $projectRoot $src)).LastWriteTime -gt $bitFile.LastWriteTime){throw 'Source is newer than bitstream'}
    }
    if($Target -in @('camera_init','camera_capture','camera_sweep','camera_sync','camera2','preview','ddr_check','camera_ddr','live_video','calibration_capture','corrected_video','corrected_capture','corrected_fast','corrected_rotate','corrected_early','corrected_overlap','corrected_tiled','corrected_adaptive','corrected_overlap_route','corrected_adaptive_seed2','corrected_pipeline_hit','corrected_pipeline_cadence_seed4','corrected_pipeline_parity_cadence','corrected_adaptive_cadence','corrected_host','corrected_host_cadence','corrected_gamma','corrected_gamma_d5','gamma_capture','gamma_capture_settled','gamma_capture_settled_d5','gamma_capture_colorbars','gamma_capture_colorbars_d5','camera_isp_probe')) {
        foreach($src in @('board\camera_init.v','board\camera_init.fdc','board\build-camera_init.tcl','rtl\ov5640_init.v','board\ov5640_commands.vh')) {
            if(!$ValidateExisting -and (Get-Item (Join-Path $projectRoot $src)).LastWriteTime -gt $bitFile.LastWriteTime){throw 'Camera initialization source is newer than bitstream'}
        }
    }
    if($Target -in @('camera_capture','camera_sweep','camera_sync','camera2','preview','ddr_check','camera_ddr','live_video','calibration_capture','corrected_video','corrected_capture','corrected_fast','corrected_rotate','corrected_early','corrected_overlap','corrected_tiled','corrected_adaptive','corrected_overlap_route','corrected_adaptive_seed2','corrected_pipeline_hit','corrected_pipeline_cadence_seed4','corrected_pipeline_parity_cadence','corrected_adaptive_cadence','corrected_host','corrected_host_cadence','corrected_gamma','corrected_gamma_d5','gamma_capture','gamma_capture_settled','gamma_capture_settled_d5','gamma_capture_colorbars','gamma_capture_colorbars_d5','camera_isp_probe')) {
        foreach($src in @('board\camera_capture.v','board\camera_capture.fdc','board\build-camera_capture.tcl','rtl\dvp_rgb565_capture.v','rtl\dvp_monitor.v')) {
            if(!$ValidateExisting -and (Get-Item (Join-Path $projectRoot $src)).LastWriteTime -gt $bitFile.LastWriteTime){throw 'Capture source is newer than bitstream'}
        }
    }
    if($Target -eq 'camera_sweep') {
        foreach($src in @('board\camera_sweep.v','board\camera_sweep.fdc','board\build-camera_sweep.tcl','rtl\ov5640_pad_sweep.v')) {
            if(!$ValidateExisting -and (Get-Item (Join-Path $projectRoot $src)).LastWriteTime -gt $bitFile.LastWriteTime){throw 'Sweep source is newer than bitstream'}
        }
    }
    if($Target -eq 'camera_sync') {
        foreach($src in @('board\camera_sync.v','board\camera_sync.fdc','board\build-camera_sync.tcl')) {
            if(!$ValidateExisting -and (Get-Item (Join-Path $projectRoot $src)).LastWriteTime -gt $bitFile.LastWriteTime){throw 'Sync source is newer than bitstream'}
        }
    }
    if($Target -eq 'camera2') {
        foreach($src in @('board\camera2.v','board\camera2.fdc','board\build-camera2.tcl')) {
            if(!$ValidateExisting -and (Get-Item (Join-Path $projectRoot $src)).LastWriteTime -gt $bitFile.LastWriteTime){throw 'Camera2 source is newer than bitstream'}
        }
    }
    if($Target -eq 'preview') {
        foreach($src in @('board\preview.v','board\preview.fdc','board\build-preview.tcl','rtl\camera_preview.v')) {
            if(!$ValidateExisting -and (Get-Item (Join-Path $projectRoot $src)).LastWriteTime -gt $bitFile.LastWriteTime){throw 'Preview source is newer than bitstream'}
        }
    }
    if($Target -eq 'ddr_check') {
        foreach($src in @('board\ddr_check.v','board\ddr_check.fdc','board\build-ddr_check.tcl','rtl\camera_preview.v','rtl\ddr_integrity_test.v','platform\video_base\ipcore\ddr3_test\ddr3_test.idf')) {
            if(!$ValidateExisting -and (Get-Item (Join-Path $projectRoot $src)).LastWriteTime -gt $bitFile.LastWriteTime){throw 'DDR source is newer than bitstream'}
        }
    }
    if($Target -eq 'camera_ddr') {
        foreach($src in @('board\camera_ddr.v','board\camera_ddr.fdc','board\build-camera_ddr.tcl','rtl\camera_preview.v','rtl\rgb565_burst_pack.v','rtl\video_async_fifo.v','rtl\camera_ddr_bridge.v','rtl\ddr_frame_store.v','platform\video_base\ipcore\ddr3_test\ddr3_test.idf')) {
            if(!$ValidateExisting -and (Get-Item (Join-Path $projectRoot $src)).LastWriteTime -gt $bitFile.LastWriteTime){throw 'Camera DDR source is newer than bitstream'}
        }
    }
    if($Target -eq 'live_video') {
        foreach($src in @('board\live_video.v','board\live_video.fdc','board\build-live_video.tcl','rtl\rgb565_burst_pack.v','rtl\video_async_fifo.v','rtl\camera_live_bridge.v','rtl\ddr_video_writer.v','rtl\ddr_video_reader.v','rtl\ddr_video_output.v','rtl\ddr_live_video.v','rtl\video_crc32.vh','platform\video_base\ipcore\ddr3_test\ddr3_test.idf')) {
            if(!$ValidateExisting -and (Get-Item (Join-Path $projectRoot $src)).LastWriteTime -gt $bitFile.LastWriteTime){throw 'Live video source is newer than bitstream'}
        }
    }
    if($Target -eq 'calibration_capture') {
        foreach($src in @('board\calibration_capture.v','board\calibration_capture.fdc','board\build-calibration_capture.tcl','rtl\ddr_uart_frame.v','rtl\camera_live_bridge.v','rtl\ddr_video_writer.v','rtl\camera_preview.v','rtl\rgb565_burst_pack.v','rtl\video_async_fifo.v','rtl\video_crc32.vh','platform\video_base\ipcore\ddr3_test\ddr3_test.idf')) {
            if(!$ValidateExisting -and (Get-Item (Join-Path $projectRoot $src)).LastWriteTime -gt $bitFile.LastWriteTime){throw 'Calibration capture source is newer than bitstream'}
        }
    }
    if($Target -eq 'corrected_video') {
        foreach($src in @('board\corrected_video.v','board\corrected_video.fdc','board\build-corrected_video.tcl','board\calibration-trial.vh','rtl\ddr_corrected_video.v','rtl\remap_frame_engine.v','rtl\ddr_read_arbiter.v','rtl\ddr_write_arbiter.v','rtl\ddr_result_writer.v','rtl\brown_remap_core.v','rtl\brown_inverse_mapper.v','rtl\mul32_pipe.v','rtl\ddr_remap_sample.v','rtl\ddr_neighbour_cache.v','rtl\bilinear_rgb.v')) {
            if(!$ValidateExisting -and (Get-Item (Join-Path $projectRoot $src)).LastWriteTime -gt $bitFile.LastWriteTime){throw 'Correction source is newer than bitstream'}
        }
    }
    if($Target -eq 'corrected_capture') {
        foreach($src in @('board\corrected_capture.v','board\corrected_capture.fdc','board\build-corrected_capture.tcl','board\calibration-trial.vh','rtl\ddr_uart_frame.v','rtl\ddr_corrected_capture.v','rtl\remap_frame_engine.v','rtl\ddr_result_writer.v','rtl\brown_remap_core.v','rtl\brown_inverse_mapper.v','rtl\mul32_pipe.v','rtl\ddr_remap_sample.v','rtl\ddr_neighbour_cache.v','rtl\bilinear_rgb.v')) {
            if(!$ValidateExisting -and (Get-Item (Join-Path $projectRoot $src)).LastWriteTime -gt $bitFile.LastWriteTime){throw 'Corrected capture source is newer than bitstream'}
        }
    }
    if($Target -in @('corrected_fast','corrected_rotate','corrected_early','corrected_overlap','corrected_tiled','corrected_adaptive','corrected_overlap_route','corrected_adaptive_seed2','corrected_pipeline_hit','corrected_pipeline_cadence_seed4','corrected_pipeline_parity_cadence','corrected_adaptive_cadence','corrected_host','corrected_host_cadence','corrected_gamma','corrected_gamma_d5','gamma_capture','gamma_capture_settled','gamma_capture_settled_d5','gamma_capture_colorbars','gamma_capture_colorbars_d5','camera_isp_probe')) {
        if(!$ValidateExisting) {
            foreach($phase in @("synthesize\${Target}_syn.adf","device_map\${Target}_map.adf","place_route\${Target}_pnr.adf")) {
                if((Get-Item -LiteralPath (Join-Path $buildRoot $phase)).LastWriteTime -lt $buildStart){throw "PDS reused stale flow DB: $phase"}
            }
        }
        $dependencies=Get-Content -Raw (Join-Path $projectRoot ('board\'+$Target+'-sources.json')) | ConvertFrom-Json
        $sourceHashes=@{}
        foreach($src in $dependencies) {
            if(!$ValidateExisting -and (Get-Item (Join-Path $projectRoot $src)).LastWriteTime -gt $bitFile.LastWriteTime){throw "Optimized board source is newer than bitstream: $src"}
            $sourceHashes[$src]=(Get-FileHash -LiteralPath (Join-Path $projectRoot $src)).Hash
            if(!$ValidateExisting -and $startedSources[$src] -ne $sourceHashes[$src]){throw "Source changed while PDS was building: $src"}
            if($previousManifest -and $previousManifest.SourceSHA256) {
                $oldHash=$previousManifest.SourceSHA256.PSObject.Properties[$src]
                if(!$oldHash -or $oldHash.Value -ne $sourceHashes[$src]){throw "Source hash differs from saved build: $src"}
            }
        }
        $sourceHashes['board/'+$Target+'-pins.json']=(Get-FileHash -LiteralPath (Join-Path $projectRoot ('board\'+$Target+'-pins.json'))).Hash
        if($previousManifest -and $previousManifest.SourceSHA256) {
            $pinKey='board/'+$Target+'-pins.json'
            if($previousManifest.SourceSHA256.PSObject.Properties[$pinKey].Value -ne $sourceHashes[$pinKey]){throw 'Expected pin map differs from saved build'}
        }
    }
    if($Target -eq 'camera_diag') {
        foreach($src in @('board\camera_diag.v','board\camera_diag.fdc','board\build-camera_diag.tcl','rtl\ov5640_bus_diagnostic.v')) {
            if(!$ValidateExisting -and (Get-Item (Join-Path $projectRoot $src)).LastWriteTime -gt $bitFile.LastWriteTime){throw 'Diagnostic source is newer than bitstream'}
        }
    }
    if($buildLog -notmatch '(?m)^Executing : gen_bit_stream\b(?=[^\r\n]*-scbv \{High Voltage\})(?=[^\r\n]*-unused_io_status UNUSED)[^\r\n]* successfully\.'){throw 'Missing verified successful bitstream configuration options'}
    if($Target -in @('bringup','camera_init','camera_diag','camera_capture','camera_sweep','camera_sync','camera2','preview','ddr_check','camera_ddr','live_video','calibration_capture','corrected_video','corrected_capture','corrected_fast','corrected_rotate','corrected_early','corrected_overlap','corrected_tiled','corrected_adaptive','corrected_overlap_route','corrected_adaptive_seed2','corrected_pipeline_hit','corrected_pipeline_cadence_seed4','corrected_pipeline_parity_cadence','corrected_adaptive_cadence','corrected_host','corrected_host_cadence','corrected_gamma','corrected_gamma_d5','gamma_capture','gamma_capture_settled','gamma_capture_settled_d5','gamma_capture_colorbars','gamma_capture_colorbars_d5','camera_isp_probe')) {
        $pinFile=if($Target -in @('camera_capture','camera_sweep','camera_sync','camera2','preview','ddr_check','camera_ddr','live_video','calibration_capture','corrected_video','corrected_capture','corrected_fast','corrected_rotate','corrected_early','corrected_overlap','corrected_tiled','corrected_adaptive','corrected_overlap_route','corrected_adaptive_seed2','corrected_pipeline_hit','corrected_pipeline_cadence_seed4','corrected_pipeline_parity_cadence','corrected_adaptive_cadence','corrected_host','corrected_host_cadence','corrected_gamma','corrected_gamma_d5','gamma_capture','gamma_capture_settled','gamma_capture_settled_d5','gamma_capture_colorbars','gamma_capture_colorbars_d5','camera_isp_probe')){'board\'+$Target+'-pins.json'}else{'board\bringup-pins.json'}
        $pinMap=Get-Content -Raw (Join-Path $projectRoot $pinFile) | ConvertFrom-Json
        $pinReport=Get-Content -Raw (Join-Path $buildRoot ('place_route\'+$Target+'_prr.prt'))
        foreach($p in $pinMap.PSObject.Properties) {
            if($pinReport -notmatch ('(?m)^'+[regex]::Escape($p.Value)+'\|[^\r\n]*\|'+[regex]::Escape($p.Name)+'\|')) {
                throw "Unverified routed pin: $($p.Name)"
            }
        }
        $timingPath=Join-Path $buildRoot ('place_route\'+$Target+'_timing_summary_after_hold_fix.txt')
        if($Target -in @('corrected_video','corrected_capture','corrected_fast','corrected_rotate','corrected_early','corrected_overlap','corrected_tiled','corrected_adaptive','corrected_overlap_route','corrected_adaptive_seed2','corrected_pipeline_hit','corrected_pipeline_cadence_seed4','corrected_pipeline_parity_cadence','corrected_adaptive_cadence','corrected_host','corrected_host_cadence','corrected_gamma','corrected_gamma_d5','gamma_capture','gamma_capture_settled','gamma_capture_settled_d5','gamma_capture_colorbars','gamma_capture_colorbars_d5','camera_isp_probe')) {
            # PDS can perform another hold fix after emitting its PNR summary.
            # Gate the final report produced from the saved final routed DB.
            $timingPath=Join-Path $buildRoot ('report_timing\'+$Target+'.rtr')
            if(!$ValidateExisting) {
                $routedDB=Get-Item (Join-Path $buildRoot ('place_route\'+$Target+'_pnr.adf'))
                if((Get-Item $timingPath).LastWriteTime -lt $routedDB.LastWriteTime){throw 'Final timing report is older than routed DB'}
                if($bitFile.LastWriteTime -lt (Get-Item $timingPath).LastWriteTime){throw 'Bitstream predates final timing report'}
            }
        }
        $timingSHA=(Get-FileHash -LiteralPath $timingPath).Hash
        if($previousManifest -and $previousManifest.TimingSHA256 -and $timingSHA -ne $previousManifest.TimingSHA256){throw 'Existing final timing report differs from saved validation manifest'}
        $timing=Get-Content -Raw $timingPath
        if($timing -notmatch 'All Constraints Met'){throw 'Bringup timing failed'}
        if($Target -in @('corrected_video','corrected_capture','corrected_fast','corrected_rotate','corrected_early','corrected_overlap','corrected_tiled','corrected_adaptive','corrected_overlap_route','corrected_adaptive_seed2','corrected_pipeline_hit','corrected_pipeline_cadence_seed4','corrected_pipeline_parity_cadence','corrected_adaptive_cadence','corrected_host','corrected_host_cadence','corrected_gamma','corrected_gamma_d5','gamma_capture','gamma_capture_settled','gamma_capture_settled_d5','gamma_capture_colorbars','gamma_capture_colorbars_d5','camera_isp_probe')) {
            foreach($signature in @('Device\s+: PG2L100H','Package\s+: FBG676','Setup Summary\(Slow Corner\)','Hold Summary\(Fast Corner\)')) {
                if($timing -notmatch $signature){throw 'Final timing report device or corner coverage differs'}
            }
        }
    }
    [pscustomobject]@{Timestamp=(Get-Date).ToString('o');Bitstream=$bitFile.FullName;
        SHA256=(Get-FileHash -LiteralPath $bitFile.FullName).Hash;SCBV='High Voltage';
        Device='PG2L100H';Package='FBG676';UnusedIO='UNUSED';TimingReport=$timingPath;
        TimingSHA256=$timingSHA;SourceSHA256=$sourceHashes} |
        ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $buildRoot 'validated-build.json') -Encoding utf8
}
Get-Content (Join-Path $buildRoot 'build.log') -Tail 18

