param([ValidateSet('baseline','fast')][string]$Cache='baseline')
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
$work=Join-Path $root 'build\native_regression_sim'
$bin='E:\Vivado\Vivado\2017.4\bin'
if($Cache -eq 'baseline') {
    & 'C:\Users\22955\AppData\Local\Programs\Python\Python313\python.exe' (Join-Path $PSScriptRoot 'prepare-native-regression.py')
    if($LASTEXITCODE){throw 'Native real-frame reference generation failed'}
} else {
    $baseline=$work
    $work=Join-Path $root 'build\native_regression_fast_sim'
    New-Item -ItemType Directory -Force -Path $work | Out-Null
    foreach($name in @('source.mem','result.mem','crcs.mem','reference.json')) {
        Copy-Item -LiteralPath (Join-Path $baseline $name) -Destination (Join-Path $work $name)
    }
}
Push-Location $work
try {
    $files=@('bilinear_rgb','ddr_neighbour_cache','ddr_remap_sample','mul32_pipe','brown_inverse_mapper','brown_remap_core','ddr_result_writer','remap_frame_engine') | ForEach-Object {Join-Path $root ('rtl\'+$_+'.v')}
    if($Cache -eq 'fast') {$files=$files | ForEach-Object {if($_ -eq (Join-Path $root 'rtl\ddr_neighbour_cache.v')){Join-Path $root 'rtl\experimental\ddr_neighbour_cache_fast.v'}else{$_}}}
    $files+=Join-Path $root 'tests\tb_native_remap_regression.sv'
    & (Join-Path $bin 'xvlog.bat') --sv @files *> compile.log
    if($LASTEXITCODE){Get-Content compile.log -Tail 18;throw 'Native RTL compile failed'}
    & (Join-Path $bin 'xelab.bat') tb_native_remap_regression -s tb_native_remap_regression *> elab.log
    if($LASTEXITCODE){Get-Content elab.log -Tail 18;throw 'Native RTL elaboration failed'}
    & (Join-Path $bin 'xsim.bat') tb_native_remap_regression -runall -log simulation.log *> run.log
    $log=Get-Content -Raw simulation.log
    if($LASTEXITCODE -or $log -notmatch '(?m)^PASS native regression:' -or $log -match '(?im)fatal:|error:'){Get-Content simulation.log -Tail 18;throw 'Native RTL regression failed'}
    ($log -split "`r?`n") | Where-Object {$_ -match '^PASS '}
}finally{Pop-Location}
