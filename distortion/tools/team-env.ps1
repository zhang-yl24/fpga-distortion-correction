# Local tool paths, shared by the portable team entry points. No credentials here.
$teamWorkspace = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$teamConfigPath = Join-Path $teamWorkspace 'team-config.local.json'
$teamConfig = @{}
if (Test-Path -LiteralPath $teamConfigPath) {
    $teamConfig = Get-Content -Raw -LiteralPath $teamConfigPath | ConvertFrom-Json
}
$teamPython = if ($env:FPGA_PYTHON) { $env:FPGA_PYTHON } elseif ($teamConfig.python) { $teamConfig.python } else { 'python' }
if ($teamPython -ne 'python' -and ![System.IO.Path]::IsPathRooted($teamPython)) {
    $teamPython = Join-Path $teamWorkspace $teamPython
}
$teamPdsBin = if ($env:FPGA_PDS_BIN) { $env:FPGA_PDS_BIN } elseif ($teamConfig.pds_bin) { $teamConfig.pds_bin } else { 'E:\Pango\PDS_2022.2-SP6.4\bin' }
$teamVivadoBin = if ($env:FPGA_VIVADO_BIN) { $env:FPGA_VIVADO_BIN } elseif ($teamConfig.vivado_bin) { $teamConfig.vivado_bin } else { 'E:\Vivado\Vivado\2017.4\bin' }
