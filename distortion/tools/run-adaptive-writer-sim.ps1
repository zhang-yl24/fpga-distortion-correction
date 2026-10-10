$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'team-env.ps1')
$root=Split-Path -Parent $PSScriptRoot
$work=Join-Path $root 'build\adaptive_writer_sim'
$bin=$teamVivadoBin
New-Item -ItemType Directory -Force -Path $work | Out-Null
& $teamPython -c "import zlib,pathlib; data=bytearray(); [(data.extend((((((t*17+3)%256)>>3)<<11)|(((((t*7+11)%256)>>2)<<5))|(((t*29+5)%256)>>3)).to_bytes(2,'little'))) for t in range(1536)]; pathlib.Path('build/adaptive_writer_sim/checksum.vh').write_text('localparam [31:0] EXPECTED_CRC=32\'h'+format(zlib.crc32(data),'08x')+';\n')"
if($LASTEXITCODE){throw 'Stripe Python CRC generation failed'}
Push-Location $work
try {
    & (Join-Path $bin 'xvlog.bat') --sv (Join-Path $root 'rtl\experimental\ddr_adaptive_result_writer.v') (Join-Path $root 'tests\tb_adaptive_result_writer.sv') *> compile.log
    if($LASTEXITCODE){Get-Content compile.log -Tail 10;throw 'Stripe compile failed'}
    & (Join-Path $bin 'xelab.bat') tb_adaptive_result_writer -s tb_adaptive_result_writer *> elab.log
    if($LASTEXITCODE){Get-Content elab.log -Tail 10;throw 'Stripe elaboration failed'}
    & (Join-Path $bin 'xsim.bat') tb_adaptive_result_writer -runall -log simulation.log *> run.log
    $log=Get-Content -Raw simulation.log
    if($LASTEXITCODE -or $log -notmatch '(?m)^PASS adaptive writer:' -or $log -match '(?im)fatal:|error:'){Get-Content simulation.log -Tail 12;throw 'Stripe simulation failed'}
    ($log -split "`r?`n") | Where-Object {$_ -match '^PASS '}
}finally{Pop-Location}
