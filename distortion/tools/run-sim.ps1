$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'team-env.ps1')
$projectRoot = Split-Path -Parent $PSScriptRoot
$simRoot = Join-Path $projectRoot 'build\sim'
$vivadoBin = $teamVivadoBin
New-Item -ItemType Directory -Force -Path $simRoot | Out-Null
& python (Join-Path $PSScriptRoot 'generate_vectors.py')
if ($LASTEXITCODE -ne 0) { throw 'Vector generation failed' }
Push-Location $simRoot
try {
    & (Join-Path $vivadoBin 'xvlog.bat') --sv (Join-Path $projectRoot 'rtl\bilinear_rgb.v') (Join-Path $projectRoot 'rtl\dvp_rgb565_capture.v') (Join-Path $projectRoot 'tests\tb_bilinear.sv') (Join-Path $projectRoot 'tests\tb_dvp.sv')
    if ($LASTEXITCODE -ne 0) { throw 'RTL compilation failed' }
    foreach ($top in @('tb_bilinear','tb_dvp')) {
        & (Join-Path $vivadoBin 'xelab.bat') $top -s ($top + '_snapshot')
        if ($LASTEXITCODE -ne 0) { throw "Elaboration failed: $top" }
        & (Join-Path $vivadoBin 'xsim.bat') ($top + '_snapshot') -runall -log ($top + '.log')
        if ($LASTEXITCODE -ne 0) { throw "Simulation failed: $top" }
        $simText = Get-Content -Raw ($top + '.log')
        if ($simText -notmatch 'PASS ' -or $simText -match 'Fatal:|Error:') { throw "No clean PASS: $top" }
    }
} finally { Pop-Location }
